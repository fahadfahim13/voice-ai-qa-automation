"""Run suite page (C5, use case 4d): trigger the QA agent from the dashboard.

A form selects scenarios (all / by intent / specific), a target siteId, and run
flags, then launches a background job via the C2 job_manager (subprocess — keeps
Streamlit responsive). Live status is shown with a Refresh button (plus light
auto-poll while running); on completion the full report renders inline and a link
to the run on the Reports page is offered.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd  # type: ignore  (bundled with streamlit)
import streamlit as st  # type: ignore

from backend.orchestrator import job_manager
from backend.report import data
from backend.report.aggregate import per_criterion_averages
from backend.report.run_form import (
    MODE_BY_INTENT,
    MODE_SPECIFIC,
    MODES,
    form_to_job_kwargs,
    status_badge,
)
from backend.report.views.call_detail import render_call
from backend.scenarios import load_library
from backend.settings import get_settings

SESSION_KEY = "run_job_id"


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

    # Link to the run on the Reports page (graceful fallback if page_link rejects).
    try:
        st.page_link("reports", label="📄 Open this run on the Reports page", icon="📄")
    except Exception:
        st.caption(
            f"📄 Also on the **Reports** page under version "
            f"`{suite.get('suite_version', 'unversioned')}` (suite `{Path(suite_dir).name}`)."
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
    intents = sorted({s.intent.value for s in scenarios})

    with st.form("run_cfg"):
        dry_run = st.checkbox("Dry run (keyless debug — instant, 0 calls)", value=True)
        mode = st.radio("Scenario selection", MODES, horizontal=True)
        intent = st.selectbox("Intent", intents) if intents else None
        chosen_ids = st.multiselect("Specific scenario ids", all_ids)
        site_id = st.text_input("siteId", value=get_settings().qa_site_id)
        suite_version = st.text_input("Suite version", value="v1.0")
        cols = st.columns(3)
        headless = cols[0].checkbox("Headless", value=True)
        audio_judge = cols[1].checkbox("Audio judge", value=False)
        max_n = st.number_input("Max scenarios (0 = no limit)", min_value=0, value=0)
        submitted = st.form_submit_button("▶ Start run")

    if submitted:
        selection = {
            "mode": mode,
            "intent": intent,
            "ids": chosen_ids,
            "site_id": site_id,
            "suite_version": suite_version,
            "headless": headless,
            "audio_judge": audio_judge,
            "max_n": int(max_n) or None,
        }
        kwargs = form_to_job_kwargs(selection, scenarios=scenarios)
        if mode == MODE_BY_INTENT and not kwargs["ids"]:
            st.warning(f"No scenarios found for intent {intent!r}.")
            return
        if mode == MODE_SPECIFIC and not kwargs["ids"]:
            st.warning("Pick at least one scenario id.")
            return
        if not dry_run and not get_settings().openrouter_api_key:
            st.warning("OPENROUTER_API_KEY is not set — a real run will likely fail. Use dry run.")
        job_id = job_manager.start_job(**kwargs, dry_run=dry_run)
        st.session_state[SESSION_KEY] = job_id
        st.rerun()


def render() -> None:
    st.title("Run suite")
    st.caption("Trigger the QA agent and watch it live; the report appears here when it finishes.")

    _config_form()

    jobs = job_manager.list_jobs()
    if not jobs:
        st.info("No runs yet. Configure a run above and click **Start run**.")
        return

    st.divider()
    job_ids = [j["id"] for j in jobs]
    active = st.session_state.get(SESSION_KEY)
    default_idx = job_ids.index(active) if active in job_ids else 0
    sel_col, btn_col = st.columns([4, 1])
    selected = sel_col.selectbox("Job", job_ids, index=default_idx)
    refresh = btn_col.button("🔄 Refresh")

    job = job_manager.get_job(selected)
    if not job:
        st.warning("Job record not found.")
        return

    st.markdown(f"**Status:** {status_badge(job['status'])}  ·  `{job['id']}`")
    st.caption(f"started {job.get('started_at', '—')} · {' '.join(job.get('argv', []))}")

    if job["status"] in ("queued", "running"):
        with st.expander("Live log", expanded=True):
            st.code(job_manager.tail_log(selected, 40) or "(starting…)")
        # light auto-poll for a live feel; the Refresh button also reruns
        if not refresh:
            time.sleep(2)
        st.rerun()
    elif job["status"] == "error":
        st.error(job.get("error") or "Run failed.")
        with st.expander("Log"):
            st.code(job_manager.tail_log(selected, 80) or "(no log)")
    else:  # done
        st.success("Run complete.")
        _render_results(job["suite_dir"])
