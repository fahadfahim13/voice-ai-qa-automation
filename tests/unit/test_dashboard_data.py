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
