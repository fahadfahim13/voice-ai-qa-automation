"""Integration: Scenarios overview over the real committed library."""

from __future__ import annotations

from backend.report.scenarios_table import AXES, scenarios_overview
from backend.scenarios import load_library


def test_overview_over_committed_library():
    scenarios = load_library()
    assert scenarios, "expected a committed scenario library"

    rows = scenarios_overview(scenarios)
    assert len(rows) == len(scenarios)
    for row in rows:
        assert row["id"] and row["title"]
        for axis in AXES:
            assert axis in row and isinstance(row[axis], str)
