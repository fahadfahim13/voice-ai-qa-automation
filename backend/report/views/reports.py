"""Reports page (use case 4a): runs grouped by suite_version.

Each version group lists its runs with pass rate + avg score; a run selector
drills into per-criterion averages and the reused per-call detail view.
"""

from __future__ import annotations

import pandas as pd  # type: ignore  (bundled with streamlit)
import streamlit as st  # type: ignore

from backend.report import data
from backend.report.aggregate import pass_rate, per_criterion_averages
from backend.report.views.call_detail import render_call

UNVERSIONED = "unversioned"


def _ordered_versions(versions: set[str]) -> list[str]:
    """Real versions sorted desc, with 'unversioned' always last."""
    real = sorted((v for v in versions if v != UNVERSIONED), reverse=True)
    return real + ([UNVERSIONED] if UNVERSIONED in versions else [])


def render() -> None:
    st.title("Reports")
    st.caption("Past runs grouped by suite version (4a).")

    suite_dirs = data.list_suites()
    loaded = [(p, data.load_suite(p)) for p in suite_dirs]
    loaded = [(p, s) for p, s in loaded if s]  # drop unreadable/empty
    if not loaded:
        st.info("No suites yet. Run a suite first (Run suite page, or `scripts.run_suite`).")
        return

    groups: dict[str, list] = {}
    for p, s in loaded:
        version = s.get("suite_version") or UNVERSIONED
        groups.setdefault(version, []).append((p, s))

    for version in _ordered_versions(set(groups)):
        st.subheader(f"Version: {version}")
        rows = [
            {
                "suite": p.name,
                "started": s.get("started_at", ""),
                "total": s.get("n_total", 0),
                "pass rate": f"{pass_rate(s) * 100:.0f}%",
                "avg score": f"{s.get('avg_overall_score', 0):.2f}",
            }
            for p, s in groups[version]
        ]
        st.table(rows)

    st.divider()
    st.markdown("### Drill into a run")
    options = {p.name: s for p, s in loaded}
    choice = st.selectbox("Run", list(options.keys()))
    if not choice:
        return
    suite = options[choice]
    st.markdown(
        f"**{choice}** — pass rate {pass_rate(suite) * 100:.0f}% · "
        f"avg {suite.get('avg_overall_score', 0):.2f}"
    )

    averages = per_criterion_averages(suite)
    if averages:
        df = pd.DataFrame(
            {"criterion": list(averages.keys()), "average": list(averages.values())}
        ).set_index("criterion")
        st.bar_chart(df)
        st.table([{"criterion": k, "average": round(v, 3)} for k, v in averages.items()])
    else:
        st.caption("No scored calls in this run.")

    st.markdown("#### Calls")
    calls = suite.get("calls", [])
    if not calls:
        st.caption("No calls in this run.")
    for c in calls:
        render_call(c)
