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

MIN_PASSWORD_LEN = 8
_LOGOUT_KEY = "logged_out"  # forces signed-out state while the cookie delete settles
_CM_KEY = "_auth_cm"  # the cookie manager, shared into the auth pages for one run
_PAGES_KEY = "_auth_pages"  # {"login": st.Page, "signup": st.Page} for switch/links
_SIGNUP_DONE_KEY = "_signup_done"  # show "account created — sign in" on the login page


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


# --------------------------------------------------------------------------- #
# self-service registration + profile (no Streamlit import — unit-testable)
# --------------------------------------------------------------------------- #
def register_user(
    email: str, password: str, *, name: str | None = None, session=None
) -> User | None:
    """Create a new active user. Returns the ``User`` or ``None`` if the email is taken.

    Caller is responsible for input validation (length, confirm, format); this
    only enforces uniqueness of the (lower-cased) email.
    """
    email = (email or "").strip().lower()

    def _do(s) -> User | None:
        if s.scalars(select(User).where(User.email == email)).first():
            return None
        user = User(
            email=email,
            password_hash=hash_password(password),
            name=(name or "").strip() or None,
        )
        s.add(user)
        s.flush()  # populate user.id before the session closes
        return user

    if session is not None:
        return _do(session)
    with get_session() as s:
        return _do(s)


def change_password(
    email: str, current_password: str, new_password: str, *, session=None
) -> bool:
    """Set a new password after verifying the current one. ``False`` if it doesn't match."""
    email = (email or "").strip().lower()

    def _do(s) -> bool:
        user = s.scalars(select(User).where(User.email == email)).first()
        if not user or not verify_password(current_password, user.password_hash):
            return False
        user.password_hash = hash_password(new_password)
        return True

    if session is not None:
        return _do(session)
    with get_session() as s:
        return _do(s)


def update_profile(email: str, *, name: str | None = None, session=None) -> User | None:
    """Update editable profile fields (display name). Returns the user or ``None``."""
    email = (email or "").strip().lower()

    def _do(s) -> User | None:
        user = s.scalars(select(User).where(User.email == email)).first()
        if not user:
            return None
        user.name = (name or "").strip() or None
        return user

    if session is not None:
        return _do(session)
    with get_session() as s:
        return _do(s)


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
    # The cookie manager's delete is async: right after logout the stale cookie can
    # still be read on the next rerun and silently re-auth the user. A session flag
    # forces the signed-out state until a fresh login clears it.
    if st.session_state.get(_LOGOUT_KEY):
        token = None
    else:
        token = st.session_state.get(_TOKEN_KEY) or cm.get(_COOKIE_NAME)
    claims = decode_token(token)
    if claims:
        user = _active_user(claims.get("sub"))
        if user:
            # Persist the resolved token so downstream pages (e.g. Profile) can read it.
            st.session_state[_TOKEN_KEY] = token
            st.sidebar.caption(f"Signed in as **{user.name or user.email}**")
            if st.sidebar.button("Log out"):
                _logout(st, cm)
            return user

    # Not authenticated → path-based /login + /signup pages (URL reflects the page).
    _run_auth_nav(st, cm)
    st.stop()


def _run_auth_nav(st, cm) -> None:
    """Render the unauthenticated app: separate ``/login`` and ``/signup`` URLs.

    Uses ``st.navigation`` so the browser URL changes between the two pages and so
    logout / post-signup redirects move the URL to the login page. The cookie
    manager + page handles are stashed in session_state for this run so the page
    callables (which take no args) can reach them.
    """
    # A bare default page at "/" immediately redirects to "/login" so the login page
    # has a real /login URL (Streamlit always serves the *default* page at root).
    root_pg = st.Page(_root_redirect, title="BizFinder Voice QA", url_path="home", default=True)
    login_pg = st.Page(_login_page, title="Sign in", url_path="login")
    pages = [root_pg, login_pg]
    signup_pg = None
    if get_settings().allow_signup:
        signup_pg = st.Page(_signup_page, title="Create account", url_path="signup")
        pages.append(signup_pg)
    st.session_state[_CM_KEY] = cm
    st.session_state[_PAGES_KEY] = {"login": login_pg, "signup": signup_pg}
    st.navigation(pages, position="hidden").run()


