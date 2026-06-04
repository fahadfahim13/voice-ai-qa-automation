"""Run suite page (C5): start a run from the dashboard and watch it live.

Starts a background job via the C2 job_manager (subprocess — keeps Streamlit
responsive), polls its status across reruns, and renders the full report +
per-call details inline when the run finishes. Supports both keyless dry-runs and
real runs.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd  # type: ignore  (bundled with streamlit)
import streamlit as st  # type: ignore

from backend.orchestrator import job_manager
from backend.report import data
from backend.report.aggregate import per_criterion_averages
from backend.report.run_controls import (
    MODES,
    build_start_kwargs,
    status_badge,
)
from backend.report.views.call_detail import render_call
from backend.scenarios import load_library
from backend.settings import get_settings

SESSION_KEY = "run_suite_job_id"


def _render_results(suite_dir: str) -> None:
    suite = data.load_suite(Path(suite_dir))
    if not suite:
        st.warning("Run finished but no suite.json was found.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total", suite["n_total"])
    c2.metric("Passed", suite["n_passed"])
    c3.metric("Failed", suite["n_failed"])
    c4.metric("Errors", suite["n_errors"])
    c5.metric("Avg score", f"{suite['avg_overall_score']:.2f}")
    st.caption(
        f"{suite['started_at']} → {suite['finished_at']} · "
        f"version {suite.get('suite_version', '—')}"
    )

    averages = per_criterion_averages(suite)
    if averages:
        st.markdown("**Per-criterion averages**")
        df = pd.DataFrame(
            {"criterion": list(averages.keys()), "average": list(averages.values())}
        ).set_index("criterion")
        st.bar_chart(df)

    calls = suite.get("calls", [])
    if calls:
        st.markdown("#### Calls")
        for c in calls:
            render_call(c)


def _config_form() -> None:
    scenarios = load_library()
    all_ids = [s.id for s in scenarios]

    with st.form("run_cfg"):
        dry_run = st.checkbox("Dry run (keyless, instant, 0 calls)", value=True)
        mode = st.radio("Scenarios", MODES, horizontal=True)
        max_n = st.number_input(
            "First N", min_value=1, max_value=max(1, len(all_ids)), value=min(3, len(all_ids))
        )
        chosen_ids = st.multiselect("Specific ids", all_ids)
        suite_version = st.text_input("Suite version", value="v1.0")
        cols = st.columns(3)
        headless = cols[0].checkbox("Headless", value=True)
        audio_judge = cols[1].checkbox("Audio judge", value=False)
        site = st.text_input("Target site (optional)", value="")
        submitted = st.form_submit_button("▶ Start run")

    if submitted:
        kwargs = build_start_kwargs(
            dry_run=dry_run,
            mode=mode,
            max_n=int(max_n),
            ids=chosen_ids,
            suite_version=suite_version,
            headless=headless,
            audio_judge=audio_judge,
            site=site,
        )
        if not dry_run and not get_settings().openrouter_api_key:
            st.warning("OPENROUTER_API_KEY is not set — a real run will likely fail. Use dry run.")
        job_id = job_manager.start_job(**kwargs)
        st.session_state[SESSION_KEY] = job_id
        st.rerun()


def render() -> None:
    st.title("Run suite")
    st.caption("Start a run and watch it live; the full report appears here when it finishes.")

    _config_form()

    jobs = job_manager.list_jobs()
    if not jobs:
        st.info("No runs yet. Configure a run above and click **Start run**.")
        return

    st.divider()
    job_ids = [j["id"] for j in jobs]
    active = st.session_state.get(SESSION_KEY)
    default_idx = job_ids.index(active) if active in job_ids else 0
    selected = st.selectbox("Job", job_ids, index=default_idx)

    job = job_manager.get_job(selected)
    if not job:
        st.warning("Job record not found.")
        return

    st.markdown(f"**Status:** {status_badge(job['status'])}  ·  `{job['id']}`")
    st.caption(f"started {job.get('started_at', '—')} · {' '.join(job.get('argv', []))}")

    if job["status"] in ("queued", "running"):
        with st.expander("Live log", expanded=True):
            st.code(job_manager.tail_log(selected, 40) or "(starting…)")
        time.sleep(2)
        st.rerun()
    elif job["status"] == "error":
        st.error(job.get("error") or "Run failed.")
        with st.expander("Log"):
            st.code(job_manager.tail_log(selected, 80) or "(no log)")
    else:  # done
        st.success("Run complete.")
        _render_results(job["suite_dir"])
