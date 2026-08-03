"""Generation Agent: turns retrieved chunks + the reformulated query into a
grounded answer. The prompt is the whole safety story for this stage — it
forces the model to (a) only use the provided chunks, (b) cite a chunk_id
for every claim, and (c) explicitly say when the chunks don't cover the
question, rather than filling the gap from parametric knowledge.

The Verifier Agent downstream checks that the model actually followed these
rules instead of trusting the prompt to work — see verifier_agent.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from voltagent.llm import get_llm_client
from voltagent.retrieval.types import RetrievedChunk

_GENERATION_PROMPT = """You are VoltAgent, a technical assistant for EV charger \
field technicians. Answer ONLY using the numbered source chunks below. \
Every factual sentence in your answer must end with a citation like [1] or \
[2] referring to the chunk number it came from. If the chunks do not contain \
enough information to answer confidently, say exactly: \
"I don't have enough information in the available documents to answer that \
confidently." and nothing else. Do not use outside knowledge. Be concise — \
this will be read aloud to someone standing at a charger.

Respond in {language_name}.

Source chunks:
{chunks_block}

Technician's question: {query}

Answer:"""

_LANGUAGE_NAMES = {"en": "English", "hi": "Hindi"}


@dataclass
class GenerationResult:
    answer_text: str
    cited_chunk_ids: list[str]      # chunk_ids actually cited, resolved from [n] refs
    used_chunks: list[RetrievedChunk]
    is_insufficient: bool            # model explicitly declined to answer


_INSUFFICIENT_MARKER = "I don't have enough information in the available documents"


def _build_chunks_block(chunks: list[RetrievedChunk]) -> str:
    lines = []
    for i, c in enumerate(chunks, start=1):
        lines.append(f"[{i}] (source: {c.doc_title}, page {c.page_number})\n{c.text}")
    return "\n\n".join(lines)


def _resolve_citations(answer_text: str, chunks: list[RetrievedChunk]) -> list[str]:
    """Map bracketed [n] references in the answer back to real chunk_ids."""
    referenced_indices = {int(n) for n in re.findall(r"\[(\d+)\]", answer_text)}
    resolved = []
    for idx in sorted(referenced_indices):
        if 1 <= idx <= len(chunks):
            resolved.append(chunks[idx - 1].chunk_id)
    return resolved


def run_generation_agent(
    query: str, language: str, chunks: list[RetrievedChunk]
) -> GenerationResult:
    if not chunks:
        return GenerationResult(
            answer_text=_INSUFFICIENT_MARKER + ".",
            cited_chunk_ids=[],
            used_chunks=[],
            is_insufficient=True,
        )

    llm = get_llm_client()
    prompt = _GENERATION_PROMPT.format(
        language_name=_LANGUAGE_NAMES.get(language, "English"),
        chunks_block=_build_chunks_block(chunks),
        query=query,
    )
    answer_text = llm.complete(prompt, temperature=0.1).strip()

    is_insufficient = _INSUFFICIENT_MARKER in answer_text
    cited_ids = [] if is_insufficient else _resolve_citations(answer_text, chunks)

    return GenerationResult(
        answer_text=answer_text,
        cited_chunk_ids=cited_ids,
        used_chunks=chunks,
        is_insufficient=is_insufficient,
    )
