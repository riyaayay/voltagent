"""Verifier Agent: the differentiator of this whole project.

Retrieve → Generate pipelines fail silently — a fluent, confidently-worded
answer with a plausible-looking citation can still misstate what the source
actually says, especially under paraphrase-heavy generation. For a technician
about to act on live electrical equipment, "sounds right" isn't good enough.

This agent re-checks the generation, sentence by sentence, two ways:

1. **Citation integrity** — does every factual sentence actually cite a chunk,
   and does that chunk exist in what was retrieved? (Catches the model citing
   a chunk number that doesn't exist, or making an uncited claim.)
2. **Semantic support** — for each cited sentence, is it actually entailed by
   the text of the chunk it cites? Implemented as embedding-similarity between
   the sentence and its cited chunk, which is a lightweight proxy for NLI.
   Sentences below `settings.verifier_confidence_threshold` similarity to
   their cited source are flagged as unsupported.

If overall confidence is high enough AND there are no unsupported/uncited
claims, the answer is marked `verified=True` and passed through unchanged.
Otherwise `fallback=True`: instead of speaking a possibly-wrong answer, the
API returns the raw top source chunk(s) and says explicitly that it isn't
confident. This mirrors the Red-Team critique pattern from the SAGE IDE
project, applied to RAG instead of code generation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sentence_transformers import util

from voltagent.agents.generation_agent import GenerationResult
from voltagent.config import settings
from voltagent.retrieval.dense_qdrant import get_embedder


@dataclass
class SentenceCheck:
    sentence: str
    cited_chunk_id: str | None
    support_score: float | None    # None if uncited
    supported: bool


@dataclass
class VerificationResult:
    verified: bool
    confidence: float               # overall, 0-1
    sentence_checks: list[SentenceCheck] = field(default_factory=list)
    fallback: bool = False
    fallback_reason: str | None = None


def _split_sentences(text: str) -> list[str]:
    # Good enough for technical prose with citation brackets; a real
    # deployment would swap in a proper sentence segmenter (e.g. spaCy)
    # if source docs turn out to have unusual punctuation patterns.
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def _cited_chunk_id_for_sentence(sentence: str, chunk_by_index: dict[int, str]) -> str | None:
    refs = re.findall(r"\[(\d+)\]", sentence)
    if not refs:
        return None
    return chunk_by_index.get(int(refs[0]))


def run_verifier_agent(generation: GenerationResult) -> VerificationResult:
    if generation.is_insufficient:
        # Model already declined to answer — nothing to verify, and this
        # counts as an honest (non-hallucinated) outcome, not a failure.
        return VerificationResult(verified=True, confidence=1.0, fallback=False)

    if not generation.used_chunks:
        return VerificationResult(
            verified=False,
            confidence=0.0,
            fallback=True,
            fallback_reason="No source chunks were retrieved for this query.",
        )

    embedder = get_embedder()
    chunk_by_index = {i + 1: c.chunk_id for i, c in enumerate(generation.used_chunks)}
    chunk_text_by_id = {c.chunk_id: c.text for c in generation.used_chunks}

    sentences = _split_sentences(generation.answer_text)
    checks: list[SentenceCheck] = []

    for sentence in sentences:
        cited_id = _cited_chunk_id_for_sentence(sentence, chunk_by_index)

        if cited_id is None or cited_id not in chunk_text_by_id:
            # Uncited factual claim, or citation to a chunk that doesn't
            # exist in what was actually retrieved. Treat as unsupported.
            checks.append(
                SentenceCheck(sentence=sentence, cited_chunk_id=cited_id, support_score=None, supported=False)
            )
            continue

        source_text = chunk_text_by_id[cited_id]
        sentence_clean = re.sub(r"\[\d+\]", "", sentence).strip()

        sent_emb = embedder.encode(sentence_clean, convert_to_tensor=True)
        src_emb = embedder.encode(source_text, convert_to_tensor=True)
        similarity = float(util.cos_sim(sent_emb, src_emb)[0][0])

        supported = similarity >= settings.verifier_confidence_threshold
        checks.append(
            SentenceCheck(
                sentence=sentence, cited_chunk_id=cited_id, support_score=similarity, supported=supported
            )
        )

    if not checks:
        return VerificationResult(
            verified=False, confidence=0.0, fallback=True,
            fallback_reason="Answer produced no verifiable sentences."
        )

    scored = [c.support_score for c in checks if c.support_score is not None]
    overall_confidence = sum(scored) / len(scored) if scored else 0.0
    all_supported = all(c.supported for c in checks)

    verified = all_supported and overall_confidence >= settings.verifier_confidence_threshold

    return VerificationResult(
        verified=verified,
        confidence=round(overall_confidence, 3),
        sentence_checks=checks,
        fallback=not verified,
        fallback_reason=None if verified else "One or more claims were uncited or not well-supported by the retrieved sources.",
    )
