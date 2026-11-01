# DATASET: synthetic corpus design

ALL CONTENT IS FICTIONAL (fictional vendors Voltara and Zentra, invented requirement ids FIC-xxx). Every page says SYNTHETIC TEST DATA. Nothing is copied from a real specification.

## Regenerate
```
.venv/Scripts/python scripts/generate_synthetic_corpus.py --seed 1234
```
Writes `data/raw/` (20 valid PDFs), `data/raw_malformed/` (8 broken files), `data/manifest.json`. Existing files with the same names are overwritten; nothing else is deleted. No network.

Determinism: same seed + same library versions + same fonts gives byte-identical output (`tests/test_corpus.py::test_two_runs_have_identical_manifest_and_file_hashes`). It is NOT promised across machines: the Hindi/Hinglish PDFs embed a subset of `C:\Windows\Fonts\Nirmala.ttc` (override with `--devanagari-font`), and library versions are recorded in the manifest.

The generator reads the chunker settings (350 tokens, overlap 60) because two traps are aligned to chunk boundaries. If `chunk_size_tokens`/`chunk_overlap_tokens` change, re-run the generator; `test_corpus.py` will fail if the alignment no longer holds.

## Valid documents (data/raw)
| Id | What it is | Stresses |
|---|---|---|
| D01 | Protocol excerpt: StatusNotification, Reset, ChangeAvailability, TransactionEvent, enums, FIC ids, state table | requirement ids, enums, state table |
| D02 | Voltara AC-7 manual (Rev B) | E-101 = GroundFailure; ground-fault wait 2 minutes |
| D03 | Voltara DC-60 manual Rev C (current) | E-101 = ConnectorLockFailure; discharge wait 10 minutes; busbar torque 15 Nm |
| D04 | Zentra HomeLine manual | E-101 = HighTemperature |
| D05 | Safety/compliance: LOTO, PPE, waits, torque | exact numbers; page 2: **late-position number** (F-022); page 3: **warning split from the torque value**; page 4: **first chunk ends between "10" and "minutes"** |
| D06 | Firmware release notes | behaviour differs by version (retries 3 vs 5) |
| D07 | Troubleshooting trees as tables | multi-step procedures |
| D08 | DC-60 Rev A (superseded) | wait 5 minutes, torque 12 Nm: conflicts with Rev C |
| D09 | Hindi (Devanagari) AC-7 field guide | Hindi, Devanagari numerals; English counterpart is D02 |
| D10 | Hinglish quick card | code-mixed, transliterated and spoken codes ("E one-oh-one") |
| D11 | Scanned HomeLine code table (image only, skewed, noisy) | no text layer; needs OCR or an "unreadable" path |
| D12 | Two columns, 90-row table across pages, repeated header, footnote | reading order, spanning table, header/footer pollution |
| D13 | 152-page logbook with 3 needle facts | scale, chunk count |
| D14 | Near-duplicate of D02: ONLY "2 minutes" -> "20 seconds" differs (verified by test) | duplicates, conflicting evidence |
| D15 | Body says 30 seconds, appendix says 60 seconds | internal contradiction |
| D16 | Prompt-injection text in body, a table cell and a footnote | injection from documents |
| D17 | E-014 / E-041 / E-0140 / E-14H / E-O14 (letter O) / E-l14 (lowercase L) | lookalike codes |
| D18 | mA vs A, V vs kV, degC vs degF, ms vs s, kW vs kWh | units |
| D19 | Parameter matrix: merged cells, rotated header | table-only |
| D20 | HVAC relay manual (fault, relay, isolation, breaker) | out-of-domain distractor |

## Malformed files (data/raw_malformed)
M1 zero-byte; M2 truncated at 55%; M3 plain text named .pdf; M4 encrypted (user password required); M5 valid structure, zero pages; M6 declares a 20000x20000 image (about 390 KB file); M7 text layer garbled via ToUnicode (visually fine); `duplicate_name/D04_...pdf` same filename as D04 with different content. Each is checked by a test to really be malformed in the stated way.

## Manifest
`data/manifest.json`: `documents` (id, file, revision, date, model, language, pages, sha256), `anchors` (exact text snippet on a known page: kind `fact` or a trap kind), `malformed`. Anchors are the planned basis for golden-set gold spans (doc + anchor survives re-chunking). `test_every_anchor_is_present_on_its_page_in_the_real_pdf` opens each PDF with the system's own loader and finds every anchor (the two kinds with no text layer, D11 image text and M7 garbled text, are checked separately).

## Known limitations / honesty
- **Devanagari shaping:** reportlab does not shape conjuncts, so the Hindi PDFs may look visually imperfect when rendered. The TEXT LAYER round-trips exactly (checked with pypdf and PyMuPDF), which is all the pipeline reads. Shaped output via PyMuPDF `insert_htmlbox` extracted as garbage, so it was not used.
- **Hindi wording needs a native-speaker review.** The Hindi sentences were written by the assistant.
- **D11 text exists only in the image.** There is no OCR dependency yet; the manifest stores the ground-truth lines.
- **Not yet covered:** a truncated-but-recoverable PDF variant, rotated pages, PDF forms, embedded attachments.
- **Fonts:** Helvetica-only docs avoid any font dependency; Hindi/Hinglish docs need Nirmala.

## Golden set and labelled claim set: NOT BUILT YET
Held on purpose until the owner approves `docs/SAFETY_CONTRACT.md` (expected outcomes A/B/C depend on it). Planned item schema: `{id, split: dev|heldout, lang: en|hi|hinglish, query, category, expected_outcome: A|B|C, gold: [{doc_id, anchor_id}], must_contain_values: [...], must_not_contain: [...], notes}`, about 150 items, about 30% heldout, heldout results unseen until Phase 5. The verifier claim set will include several Hindi-claim-vs-English-chunk pairs per category (supported, subtly wrong number/unit, wrong model, negated, plausible-but-unsupported) so the Hindi cosine behaviour (F-023) gets a distribution and not n=1.
