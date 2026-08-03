"""Response cache for repeat field queries.

Multiple technicians across sites will ask about the same handful of fault
codes over and over ("E203 red blink code", "OCPP StopTransaction not
firing"). Re-running retrieval + generation + verification for an identical
normalized query is pure latency for no benefit, so every answer that passes
verification is cached, keyed on (normalized_query, language).

Two backends:
  - "memory": TTLCache from cachetools, process-local. Zero setup, fine for a
    single-instance demo.
  - "redis": shared cache across multiple API instances. Same interface.

Only VERIFIED (non-fallback) answers are cached — see `should_cache` — so a
low-confidence fallback never gets served back to the next technician as if
it were a confident answer.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from cachetools import TTLCache

from voltagent.config import settings
from voltagent.logging_utils import log_event

try:
    import redis as redis_lib
except ImportError:  # redis is optional unless CACHE_BACKEND=redis
    redis_lib = None


def normalize_query(text: str, language: str) -> str:
    """Collapse whitespace/case/punctuation so 'E203?' and 'e203' hit the
    same cache key. Deliberately conservative — we'd rather have a cache
    miss than serve a stale answer to a subtly different question."""
    cleaned = re.sub(r"\s+", " ", text.strip().lower())
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return f"{language}:{cleaned}"


def _cache_key(text: str, language: str) -> str:
    normalized = normalize_query(text, language)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


class ResponseCache:
    def __init__(self) -> None:
        self.backend = settings.cache_backend
        if self.backend == "redis":
            if redis_lib is None:
                raise RuntimeError(
                    "CACHE_BACKEND=redis but the `redis` package isn't installed."
                )
            self._redis = redis_lib.from_url(settings.redis_url)
        else:
            self._local: TTLCache = TTLCache(
                maxsize=settings.cache_max_size, ttl=settings.cache_ttl_seconds
            )

    def get(self, query_text: str, language: str) -> dict[str, Any] | None:
        key = _cache_key(query_text, language)
        if self.backend == "redis":
            raw = self._redis.get(key)
            hit = json.loads(raw) if raw else None
        else:
            hit = self._local.get(key)
        log_event("cache_lookup", key=key, hit=hit is not None, backend=self.backend)
        return hit

    def set(self, query_text: str, language: str, payload: dict[str, Any]) -> None:
        key = _cache_key(query_text, language)
        if self.backend == "redis":
            self._redis.setex(key, settings.cache_ttl_seconds, json.dumps(payload))
        else:
            self._local[key] = payload
        log_event("cache_store", key=key, backend=self.backend)

    @staticmethod
    def should_cache(verifier_result: dict[str, Any]) -> bool:
        """Only cache answers the verifier actually trusted. A fallback
        ("I'm not confident, here's the raw doc") is query-specific enough
        and low-value enough that caching it just risks serving a stale
        non-answer forever."""
        return bool(verifier_result.get("verified")) and not verifier_result.get(
            "fallback", False
        )


cache = ResponseCache()
