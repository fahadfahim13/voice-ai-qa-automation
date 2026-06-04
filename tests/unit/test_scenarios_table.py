"""Unit tests for the Scenarios page helpers."""

from __future__ import annotations

from backend.report.scenarios_table import AXES, axis_options, scenarios_overview
from backend.scenarios import load_library


def test_overview_one_row_per_scenario_with_axes():
    scenarios = load_library()
    rows = scenarios_overview(scenarios)
    assert len(rows) == len(scenarios)
    for s, row in zip(scenarios, rows, strict=True):
        assert row["id"] == s.id
        assert row["title"] == s.title
        for axis in AXES:
            assert axis in row
        # axis values match axis_tuple() exactly
        assert tuple(row[axis] for axis in AXES) == s.axis_tuple()


def test_axis_options_sorted_and_deduped():
    scenarios = load_library()
    opts = axis_options(scenarios)
    assert set(opts.keys()) == set(AXES)
    for values in opts.values():
        assert values == sorted(set(values))  # sorted + no dupes
    assert "pricing-inquiry" in opts["intent"]


def test_empty_input():
    assert scenarios_overview([]) == []
    assert axis_options([]) == {axis: [] for axis in AXES}
