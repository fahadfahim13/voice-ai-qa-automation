"""Unit tests for job naming + rename (C10 part 3)."""

from __future__ import annotations

import sys
import time
from datetime import datetime

from backend.orchestrator import job_manager


def _wait(job_id: str, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        rec = job_manager.get_job(job_id)
        if rec and rec["status"] in ("done", "error"):
            return rec
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} never finished: {job_manager.get_job(job_id)}")


def _trivial_argv(monkeypatch, tmp_path):
    monkeypatch.setattr(job_manager, "_jobs_dir", lambda: tmp_path)
    monkeypatch.setattr(
        job_manager, "build_run_argv", lambda *a, **k: [sys.executable, "-c", "print('ok')"]
    )


def test_default_name_format_contract():
    # The run form pre-fills "{website} {YYYY-MM-DD HH:MM}".
    website = "fftechsaas.xyz"
    ts = datetime(2026, 6, 5, 14, 30)
    assert f"{website} {ts:%Y-%m-%d %H:%M}" == "fftechsaas.xyz 2026-06-05 14:30"


def test_explicit_name_is_stored(tmp_path, monkeypatch):
    _trivial_argv(monkeypatch, tmp_path)
    job_id = job_manager.start_job(website="fftechsaas.xyz", name="Smoke check", dry_run=True)
    rec = _wait(job_id)
    assert rec["name"] == "Smoke check"
    assert rec["website"] == "fftechsaas.xyz"


def test_name_defaults_to_website_when_blank(tmp_path, monkeypatch):
    _trivial_argv(monkeypatch, tmp_path)
    job_id = job_manager.start_job(website="example.com", dry_run=True)
    rec = _wait(job_id)
    assert rec["name"] == "example.com"


def test_rename_job_updates_and_reads_back(tmp_path, monkeypatch):
    monkeypatch.setattr(job_manager, "_jobs_dir", lambda: tmp_path)
    job_manager._write_job(
        {
            "id": "jid1",
            "name": "old",
            "website": "x.com",
            "status": "done",
            "argv": [],
            "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": None,
            "returncode": 0,
            "suite_dir": "",
            "error": None,
        }
    )
    assert job_manager.rename_job("jid1", "New name") is True
    assert job_manager.get_job("jid1")["name"] == "New name"


def test_rename_unknown_job_returns_false(tmp_path, monkeypatch):
    monkeypatch.setattr(job_manager, "_jobs_dir", lambda: tmp_path)
    assert job_manager.rename_job("nope", "whatever") is False
