"""Reciprocal Rank Fusion (RRF) — combines the Elasticsearch BM25 leg and the
Qdrant dense leg into one ranked list without needing the two legs' raw
scores to be on comparable scales (they aren't: BM25 scores and cosine
similarities live in different worlds).

RRF score for a chunk = sum over each ranked list it appears in of
    1 / (rrf_k + rank_in_that_list)

A chunk that shows up near the top of *both* lists wins; a chunk that only
one leg found still contributes, just less. `rrf_k` (default 60, the value
from the original RRF paper) dampens the influence of rank-1 dominance.
"""
from __future__ import annotations

from voltagent.config import settings
from voltagent.retrieval.types import DenseHit, FusedHit, SparseHit


def reciprocal_rank_fusion(
    sparse_hits: list[SparseHit],
    dense_hits: list[DenseHit],
    top_k: int | None = None,
    rrf_k: int | None = None,
) -> list[FusedHit]:
    k = rrf_k or settings.rrf_k
    scores: dict[str, float] = {}
    payloads: dict[str, dict] = {}
    sparse_ranks: dict[str, int] = {}
    dense_ranks: dict[str, int] = {}

    for rank, hit in enumerate(sparse_hits, start=1):
        scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
        payloads[hit.chunk_id] = hit.payload
        sparse_ranks[hit.chunk_id] = rank

    for rank, hit in enumerate(dense_hits, start=1):
        scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
        payloads.setdefault(hit.chunk_id, hit.payload)
        dense_ranks[hit.chunk_id] = rank

    fused = [
        FusedHit(
            chunk_id=cid,
            rrf_score=score,
            payload=payloads[cid],
            sparse_rank=sparse_ranks.get(cid),
            dense_rank=dense_ranks.get(cid),
        )
        for cid, score in scores.items()
    ]
    fused.sort(key=lambda h: h.rrf_score, reverse=True)

    limit = top_k or settings.top_k_fused
    return fused[:limit]
