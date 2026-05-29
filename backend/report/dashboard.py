"""Streamlit operator dashboard.

Run:
    uv run --extra report streamlit run backend/report/dashboard.py
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st  # type: ignore

from backend.settings import get_settings


def _suites_dir() -> Path:
    return get_settings().harness_reports_dir


def main() -> None:
    st.set_page_config(page_title="BizFinder Voice QA", layout="wide")
    st.title("BizFinder Voice QA — operator dashboard")

    suites = sorted(
        (p for p in _suites_dir().glob("suite_*") if p.is_dir()),
        key=lambda p: p.name,
        reverse=True,
    )
    if not suites:
        st.warning("No suites yet. Run `uv run python -m scripts.run_suite` first.")
        return

    suite_label = st.sidebar.selectbox("Suite", [p.name for p in suites])
    suite_dir = next(p for p in suites if p.name == suite_label)
    suite_json = suite_dir / "suite.json"
    if not suite_json.exists():
        st.error(f"No suite.json in {suite_dir}")
        return

    data = json.loads(suite_json.read_text(encoding="utf-8"))
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total", data["n_total"])
    col2.metric("Passed", data["n_passed"])
    col3.metric("Failed", data["n_failed"])
    col4.metric("Errors", data["n_errors"])
    col5.metric("Avg score", f"{data['avg_overall_score']:.2f}")

    st.caption(f"{data['started_at']} → {data['finished_at']}")
    st.write(f"_{data['business_summary']}_")

    for c in data["calls"]:
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


if __name__ == "__main__":
    main()
