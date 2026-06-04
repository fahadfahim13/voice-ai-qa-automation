"""Pure helpers for the Scenarios page (C4).

Streamlit-free so they can be unit-tested on plain ``Scenario`` objects.
"""

from __future__ import annotations

from collections.abc import Iterable

from backend.scenarios import Scenario

# Axis column order, matching Scenario.axis_tuple().
AXES = (
    "intent",
    "persona",
    "accent",
    "interrupt",
    "noise",
    "complexity",
    "language",
    "adversarial",
)


def scenarios_overview(scenarios: Iterable[Scenario]) -> list[dict]:
    """One flat row per scenario: ``id``, ``title`` + the 8 axis values."""
    rows = []
    for s in scenarios:
        row = {"id": s.id, "title": s.title}
        row.update(dict(zip(AXES, s.axis_tuple(), strict=True)))
        rows.append(row)
    return rows


def axis_options(scenarios: Iterable[Scenario]) -> dict[str, list[str]]:
    """Sorted distinct values per axis, for filter dropdowns."""
    rows = scenarios_overview(scenarios)
    return {axis: sorted({row[axis] for row in rows}) for axis in AXES}
