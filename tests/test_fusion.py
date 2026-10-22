from voltagent.retrieval.fusion import reciprocal_rank_fusion
from voltagent.retrieval.types import DenseHit, SparseHit


def _payload(chunk_id: str) -> dict:
    return {"chunk_id": chunk_id, "text": f"text for {chunk_id}", "doc_id": "doc", "doc_title": "Doc", "page_number": 1}


def test_chunk_present_in_both_lists_ranks_highest():
    sparse = [
        SparseHit(chunk_id="a", score=9.0, payload=_payload("a")),
        SparseHit(chunk_id="b", score=8.0, payload=_payload("b")),
    ]
    dense = [
        DenseHit(chunk_id="a", score=0.9, payload=_payload("a")),
        DenseHit(chunk_id="c", score=0.8, payload=_payload("c")),
    ]

    fused = reciprocal_rank_fusion(sparse, dense, top_k=3)

    assert fused[0].chunk_id == "a"
    assert {h.chunk_id for h in fused} == {"a", "b", "c"}


def test_top_k_is_respected():
    sparse = [SparseHit(chunk_id=str(i), score=float(10 - i), payload=_payload(str(i))) for i in range(10)]
    dense: list[DenseHit] = []

    fused = reciprocal_rank_fusion(sparse, dense, top_k=3)

    assert len(fused) == 3


def test_chunk_only_in_one_list_still_included():
    sparse = [SparseHit(chunk_id="only-sparse", score=5.0, payload=_payload("only-sparse"))]
    dense = [DenseHit(chunk_id="only-dense", score=0.5, payload=_payload("only-dense"))]

    fused = reciprocal_rank_fusion(sparse, dense, top_k=5)
    chunk_ids = {h.chunk_id for h in fused}

    assert "only-sparse" in chunk_ids
    assert "only-dense" in chunk_ids


def test_ranks_are_recorded_on_fused_hit():
    sparse = [SparseHit(chunk_id="a", score=5.0, payload=_payload("a"))]
    dense = [DenseHit(chunk_id="a", score=0.5, payload=_payload("a"))]

    fused = reciprocal_rank_fusion(sparse, dense, top_k=1)

    assert fused[0].sparse_rank == 1
    assert fused[0].dense_rank == 1
