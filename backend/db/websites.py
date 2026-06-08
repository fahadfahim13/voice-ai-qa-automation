"""Website -> siteId mapping helpers (C10).

Operators target a **website** (URL/hostname); the internal ``siteId`` is resolved
by the widget at call time and cached back onto the row afterwards. Streamlit-free
so it's unit-testable with the ``test_db`` fixture. All DB access goes through
``get_session()`` so commit/rollback is handled centrally; the engine uses
``expire_on_commit=False`` so returned instances stay usable after the session
closes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import select

from backend.db.engine import get_session
from backend.db.models import Website


def normalize_url(url: str) -> str:
    """Canonicalize an operator-entered website to a comparable host key.

    Rules: strip whitespace; prepend ``//`` when no scheme is present so
    ``urlparse`` populates ``netloc`` (not ``path``); lowercase the host; drop
    userinfo/port/path/query/fragment; strip a single leading ``www.``.

    ``webwaala.com``, ``https://www.webwaala.com/``, ``WebWaala.com`` all map to
    ``webwaala.com``. This matches how ``build_preview_url(base, site)`` already
    uses the bare host. Raises ``ValueError`` on empty/unparseable input.
    """
    raw = (url or "").strip()
    if not raw:
        raise ValueError("empty website url")
    if "://" not in raw:
        raw = "//" + raw  # let urlparse treat it as netloc, not path
    host = (urlparse(raw).hostname or "").lower()
    if not host:
        raise ValueError(f"could not parse host from {url!r}")
    if host.startswith("www."):
        host = host[4:]
    return host


def get_or_create(url: str) -> Website:
    """Return the Website for ``url`` (normalized), creating it if absent.

    Bumps ``last_used_at``. ``s.flush()`` populates ``id``/defaults before the
    session closes so the detached instance is usable.
    """
    key = normalize_url(url)
    with get_session() as s:
        row = s.scalar(select(Website).where(Website.url == key))
        if row is None:
            row = Website(url=key)
            s.add(row)
        row.last_used_at = datetime.now(UTC)
        s.flush()
        return row


def upsert_website(url: str, site_id: str | None = None) -> Website:
    """get_or_create + set ``site_id`` when a non-empty value is given."""
    key = normalize_url(url)
    sid = (site_id or "").strip() or None
    with get_session() as s:
        row = s.scalar(select(Website).where(Website.url == key))
        if row is None:
            row = Website(url=key)
            s.add(row)
        if sid:
            row.site_id = sid
        row.last_used_at = datetime.now(UTC)
        s.flush()
        return row


def set_site_id(url: str, site_id: str) -> None:
    """Write back a resolved internal siteId. No-op on empty ``site_id``.

    Tolerant: creates the row if it was never persisted (shouldn't happen in the
    normal flow) so the mapping is still captured.
    """
    sid = (site_id or "").strip()
    if not sid:
        return
    key = normalize_url(url)
    with get_session() as s:
        row = s.scalar(select(Website).where(Website.url == key))
        if row is None:
            row = Website(url=key, site_id=sid)
            s.add(row)
        else:
            row.site_id = sid
        row.last_used_at = datetime.now(UTC)


def list_websites() -> list[Website]:
    """All websites, most-recently-used first — drives the form dropdown."""
    with get_session() as s:
        rows = s.scalars(select(Website).order_by(Website.last_used_at.desc())).all()
        return list(rows)
