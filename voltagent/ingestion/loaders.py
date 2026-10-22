"""Load source documents (OCPP spec, error-code manuals, safety PDFs) into a
uniform in-memory representation before chunking.

Kept deliberately dumb: page-by-page text extraction with source metadata
attached to every page, because the whole verification story downstream
depends on being able to point back to *exactly* which document and page a
claim came from.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from pypdf import PdfReader


@dataclass
class SourcePage:
    doc_id: str          # stable id, e.g. "ocpp-2.0.1-spec"
    doc_title: str        # human-readable, e.g. "OCPP 2.0.1 Specification"
    page_number: int      # 1-indexed
    text: str


def _doc_id_from_filename(path: str) -> str:
    base = os.path.splitext(os.path.basename(path))[0]
    return base.strip().lower().replace(" ", "-")


def load_pdf(path: str, doc_title: str | None = None) -> list[SourcePage]:
    """Extract text page-by-page from a single PDF."""
    reader = PdfReader(path)
    doc_id = _doc_id_from_filename(path)
    title = doc_title or os.path.basename(path)

    pages: list[SourcePage] = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue  # skip blank/scanned pages rather than index empty chunks
        pages.append(SourcePage(doc_id=doc_id, doc_title=title, page_number=i, text=text))
    return pages


def load_directory(directory: str) -> list[SourcePage]:
    """Load every PDF in `directory` (non-recursive)."""
    all_pages: list[SourcePage] = []
    for fname in sorted(os.listdir(directory)):
        if not fname.lower().endswith(".pdf"):
            continue
        full_path = os.path.join(directory, fname)
        all_pages.extend(load_pdf(full_path))
    return all_pages
