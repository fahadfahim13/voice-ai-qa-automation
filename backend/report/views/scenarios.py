"""Scenarios page (C4): browse the test-scenario library.

Filterable table of all scenarios with their 8 axes, plus a drill-in showing one
scenario's full detail. Read-only — no edits to the library or schema.
"""

from __future__ import annotations

import streamlit as st  # type: ignore

from backend.report.scenarios_table import AXES, axis_options, scenarios_overview
from backend.scenarios import load_library


def render() -> None:
    st.title("Scenarios")
    st.caption("Browse the QA scenario library (read-only).")

    scenarios = load_library()
    if not scenarios:
        st.info("No scenarios found in the library.")
        return

    by_id = {s.id: s for s in scenarios}
    rows = scenarios_overview(scenarios)
    options = axis_options(scenarios)

    # --- sidebar axis filters ---
    st.sidebar.markdown("### Filter scenarios")
    selected: dict[str, list[str]] = {
        axis: st.sidebar.multiselect(axis, options[axis], key=f"flt_{axis}") for axis in AXES
    }

    filtered = [
        row for row in rows if all(not selected[axis] or row[axis] in selected[axis] for axis in AXES)
    ]

    st.markdown(f"**{len(filtered)}** of {len(rows)} scenarios")
    if not filtered:
        st.caption("No scenarios match the current filters.")
        return
    st.dataframe(filtered, width="stretch", hide_index=True)

    # --- drill-in ---
    st.divider()
    st.markdown("### Scenario detail")
    label_for = {f"{row['id']}  —  {row['title']}": row["id"] for row in filtered}
    choice = st.selectbox("Scenario", list(label_for.keys()))
    if not choice:
        return
    s = by_id[label_for[choice]]

    st.subheader(s.title)
    st.caption(s.id)
    st.write(s.description)

    st.markdown("**Axes**")
    st.table([dict(zip(AXES, s.axis_tuple(), strict=True))])

    st.markdown("**Goal**")
    st.write(s.goal)
    st.markdown("**Expected outcome**")
    st.write(s.expected_outcome)

    if s.constraints:
        st.markdown("**Constraints**")
        for c in s.constraints:
            st.markdown(f"- {c}")

    if s.criterion_weights:
        st.markdown("**Criterion weights**")
        st.table([{"criterion": w.name, "weight": w.weight} for w in s.criterion_weights])

    st.caption(f"turn_count: {s.turn_count} · caller_voice: {s.caller_voice or 'provider default'}")
