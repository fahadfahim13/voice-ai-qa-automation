"""Reports page (use case 4a + 4b): runs grouped by suite_version.

Each version group lists its runs with pass rate + avg score; a run selector
drills into per-criterion averages and the reused per-call detail view. Each real
version group also offers a **Re-run** action (4b): kick the runner with the
version's pinned scenario set under the same version key, so the new run lands
beside the prior runs of that version.
"""

from __future__ import annotations

import time

import pandas as pd  # type: ignore  (bundled with streamlit)
import streamlit as st  # type: ignore

from backend.orchestrator import job_manager
from backend.orchestrator.versioning import scenario_set_hash
from backend.report import data, rerun
from backend.report.aggregate import pass_rate, per_criterion_averages
from backend.report.run_form import status_badge
from backend.report.views.call_detail import render_call
from backend.scenarios import load_library
from backend.settings import get_settings

UNVERSIONED = "unversioned"
RERUN_KEY = "reports_rerun_job_id"


def _ordered_versions(versions: set[str]) -> list[str]:
    """Real versions sorted desc, with 'unversioned' always last."""
    real = sorted((v for v in versions if v != UNVERSIONED), reverse=True)
    return real + ([UNVERSIONED] if UNVERSIONED in versions else [])


def _render_active_rerun() -> bool:
    """Show the tracked re-run job's status. Returns True while it is running."""
    job_id = st.session_state.get(RERUN_KEY)
    if not job_id:
        return False
    job = job_manager.get_job(job_id)
    if not job:
        return False

    st.markdown(f"**Re-run:** {status_badge(job['status'])} · `{job_id}`")
    status = job["status"]
    if status in ("queued", "running"):
        with st.expander("Live log", expanded=True):
            st.code(job_manager.tail_log(job_id, 40) or "(starting…)")
        return True
    if status == "error":
        st.error(job.get("error") or "Re-run failed.")
        return False
    st.success("Re-run complete — the new run appears under its version below.")
    return False


def _render_rerun_controls(
    version: str, suites: list[dict], *, dry_run: bool, library_hash: str
) -> None:
    """Drift note, stretch delta, and the Re-run button for one version group."""
    pinned = rerun.pinned_scenario_ids(version, suites)
    if not pinned:
        st.caption(f"No pinned scenarios recorded for {version} yet.")
        return

    pinned_hash = rerun.pinned_scenario_hash(version, suites)
    if pinned_hash and pinned_hash != library_hash:
        st.caption("⚠️ Scenario library has drifted since this version was pinned.")

    delta = rerun.version_delta(version, suites)
    if delta:
        with st.expander(f"Δ vs previous {version} run"):
            st.markdown(f"Pass rate Δ: **{delta['pass_rate_delta'] * 100:+.0f}%**")
            rows = [
                {"criterion": k, "Δ avg": round(v, 3)}
                for k, v in sorted(delta["criterion_deltas"].items())
            ]
            if rows:
                st.table(rows)

    if st.button(f"🔁 Re-run {version}", key=f"rerun_{version}"):
        if not dry_run and not get_settings().openrouter_api_key:
            st.warning("OPENROUTER_API_KEY is not set — a real run will likely fail. Use dry run.")
        job_id = job_manager.start_job(
            ids=pinned,
            suite_version=version,
            dry_run=dry_run,
            headless=True,
            audio_judge=False,
        )
        st.session_state[RERUN_KEY] = job_id
        st.rerun()


def render() -> None:
    st.title("Reports")
    st.caption("Past runs grouped by suite version (4a). Re-run a version's pinned set (4b).")

    loaded = data.list_loaded_suites()  # (dir, suite) for readable suites, newest first
    if not loaded:
        st.info("No suites yet. Run a suite first (Run suite page, or `scripts.run_suite`).")
        return

    all_suites = [s for _, s in loaded]
    groups: dict[str, list] = {}
    for p, s in loaded:
        version = s.get("suite_version") or UNVERSIONED
        groups.setdefault(version, []).append((p, s))

    dry_run = st.checkbox("Dry run (keyless — instant, 0 calls)", value=True)
    running = _render_active_rerun()
    library_hash = scenario_set_hash(load_library())

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
        if version != UNVERSIONED:
            _render_rerun_controls(
                version, all_suites, dry_run=dry_run, library_hash=library_hash
            )

    st.divider()
    st.markdown("### Drill into a run")
    options = {p.name: s for p, s in loaded}
    choice = st.selectbox("Run", list(options.keys()))
    if choice:
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

    # Light auto-poll so a running re-run updates without a manual refresh.
    if running:
        time.sleep(2)
        st.rerun()
