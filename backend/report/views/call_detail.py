"""Shared per-call detail renderer.

The per-call expander originally lived inline in the Overview view (C0). It is
extracted here so the Reports drill-in (C3) reuses the exact same rendering
instead of duplicating it. Renders a single `st.expander`, so callers must invoke
it at the top level (Streamlit forbids nesting expanders).
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st  # type: ignore


def render_call(c: dict) -> None:
    v = c.get("text_verdict") or {}
    status = "🟢 PASS" if v.get("pass_fail") else ("🔴 FAIL" if v else "🟠 ERROR/EMPTY")
    score = f"{v.get('overall_score', 0):.2f}" if v else "—"
    artifacts = c.get("artifacts") or {}
    with st.expander(f"{status}  ·  {c.get('scenario_id', '—')}  ·  overall {score}"):
        st.caption(
            f"elapsed {c.get('elapsed_seconds', 0):.1f}s · "
            f"session {artifacts.get('session_id') or '—'}"
        )
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
        bot_audio = artifacts.get("bot_audio")
        if bot_audio and Path(bot_audio).exists():
            st.audio(bot_audio)
