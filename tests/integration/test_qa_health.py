"""Integration test: dashboard data layer against the live QA Read API.

Marked ``live`` — hits bizfinder.ai and needs a valid QA_SHARED_SECRET. The
underlying QaApiClient rate-limits to 1 req/s, so the 1 req/s cadence is honored
automatically.
"""

from __future__ import annotations

import pytest

from backend.report import data
from backend.settings import get_settings


def _secret_available() -> bool:
    try:
        return bool(get_settings().qa_shared_secret)
    except Exception:
        return False


@pytest.mark.live
@pytest.mark.skipif(not _secret_available(), reason="QA_SHARED_SECRET not configured")
def test_qa_health_live():
    result = data.qa_health()
    assert result == {"ok": True}
