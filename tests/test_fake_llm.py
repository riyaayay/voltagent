import pytest

from voltagent.llm import FakeLLMClient


@pytest.mark.unit
def test_fake_is_deterministic():
    llm = FakeLLMClient()
    prompt = "Source chunks:\n[1] (source: d, page 1)\nWait 10 minutes. Then test.\n\nTechnician's question: q\n\nAnswer:"
    assert llm.complete(prompt) == llm.complete(prompt) == "Wait 10 minutes. [1]"


@pytest.mark.unit
def test_fake_can_emit_citation_before_the_full_stop():
    llm = FakeLLMClient(citation_style="before_period")
    prompt = "Source chunks:\n[1] (source: d, page 1)\nWait 10 minutes. Then test.\n\nTechnician's question: q\n\nAnswer:"
    assert llm.complete(prompt) == "Wait 10 minutes [1]."


@pytest.mark.unit
def test_fake_rejects_unknown_citation_style():
    with pytest.raises(ValueError):
        FakeLLMClient(citation_style="nonsense")


@pytest.mark.unit
def test_fake_reformulation_echoes_query_unchanged():
    llm = FakeLLMClient()
    prompt = "intro\n\nUser query (en): E-101 on DC-60\nRewritten query:"
    assert llm.complete(prompt) == "E-101 on DC-60"


@pytest.mark.unit
def test_fake_scripted_replies_and_exceptions_are_consumed_in_order():
    llm = FakeLLMClient(scripted=["garbage", TimeoutError("slow")])
    assert llm.complete("x") == "garbage"
    with pytest.raises(TimeoutError):
        llm.complete("x")
    # script exhausted -> back to default behaviour (unrecognised prompt -> empty)
    assert llm.complete("unrelated prompt") == ""
