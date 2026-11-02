"""Evaluate the Verifier Agent on the held-out evaluation dataset (data/eval/heldout_v2_30.json).

Integrity Rules:
- Verifies SHA-256 hash of heldout_v2_30.json
- Evaluates 15 wrong cases and 15 correct cases (20 real + 10 synthetic)
- No mocks of the verifier logic or embedding model
- Output saved to results/verifier_eval_heldout_v2.json and .txt
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

EXPECTED_HELDOUT_HASH = "ad46a72fe6cc5f0e5216aa8bef1b40edd6c63da135961770fdaf0fbf14d2f210"


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    path = Path("data/eval/heldout_v2_30.json")
    if not path.exists():
        raise FileNotFoundError(f"Missing dataset: {path}")

    actual_hash = compute_sha256(path)
    if actual_hash != EXPECTED_HELDOUT_HASH:
        raise ValueError(
            f"Integrity check failed for heldout_v2_30.json!\n"
            f"Expected: {EXPECTED_HELDOUT_HASH}\n"
            f"Actual:   {actual_hash}"
        )

    with open(path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    wrong_cases = [c for c in cases if not c["expected_verified"]]
    correct_cases = [c for c in cases if c["expected_verified"]]

    lines = []
    def log(msg: str = ""):
        print(msg)
        lines.append(msg)

    log("=" * 80)
    log("VOLTAGENT VERIFIER HELDOUT-V2-30 BENCHMARK EVALUATION")
    log("=" * 80)
    log(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    log(f"Dataset SHA-256: {actual_hash}")
    log(f"Total Cases: {len(cases)} (Wrong: {len(wrong_cases)}, Correct: {len(correct_cases)})")
    log(f"Confidence Threshold: {settings.verifier_confidence_threshold}")
    log("-" * 80)

    # 1. Evaluate wrong cases
    log("\n--- Evaluating 15 Wrong Cases (Held-Out v2) ---")
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

        status_str = "FLAGGED (Correct)" if is_flagged else "MISSED (Bug!)"
        log(f"[{c['case_id']}] {status_str} in {elapsed_ms:.1f}ms | conf={res.confidence} | type={ftype}")
        if not is_flagged:
            log(f"  -> Answer: {c['answer_text']}")
            log(f"  -> Fallback: {res.fallback}, Reason: {res.fallback_reason}")

        wrong_results.append({
            "case_id": c["case_id"],
            "source": c["source"],
            "failure_type": ftype,
            "expected_verified": False,
            "actual_verified": res.verified,
            "flagged_as_wrong": is_flagged,
            "confidence": res.confidence,
            "fallback": res.fallback,
            "fallback_reason": res.fallback_reason,
            "latency_ms": elapsed_ms,
        })

    # 2. Evaluate correct cases
    log("\n--- Evaluating 15 Correct Cases (Held-Out v2) ---")
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

        is_verified = res.verified
        status_str = "VERIFIED (Correct)" if is_verified else "FALSE FLAG (Over-cautious)"
        log(f"[{c['case_id']}] {status_str} in {elapsed_ms:.1f}ms | conf={res.confidence}")
        if not is_verified:
            log(f"  -> Answer: {c['answer_text']}")
            log(f"  -> Fallback reason: {res.fallback_reason}")
            for sc in res.sentence_checks:
                if not sc.supported:
                    log(f"     Unsupported sent: {sc.sentence} (sim={sc.support_score}, missing={sc.gate_missing}, neg_conflict={sc.negation_conflict})")

        correct_results.append({
            "case_id": c["case_id"],
            "source": c["source"],
            "expected_verified": True,
            "actual_verified": res.verified,
            "confidence": res.confidence,
            "fallback": res.fallback,
            "fallback_reason": res.fallback_reason,
            "latency_ms": elapsed_ms,
        })

    # 3. Compute Metrics
    wrong_flagged = sum(1 for r in wrong_results if r["flagged_as_wrong"])
    wrong_flag_rate = wrong_flagged / len(wrong_cases) if wrong_cases else 0.0

    wrong_real = [r for r in wrong_results if r["source"] == "real"]
    wrong_real_flagged = sum(1 for r in wrong_real if r["flagged_as_wrong"])
    wrong_synth = [r for r in wrong_results if r["source"] == "synthetic"]
    wrong_synth_flagged = sum(1 for r in wrong_synth if r["flagged_as_wrong"])

    false_flags = sum(1 for r in correct_results if not r["actual_verified"])
    false_flag_rate = false_flags / len(correct_cases) if correct_cases else 0.0

    correct_real = [r for r in correct_results if r["source"] == "real"]
    correct_real_false_flags = sum(1 for r in correct_real if not r["actual_verified"])
    correct_synth = [r for r in correct_results if r["source"] == "synthetic"]
    correct_synth_false_flags = sum(1 for r in correct_synth if not r["actual_verified"])

    log("\n" + "=" * 80)
    log("HELDOUT-V2-30 EVALUATION SUMMARY")
    log("=" * 80)
    log(f"Wrong cases tested:          {len(wrong_cases)}")
    log(f"Wrong cases flagged:         {wrong_flagged} / {len(wrong_cases)} ({wrong_flag_rate * 100:.1f}%)")
    log(f"  - Real PDF wrong cases:    {wrong_real_flagged} / {len(wrong_real)} ({wrong_real_flagged/len(wrong_real)*100:.1f}%)")
    log(f"  - Synthetic wrong cases:   {wrong_synth_flagged} / {len(wrong_synth)} ({wrong_synth_flagged/len(wrong_synth)*100:.1f}%)")
    log("\nBreakdown by failure mode:")
    for ftype, stats in sorted(type_stats.items()):
        log(f"  - {ftype:45s}: {stats['flagged']} / {stats['total']} ({stats['flagged']/stats['total']*100:.1f}%)")

    log(f"\nCorrect cases tested:        {len(correct_cases)}")
    log(f"False flags on correct:      {false_flags} / {len(correct_cases)} ({false_flag_rate * 100:.1f}%)")
    log(f"  - Real PDF false flags:    {correct_real_false_flags} / {len(correct_real)} ({correct_real_false_flags/len(correct_real)*100:.1f}%)")
    log(f"  - Synthetic false flags:   {correct_synth_false_flags} / {len(correct_synth)} ({correct_synth_false_flags/len(correct_synth)*100:.1f}%)")
    log(f"Confidence threshold:        {settings.verifier_confidence_threshold}")
    log("=" * 80)

    # Save to results/
    os.makedirs("results", exist_ok=True)
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset": "heldout_v2_30.json",
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

    with open("results/verifier_eval_heldout_v2.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    with open("results/verifier_eval_heldout_v2.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("Saved results to results/verifier_eval_heldout_v2.json and results/verifier_eval_heldout_v2.txt")


if __name__ == "__main__":
    main()
