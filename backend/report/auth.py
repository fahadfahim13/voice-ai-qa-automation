"""Password gate for the operator dashboard (C8).

A deliberately simple shared-password gate — the hosting decision is "extend
Streamlit" (no main-app JWT), so the correct minimal gate is one secret read from
the environment (``DASHBOARD_PASSWORD``), which Coolify can inject on deploy.

``evaluate_access`` is pure and unit-tested; ``require_password`` is the Streamlit
wrapper that gates the whole app. When no password is configured the app stays
open (with a visible warning) so local dev isn't blocked.
"""

from __future__ import annotations

import streamlit as st  # type: ignore

from backend.settings import get_settings

# Sentinel returned by evaluate_access when no password is configured.
OPEN_NO_PASSWORD = "open"

_AUTHED_KEY = "dashboard_authed"


def evaluate_access(entered: str | None, configured: str) -> bool | str:
    """Pure access decision.

    - ``configured == ""`` → :data:`OPEN_NO_PASSWORD` (open with a warning).
    - otherwise → ``True`` iff ``entered`` matches ``configured``.
    """
    if not configured:
        return OPEN_NO_PASSWORD
    return entered == configured


def require_password() -> None:
    """Gate the whole app behind ``DASHBOARD_PASSWORD``.

    Call once at the top of ``main()`` (after ``st.set_page_config``). Halts the
    script with ``st.stop()`` until a correct password is entered. No password
    configured → show a warning banner and let the app load (local-use only).
    """
    configured = get_settings().dashboard_password
    if evaluate_access(None, configured) == OPEN_NO_PASSWORD:
        st.warning("⚠ No DASHBOARD_PASSWORD set — local use only; anyone can access.")
        return

    if st.session_state.get(_AUTHED_KEY):
        return

    st.title("🔒 BizFinder Voice QA")
    entered = st.text_input("Password", type="password")
    if not entered:
        st.stop()
    if evaluate_access(entered, configured) is True:
        st.session_state[_AUTHED_KEY] = True
        st.rerun()
    st.error("Incorrect password.")
    st.stop()
