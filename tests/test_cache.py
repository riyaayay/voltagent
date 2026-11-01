import pytest

from voltagent.cache import ResponseCache, normalize_query

pytestmark = pytest.mark.unit


def test_normalize_query_collapses_case_punctuation_whitespace():
    assert normalize_query("  E203?  ", "en") == normalize_query("e203", "en")


def test_normalize_query_is_language_scoped():
    assert normalize_query("hello", "en") != normalize_query("hello", "hi")


def test_should_cache_true_for_verified_non_fallback():
    assert ResponseCache.should_cache({"verified": True, "fallback": False}) is True


def test_should_cache_false_for_fallback():
    assert ResponseCache.should_cache({"verified": False, "fallback": True}) is False


def test_should_cache_false_when_not_verified_even_without_explicit_fallback_flag():
    assert ResponseCache.should_cache({"verified": False}) is False


def test_memory_cache_roundtrip(monkeypatch):
    monkeypatch.setenv("CACHE_BACKEND", "memory")
    cache = ResponseCache()

    assert cache.get("some query", "en") is None

    cache.set("some query", "en", {"answer": "42"})
    hit = cache.get("some query", "en")

    assert hit == {"answer": "42"}


def test_normalize_query_normalizes_error_code_variants():
    # F-009 regression: E-101, E101, E 101 should match
    assert normalize_query("what is E-101?", "en") == normalize_query("what is E101?", "en")
    assert normalize_query("error E 101", "en") == normalize_query("error E101", "en")


def test_cache_key_varies_with_corpus_version(monkeypatch):
    # F-008 regression: re-ingest / corpus version change invalidates cache
    from voltagent.cache import _cache_key
    from voltagent.config import settings

    monkeypatch.setattr(settings, "corpus_version_hash", "v1")
    k1 = _cache_key("error E101", "en")

    monkeypatch.setattr(settings, "corpus_version_hash", "v2")
    k2 = _cache_key("error E101", "en")

    assert k1 != k2


def test_redis_failure_falls_back_gracefully(monkeypatch):
    # F-010 regression: Redis errors do not 500
    cache = ResponseCache()
    cache.backend = "redis"

    class FailingRedis:
        def get(self, key):
            raise ConnectionError("Redis connection refused")
        def setex(self, key, ttl, val):
            raise ConnectionError("Redis connection refused")

    cache._redis = FailingRedis()
    # Should not raise exception
    assert cache.get("test query", "en") is None
    cache.set("test query", "en", {"answer": "cached"})
    # Should be cached in local fallback
    assert cache._local.get(list(cache._local.keys())[0]) == {"answer": "cached"}
