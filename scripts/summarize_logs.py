"""Summarize structured JSONL event logs (T7/T8 observability).

Aggregates:
- Total queries and stage latencies (min, mean, max)
- Verification rate (verified vs fallback)
- Cache hit rate
- Feedback resolution rate
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# Bootstrap sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voltagent.config import settings


def summarize(log_file: str | None = None) -> dict:
    path = Path(log_file or settings.log_file)
    if not path.exists():
        print(f"Log file not found at {path}. No logs to summarize.")
        return {}

    events_by_stage = defaultdict(list)
    query_completes = []
    feedbacks = []
    cache_lookups = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue

            stage = ev.get("stage", "unknown")
            events_by_stage[stage].append(ev)

            if stage == "query_complete":
                query_completes.append(ev)
            elif stage == "feedback":
                feedbacks.append(ev)
            elif stage == "cache_lookup":
                cache_lookups.append(ev)

    total_queries = len(query_completes)
    verified_count = sum(1 for q in query_completes if q.get("verified"))
    total_feedbacks = len(feedbacks)
    resolved_feedbacks = sum(1 for fb in feedbacks if fb.get("resolved"))
    total_cache_lookups = len(cache_lookups)
    cache_hits = sum(1 for c in cache_lookups if c.get("hit"))

    stage_latencies = defaultdict(list)
    for q in query_completes:
        for k, v in q.items():
            if k.endswith("_ms") and isinstance(v, (int, float)):
                stage_latencies[k].append(v)

    latency_summary = {}
    for stg, lats in stage_latencies.items():
        if lats:
            lats_sorted = sorted(lats)
            latency_summary[stg] = {
                "count": len(lats),
                "mean_ms": round(sum(lats) / len(lats), 1),
                "p50_ms": round(lats_sorted[len(lats_sorted) // 2], 1),
                "p95_ms": round(lats_sorted[int(len(lats_sorted) * 0.95)], 1),
                "max_ms": round(lats_sorted[-1], 1),
            }

    summary = {
        "log_file": str(path),
        "total_queries": total_queries,
        "verification_rate": (
            round(verified_count / total_queries * 100, 1) if total_queries else 0.0
        ),
        "verified_count": verified_count,
        "fallback_count": total_queries - verified_count,
        "cache_lookup_count": total_cache_lookups,
        "cache_hit_rate": (
            round(cache_hits / total_cache_lookups * 100, 1) if total_cache_lookups else 0.0
        ),
        "feedback_count": total_feedbacks,
        "feedback_resolved_rate": (
            round(resolved_feedbacks / total_feedbacks * 100, 1) if total_feedbacks else 0.0
        ),
        "stage_latencies": latency_summary,
    }

    print("=" * 60)
    print("VOLTAGENT LOG SUMMARY")
    print("=" * 60)
    print(f"Log path:           {path}")
    print(f"Total queries:      {total_queries}")
    print(f"Verified queries:   {verified_count} ({summary['verification_rate']}%)")
    print(f"Cache lookups:      {total_cache_lookups} (Hits: {cache_hits}, {summary['cache_hit_rate']}%)")
    print(f"Feedback events:    {total_feedbacks} (Resolved: {resolved_feedbacks})")
    print("-" * 60)
    print("Stage Latencies:")
    for stg, stats in latency_summary.items():
        print(f"  {stg:20s}: mean={stats['mean_ms']}ms, p50={stats['p50_ms']}ms, p95={stats['p95_ms']}ms, max={stats['max_ms']}ms")
    print("=" * 60)

    return summary


if __name__ == "__main__":
    summarize()

