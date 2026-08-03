#!/usr/bin/env python
"""Small retrieval eval harness.

Not a full IR benchmark — a pragmatic recall@k check against a hand-labeled
set of (query, expected_doc_id) pairs, so you can see, concretely, whether
the sparse leg, dense leg, or fusion is doing the work for a given query
type. This is what turns "we added hybrid search" into a number you can put
in a README or an interview answer.

Usage:
    python scripts/evaluate_retrieval.py --gold scripts/gold_queries.json

Gold file format (JSON list):
    [
      {"query": "what does error code E203 mean", "expected_doc_id": "charger-error-codes"},
      {"query": "OCPP StopTransaction required fields", "expected_doc_id": "ocpp-2.0.1-spec"}
    ]
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

from voltagent.retrieval.dense_qdrant import QdrantRetriever
from voltagent.retrieval.fusion import reciprocal_rank_fusion
from voltagent.retrieval.sparse_es import ElasticsearchRetriever


@dataclass
class EvalCase:
    query: str
    expected_doc_id: str


def _hit_at_k(doc_ids: list[str], expected: str, k: int) -> bool:
    return expected in doc_ids[:k]


def run_eval(gold_path: str, k: int = 6) -> None:
    with open(gold_path, encoding="utf-8") as f:
        raw_cases = json.load(f)
    cases = [EvalCase(**c) for c in raw_cases]

    sparse_retriever = ElasticsearchRetriever()
    dense_retriever = QdrantRetriever()

    sparse_hits_count = dense_hits_count = fused_hits_count = 0

    print(f"{'query':<55} {'sparse':<8} {'dense':<8} {'fused':<8}")
    print("-" * 82)

    for case in cases:
        sparse = sparse_retriever.search(case.query)
        dense = dense_retriever.search(case.query)
        fused = reciprocal_rank_fusion(sparse, dense, top_k=k)

        sparse_doc_ids = [h.payload["doc_id"] for h in sparse]
        dense_doc_ids = [h.payload["doc_id"] for h in dense]
        fused_doc_ids = [h.payload["doc_id"] for h in fused]

        s_hit = _hit_at_k(sparse_doc_ids, case.expected_doc_id, k)
        d_hit = _hit_at_k(dense_doc_ids, case.expected_doc_id, k)
        f_hit = _hit_at_k(fused_doc_ids, case.expected_doc_id, k)

        sparse_hits_count += s_hit
        dense_hits_count += d_hit
        fused_hits_count += f_hit

        print(f"{case.query[:53]:<55} {str(s_hit):<8} {str(d_hit):<8} {str(f_hit):<8}")

    n = len(cases)
    print("-" * 82)
    print(f"Recall@{k}  sparse: {sparse_hits_count}/{n}   dense: {dense_hits_count}/{n}   fused: {fused_hits_count}/{n}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate hybrid retrieval quality.")
    parser.add_argument("--gold", required=True, help="Path to gold query JSON file.")
    parser.add_argument("--k", type=int, default=6)
    args = parser.parse_args()
    run_eval(args.gold, k=args.k)
