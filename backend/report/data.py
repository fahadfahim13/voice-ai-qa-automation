"""Shared data-loading layer for the operator dashboard.

Pure, sync helpers used by every dashboard page. Nothing here renders UI;
nothing here raises into the UI — callers can trust the return shapes.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
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


def suite_label(name: str) -> str:
    """Human-friendly label for a suite dir name.

    ``suite_20260604T145443Z_45fad09c`` -> ``2026-06-04 14:54 · 45fad09c``.
    Falls back to the raw name when it doesn't match the expected shape, so the
    picker never breaks on an unexpected folder.
    """
    body = name[len("suite_"):] if name.startswith("suite_") else name
    ts_part, _, short_id = body.partition("_")
    try:
        ts = datetime.strptime(ts_part, "%Y%m%dT%H%M%SZ")
    except ValueError:
        return name
    label = ts.strftime("%Y-%m-%d %H:%M")
    return f"{label} · {short_id}" if short_id else label


def list_loaded_suites() -> list[tuple[Path, dict]]:
    """``(dir, suite_dict)`` for every suite with a readable ``suite.json``.

    Newest first. Directories without a readable ``suite.json`` — e.g. a run still
    in progress (the dir is created before ``suite.json`` is written) or an aborted
    run — are skipped, so callers never see a half-written suite.
    """
    return [(p, s) for p in list_suites() if (s := load_suite(p))]


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
    data.setdefault("suite_version", "unversioned")
    data.setdefault("scenario_set_hash", "")
    data.setdefault("provider_snapshot", {})
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
