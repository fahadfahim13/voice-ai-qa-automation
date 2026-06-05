"""Unit tests for the re-run pinning helpers (4b)."""

from __future__ import annotations

from backend.report import rerun


def _suite(version, started_at, *, calls=None, scenario_ids=(), n_total=0, n_passed=0, hash="h"):
    if calls is None:
        calls = [{"scenario_id": sid} for sid in scenario_ids]
    return {
        "suite_version": version,
        "started_at": started_at,
        "scenario_set_hash": hash,
        "n_total": n_total,
        "n_passed": n_passed,
        "calls": calls,
    }


def _call(scenario_id, scores):
    return {
        "scenario_id": scenario_id,
        "text_verdict": {"criteria": [{"name": n, "score": s} for n, s in scores.items()]},
    }


def test_pinned_ids_from_latest_of_version_ignores_others():
    suites = [
        _suite("v1.0", "2026-06-01T10:00:00Z", scenario_ids=["a", "b"]),
        _suite("v2.0", "2026-06-02T10:00:00Z", scenario_ids=["x", "y"]),
    ]
    assert rerun.pinned_scenario_ids("v1.0", suites) == ["a", "b"]


def test_pinned_ids_picks_latest_when_multiple():
    suites = [
        _suite("v1.0", "2026-06-01T10:00:00Z", scenario_ids=["old1", "old2"]),
        _suite("v1.0", "2026-06-05T10:00:00Z", scenario_ids=["new1", "new2", "new3"]),
    ]
    assert rerun.pinned_scenario_ids("v1.0", suites) == ["new1", "new2", "new3"]


def test_pinned_ids_dedup_preserves_first_seen_order():
    suites = [
        _suite(
            "v1.0",
            "2026-06-01T10:00:00Z",
            calls=[
                {"scenario_id": "a"},
                {"scenario_id": "b"},
                {"scenario_id": "a"},
                {"scenario_id": "c"},
                {"scenario_id": None},  # ignored
            ],
        )
    ]
    assert rerun.pinned_scenario_ids("v1.0", suites) == ["a", "b", "c"]


def test_pinned_ids_unknown_version_and_empty_input():
    suites = [_suite("v1.0", "2026-06-01T10:00:00Z", scenario_ids=["a"])]
    assert rerun.pinned_scenario_ids("v9.9", suites) == []
    assert rerun.pinned_scenario_ids("v1.0", []) == []


def test_pinned_ids_skips_newer_zero_call_dry_run():
    # A newer dry-run (no scenario_ids) must not blank out the pin.
    suites = [
        _suite("v1.0", "2026-06-01T10:00:00Z", scenario_ids=["a", "b"]),
        _suite("v1.0", "2026-06-05T10:00:00Z", calls=[]),  # dry-run, newest
    ]
    assert rerun.pinned_scenario_ids("v1.0", suites) == ["a", "b"]


def test_pinned_ids_all_dry_runs_returns_empty():
    suites = [
        _suite("v1.0", "2026-06-01T10:00:00Z", calls=[]),
        _suite("v1.0", "2026-06-05T10:00:00Z", calls=[]),
    ]
    assert rerun.pinned_scenario_ids("v1.0", suites) == []


def test_pinned_hash_skips_newer_zero_call_dry_run():
    suites = [
        _suite("v1.0", "2026-06-01T10:00:00Z", scenario_ids=["a"], hash="real"),
        _suite("v1.0", "2026-06-05T10:00:00Z", calls=[], hash="dryrun"),
    ]
    assert rerun.pinned_scenario_hash("v1.0", suites) == "real"


def test_version_delta_ignores_dry_run_between_real_runs():
    prev = _suite(
        "v1.0",
        "2026-06-01T10:00:00Z",
        n_total=2,
        n_passed=1,
        calls=[_call("a", {"relevance": 0.6}), _call("b", {"relevance": 0.4})],
    )
    new = _suite(
        "v1.0",
        "2026-06-05T10:00:00Z",
        n_total=2,
        n_passed=2,
        calls=[_call("a", {"relevance": 0.8}), _call("b", {"relevance": 0.6})],
    )
    dry = _suite("v1.0", "2026-06-06T10:00:00Z", calls=[])  # newest, but 0-call
    delta = rerun.version_delta("v1.0", [prev, new, dry])
    assert delta is not None
    # Compares the two real runs, not the dry-run.
    assert delta["pass_rate_delta"] == 0.5
    assert round(delta["criterion_deltas"]["relevance"], 3) == 0.2


def test_pinned_hash_from_latest():
    suites = [
        _suite("v1.0", "2026-06-01T10:00:00Z", scenario_ids=["a"], hash="old"),
        _suite("v1.0", "2026-06-05T10:00:00Z", scenario_ids=["a"], hash="new"),
    ]
    assert rerun.pinned_scenario_hash("v1.0", suites) == "new"
    assert rerun.pinned_scenario_hash("nope", suites) is None


def test_version_delta_two_runs():
    prev = _suite(
        "v1.0",
        "2026-06-01T10:00:00Z",
        n_total=2,
        n_passed=1,
        calls=[_call("a", {"relevance": 0.6}), _call("b", {"relevance": 0.4})],
    )
    new = _suite(
        "v1.0",
        "2026-06-05T10:00:00Z",
        n_total=2,
        n_passed=2,
        calls=[_call("a", {"relevance": 0.8}), _call("b", {"relevance": 0.6})],
    )
    delta = rerun.version_delta("v1.0", [prev, new])
    assert delta is not None
    assert delta["pass_rate_delta"] == 0.5  # 1.0 - 0.5
    assert round(delta["criterion_deltas"]["relevance"], 3) == 0.2  # 0.7 - 0.5


def test_version_delta_single_run_is_none():
    suites = [_suite("v1.0", "2026-06-01T10:00:00Z", scenario_ids=["a"])]
    assert rerun.version_delta("v1.0", suites) is None
