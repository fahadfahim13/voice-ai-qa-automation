"""Integration: the C8 smoke test passes against the live QA Read API.

Skipped when ``QA_SHARED_SECRET`` is unavailable (mirrors test_qa_health.py).
"""

from __future__ import annotations

import pytest

from backend.settings import get_settings
from scripts.qa_smoke_test import run_smoke


def _secret_available() -> bool:
    try:
        return bool(get_settings().qa_shared_secret)
    except Exception:
        return False


@pytest.mark.live
@pytest.mark.skipif(not _secret_available(), reason="QA_SHARED_SECRET not configured")
def test_smoke_live_all_green():
    result = run_smoke()
    assert result.ok, [(c.name, c.detail) for c in result.checks]
    gate = next(c for c in result.checks if "auth gate" in c.name)
    assert gate.ok and gate.detail == "AUTH GATE OK"
