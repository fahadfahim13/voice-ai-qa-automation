"""Overview page — suite picker, headline metrics, per-call detail.

Behaviour is identical to the original single-page dashboard; only the suite
listing and JSON loading are delegated to ``backend.report.data``.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st  # type: ignore

from backend.report import data


def render() -> None:
    st.title("BizFinder Voice QA — operator dashboard")

    suites = data.list_suites()
    if not suites:
        st.warning("No suites yet. Run `uv run python -m scripts.run_suite` first.")
        return

    suite_label = st.sidebar.selectbox("Suite", [p.name for p in suites])
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
        v = c.get("text_verdict") or {}
        status = (
            "🟢 PASS" if v.get("pass_fail") else ("🔴 FAIL" if v else "🟠 ERROR/EMPTY")
        )
        score = f"{v.get('overall_score', 0):.2f}" if v else "—"
        with st.expander(f"{status}  ·  {c['scenario_id']}  ·  overall {score}"):
            st.caption(f"elapsed {c['elapsed_seconds']:.1f}s · session {c['artifacts'].get('session_id') or '—'}")
            if c.get("error"):
                st.error(c["error"])
            if v:
                st.write(v.get("summary", ""))
                st.table(
                    [
                        {
                            "criterion": cr["name"],
                            "score": cr["score"],
                            "evidence": cr["evidence"],
                            "rationale": cr["rationale"],
                        }
                        for cr in v.get("criteria", [])
                    ]
                )
            if c.get("audio_verdict") and not c["audio_verdict"].get("error"):
                st.subheader("Audio judge")
                st.json(c["audio_verdict"])
            bot_audio = c["artifacts"].get("bot_audio")
            if bot_audio and Path(bot_audio).exists():
                st.audio(bot_audio)
