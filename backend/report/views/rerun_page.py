"""Re-run page (use case 4b, dedicated): re-run a past run's exact scenarios.

Pick any prior run (grouped by version), re-run its de-duplicated scenario set
under the **same version key**, watch it live, and compare to the previous run of
that version. Reuses the C7 helpers (``rerun.py``), the shared data layer, and the
C2 ``job_manager`` — nothing here re-implements run orchestration.
"""

from __future__ import annotations

import time
from pathlib import Path

import streamlit as st  # type: ignore

from backend.orchestrator import job_manager
from backend.report import data, rerun
from backend.report.aggregate import pass_rate
from backend.report.run_form import status_badge
from backend.settings import get_settings

JOB_KEY = "rerun_page_job_id"
VERSION_KEY = "rerun_page_version"


def _render_status_and_result() -> None:
    """Show the tracked re-run job: live status, then result + delta on done."""
    job_id = st.session_state.get(JOB_KEY)
    if not job_id:
        return
    job = job_manager.get_job(job_id)
    if not job:
        return

    st.divider()
    st.markdown(f"**Re-run job:** {status_badge(job['status'])}  ·  `{job_id}`")
    status = job["status"]

    if status in ("queued", "running"):
        with st.expander("Live log", expanded=True):
            st.code(job_manager.tail_log(job_id, 40) or "(starting…)")
        time.sleep(2)
        st.rerun()
        return

    if status == "error":
        st.error(job.get("error") or "Re-run failed.")
        return

    # done
    if "--dry-run" in (job.get("argv") or []):
        st.success("Dry run complete — no calls made (this is expected).")
        st.info(
            "🧪 The pipeline was validated **without making any calls**, so a dry run "
            "produces 0 scored calls. 👉 **Uncheck “Dry run” and re-run** for a real, "
            "scored run (drives the live widget; needs API keys)."
        )
        return

    st.success("Re-run complete.")
    suite = data.load_suite(Path(job["suite_dir"]))
    if suite:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total", suite["n_total"])
        c2.metric("Passed", suite["n_passed"])
        c3.metric("Failed", suite["n_failed"])
        c4.metric("Errors", suite["n_errors"])
        c5.metric("Avg score", f"{suite['avg_overall_score']:.2f}")

    version = st.session_state.get(VERSION_KEY)
    delta = rerun.version_delta(version, [s for _, s in data.list_loaded_suites()])
    if delta:
        st.markdown("**Δ vs previous run of this version** (new − previous)")
        st.markdown(f"Pass rate Δ: **{delta['pass_rate_delta'] * 100:+.0f}%**")
        rows = [
            {"criterion": k, "Δ avg": round(v, 3)}
            for k, v in sorted(delta["criterion_deltas"].items())
        ]
        if rows:
            st.table(rows)


def render() -> None:
    st.title("Re-run")
    st.caption("Pick a past run and re-run its exact scenarios under the same version key (4b).")

    loaded = data.list_loaded_suites()
    runs = [(p, s) for p, s in loaded if rerun.scenario_ids_of(s)]
    if not runs:
        st.info("No past runs with scenarios yet — start one on the **Run suite** page.")
        return

    versions = sorted({s.get("suite_version") or "unversioned" for _, s in runs}, reverse=True)
    version = st.selectbox("Version", versions, key="rerun_version_sel")
    version_runs = [
        (p, s) for p, s in runs if (s.get("suite_version") or "unversioned") == version
    ]

    labels = {
        f"{data.suite_label(p.name)} · {len(rerun.scenario_ids_of(s))} scenarios · "
        f"{pass_rate(s) * 100:.0f}% pass": (p, s)
        for p, s in version_runs
    }
    choice = st.selectbox("Run", list(labels.keys()), key="rerun_run_sel")
    _, suite = labels[choice]
    ids = rerun.scenario_ids_of(suite)

    with st.expander(f"{len(ids)} scenario(s) that will re-run"):
        for sid in ids:
            st.write(f"• {sid}")

    dry = st.checkbox("Dry run (keyless — instant, 0 calls)", value=True)
    if st.button("🔁 Re-run this run"):
        if not dry and not get_settings().openrouter_api_key:
            st.warning("OPENROUTER_API_KEY is not set — a real run will likely fail. Use dry run.")
        job_id = job_manager.start_job(
            ids=ids, suite_version=version, dry_run=dry, headless=True, audio_judge=False
        )
        st.session_state[JOB_KEY] = job_id
        st.session_state[VERSION_KEY] = version
        st.rerun()

    _render_status_and_result()
