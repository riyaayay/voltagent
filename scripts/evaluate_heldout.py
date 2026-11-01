"""Evaluate the Verifier Agent on the held-out evaluation dataset (data/eval/heldout_60.json).

Integrity Rules:
- Verifies SHA-256 hash of heldout_60.json
- Evaluates 30 wrong cases (covering all 10 failure types, 22 real + 8 synthetic)
- Evaluates 30 correct cases (22 real + 8 synthetic)
- No mocks of the verifier logic or embedding model
- Output saved to results/verifier_eval_heldout_60.json and .txt
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

# Bootstrap sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voltagent.agents.generation_agent import GenerationResult
from voltagent.agents.verifier_agent import run_verifier_agent
from voltagent.config import settings
from voltagent.retrieval.types import RetrievedChunk

EXPECTED_HELDOUT_HASH = "0a758d62c985b1d62b7aeedd02e326fb1ccc01f9cac9ad4840540fc1238b8c69"


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    path = Path("data/eval/heldout_60.json")
    if not path.exists():
        raise FileNotFoundError(f"Missing dataset: {path}")

    actual_hash = compute_sha256(path)
    if actual_hash != EXPECTED_HELDOUT_HASH:
        raise ValueError(
            f"Integrity check failed for heldout_60.json!\n"
            f"Expected: {EXPECTED_HELDOUT_HASH}\n"
            f"Actual:   {actual_hash}"
        )

    with open(path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    wrong_cases = [c for c in cases if not c["expected_verified"]]
    correct_cases = [c for c in cases if c["expected_verified"]]

    print("=" * 80)
    print("VOLTAGENT VERIFIER HELDOUT-60 BENCHMARK EVALUATION")
    print("=" * 80)
    print(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print(f"Dataset SHA-256: {actual_hash}")
    print(f"Total Cases: {len(cases)} (Wrong: {len(wrong_cases)}, Correct: {len(correct_cases)})")
    print(f"Confidence Threshold: {settings.verifier_confidence_threshold}")
    print("-" * 80)

    # 1. Evaluate wrong cases
    print("\n--- Evaluating 30 Wrong Cases (Held-Out) ---")
    wrong_results = []
    type_stats: dict[str, dict[str, int]] = {}

    for c in wrong_cases:
        chunks = [
            RetrievedChunk(
                chunk_id=chk["chunk_id"],
                text=chk["text"],
                doc_id=chk["doc_id"],
                doc_title=chk["doc_id"],
                page_number=chk["page_number"],
                rrf_score=1.0,
                sparse_rank=1,
                dense_rank=1,
            )
            for chk in c.get("cited_chunks", [])
        ]

        gen = GenerationResult(
            answer_text=c["answer_text"],
            cited_chunk_ids=[chk.chunk_id for chk in chunks],
            used_chunks=chunks,
            is_insufficient=c.get("is_insufficient", False),
        )

        t0 = time.perf_counter()
        res = run_verifier_agent(gen, query_text=c.get("query"))
        elapsed_ms = (time.perf_counter() - t0) * 1000

        is_flagged = not res.verified
        ftype = c.get("failure_type", "unknown")
        if ftype not in type_stats:
            type_stats[ftype] = {"total": 0, "flagged": 0}
        type_stats[ftype]["total"] += 1
        if is_flagged:
            type_stats[ftype]["flagged"] += 1

        flagged_str = "FLAGGED (Unverified)" if is_flagged else "MISSED (Verified)"
        print(f"[{c['case_id']}] {flagged_str} | type: {ftype} | src: {c.get('source')}")
        print(f"    Confidence: {res.confidence:.3f} | Fallback: {res.fallback}")
        if res.fallback_reason:
            print(f"    Reason: {res.fallback_reason}")

        wrong_results.append({
            "case_id": c["case_id"],
            "source": c.get("source"),
            "failure_type": ftype,
            "query": c.get("query"),
            "expected_verified": False,
            "actual_verified": res.verified,
            "confidence": res.confidence,
            "fallback": res.fallback,
            "fallback_reason": res.fallback_reason,
            "missing_values": [
                val for sc in res.sentence_checks for val in sc.gate_missing
            ],
            "elapsed_ms": round(elapsed_ms, 2),
        })

    # 2. Evaluate correct cases
    print("\n--- Evaluating 30 Correct Cases (Held-Out) ---")
    correct_results = []
    for c in correct_cases:
        chunks = [
            RetrievedChunk(
                chunk_id=chk["chunk_id"],
                text=chk["text"],
                doc_id=chk["doc_id"],
                doc_title=chk["doc_id"],
                page_number=chk["page_number"],
                rrf_score=1.0,
                sparse_rank=1,
                dense_rank=1,
            )
            for chk in c.get("cited_chunks", [])
        ]

        gen = GenerationResult(
            answer_text=c["answer_text"],
            cited_chunk_ids=[chk.chunk_id for chk in chunks],
            used_chunks=chunks,
            is_insufficient=c.get("is_insufficient", False),
        )

        t0 = time.perf_counter()
        res = run_verifier_agent(gen, query_text=c.get("query"))
        elapsed_ms = (time.perf_counter() - t0) * 1000

        status = "PASSED (Verified)" if res.verified else "FALSE FLAG (Unverified)"
        print(f"[{c['case_id']}] {status} | src: {c.get('source')}")
        print(f"    Confidence: {res.confidence:.3f}")
        if not res.verified:
            print(f"    Reason: {res.fallback_reason}")

        correct_results.append({
            "case_id": c["case_id"],
            "source": c.get("source"),
            "query": c.get("query"),
            "expected_verified": True,
            "actual_verified": res.verified,
            "confidence": res.confidence,
            "fallback": res.fallback,
            "fallback_reason": res.fallback_reason,
            "missing_values": [
                val for sc in res.sentence_checks for val in sc.gate_missing
            ],
            "elapsed_ms": round(elapsed_ms, 2),
        })

    wrong_flagged = sum(1 for r in wrong_results if not r["actual_verified"])
    wrong_flag_rate = wrong_flagged / len(wrong_cases)
    false_flags = sum(1 for r in correct_results if not r["actual_verified"])
    false_flag_rate = false_flags / len(correct_cases)

    # Sub-breakdown by real vs synthetic
    wrong_real = [r for r in wrong_results if r["source"] == "real"]
    wrong_real_flagged = sum(1 for r in wrong_real if not r["actual_verified"])
    wrong_synth = [r for r in wrong_results if r["source"] == "synthetic"]
    wrong_synth_flagged = sum(1 for r in wrong_synth if not r["actual_verified"])

    correct_real = [r for r in correct_results if r["source"] == "real"]
    correct_real_false_flags = sum(1 for r in correct_real if not r["actual_verified"])
    correct_synth = [r for r in correct_results if r["source"] == "synthetic"]
    correct_synth_false_flags = sum(1 for r in correct_synth if not r["actual_verified"])

    print("\n" + "=" * 80)
    print("HELDOUT-60 EVALUATION SUMMARY")
    print("=" * 80)
    print(f"Wrong cases tested:          {len(wrong_cases)}")
    print(f"Wrong cases flagged:         {wrong_flagged} / {len(wrong_cases)} ({wrong_flag_rate * 100:.1f}%)")
    print(f"  - Real PDF wrong cases:    {wrong_real_flagged} / {len(wrong_real)} ({wrong_real_flagged/len(wrong_real)*100:.1f}%)")
    print(f"  - Synthetic wrong cases:   {wrong_synth_flagged} / {len(wrong_synth)} ({wrong_synth_flagged/len(wrong_synth)*100:.1f}%)")
    print("\nBreakdown by failure mode:")
    for ftype, stats in sorted(type_stats.items()):
        print(f"  - {ftype:45s}: {stats['flagged']} / {stats['total']} ({stats['flagged']/stats['total']*100:.1f}%)")

    print("\nCorrect cases tested:        {0}".format(len(correct_cases)))
    print(f"False flags on correct:      {false_flags} / {len(correct_cases)} ({false_flag_rate * 100:.1f}%)")
    print(f"  - Real PDF false flags:    {correct_real_false_flags} / {len(correct_real)} ({correct_real_false_flags/len(correct_real)*100:.1f}%)")
    print(f"  - Synthetic false flags:   {correct_synth_false_flags} / {len(correct_synth)} ({correct_synth_false_flags/len(correct_synth)*100:.1f}%)")
    print(f"Confidence threshold:        {settings.verifier_confidence_threshold}")
    print("=" * 80)

    # Save to results/
    os.makedirs("results", exist_ok=True)
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset": "heldout_60.json",
        "sha256": actual_hash,
        "threshold": settings.verifier_confidence_threshold,
        "metrics": {
            "wrong_flag_count": wrong_flagged,
            "wrong_flag_total": len(wrong_cases),
            "wrong_flag_rate": wrong_flag_rate,
            "wrong_real_flagged": wrong_real_flagged,
            "wrong_real_total": len(wrong_real),
            "wrong_synth_flagged": wrong_synth_flagged,
            "wrong_synth_total": len(wrong_synth),
            "false_flag_count": false_flags,
            "false_flag_total": len(correct_cases),
            "false_flag_rate": false_flag_rate,
            "correct_real_false_flags": correct_real_false_flags,
            "correct_real_total": len(correct_real),
            "correct_synth_false_flags": correct_synth_false_flags,
            "correct_synth_total": len(correct_synth),
            "failure_mode_breakdown": type_stats,
        },
        "wrong_cases_details": wrong_results,
        "correct_cases_details": correct_results,
    }

    with open("results/verifier_eval_heldout_60.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("Saved results to results/verifier_eval_heldout_60.json")


if __name__ == "__main__":
    main()

