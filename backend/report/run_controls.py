"""Pure helpers for the Run-suite page (C5).

Streamlit-free so they can be unit-tested. They translate the page's form inputs
into ``job_manager.start_job`` kwargs and map job status to a display badge.
"""

from __future__ import annotations

_BADGES = {
    "queued": "🟡 queued",
    "running": "🔵 running",
    "done": "🟢 done",
    "error": "🔴 error",
}

# Scenario-selection modes shown in the UI.
MODE_ALL = "All"
MODE_FIRST_N = "First N"
MODE_IDS = "Specific ids"
MODES = (MODE_ALL, MODE_FIRST_N, MODE_IDS)


def status_badge(status: str) -> str:
    """Map a job status to an emoji badge (falls back to the raw status)."""
    return _BADGES.get(status, f"⚪ {status}")


def build_start_kwargs(
    *,
    dry_run: bool,
    mode: str,
    max_n: int | None,
    ids: list[str] | None,
    suite_version: str,
    headless: bool,
    audio_judge: bool,
    site: str | None,
) -> dict:
    """Normalize form inputs into ``start_job`` keyword arguments.

    ``mode`` selects scenario scope: all of them, the first N, or a specific id
    list. Only the field relevant to the chosen mode is forwarded.
    """
    kwargs: dict = {
        "dry_run": bool(dry_run),
        "suite_version": (suite_version or "v1.0").strip(),
        "headless": bool(headless),
        "audio_judge": bool(audio_judge),
        "site_id": (site or "").strip() or None,
        "ids": None,
        "max_n": None,
    }
    if mode == MODE_FIRST_N:
        kwargs["max_n"] = int(max_n) if max_n else None
    elif mode == MODE_IDS:
        kwargs["ids"] = list(ids) if ids else None
    return kwargs
