#!/usr/bin/env python
"""Deterministic synthetic corpus generator (Phase 1).

Writes ~20 valid fictional PDFs (data/raw), 8 deliberately malformed files
(data/raw_malformed) and data/manifest.json describing every document and every planted
fact/trap ("anchor": an exact text snippet on a known page).

Everything is FICTIONAL. Every page footer says SYNTHETIC TEST DATA.
Same --seed and same installed library versions give byte-identical output (checked by
tests/test_corpus.py). Needs no network. Never prints Devanagari (cp1252 consoles crash on it).

Usage:
    .venv/Scripts/python scripts/generate_synthetic_corpus.py --seed 1234
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import fitz  # noqa: E402  (PyMuPDF)
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from reportlab.lib import pdfencrypt  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.utils import simpleSplit  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

import corpus_content as cc  # noqa: E402
from voltagent.config import settings  # noqa: E402
from voltagent.ingestion.chunking import chunk_page  # noqa: E402
from voltagent.ingestion.loaders import SourcePage  # noqa: E402

W, H = A4
DEFAULT_DEVANAGARI_FONT = r"C:\Windows\Fonts\Nirmala.ttc"
UNREVIEWED_LANGS = ("hi", "hinglish")


def norm(s: str) -> str:
    return " ".join(s.split())


class Registry:
    """Collects documents and anchors while the PDFs are written."""

    def __init__(self) -> None:
        self.documents: list[dict] = []
        self.anchors: list[dict] = []
        self.malformed: list[dict] = []


# =============================================================================================
# PDF writer helper (reportlab canvas with simple flow layout)
# =============================================================================================
class PdfDoc:
    def __init__(self, reg: Registry, out_dir: Path, filename: str, doc_id: str, title: str, *,
                 revision: str, date: str, model: str = "", lang: str = "en", purpose: str = "",
                 stresses: list[str] | None = None, font: str = "Helvetica", bold: str = "Helvetica-Bold",
                 columns: int = 1, header: str | None = None, bottom: int = 70, size: int = 10) -> None:
        self.reg, self.doc_id, self.filename = reg, doc_id, filename
        self.title, self.revision, self.date, self.model, self.lang = title, revision, date, model, lang
        self.purpose, self.stresses = purpose, stresses or []
        self.font, self.bold, self.columns, self.header, self.bottom, self.size = font, bold, columns, header, bottom, size
        self.margin, self.gutter = 50, 20
        self.colw = (W - 2 * self.margin - (columns - 1) * self.gutter) / columns
        self.path = out_dir / filename
        out_dir.mkdir(parents=True, exist_ok=True)
        self.c = canvas.Canvas(str(self.path), pagesize=A4, invariant=1, pageCompression=1)
        self.c.setTitle(title)
        self.c.setAuthor("SYNTHETIC TEST DATA")
        self.c.setSubject(doc_id)
        self.c.setCreator("voltagent synthetic corpus generator")
        self.page = 1
        self.page_texts: dict[int, list[str]] = {1: []}
        self.footnotes: dict[int, int] = {}
        self._own_anchors: list[dict] = []
        self._start_page()

    # ---- low level -------------------------------------------------------------------------
    @property
    def x0(self) -> float:
        return self.margin + self.col * (self.colw + self.gutter)

    def _draw(self, x: float, y: float, s: str, size: float | None = None, font: str | None = None,
              right: bool = False) -> None:
        self.c.setFont(font or self.font, size or self.size)
        (self.c.drawRightString if right else self.c.drawString)(x, y, s)
        self.page_texts[self.page].append(s)

    def _start_page(self) -> None:
        if self.header:
            self._draw(self.margin, H - 40, self.header, size=8)
        footer = f"SYNTHETIC TEST DATA | {self.doc_id} | Rev {self.revision} | {self.date}"
        self._draw(self.margin, 30, footer, size=8)
        self._draw(W - self.margin, 30, f"Page {self.page}", size=8, right=True)
        self.y = H - 70
        self.col = 0

    def _next_column_or_page(self) -> None:
        if self.col + 1 < self.columns:
            self.col += 1
            self.y = H - 70
        else:
            self.c.showPage()
            self.page += 1
            self.page_texts[self.page] = []
            self._start_page()

    def new_page(self) -> None:
        self.c.showPage()
        self.page += 1
        self.page_texts[self.page] = []
        self._start_page()

    def mark(self, mark: tuple | None) -> None:
        if not mark:
            return
        anchor_id, kind, anchor, note = mark
        # Hindi/Hinglish text was written by the assistant and is NOT reviewed by a native speaker:
        # it must not be used as ground truth for golden labels until the owner clears it.
        unreviewed = self.lang in UNREVIEWED_LANGS
        self._own_anchors.append(dict(anchor_id=anchor_id, doc_id=self.doc_id, page=self.page,
                                      kind=kind, anchor=anchor, note=note, lang=self.lang,
                                      review_status="unreviewed" if unreviewed else "n/a",
                                      usable_as_ground_truth=not unreviewed))

    # ---- flow content ----------------------------------------------------------------------
    def para(self, text: str, *, size: int | None = None, font: str | None = None,
             mark: tuple | None = None, after: int = 6) -> None:
        size = size or self.size
        font = font or self.font
        lead = size + 3
        lines = simpleSplit(text, font, size, self.colw)
        full = H - 70 - self.bottom
        if len(lines) * lead <= full and self.y - len(lines) * lead < self.bottom:
            self._next_column_or_page()          # keep a short paragraph on one page/column
        self.mark(mark)                          # page is final for a kept-together paragraph
        for ln in lines:
            if self.y - lead < self.bottom:
                self._next_column_or_page()
            self.y -= lead
            self._draw(self.x0, self.y, ln, size=size, font=font)
        self.y -= after

    def heading(self, text: str, size: int = 13) -> None:
        self.para(text, size=size, font=self.bold, after=8)

    def bullets(self, items: list[str]) -> None:
        for it in items:
            self.para("- " + it, after=3)

    def table(self, header: list[str], rows: list[list[str]], widths: list[float], *, size: int = 8,
              repeat_header: bool = True, marks: dict[int, tuple] | None = None) -> None:
        assert sum(widths) <= self.colw + 0.5, f"table too wide for column: {sum(widths)} > {self.colw}"
        marks = marks or {}
        lead = size + 2.5

        def draw_row(row: list[str], bold: bool = False) -> None:
            cells = [simpleSplit(str(cell), self.bold if bold else self.font, size, w - 6) or [""]
                     for cell, w in zip(row, widths)]
            h = max(len(c) for c in cells) * lead + 6
            if self.y - h < self.bottom:
                self._next_column_or_page()
                if repeat_header and not bold:
                    draw_row(header, bold=True)
            x = self.x0
            for lines, w in zip(cells, widths):
                self.c.rect(x, self.y - h, w, h, stroke=1, fill=0)
                ty = self.y - 3 - size
                for ln in lines:
                    self._draw(x + 3, ty, ln, size=size, font=self.bold if bold else self.font)
                    ty -= lead
                x += w
            self.y -= h

        draw_row(header, bold=True)
        for i, row in enumerate(rows):
            if i in marks:
                # make sure the mark records the page the row really lands on
                probe_h = max(len(simpleSplit(str(c), self.font, size, w - 6)) or 1
                              for c, w in zip(row, widths)) * lead + 6
                if self.y - probe_h < self.bottom:
                    self._next_column_or_page()
                    if repeat_header:
                        draw_row(header, bold=True)
                self.mark(marks[i])
            draw_row(row)
        self.y -= 8

    def merged_table(self, col_w: list[float], row_h: list[float], cells: list[tuple], size: int = 8) -> None:
        """cells: (row, col, rowspan, colspan, text, rotated, mark)"""
        total_h = sum(row_h)
        if self.y - total_h < self.bottom:
            self._next_column_or_page()
        x0, y_top = self.x0, self.y
        for r, c, rs, cs, text, rotated, mk in cells:
            x = x0 + sum(col_w[:c])
            w = sum(col_w[c:c + cs])
            h = sum(row_h[r:r + rs])
            ytop = y_top - sum(row_h[:r])
            self.c.rect(x, ytop - h, w, h, stroke=1, fill=0)
            self.mark(mk)
            if rotated:
                self.c.saveState()
                self.c.setFont(self.bold, size)
                self.c.translate(x + w / 2 + size / 2 - 1, ytop - h + 4)
                self.c.rotate(90)
                self.c.drawString(0, 0, text)
                self.c.restoreState()
                self.page_texts[self.page].append(text)
            else:
                ty = ytop - 3 - size
                for ln in simpleSplit(text, self.font, size, w - 6) or [""]:
                    self._draw(x + 3, ty, ln, size=size)
                    ty -= size + 2.5
        self.y -= total_h + 8

    def footnote(self, text: str) -> None:
        i = self.footnotes.get(self.page, 0)
        self.footnotes[self.page] = i + 1
        self._draw(self.margin, 58 + 9 * i, text, size=7)

    # ---- finish ----------------------------------------------------------------------------
    def finish(self) -> Path:
        self.c.save()
        for a in self._own_anchors:
            page_text = norm(" ".join(self.page_texts[a["page"]]))
            assert norm(a["anchor"]) in page_text, f"{a['anchor_id']}: anchor not on page {a['page']} of {self.doc_id}"
            self.reg.anchors.append(a)
        self.reg.documents.append(dict(
            doc_id=self.doc_id, filename=self.filename, title=self.title, revision=self.revision,
            date=self.date, model=self.model, lang=self.lang, pages=self.page, purpose=self.purpose,
            stresses=self.stresses, sha256=sha256_file(self.path),
            text_review_status="unreviewed" if self.lang in UNREVIEWED_LANGS else "n/a"))
        return self.path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def error_rows(errors: dict) -> list[list[str]]:
    return [[code, enum, meaning, action] for code, (enum, meaning, action) in errors.items()]


ERR_HDR = ["Code", "Name", "Meaning", "Action"]
ERR_W = [38, 92, 160, 205]


# =============================================================================================
# Valid documents
# =============================================================================================
def d01_protocol(reg, out, rng):
    d = PdfDoc(reg, out, "D01_protocol_spec_excerpt.pdf", "D01", "Fictional Charger Interface Protocol (FIC) excerpt",
               revision="1.2", date="2024-06-01", purpose="Protocol message flows, enums, requirement ids, state tables",
               stresses=["requirement ids", "enums", "state-transition table"])
    d.heading("FIC 1.2 - Station Management Messages (fictional excerpt)")
    d.para("This excerpt describes messages exchanged between a charging station and its management system. "
           "It is a fictional protocol that imitates the vocabulary of real charger protocols.")
    d.heading("1. StatusNotification", 11)
    d.para("FIC-101 The station SHALL send a StatusNotification message within 5 seconds after any change of ConnectorStatus.",
           mark=("A-D01-FIC101", "fact", "within 5 seconds after any change of ConnectorStatus", "FIC-101"))
    d.para("FIC-102 A StatusNotification SHALL carry the connector identifier, the ConnectorStatus and, when the status is Faulted, an ErrorCode.")
    d.table(["ConnectorStatus", "Meaning"], [
        ["Available", "No vehicle connected; ready for a new session."],
        ["Occupied", "A vehicle is connected or a session is active."],
        ["Reserved", "Held for a specific user until the reservation ends."],
        ["Unavailable", "Out of service by operator request (see ChangeAvailability)."],
        ["Faulted", "A fault is active; an ErrorCode SHALL be reported."]], [120, 375])
    d.table(["ErrorCode", "Meaning"], [
        ["NoError", "No fault active."], ["GroundFailure", "Leakage to protective earth detected."],
        ["OverCurrentFailure", "Output current above the permitted limit."],
        ["ConnectorLockFailure", "The connector lock could not lock or unlock."],
        ["EVCommunicationError", "Communication with the vehicle failed."],
        ["PowerMeterFailure", "The energy meter failed."], ["HighTemperature", "A temperature limit was exceeded."],
        ["OtherError", "Any other fault; details in the vendor field."]], [140, 355])
    d.heading("2. Reset and ChangeAvailability", 11)
    d.para("FIC-210 A station that receives a Reset request of type Immediate SHALL end all transactions and restart within 60 seconds.",
           mark=("A-D01-FIC210", "fact", "restart within 60 seconds", "FIC-210"))
    d.para("FIC-220 A station that receives a Reset request of type OnIdle SHALL restart only after the last transaction has ended.")
    d.para("FIC-230 A ChangeAvailability request to Unavailable SHALL be accepted immediately when idle, and scheduled when a transaction is active.")
    d.heading("3. TransactionEvent", 11)
    d.para("FIC-240 The station SHALL send a TransactionEvent of type Started when charging begins, Updated at the configured interval, and Ended when the session ends.")
    d.table(["From", "Trigger", "To"], [
        ["Available", "vehicle plugged in", "Occupied"], ["Occupied", "session ended and cable removed", "Available"],
        ["Available", "fault detected", "Faulted"], ["Occupied", "fault detected", "Faulted"],
        ["Faulted", "fault cleared", "Available"], ["Available", "ChangeAvailability Unavailable", "Unavailable"]], [150, 245, 100])
    d.finish()


def ac7_manual(reg, out, doc_id, filename, iso_wait, date, rng):
    d = PdfDoc(reg, out, filename, doc_id, f"{cc.AC7} Installation and Service Manual", revision="B", date=date, model="AC-7",
               purpose="AC-7 specs, error codes, ground-fault procedure",
               stresses=["error codes overlap across models"] + (["near-duplicate with one number changed"] if doc_id == "D14" else []))
    d.heading(f"{cc.AC7} 7.4 kW AC wallbox - Installation and Service Manual")
    d.para("Rated power 7.4 kW, 230 V single phase, rated current 32 A, enclosure rating IP54. Fictional product.")
    d.table(["Parameter", "Value"], [["Rated power", "7.4 kW"], ["Supply", "230 V AC, single phase"],
                                      ["Rated current", "32 A"], ["Ground-fault trip", "30 mA"], ["Enclosure", "IP54"]], [200, 295])
    d.heading("Error codes", 11)
    d.table(ERR_HDR, error_rows(cc.AC7_ERRORS), ERR_W,
            marks={0: ("A-%s-E101" % doc_id, "fact", "E-101", f"{cc.AC7} E-101 GroundFailure")})
    d.heading("Ground failure procedure (E-101)", 11)
    d.para("1. Switch off breaker Q1 at the supply panel and apply your lock and tag.")
    d.para(f"2. Wait {iso_wait} before touching any conductor.",
           mark=("A-%s-ISO-WAIT" % doc_id, "fact", f"Wait {iso_wait} before touching any conductor",
                 "AC-7 isolation wait before touching conductors"))
    d.para("3. Measure protective earth continuity; it must be below 0.3 ohm.")
    d.para("4. Re-energise only after the cause of the leakage has been found and corrected.")
    d.para(cc.filler_words(random.Random(77), 90))      # identical in D02 and D14 on purpose (fixed seed)
    d.finish()


def d03_dc60_revC(reg, out, rng):
    d = PdfDoc(reg, out, "D03_voltara_dc60_manual_revC.pdf", "D03", f"{cc.DC60} Service Manual Rev C", revision="C",
               date="2024-11-01", model="DC-60", purpose="Current DC-60 manual", stresses=["error codes overlap", "revision"])
    d.heading(f"{cc.DC60} 60 kW DC fast charger - Service Manual (Rev C, current)")
    d.para("Rated power 60 kW, DC output 200 to 500 V, maximum 150 A. Fictional product.")
    d.heading("Error codes", 11)
    d.table(ERR_HDR, error_rows(cc.DC60_ERRORS), ERR_W,
            marks={0: ("A-D03-E101", "fact", "E-101", f"{cc.DC60} E-101 ConnectorLockFailure")})
    d.heading("Capacitor discharge (Rev C)", 11)
    d.para(f"After isolating the DC bus, wait {cc.DC60_CAP_WAIT_REV_C} before opening the power cabinet. "
           "Verify that the bus voltage is below 50 V with a CAT III meter.",
           mark=("A-D03-CAP-WAIT", "fact", f"wait {cc.DC60_CAP_WAIT_REV_C} before opening the power cabinet",
                 "DC-60 Rev C discharge wait"))
    d.para(f"Tighten the DC busbar bolts to {cc.DC60_TORQUE_REV_C}.",
           mark=("A-D03-TORQUE", "fact", f"busbar bolts to {cc.DC60_TORQUE_REV_C}", "DC-60 Rev C busbar torque"))
    d.para("Supersedes Rev A (2023-03-01). Rev A values must not be used.")
    d.finish()


def d04_homeline(reg, out, rng, filename="D04_zentra_homeline_manual.pdf", leak="20 mA", out_dir=None, doc_id="D04",
                 stress=None):
    errors = dict(cc.HL_ERRORS)
    errors["E-102"] = (errors["E-102"][0], f"Leakage current above {leak}.", errors["E-102"][2])
    d = PdfDoc(reg, out_dir or out, filename, doc_id, f"{cc.HL} 3.3 kW Owner and Service Guide", revision="A",
               date="2024-02-10", model="HomeLine", purpose="HomeLine specs and error codes",
               stresses=stress or ["error codes overlap"])
    d.heading(f"{cc.HL} 3.3 kW home charger - Guide")
    d.para("Rated power 3.3 kW, 230 V, 16 A. For indoor and sheltered outdoor use. Fictional product.")
    d.heading("Error codes", 11)
    d.table(ERR_HDR, error_rows(errors), ERR_W,
            marks={0: ("A-%s-E101" % doc_id, "fact", "E-101", f"{cc.HL} E-101 HighTemperature")})
    d.para(cc.filler_words(random.Random(88), 60))
    return d


def d05_safety(reg, out, rng):
    d = PdfDoc(reg, out, "D05_ev_safety_compliance.pdf", "D05", "EV Charger Service Safety and Compliance Guide", revision="3",
               date="2024-08-15", purpose="Isolation/LOTO, PPE, discharge waits, torque; late-position and chunk-boundary traps",
               stresses=["exact numbers with units", "late-position number (F-022)", "warning split from procedure",
                         "number split from unit at chunk boundary"])
    d.heading("Isolation and lock-out/tag-out (LOTO) procedure")
    for i, s in enumerate([
            "Announce the work to the site manager and identify the station by its label.",
            "Stop any active session and remove the vehicle connector.",
            "Open the upstream breaker and apply your personal lock and tag.",
            "Prove the circuit dead with a rated meter; test the meter on a known live source before and after.",
            "Wait for the discharge time listed for the model before opening any cabinet.",
            "Verify that the bus voltage is below 50 V.",
            "Only then open the enclosure; never work on a live station alone.",
            "Remove the lock and tag only yourself, after the work is complete."], 1):
        d.para(f"{i}. {s}")
    d.heading("Personal protective equipment", 11)
    d.table(["Item", "Rating"], [["Insulating gloves", "Class 0, rated 1000 V AC"], ["Face shield", "Arc rated, 8 cal/cm2"],
                                  ["Safety footwear", "Electrical hazard rated, 600 V"], ["Meter", "CAT III 1000 V"]], [200, 295],
            marks={0: ("A-D05-GLOVES", "fact", "Class 0, rated 1000 V AC", "PPE gloves rating")})
    d.heading("Discharge waits by model", 11)
    d.table(["Model", "Wait after isolation", "Bus voltage limit"], [
        ["Voltara AC-7", cc.AC7_ISO_WAIT, "below 50 V"], ["Zentra HomeLine", "1 minute", "below 50 V"],
        ["Voltara DC-60 (Rev C)", cc.DC60_CAP_WAIT_REV_C, "below 50 V"]], [180, 180, 135],
            marks={2: ("A-D05-WAIT-TABLE-DC60", "fact", f"{cc.DC60_CAP_WAIT_REV_C}", "DC-60 wait in safety table")})

    # --- late-position trap: the critical number sits AFTER the first ~128 wordpieces of its chunk
    d.new_page()
    d.heading("Cabinet access - DC-60 (read the whole page)")
    d.para(cc.filler_words(random.Random(seed_of(rng, "late")), 170))
    d.para(f"WARNING: after isolation, wait {cc.DC60_CAP_WAIT_REV_C} before opening the DC-60 power cabinet. "
           "Do not open it earlier.",
           mark=("A-D05-LATE-WAIT", "late_position_number",
                 f"wait {cc.DC60_CAP_WAIT_REV_C} before opening the DC-60 power cabinet",
                 "critical number placed after the embedder window (F-022); page is a single chunk"))

    # --- warning split from the procedure: WARNING at the top, the torque value in a later chunk
    d.new_page()
    d.para("WARNING: Do NOT energise the busbar until every bolt has been torqued to specification.",
           mark=("A-D05-SPLIT-WARNING", "warning_split_from_value", "Do NOT energise the busbar",
                 "warning is in the first chunk of this page, the torque value only in the second"))
    d.para(cc.filler_words(random.Random(seed_of(rng, "split")), 330))
    d.para("Torque specification: DC-60 busbar bolts, 15 Nm, checked with a calibrated wrench.",
           mark=("A-D05-SPLIT-VALUE", "warning_split_from_value", "busbar bolts, 15 Nm",
                 "torque value; the warning above is NOT in the chunk that contains this value"))

    # --- number split from its unit at a chunk boundary
    d.new_page()
    d.heading("Cabinet access - AC-7 wallbox")
    text, k = boundary_text(rng)
    d.para(text, mark=("A-D05-BOUNDARY", "chunk_boundary_number_unit", "Wait 10 minutes before opening the power cabinet",
                       f"first chunk of this page ends right after 'Wait 10' (pad={k})"))
    d.finish()


def seed_of(rng: random.Random, salt: str) -> int:
    return int(hashlib.sha256(f"{rng.random()}-{salt}".encode()).hexdigest()[:8], 16)


def boundary_text(rng: random.Random) -> tuple[str, int]:
    """Search a padding length so the system's OWN loader + chunker end the first chunk right after 'Wait 10'.

    The text is probed through a throwaway one-page PDF with the same footer and heading as the real
    page, because the loader sees footer/heading text in front of the paragraph and that shifts
    the token positions.
    """
    import tempfile
    from voltagent.ingestion.loaders import load_pdf

    base = cc.filler_words(random.Random(5150), 140)
    tail = cc.filler_words(random.Random(5151), 160)

    def first_chunk_ends_after_wait_10(text: str) -> bool:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            probe = PdfDoc(Registry(), Path(td), "probe.pdf", "D05", "probe", revision="3", date="2024-08-15")
            probe.heading("Cabinet access - AC-7 wallbox")
            probe.para(text)
            probe.c.save()
            pages = load_pdf(str(Path(td) / "probe.pdf"))
        chunks = chunk_page(pages[0])
        return len(chunks) > 1 and norm(chunks[0].text).endswith("Wait 10")

    for k in range(0, 200):
        pad = ("Inspection status: " + "ok " * k).strip() + "."
        text = f"{base} {pad} Wait 10 minutes before opening the power cabinet. {tail}"
        if first_chunk_ends_after_wait_10(text):
            return text, k
    raise RuntimeError("could not align a chunk boundary between '10' and 'minutes'; chunker settings changed?")


def d06_firmware(reg, out, rng):
    d = PdfDoc(reg, out, "D06_firmware_release_notes.pdf", "D06", "Voltara firmware release notes", revision="2.0", date="2024-09-30",
               purpose="Behaviour differs by firmware version", stresses=["version-dependent answers"])
    d.heading("Voltara firmware release notes (AC-7 and DC-60)")
    d.table(["Version", "Date", "Change"], [
        ["1.2.0", "2023-05-02", "E-104 EVCommunicationError: the station retries 3 times before faulting."],
        ["1.3.0", "2023-11-20", "Automatic reset after GroundFailure (E-101 on AC-7) removed; a manual reset is now required."],
        ["2.0.0", "2024-09-30", "E-104 EVCommunicationError: the station retries 5 times before faulting. StatusNotification sent within 5 seconds."]],
            [50, 70, 375],
            marks={0: ("A-D06-RETRY-OLD", "fact", "retries 3 times", "firmware 1.2.0 retry count"),
                   2: ("A-D06-RETRY-NEW", "fact", "retries 5 times", "firmware 2.0.0 retry count")})
    d.para(cc.filler_words(rng, 60))
    d.finish()


def d07_trees(reg, out, rng):
    d = PdfDoc(reg, out, "D07_troubleshooting_trees.pdf", "D07", "Troubleshooting decision trees", revision="1", date="2024-07-01",
               purpose="Decision trees as step tables", stresses=["procedural multi-step", "tables"])
    d.heading("Station does not start charging (AC-7)")
    d.table(["Step", "Check", "If yes", "If no"], [
        ["1", "Is the status indicator lit?", "Go to step 2", "Check supply breaker Q1 and the 230 V supply"],
        ["2", "Is an error code shown?", "Look up the code in the AC-7 manual", "Go to step 3"],
        ["3", "Does the vehicle accept the connector?", "Go to step 4", "Test the connector lock (E-103)"],
        ["4", "Does a second vehicle charge?", "Fault is in the first vehicle", "Replace the control board"]],
            [35, 160, 150, 150],
            marks={2: ("A-D07-STEP3", "fact", "Test the connector lock (E-103)", "AC-7 tree step 3")})
    d.heading("Fast charger derates (DC-60)", 11)
    d.table(["Step", "Check", "If yes", "If no"], [
        ["1", "Is E-106 active?", "Clean the air filter, check both fans", "Go to step 2"],
        ["2", "Is the ambient temperature high?", "Wait for cooling; output recovers by itself", "Inspect the power module"]], [35, 160, 150, 150])
    d.finish()


def dc60_revA(reg, out, rng):
    d = PdfDoc(reg, out, "D08_voltara_dc60_manual_revA_superseded.pdf", "D08", f"{cc.DC60} Service Manual Rev A", revision="A",
               date="2023-03-01", model="DC-60", purpose="SUPERSEDED DC-60 manual that conflicts with Rev C",
               stresses=["superseded revision", "conflicting sources"])
    d.heading(f"{cc.DC60} 60 kW DC fast charger - Service Manual (Rev A)")
    d.para("Rated power 60 kW, DC output 200 to 500 V, maximum 150 A. Fictional product.")
    d.heading("Capacitor discharge (Rev A)", 11)
    d.para(f"After isolating the DC bus, wait {cc.DC60_CAP_WAIT_REV_A} before opening the power cabinet.",
           mark=("A-D08-CAP-WAIT", "conflicting_revision", f"wait {cc.DC60_CAP_WAIT_REV_A} before opening the power cabinet",
                 "Rev A value; Rev C (D03) says 10 minutes"))
    d.para(f"Tighten the DC busbar bolts to {cc.DC60_TORQUE_REV_A}.",
           mark=("A-D08-TORQUE", "conflicting_revision", f"busbar bolts to {cc.DC60_TORQUE_REV_A}", "Rev A torque; Rev C says 15 Nm"))
    d.para("Revision A. Later revisions may change these values.")
    d.finish()


def register_devanagari(font_path: str) -> None:
    if not Path(font_path).exists():
        raise SystemExit(f"Devanagari font not found: {font_path} (pass --devanagari-font)")
    pdfmetrics.registerFont(TTFont("Nirmala", font_path, subfontIndex=0))


def d09_hindi(reg, out, rng):
    d = PdfDoc(reg, out, "D09_hindi_field_guide_ac7.pdf", "D09", "Voltara AC-7 Hindi field guide", revision="1", date="2024-04-01",
               model="AC-7", lang="hi", font="Nirmala", bold="Nirmala", purpose="Hindi (Devanagari) field guide for AC-7",
               stresses=["Devanagari", "Devanagari numerals", "cross-lingual with English D02"])
    d.para(cc.HINDI_TITLE, size=14)
    for text, aid, anchor, kind in cc.HINDI_LINES:
        d.para(text, mark=(aid, kind, anchor, "Hindi line; English counterpart in D02"), after=8)
    d.finish()


def d10_hinglish(reg, out, rng):
    d = PdfDoc(reg, out, "D10_hinglish_quick_reference.pdf", "D10", "Hinglish quick-reference card", revision="1", date="2024-04-15",
               lang="hinglish", font="Nirmala", bold="Nirmala", purpose="Code-mixed Hindi-English card with transliterated codes",
               stresses=["code-mixed", "transliterated codes", "spoken codes"])
    d.para("Quick reference card - AC-7 aur DC-60", size=13)
    for text, aid, anchor, kind in cc.HINGLISH_LINES:
        d.para(text, mark=(aid, kind, anchor, "Hinglish line"), after=8)
    d.finish()


def d11_scanned(reg, out, rng_seed):
    """Image-only PDF: a rasterised, skewed, noisy page holding a HomeLine error-code table."""
    name, doc_id = "D11_scanned_homeline_codes.pdf", "D11"
    tmp = io.BytesIO()
    c = canvas.Canvas(tmp, pagesize=A4, invariant=1)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(60, 780, "Zentra HomeLine - error code table (scanned copy)")
    c.setFont("Helvetica", 11)
    truth = []
    y = 740
    for code, (enum, meaning, action) in cc.HL_ERRORS.items():
        line = f"{code}  {enum}: {meaning}"
        c.drawString(60, y, line)
        truth.append(line)
        y -= 26
    c.setFont("Helvetica", 8)
    c.drawString(60, 30, "SYNTHETIC TEST DATA | D11 | Rev A | 2024-02-10")
    c.save()
    pix = fitz.open(stream=tmp.getvalue(), filetype="pdf")[0].get_pixmap(dpi=150)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
    nrng = np.random.default_rng(rng_seed)
    img = img.rotate(float(nrng.uniform(-2.0, 2.0)), resample=Image.Resampling.BICUBIC, expand=True, fillcolor=255)
    arr = np.asarray(img, dtype=np.float32) + nrng.normal(0, 14, (img.height, img.width))
    speck = nrng.random((img.height, img.width)) < 0.002
    arr[speck] = 0
    noisy = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))   # 2-D uint8 -> mode L
    png = io.BytesIO()
    noisy.save(png, format="PNG", compress_level=6)
    doc = fitz.open()
    page = doc.new_page(width=W, height=H)
    page.insert_image(fitz.Rect(0, 0, W, H), stream=png.getvalue())
    doc.set_metadata({"title": "Scanned HomeLine codes", "author": "SYNTHETIC TEST DATA", "producer": "", "creator": "",
                      "creationDate": "", "modDate": "", "subject": doc_id, "keywords": ""})
    path = out / name
    out.mkdir(parents=True, exist_ok=True)
    doc.save(str(path), garbage=4, deflate=True, no_new_id=True)
    reg.documents.append(dict(doc_id=doc_id, filename=name, title="Scanned HomeLine codes", revision="A", date="2024-02-10",
                              model="HomeLine", lang="en", pages=1, purpose="Image-only scan with an error-code table",
                              stresses=["scanned / OCR path", "skew", "noise"], sha256=sha256_file(path),
                              text_review_status="n/a"))
    reg.anchors.append(dict(anchor_id="A-D11-IMAGE-TEXT", doc_id=doc_id, page=1, kind="image_only_text",
                            anchor=truth[0], note="Text exists ONLY inside the image (no text layer). Ground truth of the image: "
                            + " | ".join(truth), lang="en", review_status="n/a", usable_as_ground_truth=True))


def d12_twocol(reg, out, rng):
    d = PdfDoc(reg, out, "D12_two_column_status_tables.pdf", "D12", "DC-60 status and fault tables (two-column layout)", revision="C",
               date="2024-11-01", model="DC-60", columns=2, bottom=100, size=9,
               header="Voltara DC-60 Service Manual - Chapter 4 - Status and Faults - CONFIDENTIAL FICTIONAL",
               purpose="Two columns, table spanning pages, footnotes, repeated header/footer",
               stresses=["multi-column reading order", "table spanning pages", "headers/footers on every page", "footnotes"])
    d.heading("4.1 Status behaviour")
    d.para(cc.filler_words(random.Random(seed_of(rng, "d12a")), 120))
    rows = []
    for i in range(1, 91):
        rows.append([f"S{i:02d}", f"Condition {i}", "Faulted" if i % 3 == 0 else "Occupied",
                     f"{(i * 7) % 90 + 10} s"])
    rows[69] = ["S70", "Output contactor welded", "Faulted", "0 s"]
    d.table(["Id", "Condition", "Status", "Delay"], rows, [30, 95, 60, 50],
            marks={69: ("A-D12-S70", "table_spanning_pages", "Output contactor welded",
                        "row on a later page than the table start; the header row repeats on each column/page")})
    d.footnote("1) Delay values apply to firmware 2.0.0 and later.")
    d.heading("4.2 Notes")
    d.para(cc.filler_words(random.Random(seed_of(rng, "d12b")), 160))
    d.finish()


def d13_long(reg, out, rng):
    d = PdfDoc(reg, out, "D13_fleet_maintenance_logbook.pdf", "D13", "Fleet maintenance logbook template", revision="1",
               date="2024-01-15", purpose="152-page repetitive boilerplate with 3 needle facts", stresses=["scale", "chunk explosion"])
    needles = {37: "The DC-60 air filter service interval is 6 months.",
               91: "The AC-7 fan inspection interval is 12 months.",
               143: "The HomeLine seal replacement interval is 24 months."}
    for p in range(1, 153):
        d.heading(f"Section {p}: scheduled inspection record", 12)
        r = random.Random(1000 + p)
        d.para(cc.filler_words(r, 100))
        if p in needles:
            d.para(needles[p], mark=(f"A-D13-NEEDLE-P{p}", "needle_in_long_doc", needles[p], "unique fact in a very long document"))
        d.table(["Item", "Check", "Result"], [[f"{p}.{i}", "Inspect and record", ""] for i in range(1, 6)], [60, 300, 135])
        if p < 152:
            d.new_page()
    d.finish()


def d15_contradictory(reg, out, rng):
    d = PdfDoc(reg, out, "D15_internally_contradictory.pdf", "D15", "Voltara AC-7 connector unlock behaviour", revision="1",
               date="2024-05-05", model="AC-7", purpose="Body says 30 s, appendix says 60 s", stresses=["internal contradiction"])
    d.heading("Connector unlock timeout")
    d.para("After a session ends the AC-7 keeps the connector locked until the unlock timeout of 30 seconds has elapsed.",
           mark=("A-D15-BODY", "internal_contradiction", "unlock timeout of 30 seconds", "body says 30 s; appendix says 60 s"))
    d.para(cc.filler_words(rng, 120))
    d.new_page()
    d.heading("Appendix A - Parameter summary")
    d.table(["Parameter", "Value"], [["Unlock timeout", "60 seconds"], ["Lock confirm timeout", "5 seconds"]], [250, 245],
            marks={0: ("A-D15-APPENDIX", "internal_contradiction", "Unlock timeout 60 seconds",
                       "appendix says 60 s; body says 30 s")})
    d.finish()


def d16_injection(reg, out, rng):
    d = PdfDoc(reg, out, "D16_ac7_quick_tips_injection.pdf", "D16", "AC-7 quick tips", revision="1", date="2024-06-20", model="AC-7",
               purpose="Prompt-injection text in body, a table cell and a footnote", stresses=["prompt injection from documents"])
    d.heading("AC-7 quick tips")
    d.para("Keep the service log up to date. " + cc.INJECTION_TEXT + " Report unusual noise immediately.",
           mark=("A-D16-BODY", "prompt_injection", cc.INJECTION_TEXT, "injection in body text"))
    d.table(["Tip", "Detail"], [["Cleaning", "Use a dry cloth."],
                                ["Safety", cc.INJECTION_TEXT]], [150, 345],
            marks={1: ("A-D16-CELL", "prompt_injection", cc.INJECTION_TEXT, "injection in a table cell")})
    d.footnote("Note: " + cc.INJECTION_TEXT)
    d.mark(("A-D16-FOOTNOTE", "prompt_injection", "Note: " + cc.INJECTION_TEXT, "injection in a footnote"))
    d.finish()


def d17_lookalikes(reg, out, rng):
    d = PdfDoc(reg, out, "D17_lookalike_codes.pdf", "D17", "Zentra lookalike code reference", revision="1", date="2024-03-03", model="HomeLine",
               purpose="E-014 / E-041 / E-0140 / E-14H / E-O14 / E-l14", stresses=["lookalike codes", "O vs 0", "l vs 1"])
    d.heading("Service codes (HomeLine service menu)")
    rows = [["E-014", "Relay stuck closed"], ["E-041", "Supply voltage low"], ["E-0140", "Display board fault"],
            ["E-14H", "Humidity sensor fault"], ["E-O14", "Letter O variant: legacy display glitch"],
            ["E-l14", "Lowercase L variant: legacy log entry"]]
    d.table(["Code", "Meaning"], rows, [120, 375],
            marks={0: ("A-D17-E014", "lookalike_code", "E-014", "E-014 relay stuck closed"),
                   1: ("A-D17-E041", "lookalike_code", "E-041", "E-041 supply voltage low"),
                   2: ("A-D17-E0140", "lookalike_code", "E-0140", "E-0140 display board"),
                   3: ("A-D17-E14H", "lookalike_code", "E-14H", "E-14H humidity sensor"),
                   4: ("A-D17-EO14", "lookalike_code", "E-O14", "letter O, not zero"),
                   5: ("A-D17-El14", "lookalike_code", "E-l14", "lowercase L, not one")})
    d.finish()


def d18_units(reg, out, rng):
    d = PdfDoc(reg, out, "D18_unit_heavy_specs.pdf", "D18", "Voltara unit-sensitive specifications", revision="1", date="2024-03-20",
               purpose="mA vs A, V vs kV, degC vs degF, ms vs s, kW vs kWh", stresses=["units"])
    d.heading("Specifications where the unit matters")
    d.para("The ground-fault trip threshold is 30 mA. A current of 30 A would be a short circuit, not a leakage.",
           mark=("A-D18-MA", "unit_critical", "trip threshold is 30 mA", "mA not A"))
    d.para("The DC output is rated up to 0.5 kV, which is 500 V.", mark=("A-D18-KV", "unit_critical", "up to 0.5 kV", "kV vs V"))
    d.para("The shutdown temperature is 85 \u00b0C (185 \u00b0F).", mark=("A-D18-TEMP", "unit_critical", "85 \u00b0C (185 \u00b0F)", "degC vs degF"))
    d.para("The overcurrent delay is 100 ms; a delay of 100 s would be unsafe.", mark=("A-D18-MS", "unit_critical", "delay is 100 ms", "ms vs s"))
    d.para("The charger delivers 60 kW of power; a session of one hour delivers up to 60 kWh of energy.",
           mark=("A-D18-KW", "unit_critical", "delivers 60 kW of power", "kW vs kWh"))
    d.finish()


def d19_tableonly(reg, out, rng):
    d = PdfDoc(reg, out, "D19_parameter_matrix.pdf", "D19", "Parameter matrix", revision="1", date="2024-04-20",
               purpose="Table only, merged cells, rotated header", stresses=["merged cells", "rotated header", "no prose"])
    col_w = [120, 120, 120, 120]
    row_h = [70, 22, 22, 22]
    cells = [
        (0, 0, 1, 1, "Parameter", False, None),
        (0, 1, 1, 1, "Voltara AC-7", True, None), (0, 2, 1, 1, "Voltara DC-60", True, None), (0, 3, 1, 1, "Zentra HomeLine", True, None),
        (1, 0, 1, 1, "Rated power", False, None), (1, 1, 1, 1, "7.4 kW", False, ("A-D19-AC7-POWER", "table_fact", "7.4 kW", "AC-7 power")),
        (1, 2, 1, 1, "60 kW", False, None), (1, 3, 1, 1, "3.3 kW", False, None),
        (2, 0, 1, 1, "Leakage trip", False, None), (2, 1, 1, 1, "30 mA", False, None),
        (2, 2, 1, 2, "see insulation monitor", False, ("A-D19-MERGED", "merged_cell", "see insulation monitor", "merged across two columns")),
        (3, 0, 1, 1, "Max current", False, None), (3, 1, 1, 1, "32 A", False, None), (3, 2, 1, 1, "150 A", False, None), (3, 3, 1, 1, "16 A", False, None),
    ]
    d.merged_table(col_w, row_h, cells)
    d.finish()


def d20_hvac(reg, out, rng):
    d = PdfDoc(reg, out, "D20_industrial_relay_manual.pdf", "D20", "Industrial HVAC relay and breaker manual", revision="2", date="2023-09-09",
               purpose="Out-of-domain distractor using fault/relay/isolation/breaker", stresses=["out-of-domain", "retrieval precision"])
    d.heading("HVAC control relay - fault finding")
    d.para("A relay fault on the air-handling unit is cleared by isolating the control breaker, waiting 30 seconds and re-closing it.",
           mark=("A-D20-RELAY", "distractor", "isolating the control breaker, waiting 30 seconds", "HVAC, not EV charging"))
    d.para("Isolation of the compressor circuit requires a second breaker. A tripped breaker indicates a motor fault.")
    d.para(cc.filler_words(rng, 120))
    d.finish()


# =============================================================================================
# Malformed files
# =============================================================================================
def raw_pdf(objects: list[bytes], root: int = 1) -> bytes:
    """Minimal valid PDF writer: objects[i] is the body of object i+1."""
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root {root} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def stream_obj(dict_body: str, data: bytes) -> bytes:
    return f"<< {dict_body} /Length {len(data)} >>\nstream\n".encode() + data + b"\nendstream"


def write_malformed(reg, mdir: Path, raw_dir: Path) -> None:
    mdir.mkdir(parents=True, exist_ok=True)

    def add(name, data, defect, expected, subdir=None):
        target_dir = mdir / subdir if subdir else mdir
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / name).write_bytes(data)
        reg.malformed.append(dict(file=(f"{subdir}/{name}" if subdir else name), defect=defect, expected_ingest_behavior=expected,
                                  sha256=hashlib.sha256(data).hexdigest()))

    skip = "skipped with a logged reason; batch continues; no chunks from this file"
    add("M1_zero_byte.pdf", b"", "zero-byte file", skip)

    good = (raw_dir / "D04_zentra_homeline_manual.pdf").read_bytes()
    add("M2_truncated.pdf", good[: int(len(good) * 0.55)], "valid PDF cut off at 55% (no xref/trailer)",
        "skipped or partially recovered, but never abort the batch")
    add("M3_not_a_pdf.pdf", b"This is plain text renamed to .pdf. It is not a PDF document.\n" * 5,
        "plain text with a .pdf extension", skip)

    enc = pdfencrypt.StandardEncryption("userpass", "ownerpass", canPrint=1, strength=128)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, invariant=1, encrypt=enc)
    c.drawString(72, 720, "Encrypted fictional document. SYNTHETIC TEST DATA")
    c.save()
    add("M4_password_protected.pdf", buf.getvalue(), "encrypted; user password required",
        "skipped with reason 'password protected'; never guess passwords")

    add("M5_zero_pages.pdf", raw_pdf([b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [] /Count 0 >>"]),
        "structurally valid PDF with zero pages", "skipped with reason 'no pages'")

    # declared 20000 x 20000 gray image (400 MP) compressed to a few hundred KB
    comp = zlib.compressobj(9)
    parts = [comp.compress(b"\x80" * 1_000_000) for _ in range(400)]
    parts.append(comp.flush())
    img = stream_obj("/Type /XObject /Subtype /Image /Width 20000 /Height 20000 /ColorSpace /DeviceGray "
                     "/BitsPerComponent 8 /Filter /FlateDecode", b"".join(parts))
    content = b"q 400 0 0 400 100 300 cm /Im0 Do Q BT /F1 12 Tf 72 720 Td (Page with a huge image. SYNTHETIC TEST DATA) Tj ET"
    huge = raw_pdf([
        b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> /XObject << /Im0 6 0 R >> >> >>",
        stream_obj("", content), b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", img])
    add("M6_huge_image.pdf", huge, "declares a 20000x20000 pixel image (decompression-heavy)",
        "must not exhaust memory; text-layer extraction should still work or the file is skipped with a reason")

    # text layer whose ToUnicode map points every character into the Private Use Area
    text = "Capacitor discharge: wait 10 minutes before opening the cabinet."
    cmap = ("/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /Garbled def /CMapType 2 def "
            "1 begincodespacerange <00> <FF> endcodespacerange 95 beginbfchar\n"
            + "\n".join(f"<{c:02X}> <{0xE000 + c:04X}>" for c in range(0x20, 0x7F))
            + "\nendbfchar endcmap CMapName currentdict /CMap defineresource pop end end")
    garbled = raw_pdf([
        b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        stream_obj("", f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding /ToUnicode 6 0 R >>",
        stream_obj("", cmap.encode())])
    add("M7_broken_font_encoding.pdf", garbled, "renders fine but the text layer (ToUnicode) is garbled",
        "extracted text is nonsense: flag as unreadable / low text quality instead of indexing garbage")
    reg.anchors.append(dict(anchor_id="A-M7-TRUTH", doc_id="M7", page=1, kind="garbled_text_layer", anchor=text,
                            note="what the page visually says; the extractable text layer does NOT contain this",
                            lang="en", review_status="n/a", usable_as_ground_truth=True))

    # same filename as a valid doc, different content (HomeLine leakage 30 mA instead of 20 mA)
    tmp_reg = Registry()
    dup = d04_homeline(tmp_reg, mdir / "duplicate_name", None, filename="D04_zentra_homeline_manual.pdf", leak="30 mA",
                       out_dir=mdir / "duplicate_name", doc_id="D04", stress=["duplicate filename, different content"])
    dup.finish()
    data = (mdir / "duplicate_name" / "D04_zentra_homeline_manual.pdf").read_bytes()
    reg.malformed.append(dict(file="duplicate_name/D04_zentra_homeline_manual.pdf",
                              defect="same filename as data/raw/D04_zentra_homeline_manual.pdf but different content (leakage 30 mA)",
                              expected_ingest_behavior="detect the filename/doc_id collision; never silently overwrite or merge",
                              sha256=hashlib.sha256(data).hexdigest()))


# =============================================================================================
def unreviewed_strings() -> list[tuple[str, str]]:
    out = [("corpus_content.HINDI_TITLE", cc.HINDI_TITLE)]
    out += [(f"corpus_content.HINDI_LINES[{i}]", line[0]) for i, line in enumerate(cc.HINDI_LINES)]
    out += [(f"corpus_content.HINGLISH_LINES[{i}]", line[0]) for i, line in enumerate(cc.HINGLISH_LINES)]
    return out


def build(out_raw: Path, out_malformed: Path, manifest_path: Path, seed: int, font_path: str) -> dict:
    register_devanagari(font_path)
    reg = Registry()
    rng = random.Random(seed)
    d01_protocol(reg, out_raw, rng)
    ac7_manual(reg, out_raw, "D02", "D02_voltara_ac7_manual.pdf", cc.AC7_ISO_WAIT, "2024-03-12", rng)
    d03_dc60_revC(reg, out_raw, rng)
    d04_homeline(reg, out_raw, rng).finish()
    d05_safety(reg, out_raw, rng)
    d06_firmware(reg, out_raw, rng)
    d07_trees(reg, out_raw, rng)
    dc60_revA(reg, out_raw, rng)
    d09_hindi(reg, out_raw, rng)
    d10_hinglish(reg, out_raw, rng)
    d11_scanned(reg, out_raw, seed)
    d12_twocol(reg, out_raw, rng)
    d13_long(reg, out_raw, rng)
    ac7_manual(reg, out_raw, "D14", "D14_voltara_ac7_manual_reprint.pdf", cc.AC7_ISO_WAIT_ALTERED, "2024-03-12", rng)
    d15_contradictory(reg, out_raw, rng)
    d16_injection(reg, out_raw, rng)
    d17_lookalikes(reg, out_raw, rng)
    d18_units(reg, out_raw, rng)
    d19_tableonly(reg, out_raw, rng)
    d20_hvac(reg, out_raw, rng)
    write_malformed(reg, out_malformed, out_raw)

    manifest = dict(
        note="ALL CONTENT IS FICTIONAL. Anchors are exact text snippets on a known page of a known document.",
        generator=dict(seed=seed, script="scripts/generate_synthetic_corpus.py",
                       chunker=dict(chunk_size_tokens=settings.chunk_size_tokens,
                                    chunk_overlap_tokens=settings.chunk_overlap_tokens),
                       versions=dict(reportlab=__import__("reportlab").Version, pymupdf=fitz.VersionBind,
                                     numpy=np.__version__, pillow=Image.__version__)),
        documents=sorted(reg.documents, key=lambda x: x["doc_id"]),
        anchors=sorted(reg.anchors, key=lambda x: x["anchor_id"]),
        malformed=sorted(reg.malformed, key=lambda x: x["file"]),
        # every Hindi/Hinglish string in scripts/corpus_content.py, none reviewed by a native speaker
        unreviewed_text=[dict(source=src, text=t, status="unreviewed", usable_as_ground_truth=False)
                         for src, t in unreviewed_strings()],
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate the fictional synthetic corpus.")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--out-raw", default="data/raw")
    ap.add_argument("--out-malformed", default="data/raw_malformed")
    ap.add_argument("--manifest", default="data/manifest.json")
    ap.add_argument("--devanagari-font", default=DEFAULT_DEVANAGARI_FONT)
    a = ap.parse_args()
    m = build(Path(a.out_raw), Path(a.out_malformed), Path(a.manifest), a.seed, a.devanagari_font)
    print(f"documents: {len(m['documents'])}  anchors: {len(m['anchors'])}  malformed: {len(m['malformed'])}")
    print(f"manifest: {a.manifest}")


if __name__ == "__main__":
    main()
