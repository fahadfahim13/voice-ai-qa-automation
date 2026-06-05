"""Re-run helpers for the Reports page (use case 4b).

Pure, Streamlit-free helpers operating on loaded ``suite.json`` dicts (same style
as ``aggregate.py``), so they are unit-testable without a UI or the filesystem.

"Pinned scenario set" = the exact, de-duplicated ``scenario_id`` list from the
**latest** prior run of a given ``suite_version``. Re-running with that set under
the same version key keeps two runs of a version comparable.
"""

from __future__ import annotations

from backend.report.aggregate import pass_rate, per_criterion_averages


def _has_scenarios(suite: dict) -> bool:
    """True when the suite recorded at least one ``scenario_id`` (not a dry-run)."""
    return any(c.get("scenario_id") for c in suite.get("calls", []))


def _suites_for_version(version: str, suites: list[dict], *, with_scenarios: bool = False) -> list[dict]:
    """Suites of ``version``, newest first (by ``started_at`` ISO string).

    With ``with_scenarios=True``, 0-call runs (e.g. dry-runs) are skipped so the
    "pinned set" comes from the latest run that actually exercised scenarios.
    """
    matching = [s for s in suites if (s.get("suite_version") or "") == version]
    if with_scenarios:
        matching = [s for s in matching if _has_scenarios(s)]
    return sorted(matching, key=lambda s: s.get("started_at") or "", reverse=True)


def _latest_for_version(version: str, suites: list[dict]) -> dict | None:
    """Latest run of ``version`` that recorded scenarios (ignores dry-runs)."""
    matching = _suites_for_version(version, suites, with_scenarios=True)
    return matching[0] if matching else None


def pinned_scenario_ids(version: str, suites: list[dict]) -> list[str]:
    """Scenario ids from the latest run of ``version`` that recorded scenarios.

    De-duplicated, first-seen order preserved. 0-call runs (dry-runs) are skipped,
    so a recent dry-run can't blank out the pin. Unknown version (or no real run
    of it) → ``[]``. Never raises.
    """
    latest = _latest_for_version(version, suites)
    if not latest:
        return []
    ids = [
        c.get("scenario_id")
        for c in latest.get("calls", [])
        if c.get("scenario_id")
    ]
    return list(dict.fromkeys(ids))


def pinned_scenario_hash(version: str, suites: list[dict]) -> str | None:
    """Recorded ``scenario_set_hash`` of the latest run of ``version`` with scenarios.

    Same suite that :func:`pinned_scenario_ids` pins, so the UI's drift warning
    compares like for like. Returns ``None`` for an unknown version or a suite
    without the field.
    """
    latest = _latest_for_version(version, suites)
    if not latest:
        return None
    return latest.get("scenario_set_hash") or None


def version_delta(version: str, suites: list[dict]) -> dict | None:
    """Compare the two most recent runs of ``version`` (new minus previous).

    Returns ``{"pass_rate_delta": float, "criterion_deltas": {name: float}}`` or
    ``None`` when fewer than two runs of the version exist. Reuses the Reports
    aggregation helpers so the numbers match the rest of the page.
    """
    matching = _suites_for_version(version, suites, with_scenarios=True)
    if len(matching) < 2:
        return None
    new, prev = matching[0], matching[1]

    new_avgs = per_criterion_averages(new)
    prev_avgs = per_criterion_averages(prev)
    criterion_deltas = {
        name: new_avgs.get(name, 0.0) - prev_avgs.get(name, 0.0)
        for name in (new_avgs.keys() | prev_avgs.keys())
    }
    return {
        "pass_rate_delta": pass_rate(new) - pass_rate(prev),
        "criterion_deltas": criterion_deltas,
    }
