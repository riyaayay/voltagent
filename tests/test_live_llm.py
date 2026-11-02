import os
import pytest

from voltagent.config import settings


@pytest.mark.live
def test_live_provider_smoke():
    has_gemini = bool(settings.gemini_api_key or os.environ.get("GEMINI_API_KEY"))
    has_openai = bool(settings.openai_api_key or os.environ.get("OPENAI_API_KEY"))
    if not (has_gemini or has_openai):
        pytest.skip("No live LLM API key configured; skipping live provider smoke test.")

    from voltagent.llm import get_llm_client, set_llm_client

    set_llm_client(None)
    reply = get_llm_client().complete("Reply with the single word: ok").strip()
    assert len(reply) > 0
