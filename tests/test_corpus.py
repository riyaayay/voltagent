"""Phase 1 verification of the synthetic corpus generator.

- deterministic: two runs, identical hashes
- every manifest anchor is really present on its page (text extracted with the system's own loader)
- every malformed file is malformed in the stated way
- chunker-dependent traps hold when run through the system's own chunker and embedder tokenizer
Generation takes a while, so everything shares two session-scoped runs.
"""
import difflib
import hashlib
import json
import unicodedata
from pathlib import Path

import pytest
from pypdf import PdfReader

from voltagent.ingestion.chunking import chunk_page
from voltagent.ingestion.loaders import load_pdf

pytestmark = pytest.mark.slow
NO_TEXT_LAYER_KINDS = {"image_only_text", "garbled_text_layer"}
# fixtures `corpus_runs` and `corpus` live in conftest.py (shared with the ingestion repro tests)


def _n(s: str) -> str:
    return " ".join(unicodedata.normalize("NFC", s).split())


def _page_texts(pdf: Path) -> list[str]:
    return [_n(p.extract_text() or "") for p in PdfReader(str(pdf)).pages]


# ---- determinism ---------------------------------------------------------------------------
def test_two_runs_have_identical_manifest_and_file_hashes(corpus_runs):
    a, b = corpus_runs
    assert (a / "manifest.json").read_bytes() == (b / "manifest.json").read_bytes()
    files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
    assert files_a == files_b and len(files_a) > 25
    for rel in files_a:
        ha = hashlib.sha256((a / rel).read_bytes()).hexdigest()
        hb = hashlib.sha256((b / rel).read_bytes()).hexdigest()
        assert ha == hb, f"non-deterministic output: {rel}"


def test_manifest_hashes_match_files(corpus):
    for doc in corpus["manifest"]["documents"]:
        assert hashlib.sha256((corpus["raw"] / doc["filename"]).read_bytes()).hexdigest() == doc["sha256"]
    for m in corpus["manifest"]["malformed"]:
        assert hashlib.sha256((corpus["bad"] / m["file"]).read_bytes()).hexdigest() == m["sha256"]


def test_about_twenty_valid_documents_with_distinct_ids(corpus):
    docs = corpus["manifest"]["documents"]
    assert len(docs) == 20 and len({d["doc_id"] for d in docs}) == 20


# ---- valid documents ------------------------------------------------------------------------
def test_every_text_page_carries_the_synthetic_footer_and_page_counts_match(corpus):
    for doc in corpus["manifest"]["documents"]:
        if doc["doc_id"] == "D11":
            continue                                    # image-only: no text layer by design
        texts = _page_texts(corpus["raw"] / doc["filename"])
        assert len(texts) == doc["pages"], doc["doc_id"]
        for i, t in enumerate(texts, 1):
            assert "SYNTHETIC TEST DATA" in t, f"{doc['doc_id']} page {i} lacks the footer"


def test_long_document_has_more_than_150_pages(corpus):
    d13 = next(d for d in corpus["manifest"]["documents"] if d["doc_id"] == "D13")
    assert d13["pages"] >= 150


def test_every_anchor_is_present_on_its_page_in_the_real_pdf(corpus):
    cache: dict[str, list[str]] = {}
    checked = 0
    for a in corpus["manifest"]["anchors"]:
        if a["kind"] in NO_TEXT_LAYER_KINDS:
            continue
        doc = next(d for d in corpus["manifest"]["documents"] if d["doc_id"] == a["doc_id"])
        texts = cache.setdefault(doc["filename"], _page_texts(corpus["raw"] / doc["filename"]))
        assert _n(a["anchor"]) in texts[a["page"] - 1], f"{a['anchor_id']} not found on page {a['page']} of {doc['doc_id']}"
        checked += 1
    assert checked >= 45


