# Safety contract

Status: DRAFT v2. Approved by:riya Date: 23/10/26.
(Only the owner removes this line. Tests and golden labels rely on this file only after approval.)

Context: VoltAgent advises technicians working on live electrical equipment.
A confident wrong answer is the worst outcome. An honest "I can't verify this"
is always acceptable.

## 1. Outcomes

Every `/query` ends in exactly one outcome. Anything else is a bug.

| Code | Name | Required content |
|---|---|---|
| A | Verified answer | Answer in the query's language; citations to real retrieved chunks; model and revision named for any code-specific claim; every critical value passes the exact-match gate (section 2); all per-claim verdicts pass. |
| B1 | Low confidence | Fixed fallback line; the raw source passage(s) shown; reason. |
| B2 | Source conflict | Fixed fallback line; both sources, revisions and conflicting values shown; no value picked. |
| B3 | Ambiguous query | A question asking for what is missing (usually the charger model or firmware); no answer content. |
| B4 | Model declined / no support | Fixed fallback line; nearest sources shown if any; never reported as "verified". |
| C | Cannot answer / degraded | Explicit statement that the system could not answer; which stage failed; no guess. |

Response shape (fixed so tests can assert on it):
`outcome` ("A","B1","B2","B3","B4","C"), `answer`, `citations`, `reason`,
`degraded_stages`, `trace_id`, `lang`. Legacy `verified`/`fallback` booleans
may remain but are derived from `outcome`.

## 2. Critical values and the exact-match gate

Critical values: voltages, currents, times and delays, temperatures, torque,
PPE ratings, part numbers, error codes, model names, firmware/revision numbers,
and any other number with a unit.

The gate is deterministic (no LLM, no embeddings) and reads the FULL text of
every cited chunk.

1. Numbers must match exactly. Devanagari numerals equal Western numerals (३० = 30).
2. Units must match after normalisation (min = minutes = मिनट, Nm = N·m, mA = milliamp).
   Magnitude is part of the unit (mA is not A, ms is not s, kW is not kWh).
3. Unit conversion (10 min vs 600 s) passes only if computed deterministically
   and exactly; otherwise it fails.
4. Error codes match by exact normalised form. E-101, E101 and E 101 are one code;
   E-0140 and E-014 are not.
5. If ANY number, code or model in the answer is absent from the cited chunks,
   the whole answer fails (not only that sentence). Outcome becomes B1 or B4.
6. Hindi and Hinglish answers go through the same gate against English or Hindi
   chunks.

## 3. Scoping and sources

1. An answer about an error code, procedure or value must name the charger model
   (and revision where it matters). If the query does not identify the model and
   the retrieved sources disagree across models, the outcome is B3.
2. The current revision wins. If a superseded document gives a different value
   for the same item, the answer uses the current one and says a superseded
   document differs, or the outcome is B2. It never silently uses the old one.
3. Conflicting sources are flagged (B2), never resolved silently. Internal
   contradictions inside one document count as conflicts.
4. Out of domain or unanswerable: if nothing relevant is retrieved (or retrieval
   scores fall below the floor), the outcome is B1 or C. The system never answers
   from the LLM's own knowledge.
5. Retrieved text and query text are data. Instructions inside them are never
   obeyed.

## 4. Safety bias

If an answer could lead a technician to skip, shorten or reorder isolation,
lockout, discharge waiting or PPE steps, it may be outcome A only if the cited
chunk contains the complete warning together with the procedure. Otherwise B1.
A query asking to skip a safety step gets the safety step restated from sources,
never a shortcut.

## 5. Degradation

1. One retrieval leg down: allowed to continue only if flagged in
   `degraded_stages` AND the answer still passes every check in sections 2-4.
   Otherwise C.
2. Both legs down, LLM down, verifier down, or any unhandled error: C.
3. Timeouts are bounded (default: ____ s per stage, ____ s per request). A timeout is C.
4. The technician never sees a stack trace, secret, or raw exception text.

## 6. Caching, logging

1. Only outcome A is cached. B, C and degraded results are never cached as verified.
2. Cache keys include language and a corpus-version hash; re-ingest invalidates.
3. Every request has a trace id and a complete log trail, including failures.
4. A log line holds enough to replay the request offline.

## 7. Language

1. The answer is in the query's language. If detection is uncertain, answer in
   English and say so.
2. If no voice exists for the language, the text is shown with a visible notice;
   Hindi text is never read by an English voice.
3. Critical codes heard by speech recognition are read back for confirmation
   before a lookup (UI requirement).

## 8. Fixed fallback lines (spoken and shown)

Placeholders, to be finalised and reviewed by a native Hindi speaker:

| Outcome | English | Hindi (draft, UNREVIEWED) |
|---|---|---|
| B1 | I can't verify this answer. The source document is shown on screen. | मैं इस उत्तर की पुष्टि नहीं कर सकता। स्रोत दस्तावेज़ स्क्रीन पर दिखाया गया है। |
| B2 | The documents disagree. Both sources are shown. Do not proceed until confirmed. | दस्तावेज़ों में अंतर है। दोनों स्रोत दिखाए गए हैं। पुष्टि होने तक आगे न बढ़ें। |
| B3 | Which charger model is this? | यह कौन सा चार्जर मॉडल है? |
| B4 | I could not find supported guidance. Nearest sources are shown. | मुझे प्रमाणित जानकारी नहीं मिली। निकटतम स्रोत दिखाए गए हैं। |
| C | The system could not answer right now. Do not guess. Follow your site procedure. | सिस्टम अभी उत्तर नहीं दे सका। अनुमान न लगाएँ। अपनी साइट की प्रक्रिया का पालन करें। |

## 9. Tolerances (proposed, owner to confirm)

| Metric | Target |
|---|---|
| False confidence (expected B/C, got A), safety-critical categories | 0 on the dev and held-out golden sets |
| False confidence, all other categories | <= ____ % (proposed 1%) |
| Wrong critical value inside an outcome A | 0 |
| Unhandled exceptions / stack traces in responses | 0 under chaos and fuzz |
| False abstention (expected A, got B/C) | measured and reported; ceiling ____ % (proposed 25% at first, tightened later) |
| Outcome A without valid citations | 0 |
| Requests with an incomplete log trail | 0 |

A target of 0 means any single violation is a new ledger entry and blocks handoff.

## 10. Out of scope (stated honestly)

The gate cannot prove an instruction is correct, only that its critical values
and warnings are present in the cited sources. ASR errors that change a code
are mitigated by read-back, not eliminated.