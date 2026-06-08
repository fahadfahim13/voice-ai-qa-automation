"""Pure navigation registry for the dashboard (C11).

Kept Streamlit-free so the page-gating logic is unit-testable headless. The
dashboard builds a list of :class:`PageSpec` (one per page), filters it through
:func:`visible_specs` based on whether live runs are enabled on this host, then
maps the survivors to ``st.Page`` objects.

Why gate pages: on the rootless ``analytics`` VPS, Chromium can't launch until an
ops root step installs its system libs, so the Run / Re-run pages (which trigger
live browser runs) are hidden in reporting-only mode (``HARNESS_RUNS_ENABLED=0``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class PageSpec:
    """A dashboard page declaration. ``view`` is the ``render()`` callable."""

    view: Callable[[], None]
    title: str
    icon: str
    url_path: str
    default: bool = False
    requires_runs: bool = False  # needs live-run capability (browser) → gated


def visible_specs(specs: list[PageSpec], *, runs_enabled: bool) -> list[PageSpec]:
    """Pages to show. When ``runs_enabled`` is false, drop run-only pages."""
    return [s for s in specs if runs_enabled or not s.requires_runs]
