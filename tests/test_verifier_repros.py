"""Verifier failure reproductions (F-001, F-002, F-003) against the REAL embedder.

Nothing is mocked here: the embedding model is the thing under test. Strict xfail
while the bug exists; the marker must be removed deliberately when the bug is fixed.
Probe numbers behind these tests (2026-10-23, threshold 0.55): correct 0.685,
wrong number 0.654, wrong unit 0.682, negated 0.502, unrelated 0.414.

Every test runs in BOTH citation formats the real LLM may produce:
  after_period  -> "sentence. [1]"
  before_period -> "sentence [1]."
(F-020 was fixed in the sentence splitter; these parametrised tests keep it fixed.)
"""
import pytest

from voltagent.agents.generation_agent import GenerationResult
from voltagent.agents.verifier_agent import run_verifier_agent
from voltagent.retrieval.types import RetrievedChunk

DISCHARGE_CHUNK = (
    "Capacitor discharge: after isolating the DC bus, wait 10 minutes before opening the "
    "power cabinet. Verify bus voltage is below 50 V with a CAT III meter."
)
HVAC_CHUNK = "The HVAC relay must be reset after a breaker isolation fault."

STYLES = ["after_period", "before_period"]


def _cite(sentence: str, refs: str, style: str) -> str:
    """sentence has no trailing period."""
    return f"{sentence}. {refs}" if style == "after_period" else f"{sentence} {refs}."


def _chunk(chunk_id: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(chunk_id=chunk_id, text=text, doc_id="d", doc_title="D", page_number=1,
                          rrf_score=0.1, sparse_rank=1, dense_rank=1)


def _generation(answer: str, chunks: list[RetrievedChunk]) -> GenerationResult:
    return GenerationResult(answer_text=answer, cited_chunk_ids=[c.chunk_id for c in chunks],
                            used_chunks=chunks, is_insufficient=False)


@pytest.mark.slow
@pytest.mark.parametrize("style", STYLES)
def test_control_correct_claim_is_verified_in_both_citation_formats(style):
    """Control (F-020 regression): proves the harness works, so the xfails below are not
    failing for setup reasons. Failed for 'after_period' before the splitter fix."""
    answer = _cite("Wait 10 minutes after isolating the DC bus before opening the cabinet", "[1]", style)
    result = run_verifier_agent(_generation(answer, [_chunk("c1", DISCHARGE_CHUNK)]))
    assert result.verified is True


@pytest.mark.slow
@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("wrong", ["5 minutes", "10 seconds"])
def test_wrong_number_or_unit_is_not_verified(wrong, style):
    """F-001 regression: fixed by the deterministic numeric gate (numeric_gate.py)."""
    answer = _cite(f"Wait {wrong} after isolating the DC bus before opening the cabinet", "[1]", style)
    assert run_verifier_agent(_generation(answer, [_chunk("c1", DISCHARGE_CHUNK)])).verified is False


@pytest.mark.unit
def test_refusal_is_not_reported_as_verified_answer():
    gen = GenerationResult(
        answer_text="I don't have enough information in the available documents to answer that confidently.",
        cited_chunk_ids=[], used_chunks=[], is_insufficient=True)
    result = run_verifier_agent(gen)
    assert result.verified is False


@pytest.mark.slow
@pytest.mark.parametrize("style", STYLES)
def test_citation_to_unrelated_chunk_is_not_verified(style):
    answer = _cite("Wait 10 minutes after isolating the DC bus before opening the cabinet", "[1][2]", style)
    gen = _generation(answer, [_chunk("c1", DISCHARGE_CHUNK), _chunk("c2", HVAC_CHUNK)])
    assert run_verifier_agent(gen).verified is False
