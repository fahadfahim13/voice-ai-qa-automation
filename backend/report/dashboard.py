"""Streamlit operator dashboard — multipage shell.

Run:
    uv run --extra report streamlit run backend/report/dashboard.py

This module is the nav entrypoint. Each page lives under
``backend/report/views/`` and the shared data layer is ``backend/report/data``.
"""

from __future__ import annotations

import streamlit as st  # type: ignore

from backend.report import data
from backend.report.views import overview, placeholders, reports, scenarios


def _render_health_badge() -> None:
    health = data.qa_health()
    if health.get("ok"):
        st.sidebar.success("🟢 QA API: healthy")
    else:
        st.sidebar.error(f"🔴 QA API: {health.get('error', 'unreachable')}")


def main() -> None:
    st.set_page_config(page_title="BizFinder Voice QA", layout="wide")

    _render_health_badge()

    pages = [
        st.Page(overview.render, title="Overview", icon="📊", url_path="overview", default=True),
        st.Page(reports.render, title="Reports", icon="📄", url_path="reports"),
        st.Page(scenarios.render, title="Scenarios", icon="🧪", url_path="scenarios"),
        st.Page(placeholders.render_run_suite, title="Run suite", icon="▶️", url_path="run-suite"),
        st.Page(placeholders.render_rerun, title="Re-run", icon="🔁", url_path="re-run"),
    ]
    st.navigation(pages).run()


if __name__ == "__main__":
    main()
