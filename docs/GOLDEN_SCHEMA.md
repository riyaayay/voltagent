# Golden set: schema and quotas only (NO ITEMS YET)

Items are not built until the owner says **"contract approved"** for `docs/SAFETY_CONTRACT.md`.
Code: `scripts/golden_schema.py` (validator + quotas). Tests: `tests/test_golden_schema.py` (fake structural items only).

## Item
```json
{
  "id": "G-001", "split": "dev | heldout", "lang": "en | hi | hinglish",
  "query": "text (may be empty or whitespace for the empty-input category)",
  "category": "one of the quota keys below",
  "expected_outcome": "A | B1 | B2 | B3 | B4 | C",
  "gold": [{"doc_id": "D03", "anchor_id": "A-D03-CAP-WAIT"}],
  "must_contain_values": ["10 min"],
  "must_not_contain": ["5 min"],
  "notes": "free text",
  "label_status": "draft | final"
}
```
Gold spans are `doc_id + anchor_id` from `data/manifest.json` so they survive re-chunking. The outcome codes come from the contract draft and live in one constant (`OUTCOMES`).

## Rules enforced by the validator
- outcome A needs at least one gold anchor and `must_contain_values`; B2 (source conflict) needs at least two gold anchors
- every gold `anchor_id` must exist in the manifest and belong to the stated `doc_id`
- a **final** label may not rely on an anchor with `usable_as_ground_truth: false` (all Hindi/Hinglish text until the owner's reviewer clears it)
- unique ids; quotas checked with `validate_set(..., require_quotas=True)`

## Quotas: 150 items, 43 heldout (28.7%)
| Category | Total | Heldout |
|---|---|---|
| exact_code_lookup | 10 | 3 |
| code_plus_model_disambiguation | 10 | 3 |
| procedural_multi_step | 8 | 2 |
| numeric_unit_critical | 14 | 4 |
| multi_doc_synthesis | 6 | 2 |
| version_revision_dependent | 8 | 2 |
| unanswerable | 10 | 3 |
| out_of_domain | 8 | 2 |
| ambiguous_missing_model | 8 | 2 |
| conflicting_sources | 8 | 2 |
| injection_in_query | 6 | 2 |
| injection_in_docs | 6 | 2 |
| hindi | 8 | 2 |
| hinglish | 6 | 2 |
| devanagari_numerals_transliterated_codes | 6 | 2 |
| asr_noisy | 8 | 2 |
| very_short | 4 | 1 |
| very_long_rambling | 4 | 1 |
| empty_emoji_mixed_script | 6 | 2 |
| safety_skip_step_temptation | 6 | 2 |

Heldout items are never inspected or evaluated until Phase 5. Expected outcomes per category (for example which unanswerable items are B1 vs B4 vs C) are deliberately NOT decided here; they depend on the approved contract.
