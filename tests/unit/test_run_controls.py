"""Unit tests for the Run-suite pure helpers."""

from __future__ import annotations

from backend.report.run_controls import (
    MODE_ALL,
    MODE_FIRST_N,
    MODE_IDS,
    build_start_kwargs,
    status_badge,
)


def test_status_badge_known_and_unknown():
    assert "queued" in status_badge("queued")
    assert "running" in status_badge("running")
    assert "done" in status_badge("done")
    assert "error" in status_badge("error")
    assert "weird" in status_badge("weird")  # falls back to raw status


def _base(**over):
    kw = dict(
        dry_run=True,
        mode=MODE_ALL,
        max_n=5,
        ids=["a", "b"],
        suite_version="v1.0",
        headless=True,
        audio_judge=False,
        site="",
    )
    kw.update(over)
    return build_start_kwargs(**kw)


def test_mode_all_ignores_n_and_ids():
    kw = _base(mode=MODE_ALL)
    assert kw["max_n"] is None
    assert kw["ids"] is None


def test_mode_first_n_sets_max_n_only():
    kw = _base(mode=MODE_FIRST_N, max_n=3)
    assert kw["max_n"] == 3
    assert kw["ids"] is None


def test_mode_ids_sets_ids_only():
    kw = _base(mode=MODE_IDS, ids=["x", "y"])
    assert kw["ids"] == ["x", "y"]
    assert kw["max_n"] is None


def test_site_blank_becomes_none_and_version_defaults():
    kw = _base(site="   ", suite_version="")
    assert kw["site_id"] is None
    assert kw["suite_version"] == "v1.0"


def test_site_and_flags_passthrough():
    kw = _base(site="webwaala.com", dry_run=False, headless=False, audio_judge=True)
    assert kw["site_id"] == "webwaala.com"
    assert kw["dry_run"] is False
    assert kw["headless"] is False
    assert kw["audio_judge"] is True


def test_empty_ids_list_is_none():
    kw = _base(mode=MODE_IDS, ids=[])
    assert kw["ids"] is None
