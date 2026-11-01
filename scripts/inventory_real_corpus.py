#!/usr/bin/env python
"""Analyze real PDFs in data/raw/real/ for Phase 1.0 inventory."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pypdf import PdfReader

from voltagent.ingestion.loaders import load_pdf
from voltagent.ingestion.chunking import chunk_pages

REAL_DIR = Path("data/raw/real")
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

docs_meta = {
    "ocpp-2.0.1-spec.pdf": {
        "publisher": "Open Charge Alliance (OCA)",
        "url": "https://www.openchargealliance.org/protocols/ocpp-201/",
        "title": "OCPP 2.0.1 Specification Part 2 - Specification Edition 2"
    },
    "ocpp-2.0.1-appendices.pdf": {
        "publisher": "Open Charge Alliance (OCA)",
        "url": "https://www.openchargealliance.org/protocols/ocpp-201/",
        "title": "OCPP 2.0.1 Specification Part 2 - Appendices"
    },
    "charger-error-codes.pdf": {
        "publisher": "EVBox",
        "url": "https://help.evbox.com/",
        "title": "EVBox BusinessLine / Elvi LED Status & Error Code Manual"
    },
    "wallbox-pulsar-plus-install.pdf": {
        "publisher": "Wallbox",
        "url": "https://support.wallbox.com/",
        "title": "Wallbox Pulsar Plus Installation Guide"
    },
    "ev-safety-compliance.pdf": {
        "publisher": "OSHA / NFPA",
        "url": "https://www.osha.gov/publications/osha3075",
        "title": "OSHA 3075 Controlling Electrical Hazards & EV Safety Compliance"
    }
}

def analyze():
    report = []
    for pdf_path in sorted(REAL_DIR.glob("*.pdf")):
        filename = pdf_path.name
        doc_id = pdf_path.stem
        meta = docs_meta.get(filename, {"publisher": "Unknown", "url": "Unknown", "title": doc_id})

        reader = PdfReader(str(pdf_path))
        page_count = len(reader.pages)

        # Load through our actual loader
        loaded_pages = load_pdf(str(pdf_path))
        extractable_pages = len(loaded_pages)
        skipped_pages = page_count - extractable_pages
        pct_extractable = (extractable_pages / page_count * 100) if page_count else 0.0

        chunks = chunk_pages(loaded_pages)
        total_chunks = len(chunks)

        is_scan = pct_extractable < 80.0

        # Sample 5-10 pages for text quality inspection
        samples = []
        sample_step = max(1, extractable_pages // 10)
        for p in loaded_pages[::sample_step][:10]:
            samples.append({
                "page": p.page_number,
                "text_snippet": p.text[:300]
            })

        entry = {
            "filename": filename,
            "doc_id": doc_id,
            "title": meta["title"],
            "publisher": meta["publisher"],
            "url": meta["url"],
            "page_count": page_count,
            "extractable_pages": extractable_pages,
            "skipped_pages": skipped_pages,
            "pct_extractable": round(pct_extractable, 2),
            "is_scan": is_scan,
            "total_chunks": total_chunks,
            "samples": samples
        }
        report.append(entry)
        print(f"{filename}: {page_count} pages, {extractable_pages} extractable ({pct_extractable:.1f}%), {total_chunks} chunks, scan={is_scan}")

    out_file = RESULTS_DIR / "corpus_inventory.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nInventory saved to {out_file}")

if __name__ == "__main__":
    analyze()
