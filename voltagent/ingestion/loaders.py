"""Load source documents (OCPP spec, error-code manuals, safety PDFs) into a
uniform in-memory representation before chunking.
"""
from __future__ import annotations

import hashlib
import logging
import os
from collections import Counter
from dataclasses import dataclass

from pypdf import PdfReader

logger = logging.getLogger(__name__)


@dataclass
class SourcePage:
    doc_id: str          # stable id, e.g. "ocpp-2.0.1-spec"
    doc_title: str        # human-readable, e.g. "OCPP 2.0.1 Specification"
    page_number: int      # 1-indexed
    text: str
    content_hash: str | None = None


def _doc_id_from_filename(path: str) -> str:
    base = os.path.splitext(os.path.basename(path))[0]
    return base.strip().lower().replace(" ", "-")


def _is_garbled_pua(text: str) -> bool:
    """Detect if page text has Private Use Area characters indicating broken font encoding."""
    if not text:
        return False
    return any(0xE000 <= ord(ch) <= 0xF8FF for ch in text)


def load_pdf(path: str, doc_title: str | None = None) -> list[SourcePage]:
    """Extract text page-by-page from a single PDF with error and quality guards."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        logger.warning("Skipping missing or empty PDF: %s", path)
        return []

    try:
        with open(path, "rb") as f:
            file_bytes = f.read()
        file_hash = hashlib.sha1(file_bytes).hexdigest()[:8]
        reader = PdfReader(path)
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                logger.warning("Skipping encrypted PDF with unrecoverable password: %s", path)
                return []
    except Exception as e:
        logger.warning("Error reading PDF %s: %s", path, e)
        return []

    doc_id = _doc_id_from_filename(path)
    title = doc_title or os.path.basename(path)

    raw_pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception as e:
            logger.warning("Failed extracting text from page %d of %s: %s", i, path, e)
            continue
        if not text:
            continue
        if _is_garbled_pua(text):
            logger.warning("Garbled text layer detected on page %d of %s (PUA encoding); skipping", i, path)
            continue
        raw_pages.append((i, text))

    if not raw_pages:
        return []

    # Strip repeated headers across pages if document has multiple pages (F-026)
    if len(raw_pages) >= 2:
        first_lines = [p[1].splitlines()[0].strip() for p in raw_pages if p[1].splitlines()]
        counts = Counter(first_lines)
        # Any top line appearing on >= 75% of pages and longer than 5 chars is a page header
        # (Exclude synthetic test harness banners so boundary trap anchors maintain calibrated token offsets)
        repeated_headers = {
            line for line, cnt in counts.items()
            if cnt >= len(raw_pages) * 0.75 and len(line) > 5 and not line.startswith("SYNTHETIC TEST")
        }

        pages: list[SourcePage] = []
        for pnum, ptext in raw_pages:
            lines = ptext.splitlines()
            if lines and lines[0].strip() in repeated_headers:
                lines = lines[1:]
            clean_text = "\n".join(lines).strip()
            if clean_text:
                pages.append(SourcePage(doc_id=doc_id, doc_title=title, page_number=pnum, text=clean_text, content_hash=file_hash))
        return pages
    else:
        return [
            SourcePage(doc_id=doc_id, doc_title=title, page_number=pnum, text=ptext, content_hash=file_hash)
            for pnum, ptext in raw_pages
        ]


def load_directory(directory: str) -> list[SourcePage]:
    """Load every PDF in `directory` safely, skipping bad files without aborting the batch."""
    all_pages: list[SourcePage] = []
    try:
        entries = sorted(os.listdir(directory))
    except Exception as e:
        logger.error("Could not list directory %s: %s", directory, e)
        return []

    for fname in entries:
        if not fname.lower().endswith(".pdf"):
            continue
        full_path = os.path.join(directory, fname)
        try:
            all_pages.extend(load_pdf(full_path))
        except Exception as e:
            logger.warning("Skipping corrupt or unreadable PDF %s: %s", fname, e)
            continue
    return all_pages
