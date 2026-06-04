"""Integration: a dry-run job driven through form_to_job_kwargs (C5, 4d).

Keyless via C2's --dry-run path. Uses a tmp reports dir so nothing pollutes the
repo (same pattern as test_run_trigger_dryrun.py).
"""

from __future__ import annotations

import time
from pathlib import Path

import backend.settings as settings_mod
from backend.orchestrator import job_manager
from backend.report.run_form import MODE_SPECIFIC, form_to_job_kwargs
from backend.scenarios import load_library


def _wait(job_id: str, timeout: float = 90.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        rec = job_manager.get_job(job_id)
        if rec and rec["status"] in ("done", "error"):
            return rec
        time.sleep(0.2)
    raise AssertionError(f"job {job_id} never finished: {job_manager.get_job(job_id)}")


def test_dry_run_via_form_kwargs(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_REPORTS_DIR", str(tmp_path))
    monkeypatch.setattr(settings_mod, "_settings", None)  # reset cached Settings

    one_id = load_library()[0].id
    selection = {
        "mode": MODE_SPECIFIC,
        "ids": [one_id],
        "site_id": "qa-judge",
        "suite_version": "v1.0",
        "headless": True,
        "audio_judge": False,
        "max_n": None,
    }
    kwargs = form_to_job_kwargs(selection)

    job_id = job_manager.start_job(**kwargs, dry_run=True)
    rec = _wait(job_id)

    assert rec["status"] == "done", rec
    suite_json = Path(rec["suite_dir"]) / "suite.json"
    assert suite_json.exists()
