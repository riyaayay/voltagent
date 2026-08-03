"""Elasticsearch BM25 leg of hybrid retrieval.

Sparse (lexical) search is what catches exact fault codes, error strings,
and OCPP message names verbatim — things like "StopTransaction.conf" or
"E203" that a dense embedding model can blur into a generic neighborhood.
This is precisely why the JD asks for hybrid search rather than pure vector
search: field technicians query with exact codes far more than they query
with natural paraphrases.
"""
from __future__ import annotations

from elasticsearch import Elasticsearch

from voltagent.config import settings
from voltagent.ingestion.chunking import Chunk
from voltagent.retrieval.types import SparseHit


class ElasticsearchRetriever:
    def __init__(self, url: str | None = None, index: str | None = None) -> None:
        self.client = Elasticsearch(url or settings.elasticsearch_url)
        self.index = index or settings.elasticsearch_index

    def ensure_index(self) -> None:
        if self.client.indices.exists(index=self.index):
            return
        self.client.indices.create(
            index=self.index,
            mappings={
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "doc_id": {"type": "keyword"},
                    "doc_title": {"type": "text"},
                    "page_number": {"type": "integer"},
                    "text": {"type": "text", "analyzer": "standard"},
                }
            },
        )

    def index_chunks(self, chunks: list[Chunk]) -> None:
        self.ensure_index()
        for chunk in chunks:
            self.client.index(index=self.index, id=chunk.chunk_id, document=chunk.to_payload())
        self.client.indices.refresh(index=self.index)

    def search(self, query: str, top_k: int | None = None) -> list[SparseHit]:
        k = top_k or settings.top_k_sparse
        resp = self.client.search(
            index=self.index,
            query={"match": {"text": {"query": query}}},
            size=k,
        )
        hits: list[SparseHit] = []
        for hit in resp["hits"]["hits"]:
            hits.append(
                SparseHit(chunk_id=hit["_source"]["chunk_id"], score=hit["_score"], payload=hit["_source"])
            )
        return hits
