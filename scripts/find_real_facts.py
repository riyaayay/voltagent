#!/usr/bin/env python
"""Search exact verbatim quotes from data/raw/real/ for gold and eval construction."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from voltagent.ingestion.loaders import load_pdf

REAL_DIR = Path("data/raw/real")

def find_terms():
    terms = [
        ("charger-error-codes.pdf", ["Green", "Light blue", "Yellow", "Red", "halo"]),
        ("wallbox-pulsar-plus-install.pdf", ["torque", "NEMA", "240 V", "40 A", "48 A", "ground"]),
        ("ev-safety-compliance.pdf", ["1910.147", "ventricular fibrillation", "let-go", "5 milliampere", "static electricity"]),
        ("ocpp-2.0.1-spec.pdf", ["StatusNotificationRequest", "TransactionEventRequest", "RequestStopTransaction", "eventType", "seqNo"]),
        ("ocpp-2.0.1-appendices.pdf", ["AirCoolingSystem", "ISO15118", "FanSpeed", "Recloser"])
    ]

    findings = []
    for pdf_name, query_list in terms:
        pdf_path = REAL_DIR / pdf_name
        doc_id = pdf_path.stem
        pages = load_pdf(str(pdf_path))
        print(f"Loaded {pdf_name} ({len(pages)} pages)")

        for q in query_list:
            found = False
            for p in pages:
                if q.lower() in p.text.lower():
                    # extract a surrounding 150-char snippet
                    idx = p.text.lower().find(q.lower())
                    start = max(0, idx - 50)
                    end = min(len(p.text), idx + 100)
                    snippet = p.text[start:end].replace("\n", " ").strip()
                    findings.append({
                        "doc_id": doc_id,
                        "pdf_name": pdf_name,
                        "page": p.page_number,
                        "query": q,
                        "snippet": snippet
                    })
                    print(f"  [{doc_id} p.{p.page_number}] '{q}': {snippet[:80]}...")
                    found = True
                    break

    with open("results/extracted_facts.json", "w", encoding="utf-8") as f:
        json.dump(findings, f, indent=2)

if __name__ == "__main__":
    find_terms()

