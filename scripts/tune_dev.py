"""Run dev split tuning for the verifier agent.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

# Bootstrap sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voltagent.agents.verifier_agent import run_verifier_agent
from voltagent.agents.generation_agent import GenerationResult
from voltagent.retrieval.types import RetrievedChunk


def run_dev():
    with open("data/eval/dev.json", "r", encoding="utf-8") as f:
        dev_cases = json.load(f)

    passed = 0
    total = len(dev_cases)
    print(f"Evaluating {total} dev tuning cases...")

    for case in dev_cases:
        chunks = [
            RetrievedChunk(
                chunk_id=c["chunk_id"],
                text=c["text"],
                doc_id=c["doc_id"],
                doc_title=c["doc_id"],
                page_number=c["page_number"],
                rrf_score=1.0,
                sparse_rank=1,
                dense_rank=1,
            )
            for c in case["cited_chunks"]
        ]
        gen = GenerationResult(
            answer_text=case["answer_text"],
            cited_chunk_ids=[c.chunk_id for c in chunks],
            used_chunks=chunks,
            is_insufficient=case.get("is_insufficient", False),
        )
        res = run_verifier_agent(gen, query_text=case["query"])
        match = res.verified == case["expected_verified"]
        if match:
            passed += 1
        print(f"[{case['case_id']}] verified={res.verified} (expected={case['expected_verified']}) match={match}")
        print(f"   conf={res.confidence}, fallback={res.fallback}, reason={res.fallback_reason}")
        if res.sentence_checks:
            for sc in res.sentence_checks:
                print(f"   sc: score={sc.support_score}, supported={sc.supported}, missing={sc.gate_missing}")

    print(f"\nDev Score: {passed}/{total} ({passed/total*100:.1f}%)")


if __name__ == "__main__":
    run_dev()

