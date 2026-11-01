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
from voltagent.agents.numeric_gate import gate_claim
from voltagent.config import settings
from voltagent.insights.feedback_loop import get_threshold_override
from voltagent.logging_utils import extract_error_code
from voltagent.retrieval.dense_qdrant import get_embedder


@dataclass
class SentenceCheck:
    sentence: str
    cited_chunk_id: str | None
    support_score: float | None    # None if uncited
    supported: bool
    gate_missing: list[str] = field(default_factory=list)   # critical values not found in the cited chunks
    negation_conflict: bool = False


@dataclass
class VerificationResult:
    verified: bool
    confidence: float               # overall, 0-1
    sentence_checks: list[SentenceCheck] = field(default_factory=list)
    fallback: bool = False
    fallback_reason: str | None = None
    threshold_applied: float | None = None   # set when insights feedback loop tightened the bar


def _split_sentences(text: str) -> list[str]:
    # Good enough for technical prose with citation brackets; a real
    # deployment would swap in a proper sentence segmenter (e.g. spaCy)
    # if source docs turn out to have unusual punctuation patterns.
    #
    # A sentence ends at ./!/? followed by whitespace (so "5.5 kW" is not split),
    # and any citation brackets right after the terminator belong to THAT sentence.
    # This accepts both "sentence [1]." and "sentence. [1]" (F-020): splitting on
    # the terminator alone turned the bare "[1]" into its own sentence.
    parts = re.findall(r".+?[.!?](?:\s*\[\d+\])*(?=\s|$)|.+$", text.strip(), flags=re.S)
    return [p.strip() for p in parts if p.strip()]


def _cited_chunk_id_for_sentence(sentence: str, chunk_by_index: dict[int, str]) -> str | None:
    refs = re.findall(r"\[(\d+)\]", sentence)
    if not refs:
        return None
    return chunk_by_index.get(int(refs[0]))


def check_negation_conflict(claim: str, source: str) -> bool:
    """Deterministic check for negation flip (V4 in STATUS.md).

    Detects when a claim affirms an action that the cited source explicitly negates
    (e.g. 'will charge' vs 'will not charge') or vice-versa.
    """
    aux = r"(?:will|shall|can|could|should|must|may|might|do|does|did|is|are|was|were)"
    negated_in_src = set(re.findall(rf"\b{aux}\s+(?:not|never)\s+([a-z]+)\b", source.lower()))
    negated_in_claim = set(re.findall(rf"\b{aux}\s+(?:not|never)\s+([a-z]+)\b", claim.lower()))

    # Also handle "cannot <verb>"
    negated_in_src |= set(re.findall(r"\bcannot\s+([a-z]+)\b", source.lower()))
    negated_in_claim |= set(re.findall(r"\bcannot\s+([a-z]+)\b", claim.lower()))

    affirmed_in_src = set(re.findall(rf"\b{aux}\s+([a-z]+)\b", source.lower())) - negated_in_src
    affirmed_in_claim = set(re.findall(rf"\b{aux}\s+([a-z]+)\b", claim.lower())) - negated_in_claim

    conflict_1 = (negated_in_src & affirmed_in_claim) - {"be", "have"}
    conflict_2 = (affirmed_in_src & negated_in_claim) - {"be", "have"}

    return bool(conflict_1 or conflict_2)


def run_verifier_agent(generation: GenerationResult, query_text: str | None = None) -> VerificationResult:
    if generation.is_insufficient:
        # F-002: Model declined to answer (Outcome B4). Never report as verified.
        return VerificationResult(
            verified=False,
            confidence=0.0,
            sentence_checks=[],
            fallback=True,
            fallback_reason="Model declined to answer / insufficient documentation.",
        )

    if not generation.used_chunks:
        return VerificationResult(
            verified=False,
            confidence=0.0,
            fallback=True,
            fallback_reason="No source chunks were retrieved for this query.",
        )

    # Insights feedback loop: if the docs cited here (or the error code in
    # the query) are on the nightly Spark job's "known documentation gap"
    # list, hold this answer to a stricter bar than the default.
    doc_ids = [c.doc_id for c in generation.used_chunks]
    error_code = extract_error_code(query_text) if query_text else None
    threshold = get_threshold_override(doc_ids=doc_ids, error_code=error_code)

    embedder = get_embedder()
    chunk_by_index = {i + 1: c.chunk_id for i, c in enumerate(generation.used_chunks)}
    chunk_text_by_id = {c.chunk_id: c.text for c in generation.used_chunks}

    sentences = _split_sentences(generation.answer_text)
    checks: list[SentenceCheck] = []

    for sentence in sentences:
        raw_refs = re.findall(r"\[(\d+)\]", sentence)
        if not raw_refs:
            # Uncited factual claim
            checks.append(
                SentenceCheck(sentence=sentence, cited_chunk_id=None, support_score=None, supported=False)
            )
            continue

        cited_ids = [chunk_by_index.get(int(ref)) for ref in raw_refs]
        # F-003: If any reference cited a chunk number that doesn't exist in what was retrieved
        if any(cid is None or cid not in chunk_text_by_id for cid in cited_ids):
            checks.append(
                SentenceCheck(sentence=sentence, cited_chunk_id=cited_ids[0], support_score=None, supported=False)
            )
            continue

        sentence_clean = re.sub(r"\[\d+\]", "", sentence).strip()
        sent_emb = embedder.encode(sentence_clean, convert_to_tensor=True)

        # F-003: Check semantic support against EVERY chunk this sentence cites
        chunk_sims: list[float] = []
        for cid in cited_ids:
            src_text = chunk_text_by_id[cid]
            src_emb = embedder.encode(src_text, convert_to_tensor=True)
            chunk_sims.append(float(util.cos_sim(sent_emb, src_emb)[0][0]))

        min_sim = min(chunk_sims)

        # Deterministic gate on the FULL text of every chunk this sentence cites. Cosine alone
        # accepted a wrong number or unit (F-001) and cannot see past the embedder window (F-022).
        cited_texts = [chunk_text_by_id[cid] for cid in cited_ids]
        gate = gate_claim(sentence_clean, cited_texts)

        # Deterministic negation conflict check (V4 in STATUS.md)
        negation_conflict = check_negation_conflict(sentence_clean, " ".join(cited_texts))

        supported = min_sim >= threshold and gate.passed and not negation_conflict
        checks.append(
            SentenceCheck(
                sentence=sentence,
                cited_chunk_id=cited_ids[0],
                support_score=min_sim,
                supported=supported,
                gate_missing=gate.missing,
                negation_conflict=negation_conflict,
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

    verified = all_supported and overall_confidence >= threshold

    return VerificationResult(
        verified=verified,
        confidence=round(overall_confidence, 3),
        sentence_checks=checks,
        fallback=not verified,
        fallback_reason=None if verified else "One or more claims were uncited or not well-supported by the retrieved sources.",
        threshold_applied=threshold,
    )