def test_scanned_document_has_no_text_layer_but_an_image(corpus):
    pdf = corpus["raw"] / "D11_scanned_homeline_codes.pdf"
    assert _page_texts(pdf) == [""]
    import fitz
    assert len(fitz.open(str(pdf))[0].get_images()) == 1


def test_error_codes_overlap_across_models_with_different_meanings(corpus):
    meanings = {}
    for fname, key in [("D02_voltara_ac7_manual.pdf", "AC-7"), ("D03_voltara_dc60_manual_revC.pdf", "DC-60"),
                       ("D04_zentra_homeline_manual.pdf", "HomeLine")]:
        text = " ".join(_page_texts(corpus["raw"] / fname))
        assert "E-101" in text
        meanings[key] = text
    assert "GroundFailure" in meanings["AC-7"] and "ConnectorLockFailure" in meanings["DC-60"] and "HighTemperature" in meanings["HomeLine"]


def test_superseded_revision_conflicts_with_current(corpus):
    a = {x["anchor_id"]: x["anchor"] for x in corpus["manifest"]["anchors"]}
    assert "10 minutes" in a["A-D03-CAP-WAIT"] and "5 minutes" in a["A-D08-CAP-WAIT"]


def test_near_duplicate_differs_by_exactly_one_number_and_unit(corpus):
    def body(fname):
        lines = []
        for p in PdfReader(str(corpus["raw"] / fname)).pages:
            lines += [ln for ln in (p.extract_text() or "").splitlines() if "SYNTHETIC TEST DATA |" not in ln]
        return " ".join(lines).split()

    w2, w14 = body("D02_voltara_ac7_manual.pdf"), body("D14_voltara_ac7_manual_reprint.pdf")
    changed = set()
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, w2, w14, autojunk=False).get_opcodes():
        if op != "equal":
            changed |= set(w2[i1:i2]) | set(w14[j1:j2])
    assert changed == {"2", "minutes", "20", "seconds"}


def test_contradictory_document_has_both_values(corpus):
    a = {x["anchor_id"]: x["anchor"] for x in corpus["manifest"]["anchors"]}
    assert "30 seconds" in a["A-D15-BODY"] and "60 seconds" in a["A-D15-APPENDIX"]


def test_injection_text_is_present_in_body_cell_and_footnote(corpus):
    kinds = [x["anchor_id"] for x in corpus["manifest"]["anchors"] if x["kind"] == "prompt_injection"]
    assert sorted(kinds) == ["A-D16-BODY", "A-D16-CELL", "A-D16-FOOTNOTE"]


def test_table_spanning_pages_lands_on_a_later_page(corpus):
    a = next(x for x in corpus["manifest"]["anchors"] if x["anchor_id"] == "A-D12-S70")
    assert a["page"] >= 2


# ---- chunker-dependent traps (run through the system's own loader and chunker) --------------
def _chunks(corpus, filename, page):
    pages = [p for p in load_pdf(str(corpus["raw"] / filename)) if p.page_number == page]
    assert pages, f"{filename} page {page} has no extractable text"
    return chunk_page(pages[0])


def _anchor(corpus, aid):
    return next(x for x in corpus["manifest"]["anchors"] if x["anchor_id"] == aid)


def test_boundary_trap_first_chunk_ends_between_number_and_unit(corpus):
    a = _anchor(corpus, "A-D05-BOUNDARY")
    chunks = _chunks(corpus, "D05_ev_safety_compliance.pdf", a["page"])
    assert len(chunks) > 1
    assert _n(chunks[0].text).endswith("Wait 10")


def test_warning_is_split_from_its_value(corpus):
    w = _anchor(corpus, "A-D05-SPLIT-WARNING")
    v = _anchor(corpus, "A-D05-SPLIT-VALUE")
    chunks = _chunks(corpus, "D05_ev_safety_compliance.pdf", v["page"])
    with_value = [c for c in chunks if _n(v["anchor"]) in _n(c.text)]
    assert with_value, "torque value not found in any chunk"
    assert all(_n(w["anchor"]) not in _n(c.text) for c in with_value), "a chunk holds both the warning and the value"
    assert any(_n(w["anchor"]) in _n(c.text) for c in chunks)


