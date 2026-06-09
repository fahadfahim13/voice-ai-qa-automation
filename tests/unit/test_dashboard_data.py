"""Unit tests for the dashboard shared data layer."""

from __future__ import annotations

import json
from pathlib import Path

from backend.report import data


def test_list_suites_newest_first(tmp_path, monkeypatch):
    (tmp_path / "suite_20260101T000000Z").mkdir()
    (tmp_path / "suite_20260601T000000Z").mkdir()
    # noise that should be ignored
    (tmp_path / "not_a_suite").mkdir()
    (tmp_path / "suite_ignored_file").write_text("x", encoding="utf-8")

    monkeypatch.setattr(data, "_suites_dir", lambda: tmp_path)

    suites = data.list_suites()
    names = [p.name for p in suites]
    assert names == ["suite_20260601T000000Z", "suite_20260101T000000Z"]


def test_list_suites_missing_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "_suites_dir", lambda: tmp_path / "nope")
    assert data.list_suites() == []


def test_suite_label_with_timestamp_and_id():
    assert data.suite_label("suite_20260604T145443Z_45fad09c") == "2026-06-04 14:54 · 45fad09c"


def test_suite_label_timestamp_only():
    assert data.suite_label("suite_20260601T000000Z") == "2026-06-01 00:00"


def test_suite_label_unparseable_falls_back_to_raw():
    assert data.suite_label("not_a_suite") == "not_a_suite"
    assert data.suite_label("suite_garbage_abc") == "suite_garbage_abc"


def test_list_loaded_suites_skips_incomplete_and_unreadable(tmp_path, monkeypatch):
    # A finished suite (has suite.json).
    good = tmp_path / "suite_20260601T000000Z"
    good.mkdir()
    (good / "suite.json").write_text(json.dumps({"n_total": 1}), encoding="utf-8")
    # An in-progress run: dir exists, no suite.json yet.
    (tmp_path / "suite_20260605T000000Z").mkdir()
    # A corrupt suite.json.
    bad = tmp_path / "suite_20260603T000000Z"
    bad.mkdir()
    (bad / "suite.json").write_text("{not json", encoding="utf-8")

    monkeypatch.setattr(data, "_suites_dir", lambda: tmp_path)

    loaded = data.list_loaded_suites()
    # Only the readable suite is returned; in-progress and corrupt are skipped.
    assert [p.name for p, _ in loaded] == ["suite_20260601T000000Z"]
    assert loaded[0][1]["n_total"] == 1


def test_load_suite_permission_denied_returns_empty(tmp_path, monkeypatch):
    """A suite dir the dashboard user can't read is skipped, not raised.

    Regression: ``Path.exists()`` re-raises EACCES instead of returning False,
    so a suite.json the process can't stat/read once crashed the whole page.
    """
    suite_dir = tmp_path / "suite_locked"
    suite_dir.mkdir()
    (suite_dir / "suite.json").write_text(json.dumps({"n_total": 1}), encoding="utf-8")

    orig_read_text = Path.read_text

    def deny(self, *args, **kwargs):
        if self.name == "suite.json":
            raise PermissionError(13, "Permission denied")
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", deny)

    assert data.load_suite(suite_dir) == {}


def test_list_loaded_suites_skips_permission_denied(tmp_path, monkeypatch):
    """One unreadable suite dir must not take down the whole listing.

    Reproduces the production failure on ``suite_20260609T103851Z_aa763f3b``.
    """
    good = tmp_path / "suite_20260601T000000Z"
    good.mkdir()
    (good / "suite.json").write_text(json.dumps({"n_total": 1}), encoding="utf-8")
    locked = tmp_path / "suite_20260609T103851Z_aa763f3b"
    locked.mkdir()
    (locked / "suite.json").write_text(json.dumps({"n_total": 9}), encoding="utf-8")

    orig_read_text = Path.read_text

    def deny(self, *args, **kwargs):
        if "suite_20260609T103851Z_aa763f3b" in str(self):
            raise PermissionError(13, "Permission denied")
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", deny)
    monkeypatch.setattr(data, "_suites_dir", lambda: tmp_path)

    loaded = data.list_loaded_suites()  # must not raise
    assert [p.name for p, _ in loaded] == ["suite_20260601T000000Z"]


def test_load_suite_full(tmp_path):
    suite_dir = tmp_path / "suite_full"
    suite_dir.mkdir()
    payload = {
        "started_at": "2026-06-01T11:03:41Z",
        "finished_at": "2026-06-01T11:13:19Z",
        "business_summary": "FFTech SaaS",
        "n_total": 6,
        "n_passed": 0,
        "n_failed": 6,
        "n_errors": 0,
        "avg_overall_score": 0.4066,
        "calls": [{"scenario_id": "x"}],
    }
    (suite_dir / "suite.json").write_text(json.dumps(payload), encoding="utf-8")

    loaded = data.load_suite(suite_dir)
    assert loaded["n_total"] == 6
    assert loaded["business_summary"] == "FFTech SaaS"
    assert loaded["calls"] == [{"scenario_id": "x"}]


def test_load_suite_missing_optional_keys(tmp_path):
    suite_dir = tmp_path / "suite_sparse"
    suite_dir.mkdir()
    (suite_dir / "suite.json").write_text(json.dumps({"n_total": 2}), encoding="utf-8")

    loaded = data.load_suite(suite_dir)
    # provided key preserved
    assert loaded["n_total"] == 2
    # optional keys defaulted, no exception
    assert loaded["n_passed"] == 0
    assert loaded["avg_overall_score"] == 0.0
    assert loaded["calls"] == []
    assert loaded["business_summary"] == ""


def test_load_suite_absent(tmp_path):
    assert data.load_suite(tmp_path / "missing") == {}


def test_load_suite_corrupt_json(tmp_path):
    suite_dir = tmp_path / "suite_bad"
    suite_dir.mkdir()
    (suite_dir / "suite.json").write_text("{not json", encoding="utf-8")
    assert data.load_suite(Path(suite_dir)) == {}
