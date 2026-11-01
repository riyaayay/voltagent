"""Golden-set SCHEMA and category QUOTAS only. No items exist yet.

Items are not built until the owner says "contract approved" (docs/SAFETY_CONTRACT.md). The allowed
outcome codes below are copied from that (still unapproved) contract; if the contract changes, change
OUTCOMES here and nothing else. Hindi/Hinglish items cannot be final while the text they rely on is
unreviewed (see data/manifest.json: usable_as_ground_truth).
"""
from __future__ import annotations

OUTCOMES = ("A", "B1", "B2", "B3", "B4", "C")
SPLITS = ("dev", "heldout")
LANGS = ("en", "hi", "hinglish")
LABEL_STATUS = ("draft", "final")

# category -> (total items, heldout items). ~30% heldout per category; sums to 150 / 43.
QUOTAS: dict[str, tuple[int, int]] = {
    "exact_code_lookup": (10, 3),
    "code_plus_model_disambiguation": (10, 3),
    "procedural_multi_step": (8, 2),
    "numeric_unit_critical": (14, 4),
    "multi_doc_synthesis": (6, 2),
    "version_revision_dependent": (8, 2),
    "unanswerable": (10, 3),
    "out_of_domain": (8, 2),
    "ambiguous_missing_model": (8, 2),
    "conflicting_sources": (8, 2),
    "injection_in_query": (6, 2),
    "injection_in_docs": (6, 2),
    "hindi": (8, 2),
    "hinglish": (6, 2),
    "devanagari_numerals_transliterated_codes": (6, 2),
    "asr_noisy": (8, 2),
    "very_short": (4, 1),
    "very_long_rambling": (4, 1),
    "empty_emoji_mixed_script": (6, 2),
    "safety_skip_step_temptation": (6, 2),
}
REQUIRED_FIELDS = ("id", "split", "lang", "query", "category", "expected_outcome", "gold",
                   "must_contain_values", "must_not_contain", "notes", "label_status")


def validate_item(item: dict, manifest: dict | None = None) -> list[str]:
    """Return a list of problems (empty = valid). With a manifest, gold anchors are resolved."""
    p: list[str] = []
    for f in REQUIRED_FIELDS:
        if f not in item:
            p.append(f"missing field: {f}")
    if p:
        return p
    if item["split"] not in SPLITS:
        p.append(f"bad split: {item['split']}")
    if item["lang"] not in LANGS:
        p.append(f"bad lang: {item['lang']}")
    if item["category"] not in QUOTAS:
        p.append(f"unknown category: {item['category']}")
    if item["expected_outcome"] not in OUTCOMES:
        p.append(f"bad expected_outcome: {item['expected_outcome']}")
    if item["label_status"] not in LABEL_STATUS:
        p.append(f"bad label_status: {item['label_status']}")
    if not isinstance(item["query"], str):
        p.append("query must be a string (it may be empty or whitespace for the empty-input category)")
    for k in ("must_contain_values", "must_not_contain", "gold"):
        if not isinstance(item[k], list):
            p.append(f"{k} must be a list")
    if p:
        return p
    for g in item["gold"]:
        if not {"doc_id", "anchor_id"} <= set(g):
            p.append("each gold entry needs doc_id and anchor_id")
    # outcome-specific shape
    if item["expected_outcome"] == "A" and not item["gold"]:
        p.append("outcome A needs at least one gold anchor")
    if item["expected_outcome"] == "A" and not item["must_contain_values"]:
        p.append("outcome A needs must_contain_values (the critical values the answer must state)")
    if item["expected_outcome"] == "B2" and len(item["gold"]) < 2:
        p.append("outcome B2 (source conflict) needs at least two gold anchors")
    if manifest is not None:
        anchors = {a["anchor_id"]: a for a in manifest["anchors"]}
        for g in item["gold"]:
            a = anchors.get(g.get("anchor_id"))
            if a is None:
                p.append(f"unknown anchor: {g.get('anchor_id')}")
                continue
            if a["doc_id"] != g.get("doc_id"):
                p.append(f"anchor {a['anchor_id']} belongs to {a['doc_id']}, not {g.get('doc_id')}")
            if item["label_status"] == "final" and not a.get("usable_as_ground_truth", True):
                p.append(f"final label relies on unreviewed text: {a['anchor_id']}")
    return p


def validate_set(items: list[dict], manifest: dict | None = None, require_quotas: bool = False) -> list[str]:
    p: list[str] = []
    ids = [i.get("id") for i in items]
    if len(ids) != len(set(ids)):
        p.append("duplicate item ids")
    for it in items:
        p += [f"{it.get('id')}: {x}" for x in validate_item(it, manifest)]
    if require_quotas:
        for cat, (total, heldout) in QUOTAS.items():
            in_cat = [i for i in items if i.get("category") == cat]
            h = [i for i in in_cat if i.get("split") == "heldout"]
            if len(in_cat) != total or len(h) != heldout:
                p.append(f"quota {cat}: have {len(in_cat)} total / {len(h)} heldout, need {total} / {heldout}")
    return p
