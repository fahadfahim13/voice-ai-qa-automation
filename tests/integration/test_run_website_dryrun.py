"""End-to-end dry-run job driven by a WEBSITE (not a raw siteId) — C10.

Keyless: start_job → subprocess → scripts.run_suite --dry-run → suite.json. Mirrors
the run form's path (normalize website, upsert the row, form_to_job_kwargs) without
Streamlit.
"""

from __future__ import annotations

import time

import backend.settings as settings_mod
from backend import db
from backend.orchestrator import job_manager
from backend.report.run_form import form_to_job_kwargs


def _wait(job_id: str, timeout: float = 90.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        rec = job_manager.get_job(job_id)
        if rec and rec["status"] in ("done", "error"):
            return rec
        time.sleep(0.2)
    raise AssertionError(f"job {job_id} never finished: {job_manager.get_job(job_id)}")


def test_dry_run_with_website_and_name(tmp_path, monkeypatch):
    # Point reports + DB at a tmp dir for both this process and the child subprocess.
    monkeypatch.setenv("HARNESS_REPORTS_DIR", str(tmp_path))
    monkeypatch.setenv("QA_DB_URL", f"sqlite:///{(tmp_path / 'qa.db').as_posix()}")
    monkeypatch.setattr(settings_mod, "_settings", None)  # reset cached Settings
    db.reset_engine()
    db.init_db()

    # The view normalizes the website and upserts the row before submitting.
    website = db.normalize_url("https://www.fftechsaas.xyz/")
    db.upsert_website(website)
    selection = {
        "mode": "All",
        "website": website,
        "name": "Smoke check",
        "suite_version": "v1.0",
        "headless": True,
        "audio_judge": False,
    }
    kwargs = form_to_job_kwargs(selection)
    assert kwargs["site_id"] is None  # no raw siteId required from the form

    job_id = job_manager.start_job(**kwargs, dry_run=True)
    rec = _wait(job_id)

    assert rec["status"] == "done", rec
    assert rec["name"] == "Smoke check"
    assert rec["website"] == "fftechsaas.xyz"  # normalized host
    assert "--site" not in rec["argv"]  # no siteId on the command line

    # A Website row exists for the normalized host.
    assert any(w.url == "fftechsaas.xyz" for w in db.list_websites())
