"""Streamlit operator dashboard — multipage shell.

Run:
    uv run --extra report streamlit run backend/report/dashboard.py

This module is the nav entrypoint. Each page lives under
``backend/report/views/`` and the shared data layer is ``backend/report/data``.
"""

from __future__ import annotations

import streamlit as st  # type: ignore

from backend.report import data
from backend.report.auth import require_auth
from backend.report.nav import PageSpec, visible_specs
from backend.report.theme import inject_theme
from backend.report.views import overview, profile, reports, rerun_page, run, scenarios
from backend.settings import get_settings


def _render_health_badge() -> None:
    health = data.qa_health()
    if health.get("ok"):
        st.sidebar.success("🟢 QA API: healthy")
    else:
        st.sidebar.error(f"🔴 QA API: {health.get('error', 'unreachable')}")


def _page_specs() -> list[PageSpec]:
    """All dashboard pages; Run/Re-run require live-run (browser) capability."""
    return [
        PageSpec(overview.render, "Overview", "📊", "overview", default=True),
        PageSpec(reports.render, "Reports", "📄", "reports"),
        PageSpec(scenarios.render, "Scenarios", "🧪", "scenarios"),
        PageSpec(run.render, "Run suite", "▶️", "run-suite", requires_runs=True),
        PageSpec(rerun_page.render, "Re-run", "🔁", "re-run", requires_runs=True),
        PageSpec(profile.render, "Profile", "👤", "profile"),
    ]


def main() -> None:
    st.set_page_config(page_title="BizFinder Voice QA", layout="wide")
    inject_theme()  # premium look (CSS only — no behaviour change)

    require_auth()  # per-user login gate (renders login form + owns sidebar user/logout)

    _render_health_badge()

    runs_enabled = get_settings().harness_runs_enabled
    if not runs_enabled:
        st.info(
            "Live runs are disabled on this host (pending Chromium system libs). "
            "Reporting is available."
        )

    specs = visible_specs(_page_specs(), runs_enabled=runs_enabled)
    pages = [
        st.Page(s.view, title=s.title, icon=s.icon, url_path=s.url_path, default=s.default)
        for s in specs
    ]
    st.navigation(pages).run()


if __name__ == "__main__":
    main()
