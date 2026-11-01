"""Manifest behaviour: anchors validate WITHOUT file hashes; Hindi/Hinglish text is flagged unreviewed.

Cross-machine regeneration changes bytes (fonts, library versions) and therefore sha256, but the
anchors must still validate. The test proves independence by validating one seed's manifest against
a corpus generated with a different seed (different bytes, same planted text).
"""
import copy
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def other_seed_corpus(corpus, tmp_path_factory):
    import generate_synthetic_corpus as gen
    root = tmp_path_factory.mktemp("corpus_other_seed")
    gen.build(root / "raw", root / "bad", root / "manifest.json", 4321, gen.DEFAULT_DEVANAGARI_FONT)
    return dict(raw=root / "raw", manifest=json.loads((root / "manifest.json").read_text(encoding="utf-8")))


def _strip_hashes(manifest: dict) -> dict:
    m = copy.deepcopy(manifest)
    for d in m["documents"]:
        d.pop("sha256", None)
    for x in m["malformed"]:
        x.pop("sha256", None)
    return m


def test_anchors_validate_with_all_hashes_removed(corpus):
    from corpus_validate import validate_anchors
    assert validate_anchors(_strip_hashes(corpus["manifest"]), corpus["raw"]) == []


def test_anchors_validate_against_a_regenerated_corpus_with_different_bytes(corpus, other_seed_corpus):
    from corpus_validate import validate_anchors
    old = {d["doc_id"]: d["sha256"] for d in corpus["manifest"]["documents"]}
    new = {d["doc_id"]: d["sha256"] for d in other_seed_corpus["manifest"]["documents"]}
    assert any(old[k] != new[k] for k in old), "seed change should change at least one file's bytes"
    # old manifest (with its now-wrong hashes) against the new files
    assert validate_anchors(corpus["manifest"], other_seed_corpus["raw"]) == []


def test_validator_detects_a_wrong_anchor(corpus):
    from corpus_validate import validate_anchors
    broken = copy.deepcopy(corpus["manifest"])
    next(a for a in broken["anchors"] if a["anchor_id"] == "A-D03-CAP-WAIT")["anchor"] = "wait 99 minutes"
    problems = validate_anchors(broken, corpus["raw"])
    assert len(problems) == 1 and "A-D03-CAP-WAIT" in problems[0]


def test_hindi_and_hinglish_text_is_marked_unreviewed_and_not_ground_truth(corpus):
    m = corpus["manifest"]
    hi_docs = {d["doc_id"] for d in m["documents"] if d["lang"] in ("hi", "hinglish")}
    assert hi_docs == {"D09", "D10"}
    for d in m["documents"]:
        assert d["text_review_status"] == ("unreviewed" if d["doc_id"] in hi_docs else "n/a")
    for a in m["anchors"]:
        if a["doc_id"] in hi_docs:
            assert a["review_status"] == "unreviewed" and a["usable_as_ground_truth"] is False, a["anchor_id"]
        else:
            assert a["usable_as_ground_truth"] is True, a["anchor_id"]


def test_every_hindi_or_hinglish_source_string_is_listed_as_unreviewed(corpus):
    import corpus_content as cc
    listed = {u["text"] for u in corpus["manifest"]["unreviewed_text"]}
    expected = {cc.HINDI_TITLE} | {x[0] for x in cc.HINDI_LINES} | {x[0] for x in cc.HINGLISH_LINES}
    assert expected <= listed
    assert all(u["status"] == "unreviewed" and u["usable_as_ground_truth"] is False
               for u in corpus["manifest"]["unreviewed_text"])
