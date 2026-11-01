#!/usr/bin/env python
"""Retrieval evaluation harness (Phase 1.3).

Evaluates sparse, dense, and fused retrieval legs on data/eval/gold.json.
Reports Recall@k and MRR split by:
  - Source: Real documents vs Synthetic documents
  - Language: English vs Hindi/Hinglish (cross-lingual)
  - Category: error_led_lookup, exact_field_message, safety_limit_numeric, etc.

Usage:
    python scripts/evaluate_retrieval.py --gold data/eval/gold.json --k 6
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# Self-bootstrap sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from voltagent.retrieval.dense_qdrant import QdrantRetriever
from voltagent.retrieval.fusion import reciprocal_rank_fusion
from voltagent.retrieval.sparse_es import ElasticsearchRetriever


@dataclass
class EvalCase:
    query: str
    expected_doc_id: str | None
    query_id: str = ""
    source: str = "unknown"
    category: str = "general"
    language: str = "en"
    expected_page: int | None = None
    evidence: str = ""


def _rank_of(doc_ids: list[str], expected: str | None, k: int) -> int | None:
    if expected is None:
        return None
    for i, doc_id in enumerate(doc_ids[:k]):
        if doc_id == expected:
            return i + 1
    return None


def run_eval(gold_path: str, k: int = 6) -> dict:
    with open(gold_path, encoding="utf-8") as f:
        raw_cases = json.load(f)

    cases = [
        EvalCase(
            query=c["query"],
            expected_doc_id=c.get("expected_doc_id"),
            query_id=c.get("query_id", ""),
            source=c.get("source", "unknown"),
            category=c.get("category", "general"),
            language=c.get("language", "en"),
            expected_page=c.get("expected_page"),
            evidence=c.get("evidence", ""),
        )
        for c in raw_cases
    ]

    sparse_retriever = ElasticsearchRetriever()
    dense_retriever = QdrantRetriever()

    # Track metrics overall and by split
    splits: dict[str, list[dict]] = defaultdict(list)

    print("=" * 90)
    print(f"VOLTAGENT HYBRID RETRIEVAL BENCHMARK (k={k})")
    print("=" * 90)
    print(f"{'query_id':<25} {'source':<10} {'lang':<6} {'sparse':<8} {'dense':<8} {'fused':<8}")
    print("-" * 90)

    for case in cases:
        # Out-of-scope probes (expected_doc_id is None)
        if case.expected_doc_id is None:
            continue

        sparse = sparse_retriever.search(case.query)
        dense = dense_retriever.search(case.query)
        fused = reciprocal_rank_fusion(sparse, dense, top_k=k)

        sparse_doc_ids = [h.payload["doc_id"] for h in sparse]
        dense_doc_ids = [h.payload["doc_id"] for h in dense]
        fused_doc_ids = [h.payload["doc_id"] for h in fused]

        s_rank = _rank_of(sparse_doc_ids, case.expected_doc_id, k)
        d_rank = _rank_of(dense_doc_ids, case.expected_doc_id, k)
        f_rank = _rank_of(fused_doc_ids, case.expected_doc_id, k)

        s_hit = s_rank is not None
        d_hit = d_rank is not None
        f_hit = f_rank is not None

        item = {
            "query_id": case.query_id,
            "query": case.query,
            "expected_doc_id": case.expected_doc_id,
            "source": case.source,
            "language": case.language,
            "category": case.category,
            "sparse_hit": s_hit,
            "dense_hit": d_hit,
            "fused_hit": f_hit,
            "sparse_mrr": 1.0 / s_rank if s_rank else 0.0,
            "dense_mrr": 1.0 / d_rank if d_rank else 0.0,
            "fused_mrr": 1.0 / f_rank if f_rank else 0.0,
        }

        splits["all"].append(item)
        splits[f"source:{case.source}"].append(item)
        splits[f"lang:{case.language}"].append(item)
        splits[f"cat:{case.category}"].append(item)

        print(
            f"{case.query_id:<25} {case.source:<10} {case.language:<6} "
            f"{str(s_hit):<8} {str(d_hit):<8} {str(f_hit):<8}"
        )

    print("-" * 90)
    print("\nRETRIEVAL METRICS SUMMARY BY SPLIT:")
    print("=" * 90)
    print(f"{'Split':<25} {'Count':<8} {'Sparse R@k':<12} {'Dense R@k':<12} {'Fused R@k':<12} {'Fused MRR':<10}")
    print("-" * 90)

    summary_by_split = {}
    for split_name, items in sorted(splits.items()):
        n = len(items)
        s_recall = sum(1 for x in items if x["sparse_hit"]) / n
        d_recall = sum(1 for x in items if x["dense_hit"]) / n
        f_recall = sum(1 for x in items if x["fused_hit"]) / n
        f_mrr = sum(x["fused_mrr"] for x in items) / n

        summary_by_split[split_name] = {
            "count": n,
            "sparse_recall": round(s_recall, 3),
            "dense_recall": round(d_recall, 3),
            "fused_recall": round(f_recall, 3),
            "fused_mrr": round(f_mrr, 3),
        }
        print(
            f"{split_name:<25} {n:<8} {s_recall*100:>10.1f}% {d_recall*100:>10.1f}% "
            f"{f_recall*100:>10.1f}% {f_mrr:>10.3f}"
        )
    print("=" * 90)

    os.makedirs("results", exist_ok=True)
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "k": k,
        "splits": summary_by_split,
        "details": splits["all"],
    }
    with open("results/retrieval_eval.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate hybrid retrieval quality.")
    parser.add_argument("--gold", default="data/eval/gold.json", help="Path to gold query JSON file.")
    parser.add_argument("--k", type=int, default=6)
    args = parser.parse_args()
    run_eval(args.gold, k=args.k)
