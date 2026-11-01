#!/usr/bin/env python
"""End-to-end ingestion: load PDFs -> chunk -> index into both Elasticsearch
and Qdrant.

Usage:
    python scripts/ingest.py --source data/raw
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Self-bootstrap sys.path so the script can be run directly from repo root or scripts dir
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from voltagent.config import settings
from voltagent.ingestion.chunking import chunk_pages
from voltagent.ingestion.loaders import load_directory
from voltagent.retrieval.dense_qdrant import QdrantRetriever
from voltagent.retrieval.sparse_es import ElasticsearchRetriever


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest and index source PDFs.")
    parser.add_argument(
        "--source",
        nargs="+",
        default=["data/raw/real", "data/raw/synthetic"],
        help="Directories containing source PDFs.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=settings.chunk_size_tokens,
        help="Chunk size in tokens (default: settings.chunk_size_tokens)",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=settings.chunk_overlap_tokens,
        help="Chunk overlap in tokens (default: settings.chunk_overlap_tokens)",
    )
    args = parser.parse_args()

    sources = args.source if isinstance(args.source, list) else [args.source]
    print(f"[1/4] Loading PDFs from {sources} ...")
    pages = []
    for src in sources:
        p = load_directory(src)
        print(f"      Loaded {len(p)} pages from {src}")
        pages.extend(p)

    if not pages:
        print(
            f"No extractable text found in {sources}. "
            "Add OCPP/error-code/safety PDFs there first.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"      Total: {len(pages)} non-empty pages across all documents.")

    print(f"[2/4] Chunking (size={args.chunk_size}, overlap={args.overlap}) ...")
    chunks = chunk_pages(pages, chunk_size_tokens=args.chunk_size, overlap_tokens=args.overlap)
    print(f"      Produced {len(chunks)} chunks.")

    print("[3/4] Indexing into Elasticsearch (BM25 leg) ...")
    es = ElasticsearchRetriever()
    es.index_chunks(chunks)
    print("      Done.")

    print("[4/4] Indexing into Qdrant (dense leg) — this loads the embedding model, "
          "first run will be slower ...")
    qdrant = QdrantRetriever()
    qdrant.index_chunks(chunks)
    print("      Done.")

    print(f"\nIngestion complete: {len(chunks)} chunks indexed in both legs.")


if __name__ == "__main__":
    main()
