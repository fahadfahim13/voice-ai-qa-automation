"""Unit tests for the background job manager (no real suite runs)."""

from __future__ import annotations

import sys
import time

from backend.orchestrator import job_manager


def _wait(job_id: str, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        rec = job_manager.get_job(job_id)
        if rec and rec["status"] in ("done", "error"):
            return rec
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} never finished: {job_manager.get_job(job_id)}")


def test_successful_job_transitions_to_done(tmp_path, monkeypatch):
    monkeypatch.setattr(job_manager, "_jobs_dir", lambda: tmp_path)
    monkeypatch.setattr(
        job_manager, "build_run_argv", lambda *a, **k: [sys.executable, "-c", "print('ok')"]
    )
    job_id = job_manager.start_job(dry_run=True)
    rec = _wait(job_id)
    assert rec["status"] == "done"
    assert rec["returncode"] == 0
    assert rec["error"] is None
    assert rec["finished_at"]


def test_failing_job_transitions_to_error(tmp_path, monkeypatch):
    monkeypatch.setattr(job_manager, "_jobs_dir", lambda: tmp_path)
    monkeypatch.setattr(
        job_manager,
        "build_run_argv",
        lambda *a, **k: [sys.executable, "-c", "import sys; sys.exit(3)"],
    )
    job_id = job_manager.start_job()
    rec = _wait(job_id)
    assert rec["status"] == "error"
    assert rec["returncode"] == 3
    assert rec["error"]


def test_job_json_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(job_manager, "_jobs_dir", lambda: tmp_path)
    record = {
        "id": "20260101T000000Z_abcd1234",
        "status": "done",
        "argv": ["python", "-m", "scripts.run_suite"],
        "started_at": "2026-01-01T00:00:00+00:00",
        "finished_at": "2026-01-01T00:01:00+00:00",
        "returncode": 0,
        "suite_dir": "reports/suite_x",
        "error": None,
    }
    job_manager._write_job(record)
    assert job_manager.get_job(record["id"]) == record


def test_get_job_unknown_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(job_manager, "_jobs_dir", lambda: tmp_path)
    assert job_manager.get_job("nope") is None


def test_list_jobs_newest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(job_manager, "_jobs_dir", lambda: tmp_path)
    stamps = ["2026-01-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00", "2026-03-01T00:00:00+00:00"]
    for i, ts in enumerate(stamps):
        job_manager._write_job(
            {
                "id": f"job{i}",
                "status": "done",
                "argv": [],
                "started_at": ts,
                "finished_at": None,
                "returncode": 0,
                "suite_dir": "",
                "error": None,
            }
        )
    starts = [j["started_at"] for j in job_manager.list_jobs()]
    assert starts == [
        "2026-06-01T00:00:00+00:00",
        "2026-03-01T00:00:00+00:00",
        "2026-01-01T00:00:00+00:00",
    ]


def test_build_run_argv_shapes_flags(tmp_path):
    argv = job_manager.build_run_argv(
        "jid",
        tmp_path / "suite_jid",
        ids=["a", "b"],
        max_n=None,
        site_id="example.com",
        suite_version="v1.0",
        headless=True,
        audio_judge=False,
        dry_run=True,
    )
    assert argv[1:3] == ["-m", "scripts.run_suite"]
    assert "--dry-run" in argv
    assert "--headless" in argv
    assert "--no-audio-judge" in argv
    assert argv[argv.index("--ids") + 1] == "a,b"
    assert argv[argv.index("--site") + 1] == "example.com"
    assert argv[argv.index("--suite-version") + 1] == "v1.0"
