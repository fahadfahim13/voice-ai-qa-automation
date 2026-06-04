"""End-to-end dry-run job: real subprocess, no keys, no browser.

Exercises the whole pipeline (start_job → subprocess → scripts.run_suite
--dry-run → suite.json) using a tmp reports dir so nothing pollutes the repo.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import backend.settings as settings_mod
from backend.orchestrator import job_manager


def _wait(job_id: str, timeout: float = 90.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        rec = job_manager.get_job(job_id)
        if rec and rec["status"] in ("done", "error"):
            return rec
        time.sleep(0.2)
    raise AssertionError(f"job {job_id} never finished: {job_manager.get_job(job_id)}")


def test_dry_run_job_writes_versioned_suite(tmp_path, monkeypatch):
    # Point both this process and the child subprocess at a tmp reports dir.
    monkeypatch.setenv("HARNESS_REPORTS_DIR", str(tmp_path))
    monkeypatch.setattr(settings_mod, "_settings", None)  # reset cached Settings

    job_id = job_manager.start_job(dry_run=True, suite_version="v1.0", audio_judge=False)
    rec = _wait(job_id)

    assert rec["status"] == "done", rec
    assert rec["returncode"] == 0

    # job artifacts exist
    assert (tmp_path / "jobs" / f"{job_id}.json").exists()
    assert (tmp_path / "jobs" / f"{job_id}.log").exists()

    # suite.json produced and carries the C1 version field
    suite_json = Path(rec["suite_dir"]) / "suite.json"
    assert suite_json.exists()
    data = json.loads(suite_json.read_text(encoding="utf-8"))
    assert data["suite_version"] == "v1.0"
    assert data["n_total"] == 0
    assert len(data["scenario_set_hash"]) == 64
