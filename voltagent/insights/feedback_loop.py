"""Closes the loop from batch analytics back into the live RAG pipeline.

`documentation_gap_detector.py` (a Spark batch job, run nightly) writes
`priority_flags.json`: doc_ids and error_codes where technicians have
repeatedly gotten low-confidence answers. That's a proxy for "our source
docs are thin here." This module is the read side — the verifier agent
consults it at request time and applies a *stricter* confidence threshold
for flagged topics, so a known-weak area gets more conservative fallback
behavior instead of being treated the same as a well-documented one.

Deliberately a flat-file read (not a live DB) — priority flags update once
a day from a batch job, so a cached-in-process read with a short TTL is the
right amount of freshness, not a network call per verification.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

from voltagent.config import settings

_CACHE_TTL_SECONDS = 300  # priority flags only change once/day; 5 min is plenty fresh


@dataclass
class PriorityFlags:
    doc_ids: set[str]
    error_codes: set[str]
    generated_at: float | None


_cached: PriorityFlags | None = None
_cached_at: float = 0.0


def _load_from_disk() -> PriorityFlags:
    path = settings.priority_flags_path
    if not os.path.exists(path):
        return PriorityFlags(doc_ids=set(), error_codes=set(), generated_at=None)

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    return PriorityFlags(
        doc_ids=set(raw.get("flagged_doc_ids", [])),
        error_codes=set(raw.get("flagged_error_codes", [])),
        generated_at=raw.get("generated_at"),
    )


def _get_flags(force_refresh: bool = False) -> PriorityFlags:
    global _cached, _cached_at
    now = time.time()
    if force_refresh or _cached is None or (now - _cached_at) > _CACHE_TTL_SECONDS:
        _cached = _load_from_disk()
        _cached_at = now
    return _cached


def get_threshold_override(
    doc_ids: list[str] | None = None,
    error_code: str | None = None,
    base_threshold: float | None = None,
) -> float:
    """Return the confidence threshold the verifier should apply for this
    answer. Stricter (higher) than the base threshold if any cited doc or
    the query's error code is on the priority-flag list; otherwise the
    normal base threshold, unchanged.
    """
    base = base_threshold if base_threshold is not None else settings.verifier_confidence_threshold
    flags = _get_flags()

    flagged = False
    if doc_ids and flags.doc_ids.intersection(doc_ids):
        flagged = True
    if error_code and error_code in flags.error_codes:
        flagged = True

    if not flagged:
        return base

    # Tighten the bar rather than hard-blocking — a flagged topic can still
    # produce a verified answer if the support is genuinely strong; it just
    # has to clear a higher bar than usual.
    return min(base + 0.15, 0.95)
