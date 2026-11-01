"""The golden-set SCHEMA validator. Uses obviously fake structural items (ids G-TEST-n) only to
exercise validation rules; they are not golden items and carry no real labels."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import golden_schema as gs  # noqa: E402

pytestmark = pytest.mark.unit


def _item(**over):
    base = dict(id="G-TEST-1", split="dev", lang="en", query="q", category="exact_code_lookup",
                expected_outcome="B1", gold=[], must_contain_values=[], must_not_contain=[], notes="", label_status="draft")
    base.update(over)
    return base


def test_quotas_total_150_with_about_30_percent_heldout():
    total = sum(t for t, _ in gs.QUOTAS.values())
    heldout = sum(h for _, h in gs.QUOTAS.values())
    assert total == 150
    assert 0.27 <= heldout / total <= 0.33
    assert all(0 < h < t for t, h in gs.QUOTAS.values())


def test_quota_categories_cover_the_mission_list():
    required = {"exact_code_lookup", "code_plus_model_disambiguation", "procedural_multi_step", "numeric_unit_critical",
                "multi_doc_synthesis", "version_revision_dependent", "unanswerable", "out_of_domain",
                "ambiguous_missing_model", "conflicting_sources", "injection_in_query", "injection_in_docs", "hindi",
                "hinglish", "devanagari_numerals_transliterated_codes", "asr_noisy", "very_short", "very_long_rambling",
                "empty_emoji_mixed_script", "safety_skip_step_temptation"}
    assert required == set(gs.QUOTAS)


def test_valid_minimal_item_has_no_problems():
    assert gs.validate_item(_item()) == []


@pytest.mark.parametrize("over, fragment", [
    (dict(split="train"), "bad split"), (dict(lang="fr"), "bad lang"), (dict(category="nope"), "unknown category"),
    (dict(expected_outcome="X"), "bad expected_outcome"), (dict(label_status="maybe"), "bad label_status"),
    (dict(expected_outcome="A"), "needs at least one gold"),
    (dict(expected_outcome="A", gold=[dict(doc_id="D03", anchor_id="A-D03-CAP-WAIT")]), "needs must_contain_values"),
    (dict(expected_outcome="B2", gold=[dict(doc_id="D03", anchor_id="A-D03-CAP-WAIT")]), "at least two gold"),
    (dict(gold=[dict(doc_id="D03")]), "doc_id and anchor_id"),
    (dict(query=5), "query must be a string"),
])
def test_invalid_items_are_rejected(over, fragment):
    assert any(fragment in p for p in gs.validate_item(_item(**over)))


def test_missing_field_is_reported():
    item = _item()
    del item["notes"]
    assert gs.validate_item(item) == ["missing field: notes"]


def test_empty_and_whitespace_queries_are_allowed():
    assert gs.validate_item(_item(query="")) == []
    assert gs.validate_item(_item(query="   \n")) == []


def test_gold_anchors_are_resolved_against_the_manifest(corpus):
    m = corpus["manifest"]
    ok = _item(expected_outcome="A", gold=[dict(doc_id="D03", anchor_id="A-D03-CAP-WAIT")], must_contain_values=["10 min"])
    assert gs.validate_item(ok, m) == []
    unknown = copy.deepcopy(ok)
    unknown["gold"][0]["anchor_id"] = "A-NOPE"
    assert any("unknown anchor" in p for p in gs.validate_item(unknown, m))
    wrong_doc = copy.deepcopy(ok)
    wrong_doc["gold"][0]["doc_id"] = "D08"
    assert any("belongs to D03" in p for p in gs.validate_item(wrong_doc, m))


def test_final_label_cannot_rely_on_unreviewed_hindi(corpus):
    m = corpus["manifest"]
    gold = [dict(doc_id="D09", anchor_id="A-D09-E101")]
    draft = _item(lang="hi", expected_outcome="A", gold=gold, must_contain_values=["2 min"], label_status="draft")
    final = dict(draft, label_status="final")
    assert gs.validate_item(draft, m) == []
    assert any("unreviewed text" in p for p in gs.validate_item(final, m))


def test_duplicate_ids_and_quota_checks():
    items = [_item(id="G-TEST-1"), _item(id="G-TEST-1")]
    assert "duplicate item ids" in gs.validate_set(items)
    problems = gs.validate_set([], require_quotas=True)
    assert len(problems) == len(gs.QUOTAS)
