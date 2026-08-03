"""Shared, dependency-light dataclasses for retrieval hits.

Deliberately separate from sparse_es.py / dense_qdrant.py: those modules
import the Elasticsearch/Qdrant/sentence-transformers clients at module
level, which is fine for the app but means anything importing them pulls in
heavy ML/infra dependencies. fusion.py (pure ranking math) and its tests
shouldn't need any of that just to combine two lists of scored hits.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SparseHit:
    chunk_id: str
    score: float
    payload: dict


@dataclass
class DenseHit:
    chunk_id: str
    score: float
    payload: dict


@dataclass
class FusedHit:
    chunk_id: str
    rrf_score: float
    payload: dict
    sparse_rank: int | None
    dense_rank: int | None


@dataclass
class RetrievedChunk:
    """What the rest of the pipeline (generation, verification) actually
    consumes — deliberately independent of whether it came from ES, Qdrant,
    or fusion, so agent code never has to import infra clients just for a
    type hint."""

    chunk_id: str
    text: str
    doc_id: str
    doc_title: str
    page_number: int
    rrf_score: float
    sparse_rank: int | None
    dense_rank: int | None
