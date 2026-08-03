"""Tests for verifier_agent.py.

Deliberately scoped to the logic paths that don't require loading the
sentence-transformers model (sentence splitting, citation resolution, and
the two early-exit branches) so the test suite runs fast and offline.
Semantic-similarity scoring itself is exercised in an integration test
outside this repo scaffold, once a real embedding model is available.
"""
from voltagent.agents.generation_agent import GenerationResult
from voltagent.agents.verifier_agent import (
    _cited_chunk_id_for_sentence,
    _split_sentences,
    run_verifier_agent,
)


def test_split_sentences_basic():
    text = "First fact here. Second fact here! Is this a question?"
    assert _split_sentences(text) == [
        "First fact here.",
        "Second fact here!",
        "Is this a question?",
    ]


def test_cited_chunk_id_for_sentence_resolves_first_reference():
    sentence = "The relay must open within 100ms [2]."
    chunk_by_index = {1: "chunk-a", 2: "chunk-b"}
    assert _cited_chunk_id_for_sentence(sentence, chunk_by_index) == "chunk-b"


def test_cited_chunk_id_for_sentence_returns_none_when_uncited():
    sentence = "This sentence cites nothing."
    assert _cited_chunk_id_for_sentence(sentence, {1: "chunk-a"}) is None


def test_verifier_passes_through_insufficient_answers_as_verified():
    generation = GenerationResult(
        answer_text="I don't have enough information in the available documents to answer that confidently.",
        cited_chunk_ids=[],
        used_chunks=[],
        is_insufficient=True,
    )
    result = run_verifier_agent(generation)
    assert result.verified is True
    assert result.fallback is False


def test_verifier_falls_back_when_no_chunks_were_used():
    generation = GenerationResult(
        answer_text="Some answer without sources.",
        cited_chunk_ids=[],
        used_chunks=[],
        is_insufficient=False,
    )
    result = run_verifier_agent(generation)
    assert result.verified is False
    assert result.fallback is True
