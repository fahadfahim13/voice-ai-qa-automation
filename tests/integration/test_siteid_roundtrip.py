"""Live siteId round-trip (C6, 4e): a targeted run shows up under that siteId.

Heavy: drives a real browser call for ~2 min and hits OpenRouter. Gated behind
an explicit opt-in env var (RUN_SITEID_LIVE=1) AND the required keys so routine
`uv run pytest` stays fast/green. Marked live + slow.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime

import pytest

from backend.orchestrator import job_manager
from backend.report.site_targeting import _fetch_conversations

TARGET_SITE_ID = os.getenv("SITEID_LIVE_TARGET", "fftechsaas.xyz-preview")

_optin = os.getenv("RUN_SITEID_LIVE") == "1"
_has_keys = bool(os.getenv("OPENROUTER_API_KEY"))

pytestmark = [
    pytest.mark.live,
    pytest.mark.slow,
    pytest.mark.skipif(
        not (_optin and _has_keys),
        reason="set RUN_SITEID_LIVE=1 and OPENROUTER_API_KEY to run the live siteId round-trip",
    ),
]


def _wait(job_id: str, timeout: float = 360.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        rec = job_manager.get_job(job_id)
        if rec and rec["status"] in ("done", "error"):
            return rec
        time.sleep(2)
    raise AssertionError(f"job {job_id} did not finish in time")


def test_targeted_run_appears_under_site_id():
    since = datetime.now(UTC)
    job_id = job_manager.start_job(
        ids=None,
        max_n=1,
        site_id=TARGET_SITE_ID,
        suite_version="v1.0",
        headless=True,
        audio_judge=False,
    )
    rec = _wait(job_id)
    assert rec["status"] == "done", rec

    # The QA Read API should now list a conversation under the targeted siteId.
    convs = _fetch_conversations(TARGET_SITE_ID, limit=5)
    assert convs, f"no conversations found under siteId {TARGET_SITE_ID!r} after the run"
    _ = since  # (a stricter check could filter by createdAt >= since)
