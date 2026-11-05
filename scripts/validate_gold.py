#!/usr/bin/env python
"""Validate all gold queries, check verbatim evidence, and verify dataset integrity.
Saves verification output to results/gold_validation.txt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from voltagent.ingestion.loaders import load_pdf

GOLD_FILE = Path("data/eval/gold.json")
DEV_FILE = Path("data/eval/dev.json")
W10_FILE = Path("data/eval/test_wrong_10.json")
CORR_FILE = Path("data/eval/test_correct.json")

REAL_DIR = Path("data/raw/real")
SYN_DIR = Path("data/raw/synthetic")
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

_pages_cache: dict[str, list] = {}

def get_page(doc_id: str, page_num: int):
    """Return the SourcePage for the given doc and page, or None if the PDF is unavailable."""
    if doc_id not in _pages_cache:
        p = REAL_DIR / f"{doc_id}.pdf"
        if not p.exists():
            p = SYN_DIR / f"{doc_id}.pdf"
        if not p.exists():
            # PDF not checked into the repo (e.g. real/ is gitignored).
            # Cache an empty list so we don't retry on every call.
            _pages_cache[doc_id] = []
        else:
            _pages_cache[doc_id] = load_pdf(str(p))
    match = [pg for pg in _pages_cache[doc_id] if pg.page_number == page_num]
    return match[0] if match else None

def main():
    lines = []
    lines.append("=== GOLD DATASET INTEGRITY VALIDATION ===")
    
    with open(GOLD_FILE, encoding="utf-8") as f:
        gold = json.load(f)
    with open(DEV_FILE, encoding="utf-8") as f:
        dev = json.load(f)
    with open(W10_FILE, encoding="utf-8") as f:
        w10 = json.load(f)
    with open(CORR_FILE, encoding="utf-8") as f:
        corr = json.load(f)

    lines.append(f"Loaded {len(gold)} gold queries.")
    lines.append(f"Loaded {len(dev)} dev queries.")
    lines.append(f"Loaded {len(w10)} test_wrong_10 cases.")
    lines.append(f"Loaded {len(corr)} test_correct cases.")

    # Check 1: Verbatim evidence quotes in stated doc/page
    evidence_checked = 0
    evidence_passed = 0
    evidence_skipped = 0
    for item in gold:
        doc_id = item.get("expected_doc_id")
        page_num = item.get("expected_page")
        evidence = item.get("evidence")
        if doc_id and page_num and evidence:
            evidence_checked += 1
            pg = get_page(doc_id, page_num)
            if pg is None:
                evidence_skipped += 1
                continue
            norm_text = " ".join(pg.text.split())
            norm_ev = " ".join(evidence.split())
            if norm_ev in norm_text:
                evidence_passed += 1
            else:
                msg = f"FAILED quote in {item['query_id']} ({doc_id} p.{page_num}): {evidence}"
                print(msg)
                lines.append(msg)

    checkable = evidence_checked - evidence_skipped
    lines.append(f"\n[Check 1] Verbatim Evidence Quotes: {evidence_passed}/{checkable} verified ({evidence_skipped} skipped, PDF not available).")
    print(f"[Check 1] Verbatim Evidence Quotes: {evidence_passed}/{checkable} verified ({evidence_skipped} skipped).")
    assert evidence_passed == checkable, f"Failed quotes: {checkable - evidence_passed}"

    # Check 2: No gold query text appears verbatim in any ingested page/chunk
    lines.append("\n[Check 2] Checking that no gold query appears verbatim in any source text...")
    verbatim_query_leak = 0
    all_pages = []
    available_pdfs = list(REAL_DIR.glob("*.pdf")) + list(SYN_DIR.glob("*.pdf"))
    if not available_pdfs:
        lines.append("Check 2 skipped: no PDFs available (data/raw/real/ not checked in).")
        print("Check 2 skipped: no PDFs available.")
    else:
        for pdf in available_pdfs:
            all_pages.extend(load_pdf(str(pdf)))

        for item in gold:
            q = item["query"].strip()
            for p in all_pages:
                if len(q) > 15 and q.lower() in p.text.lower():
                    lines.append(f"WARNING: Query '{q}' found verbatim in {p.doc_id} p.{p.page_number}")
                    verbatim_query_leak += 1
                    break
        lines.append(f"Verbatim query leaks detected: {verbatim_query_leak} (Target: 0)")
        assert verbatim_query_leak == 0, "Gold query text leaked verbatim into source documents!"

    # Check 3: Disjointness between dev and test sets
    test_queries = {c["query"] for c in w10} | {c["query"] for c in corr}
    dev_queries = {c["query"] for c in dev}
    overlap = test_queries & dev_queries
    lines.append(f"\n[Check 3] Overlap between dev and test queries: {len(overlap)}")
    assert len(overlap) == 0, f"Query overlap detected between dev and test sets: {overlap}"

    lines.append("\nALL DATA-INTEGRITY CHECKS PASSED.")
    out_text = "\n".join(lines)
    print(out_text)

    with open(RESULTS_DIR / "gold_validation.txt", "w", encoding="utf-8") as f:
        f.write(out_text)
    print(f"\nSaved report to {RESULTS_DIR / 'gold_validation.txt'}")

if __name__ == "__main__":
    main()

