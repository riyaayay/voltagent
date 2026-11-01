#!/usr/bin/env python
"""Check a corpus against its manifest WITHOUT using file hashes.

Anchors are validated by (file name, page number, exact text snippet) only, so a corpus regenerated
on another machine (different fonts or library versions, hence different bytes and sha256) still
validates as long as the planted text is where the manifest says it is.

Usage:  .venv/Scripts/python scripts/corpus_validate.py --manifest data/manifest.json --raw data/raw
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

from pypdf import PdfReader

NO_TEXT_LAYER_KINDS = {"image_only_text", "garbled_text_layer"}


def _n(s: str) -> str:
    return " ".join(unicodedata.normalize("NFC", s).split())


def validate_anchors(manifest: dict, raw_dir: Path) -> list[str]:
    """Return a list of problems (empty = valid). Never reads sha256 fields."""
    docs = {d["doc_id"]: d for d in manifest["documents"]}
    cache: dict[str, list[str]] = {}
    problems: list[str] = []
    for a in manifest["anchors"]:
        if a["kind"] in NO_TEXT_LAYER_KINDS:
            continue
        doc = docs.get(a["doc_id"])
        if doc is None:
            problems.append(f"{a['anchor_id']}: unknown document {a['doc_id']}")
            continue
        path = raw_dir / doc["filename"]
        if not path.exists():
            problems.append(f"{a['anchor_id']}: file missing: {doc['filename']}")
            continue
        if doc["filename"] not in cache:
            cache[doc["filename"]] = [_n(p.extract_text() or "") for p in PdfReader(str(path)).pages]
        pages = cache[doc["filename"]]
        if not 1 <= a["page"] <= len(pages):
            problems.append(f"{a['anchor_id']}: page {a['page']} out of range for {doc['filename']}")
        elif _n(a["anchor"]) not in pages[a["page"] - 1]:
            problems.append(f"{a['anchor_id']}: anchor text not found on page {a['page']} of {doc['filename']}")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/manifest.json")
    ap.add_argument("--raw", default="data/raw")
    a = ap.parse_args()
    manifest = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    problems = validate_anchors(manifest, Path(a.raw))
    for p in problems:
        print("PROBLEM:", p.encode("ascii", "replace").decode())
    print(f"{len(manifest['anchors'])} anchors, {len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
