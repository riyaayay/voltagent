"""Evaluate the Verifier Agent on frozen benchmark test sets (Claim C).

Integrity Rules:
- Evaluates test_wrong_10.json (frozen, SHA-256 verified)
- Evaluates test_correct.json (frozen, SHA-256 verified)
- No mocks of the verifier logic or embedding model
- Records wrong-case flag rate (N/10), false-flag rate on correct cases, and threshold
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

EXPECTED_HASHES = {
    # Hashes computed over LF-normalised bytes (CRLF→LF) so they are
    # platform-agnostic: identical on Linux CI (LF checkout) and Windows
    # dev machines (CRLF checkout via core.autocrlf=true).
    "test_wrong_10.json": "43d61f3a928f3e46783a21211fc49591a003a2fc8ecadda753d80b9d45de0e3c",
    "test_correct.json": "b4245134db5f1af76832a37f2f12670f5736bd5eaa08cb6b3c56ab6d0350a008",
}


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 over LF-normalised file bytes.

    git's core.autocrlf converts LF→CRLF on Windows checkout, which would
    produce a different raw hash than CI (Linux, LF checkout) sees.  Normalising
    CRLF→LF before hashing makes the digest platform-agnostic and consistent
    with the values stored in EXPECTED_HASHES above.
    """
    raw = Path(path).read_bytes()
    normalised = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(normalised).hexdigest()


def evaluate_dataset(file_name: str, expected_hash: str) -> tuple[dict, list[dict]]:
    path = Path("data/eval") / file_name
    if not path.exists():
        raise FileNotFoundError(f"Missing dataset: {path}")

    actual_hash = compute_sha256(path)
    if actual_hash != expected_hash:
        raise ValueError(
            f"Integrity check failed for {file_name}!\n"
            f"Expected: {expected_hash}\n"
            f"Actual:   {actual_hash}"
        )

    with open(path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    results = []
    for c in cases:
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

        results.append({
            "case_id": c["case_id"],
            "source": c.get("source"),
            "failure_type": c.get("failure_type"),
            "query": c.get("query"),
            "expected_verified": c["expected_verified"],
            "actual_verified": res.verified,
            "confidence": res.confidence,
            "fallback": res.fallback,
            "fallback_reason": res.fallback_reason,
            "missing_values": [
                val for sc in res.sentence_checks for val in sc.gate_missing
            ],
            "elapsed_ms": round(elapsed_ms, 2),
        })

    summary = {
        "file_name": file_name,
        "sha256": actual_hash,
        "total_cases": len(cases),
        "verified_count": sum(1 for r in results if r["actual_verified"]),
        "unverified_count": sum(1 for r in results if not r["actual_verified"]),
    }
    return summary, results


def main():
    print("=" * 80)
    print("VOLTAGENT VERIFIER BENCHMARK EVALUATION (CLAIM C)")
    print("=" * 80)
    print(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print(f"Confidence Threshold: {settings.verifier_confidence_threshold}")
    print("-" * 80)

    # 1. Evaluate frozen test_wrong_10.json
    print("\nEvaluating test_wrong_10.json (Frozen 10 Deliberately Wrong Cases)...")
    summary_wrong, results_wrong = evaluate_dataset("test_wrong_10.json", EXPECTED_HASHES["test_wrong_10.json"])
    flagged_wrong = summary_wrong["unverified_count"]
    wrong_flag_rate = flagged_wrong / summary_wrong["total_cases"]

    for r in results_wrong:
        flagged = "FLAGGED (Unverified)" if not r["actual_verified"] else "MISSED (Verified)"
        print(f"[{r['case_id']}] {flagged} - type: {r['failure_type']}")
        print(f"    Confidence: {r['confidence']:.3f} | Missing: {r['missing_values']}")
        if r['fallback_reason']:
            print(f"    Reason: {r['fallback_reason']}")

    # 2. Evaluate frozen test_correct.json
    print("\n" + "-" * 80)
    print("Evaluating test_correct.json (Frozen >=20 Correct Cases)...")
    summary_correct, results_correct = evaluate_dataset("test_correct.json", EXPECTED_HASHES["test_correct.json"])
    false_flags = summary_correct["unverified_count"]
    false_flag_rate = false_flags / summary_correct["total_cases"]

    for r in results_correct:
        status = "PASSED (Verified)" if r["actual_verified"] else "FALSE FLAG (Unverified)"
        print(f"[{r['case_id']}] {status}")
        print(f"    Confidence: {r['confidence']:.3f}")
        if not r["actual_verified"]:
            print(f"    Reason: {r['fallback_reason']} | Missing: {r['missing_values']}")

    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY (CLAIM C METRICS)")
    print("=" * 80)
    print(f"Wrong cases tested:          {summary_wrong['total_cases']}")
    print(f"Wrong cases flagged:         {flagged_wrong} / {summary_wrong['total_cases']} ({wrong_flag_rate * 100:.1f}%)")
    print(f"Target wrong flag rate:      >= 8 / 10 (>= 80.0%)")
    print(f"Correct cases tested:        {summary_correct['total_cases']}")
    print(f"False flags on correct:      {false_flags} / {summary_correct['total_cases']} ({false_flag_rate * 100:.1f}%)")
    print(f"Target false-flag rate:      <= 20.0%")
    print(f"Threshold applied:           {settings.verifier_confidence_threshold}")
    print(f"Claim C Success Criteria:   {'PASSED' if (flagged_wrong >= 8 and false_flag_rate <= 0.20) else 'FAILED'}")
    print("=" * 80)

    # Save output artifacts
    os.makedirs("results", exist_ok=True)
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "threshold": settings.verifier_confidence_threshold,
        "wrong_cases_summary": summary_wrong,
        "wrong_cases_details": results_wrong,
        "correct_cases_summary": summary_correct,
        "correct_cases_details": results_correct,
        "metrics": {
            "wrong_flag_count": flagged_wrong,
            "wrong_flag_total": summary_wrong["total_cases"],
            "wrong_flag_rate": wrong_flag_rate,
            "false_flag_count": false_flags,
            "false_flag_total": summary_correct["total_cases"],
            "false_flag_rate": false_flag_rate,
            "claim_c_passed": (flagged_wrong >= 8 and false_flag_rate <= 0.20),
        }
    }
    out_prefix = sys.argv[1] if len(sys.argv) > 1 else "results/verifier_eval_frozen"
    with open(f"{out_prefix}.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()

