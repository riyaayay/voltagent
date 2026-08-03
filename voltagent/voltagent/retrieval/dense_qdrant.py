"""Qdrant dense-vector leg of hybrid retrieval.

Catches the cases lexical search misses: a technician asking "why does the
charger keep resetting mid-session" should still retrieve the spec section
on session timeout handling even though no word overlaps. Multilingual
sentence-transformers model so Hindi queries retrieve against
English-language source docs without a separate translation step.
"""
from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from voltagent.config import settings
from voltagent.ingestion.chunking import Chunk
from voltagent.retrieval.types import DenseHit

_model: SentenceTransformer | None = None


def get_embedder() -> SentenceTransformer:
    """Lazy-load the embedding model once per process — it's the expensive part."""
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def _point_id(chunk_id: str) -> str:
    # Qdrant point IDs must be UUIDs or unsigned ints; derive a stable UUID
    # from our own chunk_id so re-ingestion overwrites rather than duplicates.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class QdrantRetriever:
    def __init__(self, url: str | None = None, collection: str | None = None) -> None:
        self.client = QdrantClient(url=url or settings.qdrant_url)
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
        results = self.client.search(
            collection_name=self.collection, query_vector=query_vector, limit=k
        )
        return [
            DenseHit(chunk_id=r.payload["chunk_id"], score=r.score, payload=r.payload)
            for r in results
        ]
