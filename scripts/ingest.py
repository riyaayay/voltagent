#!/usr/bin/env python
"""End-to-end ingestion: load PDFs -> chunk -> index into both Elasticsearch
and Qdrant.

Usage:
    python scripts/ingest.py --source data/raw
"""
from __future__ import annotations

import argparse
import sys

from voltagent.ingestion.chunking import chunk_pages
from voltagent.ingestion.loaders import load_directory
from voltagent.retrieval.dense_qdrant import QdrantRetriever
from voltagent.retrieval.sparse_es import ElasticsearchRetriever


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest and index source PDFs.")
    parser.add_argument(
        "--source", default="data/raw", help="Directory containing source PDFs."
    )
    args = parser.parse_args()

    print(f"[1/4] Loading PDFs from {args.source} ...")
    pages = load_directory(args.source)
    if not pages:
        print(
            f"No extractable text found in {args.source}. "
            "Add OCPP/error-code/safety PDFs there first.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"      Loaded {len(pages)} non-empty pages across all PDFs.")

    print("[2/4] Chunking ...")
    chunks = chunk_pages(pages)
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
