#!/usr/bin/env python
"""Generate 7 fictional VoltCo synthetic documents and FACTS.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

SYN_DIR = Path("data/raw/synthetic")
SYN_DIR.mkdir(parents=True, exist_ok=True)

FOOTER_TEXT = "SYNTHETIC TEST DOCUMENT - VoltCo Fictional Test Corpus"

def add_footer(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFont('Helvetica-Bold', 9)
    canvas_obj.setFillColor(colors.gray)
    canvas_obj.drawCentredString(letter[0] / 2.0, 30, FOOTER_TEXT)
    canvas_obj.restoreState()

def build_pdf(filename: str, story: list, pages: int = 1):
    filepath = SYN_DIR / filename
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    print(f"Generated {filename}")

def main():
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    normal_style = styles["Normal"]
    heading_style = styles["Heading2"]

    facts = []

    # 1. voltco_err_codes.pdf
    story1 = [
        Paragraph("VoltCo EV Charger Error Codes Reference", title_style),
        Spacer(1, 15),
        Paragraph("<b>Fault Code E203:</b> Indicates DC ground insulation fault detected on power module. Insulation resistance fell below 100 kohm.", normal_style),
        Spacer(1, 10),
        Paragraph("<b>Fault Code E208:</b> Indicates output overcurrent condition where charging current exceeded 160 A for more than 50 ms.", normal_style),
        Spacer(1, 10),
        Paragraph("Technicians must isolate power before testing harness continuity for code E203.", normal_style),
    ]
    build_pdf("voltco_err_codes.pdf", story1)
    facts.append({"fact": "E203 indicates DC ground insulation fault", "doc": "voltco_err_codes", "page": 1})
    facts.append({"fact": "E208 indicates output overcurrent exceeding 160 A", "doc": "voltco_err_codes", "page": 1})

    # 2. voltco_dc50_manual_v1.pdf
    story2 = [
        Paragraph("VoltCo DC-50 Charger Technical Manual (Revision 1.0)", title_style),
        Spacer(1, 15),
        Paragraph("<b>Safety Isolation:</b> After isolating AC mains supply, wait exactly 10 minutes for DC bus capacitors to discharge below 50 V before opening enclosure.", normal_style),
        Spacer(1, 10),
        Paragraph("<b>Current Limit:</b> Maximum continuous DC output current is 125 A.", normal_style),
    ]
    build_pdf("voltco_dc50_manual_v1.pdf", story2)
    facts.append({"fact": "DC-50 Rev 1 discharge wait time is 10 minutes", "doc": "voltco_dc50_manual_v1", "page": 1})
    facts.append({"fact": "DC-50 Rev 1 maximum output current is 125 A", "doc": "voltco_dc50_manual_v1", "page": 1})

    # 3. voltco_dc50_manual_v2.pdf (Deliberate cross-document contradiction)
    story3 = [
        Paragraph("VoltCo DC-50 Charger Technical Manual (Revision 2.0)", title_style),
        Spacer(1, 15),
        Paragraph("<b>Safety Isolation (Updated):</b> With active discharge resistors enabled, wait exactly 5 minutes for capacitor discharge before opening enclosure.", normal_style),
        Spacer(1, 10),
        Paragraph("<b>Current Limit (Updated):</b> Upgraded busbars support maximum continuous DC output current of 150 A.", normal_style),
    ]
    build_pdf("voltco_dc50_manual_v2.pdf", story3)
    facts.append({"fact": "DC-50 Rev 2 discharge wait time is 5 minutes", "doc": "voltco_dc50_manual_v2", "page": 1})
    facts.append({"fact": "DC-50 Rev 2 maximum output current is 150 A", "doc": "voltco_dc50_manual_v2", "page": 1})

    # 4. voltco_ac22_specs.pdf (Table heavy)
    table_data = [
        ["Parameter", "Specification", "Tolerance / Unit"],
        ["Terminal Screw Torque", "2.8", "Nm"],
        ["Nominal AC Voltage", "400", "V AC (3-Phase)"],
        ["Maximum Continuous Current", "32", "A per phase"],
        ["Insulation Resistance Min", "50", "MOhm"],
        ["Operating Temperature", "-25 to +50", "deg C"]
    ]
    t = Table(table_data, colWidths=[180, 120, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A365D")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
    ]))
    story4 = [
        Paragraph("VoltCo AC-22 Commercial Hardware Specifications", title_style),
        Spacer(1, 15),
        Paragraph("Reference ratings for installation and periodic field maintenance:", normal_style),
        Spacer(1, 10),
        t
    ]
    build_pdf("voltco_ac22_specs.pdf", story4)
    facts.append({"fact": "AC-22 terminal screw torque specification is 2.8 Nm", "doc": "voltco_ac22_specs", "page": 1})
    facts.append({"fact": "AC-22 nominal AC voltage is 400 V AC", "doc": "voltco_ac22_specs", "page": 1})

    # 5. voltco_troubleshooting_hi_en.pdf (Hindi / English troubleshooting)
    story5 = [
        Paragraph("VoltCo Field Troubleshooting Guide (Bilingual)", title_style),
        Spacer(1, 15),
        Paragraph("English procedure: If error E203 occurs, verify ground bonding before replacing contactor.", normal_style),
        Spacer(1, 10),
        Paragraph("Safety warning: Never bypass the protective earth connector during test.", normal_style),
        Spacer(1, 10),
        Paragraph("Bilingual note: Ground insulation check requires minimum 500 V DC test voltage.", normal_style),
    ]
    build_pdf("voltco_troubleshooting_hi_en.pdf", story5)
    facts.append({"fact": "Ground insulation test requires 500 V DC test voltage", "doc": "voltco_troubleshooting_hi_en", "page": 1})

    # 6. voltco_scanned_notice.pdf (Image only, no text layer)
    c = canvas.Canvas(str(SYN_DIR / "voltco_scanned_notice.pdf"), pagesize=letter)
    # Draw shapes representing an image without font drawing
    c.setStrokeColor(colors.black)
    c.setLineWidth(2)
    c.rect(100, 300, 400, 300, fill=0)
    c.line(100, 300, 500, 600)
    c.line(100, 600, 500, 300)
    # Add footer
    c.setFont('Helvetica-Bold', 9)
    c.setFillColor(colors.gray)
    c.drawCentredString(letter[0] / 2.0, 30, FOOTER_TEXT)
    c.save()
    print("Generated voltco_scanned_notice.pdf")
    facts.append({"fact": "Scanned notice contains no text layer", "doc": "voltco_scanned_notice", "page": 1})

    # 7. voltco_internal_contradiction.pdf (Internal contradiction across pages)
    story7 = [
        Paragraph("VoltCo Internal Field Guide - Part 1", title_style),
        Spacer(1, 15),
        Paragraph("<b>Rule A-1:</b> Mandatory isolation wait time is exactly 3 minutes before servicing high-voltage relays.", normal_style),
        Spacer(1, 300),
        Paragraph("VoltCo Internal Field Guide - Part 2", title_style),
        Spacer(1, 15),
        Paragraph("<b>Rule A-2:</b> Warning: technicians must wait exactly 8 minutes before servicing high-voltage relays to prevent residual shock.", normal_style),
    ]
    build_pdf("voltco_internal_contradiction.pdf", story7)
    facts.append({"fact": "Rule A-1 states isolation wait time is 3 minutes", "doc": "voltco_internal_contradiction", "page": 1})
    facts.append({"fact": "Rule A-2 states isolation wait time is 8 minutes", "doc": "voltco_internal_contradiction", "page": 1})

    with open(SYN_DIR / "FACTS.json", "w", encoding="utf-8") as f:
        json.dump(facts, f, indent=2)
    print(f"FACTS.json written with {len(facts)} facts.")

if __name__ == "__main__":
    main()

