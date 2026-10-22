"""Query Agent: the first hop in the graph.

Two jobs:
1. Detect language (Hindi vs English) so the rest of the pipeline knows what
   to respond in — technicians may mix languages mid-sentence, so this is a
   best-effort classification, not a hard gate.
2. Reformulate the raw (possibly transcribed-with-errors, possibly
   code-switched) query into a clean retrieval query. Voice transcription of
   technical terms is noisy ("oh see pee pee" → "OCPP"), so this step also
   does light technical-term normalization.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from langdetect import LangDetectException, detect

from voltagent.llm import get_llm_client

# Common ASR mis-transcriptions of technical terms this domain cares about.
# Extend this table as you observe real Web Speech API output — it will be
# wrong in idiosyncratic ways.
_TERM_CORRECTIONS = {
    r"\bo\s*c\s*p\s*p\b": "OCPP",
    r"\boh see pee pee\b": "OCPP",
    r"\bstop transaction\b": "StopTransaction",
    r"\bstart transaction\b": "StartTransaction",
    r"\be(\s|-)?(\d{3})\b": r"E\2",   # "e 203" / "e-203" -> "E203"
}

_REFORMULATION_PROMPT = """You are a query normalizer for a technical RAG system \
used by EV charger field technicians. Rewrite the user's spoken, possibly \
noisy query into a clean, specific search query in English, preserving any \
exact error codes, OCPP message names, or part numbers verbatim. Do not \
answer the question. Do not add information. Output only the rewritten \
query, nothing else.

User query ({language}): {query}
Rewritten query:"""


@dataclass
class QueryAgentResult:
    original_query: str
    reformulated_query: str
    language: str            # ISO 639-1: "en" or "hi"


def _detect_language(text: str) -> str:
    try:
        code = detect(text)
    except LangDetectException:
        return "en"
    # langdetect returns fine-grained codes; we only route en/hi today.
    return "hi" if code == "hi" else "en"


def _apply_term_corrections(text: str) -> str:
    corrected = text
    for pattern, replacement in _TERM_CORRECTIONS.items():
        corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)
    return corrected


def run_query_agent(raw_query: str) -> QueryAgentResult:
    language = _detect_language(raw_query)
    pre_cleaned = _apply_term_corrections(raw_query)

    llm = get_llm_client()
    reformulated = llm.complete(
        _REFORMULATION_PROMPT.format(language=language, query=pre_cleaned)
    ).strip()

    # Guard against the LLM returning nothing usable (e.g. transient API issue).
    if not reformulated:
        reformulated = pre_cleaned

    return QueryAgentResult(
        original_query=raw_query, reformulated_query=reformulated, language=language
    )
