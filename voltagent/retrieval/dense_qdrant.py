"""Qdrant dense-vector leg of hybrid retrieval with in-memory fallback.

Catches cases lexical search misses using multilingual sentence-transformers embeddings.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer, util
import torch

from voltagent.config import settings
from voltagent.ingestion.chunking import Chunk
from voltagent.retrieval.types import DenseHit

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


def get_embedder() -> SentenceTransformer:
    """Lazy-load the embedding model once per process."""
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class InProcessDenseRetriever:
    """In-process dense retriever using exact PyTorch cosine similarity with disk persistence."""
    def __init__(self, cache_file: str = "data/index_cache/dense.pt") -> None:
        self.cache_file = Path(cache_file)
        self.chunks: list[Chunk] = []
        self.embeddings: torch.Tensor | None = None
        self._load()

    def _load(self) -> None:
        if self.cache_file.exists():
            try:
                data = torch.load(self.cache_file, map_location="cpu")
                self.chunks = data["chunks"]
                self.embeddings = data["embeddings"]
                logger.info("Loaded %d chunks and embeddings from %s", len(self.chunks), self.cache_file)
            except Exception as e:
                logger.warning("Failed to load dense cache: %s", e)

    def index_chunks(self, chunks: list[Chunk]) -> None:
        self.chunks = list(chunks)
        embedder = get_embedder()
        self.embeddings = embedder.encode([c.text for c in self.chunks], convert_to_tensor=True, show_progress_bar=False)
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"chunks": self.chunks, "embeddings": self.embeddings.cpu()}, self.cache_file)
            logger.info("Persisted %d chunks and embeddings to %s", len(self.chunks), self.cache_file)
        except Exception as e:
            logger.warning("Failed to persist dense cache: %s", e)

    def search(self, query: str, top_k: int | None = None) -> list[DenseHit]:
        if not self.chunks or self.embeddings is None:
            return []
        k = top_k or settings.top_k_dense
        embedder = get_embedder()
        q_emb = embedder.encode(query, convert_to_tensor=True)
        cos_scores = util.cos_sim(q_emb, self.embeddings)[0]
        scored = list(enumerate(cos_scores.tolist()))
        scored.sort(key=lambda x: x[1], reverse=True)

        hits: list[DenseHit] = []
        for idx, score in scored[:k]:
            if score < settings.dense_score_floor:
                continue
            chunk = self.chunks[idx]
            hits.append(DenseHit(chunk_id=chunk.chunk_id, score=float(score), payload=chunk.to_payload()))
        return hits


_in_memory_dense = InProcessDenseRetriever()


class QdrantRetriever:
    def __init__(self, url: str | None = None, collection: str | None = None) -> None:
        self.client = QdrantClient(url=url or settings.qdrant_url, timeout=settings.qdrant_timeout_seconds)
        self.collection = collection or settings.qdrant_collection

    def ensure_collection(self, vector_size: int) -> None:
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection in existing:
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    def index_chunks(self, chunks: list[Chunk], batch_size: int = 64) -> None:
        # Also maintain in-process index as instant fallback
        _in_memory_dense.index_chunks(chunks)

        embedder = get_embedder()
        vector_size = embedder.get_sentence_embedding_dimension()
        self.ensure_collection(vector_size)

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            vectors = embedder.encode([c.text for c in batch], show_progress_bar=False)
            points = [
                PointStruct(id=_point_id(c.chunk_id), vector=v.tolist(), payload=c.to_payload())
                for c, v in zip(batch, vectors)
            ]
            self.client.upsert(collection_name=self.collection, points=points)

    def search(self, query: str, top_k: int | None = None) -> list[DenseHit]:
        k = top_k or settings.top_k_dense
        embedder = get_embedder()
        query_vector = embedder.encode(query).tolist()
        try:
            results = self.client.search(
                collection_name=self.collection,
                query_vector=query_vector,
                limit=k,
                score_threshold=settings.dense_score_floor,
            )
            return [
                DenseHit(chunk_id=r.payload["chunk_id"], score=r.score, payload=r.payload)
                for r in results
            ]
        except Exception as e:
            logger.warning("Qdrant service unreachable (%s); falling back to in-process dense index", e)
            return _in_memory_dense.search(query, top_k=top_k)
