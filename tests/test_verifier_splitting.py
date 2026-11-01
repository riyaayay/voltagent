"""Sentence splitting must keep citations attached to their sentence, in both formats (F-020)."""
import pytest

from voltagent.agents.verifier_agent import _cited_chunk_id_for_sentence, _split_sentences

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Wait 10 minutes [1].", ["Wait 10 minutes [1]."]),
        ("Wait 10 minutes. [1]", ["Wait 10 minutes. [1]"]),
        ("Wait 10 minutes. [1][2]", ["Wait 10 minutes. [1][2]"]),
        ("Wait 10 minutes. [1] Then test. [2]", ["Wait 10 minutes. [1]", "Then test. [2]"]),
        ("Wait 10 minutes [1]. Then test [2].", ["Wait 10 minutes [1].", "Then test [2]."]),
        ("Torque is 5.5 Nm [1].", ["Torque is 5.5 Nm [1]."]),           # decimal point is not a sentence end
        ("No terminator here [1]", ["No terminator here [1]"]),
        ("First fact here. Second fact here! Is this a question?",
         ["First fact here.", "Second fact here!", "Is this a question?"]),
        ("", []),
    ],
)
def test_split_keeps_citations_with_their_sentence(text, expected):
    assert _split_sentences(text) == expected


@pytest.mark.parametrize("sentence", ["Wait 10 minutes. [1]", "Wait 10 minutes [1]."])
def test_citation_resolves_for_both_formats(sentence):
    assert _cited_chunk_id_for_sentence(sentence, {1: "chunk-a"}) == "chunk-a"
