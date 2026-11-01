"""F-022: the embedder reads at most `max_seq_length` (128) wordpieces but the chunker emits
350-token chunks, so text late in a chunk is invisible to dense retrieval AND to the verifier.
Real embedder, real chunker, nothing mocked.
"""
import pytest
from sentence_transformers import util

from voltagent.ingestion.chunking import chunk_page
from voltagent.ingestion.loaders import SourcePage
from voltagent.retrieval.dense_qdrant import get_embedder

pytestmark = pytest.mark.slow

FILLER = "General notes on connector maintenance and cable inspection. " * 30


def _single_chunk(text: str):
    chunks = chunk_page(SourcePage(doc_id="d", doc_title="D", page_number=1, text=text))
    assert len(chunks) == 1, "precondition: the test page must fit in one chunk"
    return chunks[0]


def _cos(a: str, b: str) -> float:
    emb = get_embedder()
    va, vb = emb.encode([a, b], convert_to_tensor=True)
    return float(util.cos_sim(va, vb))


def test_control_number_at_start_of_chunk_changes_the_embedding():
    """Control: proves the comparison below can see a difference when the number IS inside the window."""
    a = _single_chunk(f"Wait 10 minutes before opening the cabinet. {FILLER}")
    b = _single_chunk(f"Wait 99 minutes before opening the cabinet. {FILLER}")
    assert _cos(a.text, b.text) < 0.999


@pytest.mark.xfail(strict=True, reason="F-022: a full-size chunk is longer than the embedder window")
def test_full_size_chunk_fits_in_embedder_window():
    chunk = _single_chunk(f"{FILLER} Wait 10 minutes before opening the cabinet.")
    embedder = get_embedder()
    n_wordpieces = len(embedder.tokenizer(chunk.text)["input_ids"])
    assert n_wordpieces <= embedder.max_seq_length, (
        f"chunk is {n_wordpieces} wordpieces, embedder window is {embedder.max_seq_length}")


@pytest.mark.xfail(strict=True, reason="F-022: a number at the END of a full-size chunk does not affect its embedding")
def test_number_at_end_of_full_size_chunk_changes_the_embedding():
    a = _single_chunk(f"{FILLER} Wait 10 minutes before opening the cabinet.")
    b = _single_chunk(f"{FILLER} Wait 99 minutes before opening the cabinet.")
    assert _cos(a.text, b.text) < 0.999
