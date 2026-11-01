"""Query Agent: the first hop in the graph.

1. Detect language (Hindi vs English).
2. Reformulate query while preserving exact critical error codes, models, and numbers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from langdetect import LangDetectException, detect

from voltagent.llm import get_llm_client

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
    # Heuristic for Devanagari Unicode block
    if any(0x0900 <= ord(ch) <= 0x097F for ch in text):
        return "hi"
    try:
        code = detect(text)
    except LangDetectException:
        return "en"
    return "hi" if code == "hi" else "en"


def _apply_term_corrections(text: str) -> str:
    corrected = text
    for pattern, replacement in _TERM_CORRECTIONS.items():
        corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)
    return corrected


def _check_critical_tokens_survive(original: str, rewritten: str) -> bool:
    """Ensure critical codes, models, or alphanumeric IDs from the original query are preserved."""
    # Find codes like E203, DC-60, AC-7, CT4021
    tokens = re.findall(r"\b[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*\b", original)
    critical = [t for t in tokens if len(t) >= 3 and any(ch.isdigit() for ch in t)]
    for crit in critical:
        if crit.lower() not in rewritten.lower():
            return False
    return True


def run_query_agent(raw_query: str) -> QueryAgentResult:
    language = _detect_language(raw_query)
    pre_cleaned = _apply_term_corrections(raw_query)

    llm = get_llm_client()
    reformulated = llm.complete(
        _REFORMULATION_PROMPT.format(language=language, query=pre_cleaned)
    ).strip()

    # Guard against LLM failure or dropping critical tokens (F-006)
    if not reformulated or not _check_critical_tokens_survive(pre_cleaned, reformulated):
        reformulated = pre_cleaned

    return QueryAgentResult(
        original_query=raw_query, reformulated_query=reformulated, language=language
    )
