"""Overview page — suite picker, headline metrics, per-call detail.

Behaviour is identical to the original single-page dashboard; only the suite
listing and JSON loading are delegated to ``backend.report.data``.
"""

from __future__ import annotations

import streamlit as st  # type: ignore

from backend.report import data
from backend.report.views.call_detail import render_call
from scripts.qa_smoke_test import run_smoke


def _render_smoke() -> None:
    """In-UI QA Read API smoke test (health + list + wrong-secret → 401)."""
    with st.expander("🩺 QA API smoke test"):
        if st.button("Run smoke test"):
            st.session_state["smoke_result"] = run_smoke()
        result = st.session_state.get("smoke_result")
        if result is None:
            st.caption("Checks health, conversation list, and that a wrong secret is rejected.")
            return
        (st.success if result.ok else st.error)(
            "All checks green." if result.ok else f"{len(result.failures)} check(s) failed."
        )
        for c in result.checks:
            st.write(f"{'✅' if c.ok else '❌'} **{c.name}** — {c.detail}")


def render() -> None:
    st.title("BizFinder Voice QA — operator dashboard")

    _render_smoke()

    suites = data.list_suites()
    if not suites:
        st.warning("No suites yet. Run `uv run python -m scripts.run_suite` first.")
        return

    # Suite picker in the main page body (sized so the full suite name shows).
    picker_col, _ = st.columns([3, 2])
    suite_label = picker_col.selectbox("Suite", [p.name for p in suites])
    suite_dir = next(p for p in suites if p.name == suite_label)
    suite = data.load_suite(suite_dir)
    if not suite:
        st.error(f"No suite.json in {suite_dir}")
        return

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total", suite["n_total"])
    col2.metric("Passed", suite["n_passed"])
    col3.metric("Failed", suite["n_failed"])
    col4.metric("Errors", suite["n_errors"])
    col5.metric("Avg score", f"{suite['avg_overall_score']:.2f}")

    st.caption(f"{suite['started_at']} → {suite['finished_at']}")
    st.write(f"_{suite['business_summary']}_")

    for c in suite["calls"]:
        render_call(c)
