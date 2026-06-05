"""Per-user authentication for the operator dashboard (C9).

Standard, boring building blocks:
- passwords are hashed with **bcrypt** (passlib ``CryptContext``),
- access tokens are **PyJWT HS256** signed with ``settings.jwt_secret``,
- users live in the SQLite ``users`` table (``backend.db``),
- the login token is kept in a browser **cookie** so a refresh keeps you signed in.

The pure helpers (hash/verify/token/authenticate) import no Streamlit, so they are
unit-testable headless. ``require_auth`` is the Streamlit gate and imports
``streamlit`` + the cookie manager lazily. ``require_password`` is a deprecated C8
shim that now delegates to ``require_auth``.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import jwt
from loguru import logger
from passlib.context import CryptContext
from sqlalchemy import func, select

from backend.db import User, get_session, init_db
from backend.settings import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Used only when JWT_SECRET is unset — tokens then last only for this process.
_EPHEMERAL_SECRET = secrets.token_urlsafe(32)

_TOKEN_KEY = "auth_token"
_COOKIE_NAME = "qa_auth"


def _secret() -> str:
    return get_settings().jwt_secret or _EPHEMERAL_SECRET


# --------------------------------------------------------------------------- #
# password hashing
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd.verify(password, password_hash)
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def create_access_token(sub: str, *, expires_minutes: int | None = None) -> str:
    mins = get_settings().jwt_access_minutes if expires_minutes is None else expires_minutes
    now = datetime.now(UTC)
    payload = {"sub": sub, "iat": now, "exp": now + timedelta(minutes=mins)}
    return jwt.encode(payload, _secret(), algorithm="HS256")


def decode_token(token: str | None) -> dict | None:
    """Verify signature + expiry; return claims or ``None`` (never raises)."""
    if not token:
        return None
    try:
        return jwt.decode(token, _secret(), algorithms=["HS256"])
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# users
# --------------------------------------------------------------------------- #
def authenticate(email: str, password: str, *, session=None) -> User | None:
    """Active user matching email (case-insensitive) + password, else ``None``."""
    email = (email or "").strip().lower()
    if not email or not password:
        return None
    if session is not None:
        return _authenticate(session, email, password)
    with get_session() as s:
        return _authenticate(s, email, password)


def _authenticate(session, email: str, password: str) -> User | None:
    user = session.scalars(select(User).where(User.email == email)).first()
    if user and user.is_active and verify_password(password, user.password_hash):
        return user
    return None


def _active_user(email: str | None) -> User | None:
    if not email:
        return None
    with get_session() as s:
        return s.scalars(
            select(User).where(User.email == email.strip().lower(), User.is_active.is_(True))
        ).first()


def seed_admin_if_empty() -> None:
    """If there are zero users and ADMIN_EMAIL/ADMIN_PASSWORD are set, create one."""
    s = get_settings()
    if not (s.admin_email and s.admin_password):
        return
    email = s.admin_email.strip().lower()
    with get_session() as session:
        if session.scalar(select(func.count()).select_from(User)):
            return
        session.add(User(email=email, password_hash=hash_password(s.admin_password)))
    logger.info("Seeded initial admin user {} from ADMIN_EMAIL.", email)  # never log the password


# --------------------------------------------------------------------------- #
# Streamlit gate
# --------------------------------------------------------------------------- #
def _cookie_manager(st):
    import extra_streamlit_components as stx  # lazy: Streamlit-only dependency

    return stx.CookieManager(key="qa_auth_cm")


def require_auth():
    """Gate the whole app behind a valid login. Returns the signed-in ``User``.

    Call once at the top of ``main()``. Renders the login form (and ``st.stop()``)
    until a valid token is present in the cookie or session.
    """
    import streamlit as st  # lazy

    init_db()
    seed_admin_if_empty()
    if not get_settings().jwt_secret:
        st.sidebar.warning("⚠ JWT_SECRET not set — tokens won't survive a restart.")

    cm = _cookie_manager(st)
    token = st.session_state.get(_TOKEN_KEY) or cm.get(_COOKIE_NAME)
    claims = decode_token(token)
    if claims:
        user = _active_user(claims.get("sub"))
        if user:
            st.sidebar.caption(f"Signed in as **{user.email}**")
            if st.sidebar.button("Log out"):
                st.session_state.pop(_TOKEN_KEY, None)
                cm.delete(_COOKIE_NAME, key="qa_auth_del")
                st.rerun()
            return user

    # Not authenticated → login form.
    st.title("🔐 BizFinder Voice QA — sign in")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        user = authenticate(email, password)
        if user:
            tok = create_access_token(user.email)
            st.session_state[_TOKEN_KEY] = tok
            expires = datetime.now(UTC) + timedelta(minutes=get_settings().jwt_access_minutes)
            cm.set(_COOKIE_NAME, tok, expires_at=expires, key="qa_auth_set")
            st.rerun()
        st.error("Invalid email or password.")
    st.stop()


def require_password():
    """Deprecated C8 shim — now delegates to the per-user gate."""
    return require_auth()
