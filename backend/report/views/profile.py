"""Profile page — the signed-in user edits their display name and password.

Reads the current user from the session token (set by ``auth.require_auth``) via
``auth.current_user``. All mutations go through the pure helpers in
``backend.report.auth`` (``update_profile`` / ``change_password``), so the page
stays a thin Streamlit shell.
"""

from __future__ import annotations

import streamlit as st  # type: ignore

from backend.report import auth


def render() -> None:
    st.title("👤 Profile")

    user = auth.current_user()
    if not user:
        st.warning("You're not signed in.")
        return

    st.caption(f"Login email: **{user.email}**")

    # --- Display name -------------------------------------------------------
    with st.form("profile_form"):
        name = st.text_input("Display name", value=user.name or "")
        saved = st.form_submit_button("Save profile")
    if saved:
        auth.update_profile(user.email, name=name)
        st.success("Profile updated.")
        st.rerun()

    st.divider()

    # --- Change password ----------------------------------------------------
    st.subheader("Change password")
    with st.form("password_form"):
        current = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password")
        confirm = st.text_input("Confirm new password", type="password")
        changed = st.form_submit_button("Change password")
    if changed:
        if len(new) < auth.MIN_PASSWORD_LEN:
            st.error(f"New password must be at least {auth.MIN_PASSWORD_LEN} characters.")
        elif new != confirm:
            st.error("New passwords don't match.")
        elif auth.change_password(user.email, current, new):
            st.success("Password changed.")
        else:
            st.error("Current password is incorrect.")
