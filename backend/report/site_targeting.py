"""siteId targeting helpers for the Run page (C6, use case 4e).

Pure-ish, Streamlit-free helpers:
- ``validate_site_id`` probes the QA Read API to tell the operator whether a
  siteId is known / has no traffic yet / is unreachable (never raises into the UI).
- recently-used siteIds persistence under the reports dir.
- ``url_to_site_id`` — the *stretch* arbitrary-URL → siteId resolver, guarded
  behind an admin token and a mockable HTTP call (exact admin contract TBD).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx

from backend.qa_api import QaApiClient
from backend.settings import get_settings

# Known siteIds offered in the picker (free-text is always allowed too).
KNOWN_SITE_IDS = ("qa-judge", "fftechsaas.xyz-preview")

ADMIN_TOKEN_ENV = "BIZFINDER_ADMIN_TOKEN"
ADMIN_BASE_URL_ENV = "BIZFINDER_ADMIN_BASE_URL"

_RECENT_MAX = 10


# --------------------------------------------------------------------------- #
# siteId validation
# --------------------------------------------------------------------------- #
def _fetch_conversations(site_id: str, limit: int = 1) -> list:
    """Fetch up to ``limit`` conversation rows for a siteId (sync wrapper)."""

    async def _run() -> list:
        async with QaApiClient() as client:
            page = await client.list_conversations(site_id=site_id, limit=limit)
        return page.conversations

    return asyncio.run(_run())


def validate_site_id(site_id: str) -> dict:
    """Probe the QA API for a siteId. Never raises.

    Returns one of:
      ``{"status": "known", "count": n}``      — has traffic
      ``{"status": "no_traffic"}``             — reachable, no conversations yet
      ``{"status": "unreachable", "error": s}`` — API/network error
      ``{"status": "empty"}``                  — blank siteId
    """
    if not (site_id or "").strip():
        return {"status": "empty"}
    try:
        convs = _fetch_conversations(site_id.strip())
    except Exception as exc:  # never bubble into the UI
        return {"status": "unreachable", "error": str(exc)}
    return {"status": "known", "count": len(convs)} if convs else {"status": "no_traffic"}


# --------------------------------------------------------------------------- #
# recently-used siteIds (persisted under reports/)
# --------------------------------------------------------------------------- #
def _recent_path() -> Path:
    return get_settings().harness_reports_dir / "recent_site_ids.json"


def recent_site_ids() -> list[str]:
    path = _recent_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [s for s in data if isinstance(s, str)] if isinstance(data, list) else []


def remember_site_id(site_id: str) -> None:
    site_id = (site_id or "").strip()
    if not site_id:
        return
    items = [site_id] + [s for s in recent_site_ids() if s != site_id]
    items = items[:_RECENT_MAX]
    path = _recent_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# stretch: arbitrary URL -> siteId (guarded, mockable)
# --------------------------------------------------------------------------- #
def admin_scan_available() -> bool:
    """True when an admin token is configured (gates the URL-scan control)."""
    return bool(os.getenv(ADMIN_TOKEN_ENV))


def _post_scan(url: str, token: str, base_url: str) -> dict:
    """POST to the main app's admin scan endpoint. Mockable seam.

    NOTE: the exact contract (path, auth header, request/response shape) is TBD
    from the main-app owner; this is a best-effort stub kept behind a mock.
    """
    resp = httpx.post(
        f"{base_url.rstrip('/')}/api/admin/businesses/scan",
        json={"url": url},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def url_to_site_id(url: str) -> dict:
    """Resolve an arbitrary website URL to a siteId via the admin scan. Never raises.

    Returns ``{"site_id": <id>}`` on success or ``{"error": <msg>}`` otherwise.
    """
    token = os.getenv(ADMIN_TOKEN_ENV)
    if not token:
        return {"error": f"admin access not configured (set {ADMIN_TOKEN_ENV})"}
    base = os.getenv(ADMIN_BASE_URL_ENV) or get_settings().qa_base_url
    try:
        data = _post_scan(url, token, base)
    except Exception as exc:
        return {"error": str(exc)}
    site_id = data.get("siteId") or data.get("site_id")
    if not site_id:
        return {"error": "scan returned no siteId"}
    return {"site_id": site_id}
