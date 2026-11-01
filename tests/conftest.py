"""Shared test plumbing.

Conventions:
- Every test is deterministic. Randomness always comes from a seeded
  `random.Random(SEED)` (fixture `rng`), never the global generator.
- The LLM is the only thing faked, and only via FakeLLMClient. Tests marked
  `live` use the real provider and are skipped unless a key is configured.
"""
import random

# F-021: on this Windows setup, importing `elasticsearch` BEFORE `torch` makes torch fail
# with WinError 1114 (c10.dll). Import order is therefore load-bearing; keep this first.
import torch  # noqa: F401  # isort: skip

import pytest

from voltagent.config import settings
from voltagent.llm import FakeLLMClient, set_llm_client

SEED = 1234


@pytest.fixture
def rng() -> random.Random:
    return random.Random(SEED)


@pytest.fixture
def fake_llm():
    """Install a fresh deterministic fake LLM for the test, restore after."""
    client = FakeLLMClient()
    set_llm_client(client)
    yield client
    set_llm_client(None)


@pytest.fixture(scope="session")
def corpus_runs(tmp_path_factory):
    """Generate the synthetic corpus twice (same seed) into temp dirs. Shared by corpus and ingestion tests."""
    import sys
    from pathlib import Path

    scripts = Path(__file__).resolve().parent.parent / "scripts"
    sys.path.insert(0, str(scripts))
    import generate_synthetic_corpus as gen

    if not Path(gen.DEFAULT_DEVANAGARI_FONT).exists():
        pytest.skip("Devanagari font (Nirmala) not available on this machine")
    roots = []
    for name in ("a", "b"):
        root = tmp_path_factory.mktemp(f"corpus_{name}")
        gen.build(root / "raw", root / "bad", root / "manifest.json", 1234, gen.DEFAULT_DEVANAGARI_FONT)
        roots.append(root)
    return roots


@pytest.fixture(scope="session")
def corpus(corpus_runs):
    import json

    root = corpus_runs[0]
    return dict(raw=root / "raw", bad=root / "bad",
                manifest=json.loads((root / "manifest.json").read_text(encoding="utf-8")))


def pytest_collection_modifyitems(config, items):
    has_key = bool(settings.gemini_api_key or settings.openai_api_key)
    if has_key:
        return
    skip_live = pytest.mark.skip(reason="no LLM API key configured")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
