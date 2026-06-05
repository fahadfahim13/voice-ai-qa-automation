"""Unit tests for the Run-suite form mapping (C5, 4d)."""

from __future__ import annotations

from backend.report.run_form import (
    MODE_ALL,
    MODE_BY_INTENT,
    MODE_SPECIFIC,
    form_to_job_kwargs,
    is_dry_run,
    status_badge,
)
from backend.scenarios import load_library


def test_is_dry_run():
    assert is_dry_run(["python", "-m", "scripts.run_suite", "--dry-run", "--headless"]) is True
    assert is_dry_run(["python", "-m", "scripts.run_suite", "--headless", "--max", "1"]) is False
    assert is_dry_run(None) is False
    assert is_dry_run([]) is False


def _sel(**over):
    sel = {
        "mode": MODE_ALL,
        "intent": None,
        "ids": [],
        "site_id": "qa-judge",
        "suite_version": "v1.0",
        "headless": True,
        "audio_judge": False,
        "max_n": None,
    }
    sel.update(over)
    return sel


def test_all_mode_ids_none():
    assert form_to_job_kwargs(_sel(mode=MODE_ALL))["ids"] is None


def test_by_intent_resolves_exact_ids():
    expected = {s.id for s in load_library() if s.intent.value == "pricing-inquiry"}
    assert expected, "library should contain pricing-inquiry scenarios"
    kw = form_to_job_kwargs(_sel(mode=MODE_BY_INTENT, intent="pricing-inquiry"))
    assert set(kw["ids"]) == expected


def test_specific_mode_passes_ids():
    kw = form_to_job_kwargs(_sel(mode=MODE_SPECIFIC, ids=["x", "y"]))
    assert kw["ids"] == ["x", "y"]


def test_specific_empty_ids_is_none():
    assert form_to_job_kwargs(_sel(mode=MODE_SPECIFIC, ids=[]))["ids"] is None


def test_passthrough_and_normalization():
    kw = form_to_job_kwargs(
        _sel(site_id="webwaala.com", suite_version="v2.0", headless=False, audio_judge=True)
    )
    assert kw["site_id"] == "webwaala.com"
    assert kw["suite_version"] == "v2.0"
    assert kw["headless"] is False
    assert kw["audio_judge"] is True


def test_blank_site_and_version_defaults():
    kw = form_to_job_kwargs(_sel(site_id="   ", suite_version=""))
    assert kw["site_id"] is None
    assert kw["suite_version"] == "v1.0"


def test_empty_max_is_none():
    assert form_to_job_kwargs(_sel(max_n=None))["max_n"] is None
    assert form_to_job_kwargs(_sel(max_n=0))["max_n"] is None


def test_dry_run_not_in_kwargs():
    # dry_run is passed to start_job separately, not produced here
    assert "dry_run" not in form_to_job_kwargs(_sel())


def test_status_badges():
    for s in ("queued", "running", "done", "error"):
        assert s in status_badge(s)
    assert "weird" in status_badge("weird")
