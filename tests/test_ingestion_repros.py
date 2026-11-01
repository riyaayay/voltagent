"""Ingestion failure regressions against the generated corpus (F-011, F-012, F-025, F-026).
"""
import shutil

import pytest

from voltagent.ingestion.chunking import chunk_pages
from voltagent.ingestion.loaders import load_directory, load_pdf

pytestmark = pytest.mark.slow


def test_bad_file_in_directory_is_skipped_and_good_files_still_load(corpus, tmp_path):
    shutil.copy(corpus["raw"] / "D04_zentra_homeline_manual.pdf", tmp_path)
    shutil.copy(corpus["bad"] / "M1_zero_byte.pdf", tmp_path)

    pages = load_directory(str(tmp_path))

    assert any(p.doc_id.startswith("d04") for p in pages)


def test_same_filename_different_content_does_not_share_chunk_ids(corpus):
    original = chunk_pages(load_pdf(str(corpus["raw"] / "D04_zentra_homeline_manual.pdf")))
    duplicate = chunk_pages(load_pdf(str(corpus["bad"] / "duplicate_name" / "D04_zentra_homeline_manual.pdf")))

    text_by_id = {c.chunk_id: c.text for c in original}
    clashes = [c.chunk_id for c in duplicate if c.chunk_id in text_by_id and text_by_id[c.chunk_id] != c.text]

    assert clashes == []


def test_garbled_text_layer_is_not_loaded_as_indexable_text(corpus):
    pages = load_pdf(str(corpus["bad"] / "M7_broken_font_encoding.pdf"))

    assert not any(0xE000 <= ord(ch) <= 0xF8FF for p in pages for ch in p.text)


def test_repeated_page_header_is_not_part_of_the_chunk_text(corpus):
    pages = load_pdf(str(corpus["raw"] / "D12_two_column_status_tables.pdf"))
    assert len(pages) >= 2

    assert not any("Voltara DC-60 Service Manual - Chapter 4" in p.text for p in pages)