def test_late_position_number_is_beyond_the_embedder_window(corpus):
    from transformers import AutoTokenizer
    from voltagent.config import settings
    a = _anchor(corpus, "A-D05-LATE-WAIT")
    chunks = _chunks(corpus, "D05_ev_safety_compliance.pdf", a["page"])
    chunk = next(c for c in chunks if _n(a["anchor"]) in _n(c.text))
    # tokenizer only (not the 1.1 GB model): the embedder's wordpiece offset is all this test needs
    tok = AutoTokenizer.from_pretrained(settings.embedding_model, local_files_only=True)
    before = _n(chunk.text).split(_n(a["anchor"]))[0]
    offset = len(tok(before)["input_ids"])
    assert offset > 128, f"critical number starts at wordpiece {offset}, not past the 128 window"


# ---- malformed files ------------------------------------------------------------------------
def _bad(corpus, name):
    return corpus["bad"] / name


def test_malformed_files_are_all_present(corpus):
    names = {m["file"] for m in corpus["manifest"]["malformed"]}
    assert names == {"M1_zero_byte.pdf", "M2_truncated.pdf", "M3_not_a_pdf.pdf", "M4_password_protected.pdf", "M5_zero_pages.pdf",
                     "M6_huge_image.pdf", "M7_broken_font_encoding.pdf", "duplicate_name/D04_zentra_homeline_manual.pdf"}


def test_m1_is_zero_bytes(corpus):
    assert _bad(corpus, "M1_zero_byte.pdf").stat().st_size == 0


def test_m2_is_truncated_and_not_cleanly_readable(corpus):
    data = _bad(corpus, "M2_truncated.pdf").read_bytes()
    assert data.startswith(b"%PDF") and b"%%EOF" not in data[-64:]
    with pytest.raises(Exception):
        PdfReader(str(_bad(corpus, "M2_truncated.pdf")), strict=True)


def test_m3_is_not_a_pdf(corpus):
    assert not _bad(corpus, "M3_not_a_pdf.pdf").read_bytes().startswith(b"%PDF")


def test_m4_is_encrypted_and_empty_password_fails(corpus):
    r = PdfReader(str(_bad(corpus, "M4_password_protected.pdf")))
    assert r.is_encrypted
    assert r.decrypt("") == 0


def test_m5_has_zero_pages(corpus):
    assert len(PdfReader(str(_bad(corpus, "M5_zero_pages.pdf"))).pages) == 0


def test_m6_declares_a_huge_image(corpus):
    import fitz
    path = _bad(corpus, "M6_huge_image.pdf")
    assert path.stat().st_size < 5_000_000
    width, height = fitz.open(str(path))[0].get_images(full=True)[0][2:4]
    assert width * height >= 400_000_000


def test_m7_text_layer_is_garbled_although_a_layer_exists(corpus):
    truth = next(a for a in corpus["manifest"]["anchors"] if a["anchor_id"] == "A-M7-TRUTH")["anchor"]
    extracted = _n(PdfReader(str(_bad(corpus, "M7_broken_font_encoding.pdf"))).pages[0].extract_text() or "")
    assert extracted, "expected some (garbled) text layer"
    assert "Capacitor" not in extracted and "10 minutes" not in extracted
    assert truth not in extracted


def test_m8_duplicate_name_has_different_content(corpus):
    dup = _bad(corpus, "duplicate_name/D04_zentra_homeline_manual.pdf")
    orig = corpus["raw"] / "D04_zentra_homeline_manual.pdf"
    assert dup.name == orig.name
    assert dup.read_bytes() != orig.read_bytes()
    assert "30 mA" in " ".join(_page_texts(dup)) and "20 mA" in " ".join(_page_texts(orig))
