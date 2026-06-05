"""Integration: re-run a version's pinned scenario set via a keyless dry-run job.

Seeds a v1.0 suite recording two real library scenario ids, computes the pinned
set, then launches a dry-run job with those ids. Dry-run writes a 0-call suite but
records ``scenario_set_hash`` of exactly the scenarios it ran — so we assert on
that hash to prove the pinned set reached the runner. Keyless (no browser/LLM).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import backend.settings as settings_mod
from backend.orchestrator import job_manager
from backend.orchestrator.versioning import scenario_set_hash
from backend.report import data, rerun
from backend.scenarios import load_library


def _wait(job_id: str, timeout: float = 180.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        rec = job_manager.get_job(job_id)
        if rec and rec["status"] in ("done", "error"):
            return rec
        time.sleep(0.2)
    raise AssertionError(f"job {job_id} never finished: {job_manager.get_job(job_id)}")


def test_rerun_pins_scenario_set(tmp_path, monkeypatch):
    # Point both this process and the child subprocess at a tmp reports dir.
    monkeypatch.setenv("HARNESS_REPORTS_DIR", str(tmp_path))
    monkeypatch.setattr(settings_mod, "_settings", None)  # reset cached Settings

    library = load_library()
    pin_ids = [library[0].id, library[1].id]

    # Seed a v1.0 suite recording exactly those scenario ids.
    seed_dir = tmp_path / "suite_20260101T000000Z_seed"
    seed_dir.mkdir(parents=True)
    (seed_dir / "suite.json").write_text(
        json.dumps(
            {
                "suite_version": "v1.0",
                "started_at": "2026-01-01T00:00:00Z",
                "calls": [{"scenario_id": sid} for sid in pin_ids],
            }
        ),
        encoding="utf-8",
    )

    pinned = rerun.pinned_scenario_ids("v1.0", [data.load_suite(seed_dir)])
    assert pinned == pin_ids

    job_id = job_manager.start_job(
        ids=pinned, suite_version="v1.0", dry_run=True, audio_judge=False
    )
    rec = _wait(job_id)
    assert rec["status"] == "done", rec
    assert rec["returncode"] == 0

    new = json.loads((Path(rec["suite_dir"]) / "suite.json").read_text(encoding="utf-8"))
    assert new["suite_version"] == "v1.0"
    # Dry-run records the hash of exactly the scenarios it ran -> proves the pin.
    expected = scenario_set_hash([s for s in library if s.id in set(pin_ids)])
    assert new["scenario_set_hash"] == expected
