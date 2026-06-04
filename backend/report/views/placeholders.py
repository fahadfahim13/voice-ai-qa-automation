"""Placeholder pages for the multipage shell.

Each later card replaces one of these stubs with a real page. They exist now
so the left nav shows the full surface from C0 onward.
"""

from __future__ import annotations

import streamlit as st  # type: ignore


def render_scenarios() -> None:
    st.title("Scenarios")
    st.info("Coming in card C4.")


def render_run_suite() -> None:
    st.title("Run suite")
    st.info("Coming in cards C5/C6.")


def render_rerun() -> None:
    st.title("Re-run")
    st.info("Coming in card C7.")
