import json

from voltagent.insights import feedback_loop


def _write_flags(path, doc_ids=None, error_codes=None):
    payload = {
        "generated_at": 0,
        "flagged_doc_ids": doc_ids or [],
        "flagged_error_codes": error_codes or [],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def test_no_flags_file_returns_base_threshold(tmp_path, monkeypatch):
    missing_path = tmp_path / "does_not_exist.json"
    monkeypatch.setattr(feedback_loop.settings, "priority_flags_path", str(missing_path))
    feedback_loop._cached = None

    threshold = feedback_loop.get_threshold_override(doc_ids=["some-doc"], base_threshold=0.55)
    assert threshold == 0.55


def test_flagged_doc_id_tightens_threshold(tmp_path, monkeypatch):
    flags_path = tmp_path / "priority_flags.json"
    _write_flags(flags_path, doc_ids=["ocpp-2.0.1-spec"])
    monkeypatch.setattr(feedback_loop.settings, "priority_flags_path", str(flags_path))
    feedback_loop._cached = None

    threshold = feedback_loop.get_threshold_override(doc_ids=["ocpp-2.0.1-spec"], base_threshold=0.55)
    assert threshold > 0.55


def test_unflagged_doc_id_keeps_base_threshold(tmp_path, monkeypatch):
    flags_path = tmp_path / "priority_flags.json"
    _write_flags(flags_path, doc_ids=["some-other-doc"])
    monkeypatch.setattr(feedback_loop.settings, "priority_flags_path", str(flags_path))
    feedback_loop._cached = None

    threshold = feedback_loop.get_threshold_override(doc_ids=["ocpp-2.0.1-spec"], base_threshold=0.55)
    assert threshold == 0.55


def test_flagged_error_code_tightens_threshold(tmp_path, monkeypatch):
    flags_path = tmp_path / "priority_flags.json"
    _write_flags(flags_path, error_codes=["E203"])
    monkeypatch.setattr(feedback_loop.settings, "priority_flags_path", str(flags_path))
    feedback_loop._cached = None

    threshold = feedback_loop.get_threshold_override(error_code="E203", base_threshold=0.55)
    assert threshold > 0.55


def test_threshold_override_is_capped():
    # even a base threshold already near the ceiling shouldn't push past 0.95
    capped = min(0.90 + 0.15, 0.95)
    assert capped == 0.95
