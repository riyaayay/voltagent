"""Single entry point the rest of the pipeline calls: run both legs, fuse,
return a clean list of chunks with provenance. Keeps `graph.py` from needing
to know that hybrid search is two separate services under the hood.
"""
from __future__ import annotations

from voltagent.logging_utils import log_event
from voltagent.retrieval.dense_qdrant import QdrantRetriever
from voltagent.retrieval.fusion import reciprocal_rank_fusion
from voltagent.retrieval.sparse_es import ElasticsearchRetriever
from voltagent.retrieval.types import FusedHit, RetrievedChunk


class HybridRetriever:
    def __init__(self) -> None:
        self.sparse = ElasticsearchRetriever()
        self.dense = QdrantRetriever()

    def retrieve(self, query: str, query_id: str | None = None) -> list[RetrievedChunk]:
        sparse_hits = self.sparse.search(query)
        dense_hits = self.dense.search(query)
        fused: list[FusedHit] = reciprocal_rank_fusion(sparse_hits, dense_hits)

        log_event(
            "retrieval",
            query_id=query_id,
            query=query,
            sparse_hit_count=len(sparse_hits),
            dense_hit_count=len(dense_hits),
            fused_count=len(fused),
            fused_chunk_ids=[h.chunk_id for h in fused],
        )

        return [
            RetrievedChunk(
                chunk_id=h.chunk_id,
                text=h.payload["text"],
                doc_id=h.payload["doc_id"],
                doc_title=h.payload["doc_title"],
                page_number=h.payload["page_number"],
                rrf_score=h.rrf_score,
                sparse_rank=h.sparse_rank,
                dense_rank=h.dense_rank,
            )
            for h in fused
        ]
