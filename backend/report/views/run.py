"""Run suite page (C5, use case 4d): trigger the QA agent from the dashboard.

A form selects scenarios (all / by intent / specific), a target siteId, and run
flags, then launches a background job via the C2 job_manager (subprocess — keeps
Streamlit responsive). Live status is shown with a Refresh button (plus light
auto-poll while running); on completion the full report renders inline and a link
to the run on the Reports page is offered.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import pandas as pd  # type: ignore  (bundled with streamlit)
import streamlit as st  # type: ignore

from backend.db import list_websites, normalize_url, upsert_website
from backend.orchestrator import job_manager
from backend.report import data
from backend.report.aggregate import per_criterion_averages
from backend.report.run_form import (
    MODE_BY_INTENT,
    MODE_SPECIFIC,
    MODES,
    form_to_job_kwargs,
    is_dry_run,
    status_badge,
)
from backend.report.site_targeting import (
    admin_scan_available,
    url_to_site_id,
    validate_site_id,
)
from backend.report.views.call_detail import render_call
from backend.scenarios import load_library
from backend.settings import get_settings

SESSION_KEY = "run_job_id"
WEBSITE_KEY = "run_target_website"
CUSTOM = "Custom…"


def _render_results(suite_dir: str, *, dry_run: bool = False) -> None:
    suite = data.load_suite(Path(suite_dir))
    if not suite:
        st.warning("Run finished but no suite.json was found.")
        return

    if dry_run:
        # A dry run is keyless and makes 0 calls by design — explain that instead
        # of showing bare "Total 0" metrics that read like a failed run.
        st.info(
            "🧪 **Dry run** — the run pipeline was validated **without making any "
            "calls**, so `Total 0` is expected (nothing was scored). The selected "
            f"scenario set was fingerprinted (`{(suite.get('scenario_set_hash') or '—')[:12]}…`) "
            f"under version `{suite.get('suite_version', '—')}`.\n\n"
            "👉 **Uncheck “Dry run” and click Start run** for a real, scored run "
            "(drives the live widget; needs API keys)."
        )
        st.caption(f"{suite['started_at']} → {suite['finished_at']}")
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


def _website_picker() -> tuple[str, str | None]:
    """Choose the target **website**; the internal siteId is cached behind Advanced.

    Returns ``(website, site_id_override)`` — ``website`` is the normalized host
    (``""`` until something valid is entered); ``site_id_override`` is an explicit
    advanced override or ``None`` (otherwise the website's cached siteId is used,
    resolved automatically on the first run).
    """
    st.markdown("### Target website")
    known = list_websites()
    url_options = [w.url for w in known]
    options = [*url_options, CUSTOM] if url_options else [CUSTOM]
    default = st.session_state.get(WEBSITE_KEY)
    idx = options.index(default) if default in options else 0
    choice = st.selectbox("Website", options, index=idx)
    raw = st.text_input("Website URL", value=default or "") if choice == CUSTOM else choice

    website = ""
    if raw:
        try:
            website = normalize_url(raw)
        except ValueError:
            st.warning("Enter a valid website (e.g. fftechsaas.xyz).")
    st.session_state[WEBSITE_KEY] = website or None
    if website:
        st.caption(f"Normalized website: **{website}**")

    cached = next((w.site_id for w in known if w.url == website), None)

    site_id_override: str | None = None
    with st.expander("Advanced (siteId / debug)"):
        if cached:
            st.caption(f"Cached siteId for this website: `{cached}`")
        override = st.text_input(
            "siteId override",
            value="",
            help="Leave blank to use the cached siteId (resolved automatically on the first run).",
        )
        site_id_override = override.strip() or None

        probe = site_id_override or cached
        cols = st.columns([1, 4])
        if cols[0].button("🔎 Validate") and probe:
            st.session_state["siteid_check"] = validate_site_id(probe)
        check = st.session_state.get("siteid_check")
        if check:
            status = check.get("status")
            if status == "known":
                cols[1].success(f"Known siteId — {check.get('count', 0)}+ conversation(s).")
            elif status == "no_traffic":
                cols[1].info("Reachable, no traffic yet — will be created on the first call.")
            elif status == "empty":
                cols[1].warning("Enter a siteId.")
            else:
                cols[1].error(f"Unreachable: {check.get('error', 'unknown error')}")

        # Stretch: arbitrary URL → siteId (guarded by an admin token). Kept flat —
        # Streamlit forbids nesting expanders inside this one.
        if admin_scan_available():
            st.markdown("**Resolve a website URL → siteId (admin)**")
            url = st.text_input("Website URL to scan", value=raw or "")
            if st.button("Resolve URL") and url:
                res = url_to_site_id(url)
                if res.get("site_id"):
                    site_id_override = res["site_id"]
                    st.success(f"Resolved → {site_id_override}")
                else:
                    st.error(res.get("error", "scan failed"))
        else:
            st.caption("URL scan needs admin access (set `BIZFINDER_ADMIN_TOKEN`).")

    return website, site_id_override


def _config_form(website: str, site_id_override: str | None) -> None:
    scenarios = load_library()
    all_ids = [s.id for s in scenarios]
    intents = sorted({s.intent.value for s in scenarios})

    run_full = "Full run — real calls + judging"
    run_dry = "Dry run — skip the process (no calls)"

    default_name = f"{website} {datetime.now():%Y-%m-%d %H:%M}".strip()

    with st.form("run_cfg"):
        st.caption(f"Targeting website: **{website or '—'}**")
        job_name = st.text_input("Job name", value=default_name)
        run_mode = st.radio(
            "Run mode",
            [run_full, run_dry],
            index=0,  # default to the full real run so a run actually runs the pipeline
            captions=[
                "Drives the live widget and scores each call. Needs API keys; takes minutes.",
                "Validates the pipeline only — makes 0 calls and produces no scores.",
            ],
        )
        dry_run = run_mode == run_dry
        mode = st.radio("Scenario selection", MODES, horizontal=True)
        intent = st.selectbox("Intent", intents) if intents else None
        chosen_ids = st.multiselect("Specific scenario ids", all_ids)
        suite_version = st.text_input("Suite version", value="v1.0")
        cols = st.columns(3)
        headless = cols[0].checkbox("Headless", value=True)
        audio_judge = cols[1].checkbox("Audio judge", value=False)
        max_n = st.number_input("Max scenarios (0 = no limit)", min_value=0, value=0)
        submitted = st.form_submit_button("▶ Start run")

    if submitted:
        if not website:
            st.warning("Enter a website to target above.")
            return
        # Capture/refresh the Website row; use its cached siteId unless overridden.
        row = upsert_website(website)
        effective_site_id = site_id_override or row.site_id
        selection = {
            "mode": mode,
            "intent": intent,
            "ids": chosen_ids,
            "site_id": effective_site_id,
            "website": website,
            "name": job_name,
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

    website, site_id_override = _website_picker()
    _config_form(website, site_id_override)

    jobs = job_manager.list_jobs()
    if not jobs:
        st.info("No runs yet. Configure a run above and click **Start run**.")
        return

    st.divider()
    job_ids = [j["id"] for j in jobs]
    names = {j["id"]: j.get("name", j["id"]) for j in jobs}
    active = st.session_state.get(SESSION_KEY)
    default_idx = job_ids.index(active) if active in job_ids else 0
    sel_col, btn_col = st.columns([4, 1])
    selected = sel_col.selectbox(
        "Job", job_ids, index=default_idx, format_func=lambda jid: names.get(jid, jid)
    )
    refresh = btn_col.button("🔄 Refresh")

    job = job_manager.get_job(selected)
    if not job:
        st.warning("Job record not found.")
        return

    with st.expander("✏️ Rename"):
        rcols = st.columns([4, 1])
        new_name = rcols[0].text_input(
            "Job name", value=job.get("name", job["id"]), key=f"rename_{selected}"
        )
        if rcols[1].button("Save name") and new_name.strip():
            job_manager.rename_job(selected, new_name)
            st.rerun()

    st.markdown(
        f"**{job.get('name', job['id'])}** · {status_badge(job['status'])}  ·  `{job['id']}`"
    )
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
        dry = is_dry_run(job.get("argv"))
        st.success("Dry run complete — no calls made (this is expected)." if dry else "Run complete.")
        _render_results(job["suite_dir"], dry_run=dry)
