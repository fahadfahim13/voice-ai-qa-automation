"""Pure helpers for the Run-suite page (C5, use case 4d).

Streamlit-free so they can be unit-tested. ``form_to_job_kwargs`` is the seam
between the page form and ``job_manager.start_job`` — it resolves the scenario
selection (incl. "By intent" → ids) and normalizes the other fields.
"""

from __future__ import annotations

from collections.abc import Iterable

from backend.scenarios import Scenario, load_library

_BADGES = {
    "queued": "🟡 queued",
    "running": "🔵 running",
    "done": "🟢 done",
    "error": "🔴 error",
}

# Scenario-selection modes shown in the UI.
MODE_ALL = "All"
MODE_BY_INTENT = "By intent"
MODE_SPECIFIC = "Specific"
MODES = (MODE_ALL, MODE_BY_INTENT, MODE_SPECIFIC)


def status_badge(status: str) -> str:
    """Map a job status to an emoji badge (falls back to the raw status)."""
    return _BADGES.get(status, f"⚪ {status}")


def is_dry_run(argv: list[str] | None) -> bool:
    """True when a job was launched as a dry run (``--dry-run`` in its argv).

    Used by the Run page to explain a 0-call dry-run result instead of showing
    bare ``Total 0`` metrics that read like a failure.
    """
    return "--dry-run" in (argv or [])


def form_to_job_kwargs(selection: dict, scenarios: Iterable[Scenario] | None = None) -> dict:
    """Map the Run-suite form ``selection`` to ``start_job`` kwargs.

    ``selection`` keys: ``mode`` (All/By intent/Specific), ``intent``, ``ids``,
    ``site_id``, ``suite_version``, ``headless``, ``audio_judge``, ``max_n``.

    "By intent" resolves to the scenario ids of that intent from the library.
    ``dry_run`` is intentionally NOT included here — the caller passes it to
    ``start_job`` separately.
    """
    mode = selection.get("mode", MODE_ALL)
    ids: list[str] | None = None
    if mode == MODE_BY_INTENT:
        scs = list(scenarios) if scenarios is not None else load_library()
        wanted = selection.get("intent")
        ids = [s.id for s in scs if s.intent.value == wanted]
    elif mode == MODE_SPECIFIC:
        ids = list(selection.get("ids") or []) or None

    return {
        "ids": ids,
        "max_n": selection.get("max_n") or None,
        "site_id": (selection.get("site_id") or "").strip() or None,
        "suite_version": (selection.get("suite_version") or "v1.0").strip() or "v1.0",
        "headless": bool(selection.get("headless", True)),
        "audio_judge": bool(selection.get("audio_judge", False)),
    }
