"""Re-run helpers for the Reports page (use case 4b).

Pure, Streamlit-free helpers operating on loaded ``suite.json`` dicts (same style
as ``aggregate.py``), so they are unit-testable without a UI or the filesystem.

"Pinned scenario set" = the exact, de-duplicated ``scenario_id`` list from the
**latest** prior run of a given ``suite_version``. Re-running with that set under
the same version key keeps two runs of a version comparable.
"""

from __future__ import annotations

from backend.report.aggregate import pass_rate, per_criterion_averages


def _suites_for_version(version: str, suites: list[dict]) -> list[dict]:
    """Suites of ``version``, newest first (by ``started_at`` ISO string)."""
    matching = [s for s in suites if (s.get("suite_version") or "") == version]
    return sorted(matching, key=lambda s: s.get("started_at") or "", reverse=True)


def _latest_for_version(version: str, suites: list[dict]) -> dict | None:
    matching = _suites_for_version(version, suites)
    return matching[0] if matching else None


def pinned_scenario_ids(version: str, suites: list[dict]) -> list[str]:
    """Scenario ids from the latest suite of ``version``.

    De-duplicated, first-seen order preserved. Unknown version (or a run with no
    recorded calls) → ``[]``. Never raises.
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
    """Recorded ``scenario_set_hash`` of the latest suite of ``version``.

    Lets the UI warn when the current library has drifted from what was pinned.
    Returns ``None`` for an unknown version or a suite without the field.
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
    matching = _suites_for_version(version, suites)
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