def _root_redirect() -> None:
    import streamlit as st  # lazy

    login_pg = (st.session_state.get(_PAGES_KEY) or {}).get("login")
    if login_pg is not None:
        st.switch_page(login_pg)


def _login_page() -> None:
    import streamlit as st  # lazy

    _render_login(st, st.session_state[_CM_KEY])


def _signup_page() -> None:
    import streamlit as st  # lazy

    _render_signup(st, st.session_state[_CM_KEY])


def _complete_login(st, cm, user: User) -> None:
    """Issue a token, persist it (session + cookie), and rerun into the app."""
    st.session_state.pop(_LOGOUT_KEY, None)  # a fresh login overrides a prior logout
    tok = create_access_token(user.email)
    st.session_state[_TOKEN_KEY] = tok
    expires = datetime.now(UTC) + timedelta(minutes=get_settings().jwt_access_minutes)
    cm.set(_COOKIE_NAME, tok, expires_at=expires, key="qa_auth_set")
    st.rerun()


def _logout(st, cm) -> None:
    """Sign out: clear the session token + the auth cookie, then rerun to /login.

    Two things are deliberate, both learned from breaking it:
    - **No ``st.switch_page`` here.** It raises a rerun immediately and interrupts the
      cookie ``delete`` before it flushes, so the cookie would survive a refresh and
      silently re-authenticate the user. Plain ``st.rerun`` lets the delete land; the
      existing root-redirect page then moves the URL to ``/login``.
    - **``delete`` only — no overwrite-with-expired ``set``.** The cookie manager's
      ``set`` re-creates the cookie, which defeats the ``delete``.
    """
    st.session_state[_LOGOUT_KEY] = True
    st.session_state.pop(_TOKEN_KEY, None)
    try:
        cm.delete(_COOKIE_NAME, key="qa_auth_del")
    except Exception:
        pass  # cookie may already be absent; the _LOGOUT_KEY flag still forces logout
    st.rerun()


def _render_login(st, cm) -> None:
    st.title("🔐 BizFinder Voice QA — Sign in")
    if st.session_state.pop(_SIGNUP_DONE_KEY, None):
        st.success("Account created — please sign in.")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        user = authenticate(email, password)
        if user:
            _complete_login(st, cm, user)
        st.error("Invalid email or password.")
    signup_pg = (st.session_state.get(_PAGES_KEY) or {}).get("signup")
    if signup_pg is not None:
        st.caption("Don't have an account?")
        st.page_link(signup_pg, label="Create an account →")


def _render_signup(st, cm) -> None:
    st.title("🔐 BizFinder Voice QA — Create account")
    with st.form("signup_form"):
        name = st.text_input("Display name (optional)")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create account")
    pages = st.session_state.get(_PAGES_KEY) or {}
    if submitted:
        err = signup_error(email, password, confirm)
        if err:
            st.error(err)
        elif register_user(email, password, name=name) is None:
            st.error("An account with that email already exists.")
        else:
            # No auto-login: flag a success message and redirect the URL to /login.
            st.session_state[_SIGNUP_DONE_KEY] = True
            if pages.get("login") is not None:
                st.switch_page(pages["login"])
            st.rerun()
    if pages.get("login") is not None:
        st.caption("Already have an account?")
        st.page_link(pages["login"], label="← Back to sign in")


def signup_error(email: str, password: str, confirm: str) -> str | None:
    """Validate signup inputs. Returns an error message, or ``None`` if valid (pure)."""
    email = (email or "").strip()
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return "Enter a valid email address."
    if len(password) < MIN_PASSWORD_LEN:
        return f"Password must be at least {MIN_PASSWORD_LEN} characters."
    if password != confirm:
        return "Passwords don't match."
    return None


def current_user() -> User | None:
    """The signed-in user from the session token — for pages rendered after the gate."""
    import streamlit as st  # lazy

    claims = decode_token(st.session_state.get(_TOKEN_KEY))
    return _active_user(claims.get("sub")) if claims else None


def require_password():
    """Deprecated C8 shim — now delegates to the per-user gate."""
    return require_auth()
