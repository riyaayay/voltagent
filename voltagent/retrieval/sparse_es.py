"""Elasticsearch BM25 leg of hybrid retrieval with in-process rank-bm25 fallback.

Sparse (lexical) search catches exact fault codes, error strings, and OCPP message
names verbatim ("StopTransaction.conf", "E203", "1.40 m").
"""
from __future__ import annotations

import logging
import pickle
import re
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch
from rank_bm25 import BM25Okapi

from voltagent.config import settings
from voltagent.ingestion.chunking import Chunk
from voltagent.retrieval.types import SparseHit

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """Tokenize query and document text for BM25 matching."""
    return re.findall(r"\w+", text.lower())


class RankBM25Retriever:
    """In-memory, zero-dependency BM25 retriever with disk persistence."""
    def __init__(self, cache_file: str = "data/index_cache/bm25.pkl") -> None:
        self.cache_file = Path(cache_file)
        self.chunks: list[Chunk] = []
        self.bm25: BM25Okapi | None = None
        self._load()

    def _load(self) -> None:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "rb") as f:
                    self.chunks = pickle.load(f)
                tokenized_corpus = [_tokenize(c.text) for c in self.chunks]
                self.bm25 = BM25Okapi(tokenized_corpus)
                logger.info("Loaded %d chunks from BM25 cache at %s", len(self.chunks), self.cache_file)
            except Exception as e:
                logger.warning("Failed to load BM25 cache: %s", e)

    def index_chunks(self, chunks: list[Chunk]) -> None:
        self.chunks = list(chunks)
        tokenized_corpus = [_tokenize(c.text) for c in self.chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "wb") as f:
                pickle.dump(self.chunks, f)
            logger.info("Persisted %d chunks into BM25 cache at %s", len(self.chunks), self.cache_file)
        except Exception as e:
            logger.warning("Failed to persist BM25 cache: %s", e)

    def search(self, query: str, top_k: int | None = None) -> list[SparseHit]:
        if not self.chunks or self.bm25 is None:
            return []
        k = top_k or settings.top_k_sparse
        tokenized_query = _tokenize(query)
        if not tokenized_query:
            return []
        scores = self.bm25.get_scores(tokenized_query)
        scored_pairs = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

        hits: list[SparseHit] = []
        for idx, score in scored_pairs[:k]:
            if score <= 0.0:
                continue
            chunk = self.chunks[idx]
            hits.append(SparseHit(chunk_id=chunk.chunk_id, score=float(score), payload=chunk.to_payload()))
        return hits


_in_memory_bm25 = RankBM25Retriever()


class ElasticsearchRetriever:
    def __init__(self, url: str | None = None, index: str | None = None) -> None:
        self.client = Elasticsearch(
            url or settings.elasticsearch_url,
            request_timeout=settings.elasticsearch_timeout_seconds,
            max_retries=0,
        )
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
        # Also index into in-memory BM25 so fallback is always pre-populated
        _in_memory_bm25.index_chunks(chunks)
        self.ensure_index()
        for chunk in chunks:
            self.client.index(index=self.index, id=chunk.chunk_id, document=chunk.to_payload())
        self.client.indices.refresh(index=self.index)

    def search(self, query: str, top_k: int | None = None) -> list[SparseHit]:
        if settings.sparse_backend == "bm25":
            return _in_memory_bm25.search(query, top_k=top_k)

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
