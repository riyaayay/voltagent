#!/usr/bin/env python
"""Construct and validate data/eval sets from real and synthetic facts."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from voltagent.ingestion.loaders import load_pdf

EVAL_DIR = Path("data/eval")
EVAL_DIR.mkdir(parents=True, exist_ok=True)
REAL_DIR = Path("data/raw/real")

# Cache loaded pages for fast validation
_pages_cache: dict[str, list] = {}

def get_page_text(doc_id: str, page_num: int) -> str:
    if doc_id not in _pages_cache:
        pdf_path = REAL_DIR / f"{doc_id}.pdf"
        if not pdf_path.exists():
            pdf_path = Path("data/raw/synthetic") / f"{doc_id}.pdf"
        _pages_cache[doc_id] = load_pdf(str(pdf_path))
    pages = _pages_cache[doc_id]
    match = [p for p in pages if p.page_number == page_num]
    if not match:
        raise ValueError(f"Page {page_num} not found in {doc_id}")
    return match[0].text

def verify_evidence(doc_id: str, page_num: int, evidence: str) -> bool:
    text = get_page_text(doc_id, page_num)
    # Normalize whitespace
    norm_text = " ".join(text.split())
    norm_ev = " ".join(evidence.split())
    return norm_ev in norm_text

print("Loader verification helper ready.")

