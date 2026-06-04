"""Shared data-loading layer for the operator dashboard.

Pure, sync helpers used by every dashboard page. Nothing here renders UI;
nothing here raises into the UI — callers can trust the return shapes.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from backend.qa_api.client import QaApiClient
from backend.settings import get_settings


def _suites_dir() -> Path:
    return get_settings().harness_reports_dir


def list_suites() -> list[Path]:
    """Suite directories under the reports dir, newest first.

    Returns ``[]`` when the reports dir does not exist yet.
    """
    root = _suites_dir()
    if not root.exists():
        return []
    return sorted(
        (p for p in root.glob("suite_*") if p.is_dir()),
        key=lambda p: p.name,
        reverse=True,
    )


def load_suite(suite_dir: Path) -> dict:
    """Parse ``suite.json`` from a suite dir, tolerant of missing keys.

    Returns ``{}`` when ``suite.json`` is absent or unreadable. Optional keys
    are filled with sane defaults so callers can index without guarding.
    """
    suite_json = Path(suite_dir) / "suite.json"
    if not suite_json.exists():
        return {}
    try:
        data = json.loads(suite_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}

    data.setdefault("started_at", "")
    data.setdefault("finished_at", "")
    data.setdefault("business_summary", "")
    data.setdefault("n_total", 0)
    data.setdefault("n_passed", 0)
    data.setdefault("n_failed", 0)
    data.setdefault("n_errors", 0)
    data.setdefault("avg_overall_score", 0.0)
    data.setdefault("calls", [])
    return data


def qa_health() -> dict:
    """Probe the QA Read API health endpoint.

    Returns ``{"ok": True}`` on success or ``{"ok": False, "error": <msg>}``
    on any failure. Never raises — safe to call straight from a UI widget.
    """

    async def _probe() -> dict:
        async with QaApiClient() as client:
            health = await client.health()
        return {"ok": bool(health.ok)}

    try:
        return asyncio.run(_probe())
    except Exception as exc:  # never raise into the UI
        return {"ok": False, "error": str(exc)}
