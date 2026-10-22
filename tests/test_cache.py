from voltagent.cache import ResponseCache, normalize_query


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
