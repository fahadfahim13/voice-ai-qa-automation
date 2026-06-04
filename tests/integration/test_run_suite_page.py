"""Integration: the Run-suite page renders a completed job's report inline."""

from __future__ import annotations

import json

from streamlit.testing.v1 import AppTest

from backend.orchestrator import job_manager


def test_run_suite_page_renders_completed_job(tmp_path, monkeypatch):
    suite_dir = tmp_path / "suite_x"
    suite_dir.mkdir()
    suite = {
        "started_at": "2026-06-04T00:00:00Z",
        "finished_at": "2026-06-04T00:01:00Z",
        "business_summary": "demo",
        "n_total": 1,
        "n_passed": 1,
        "n_failed": 0,
        "n_errors": 0,
        "avg_overall_score": 0.72,
        "suite_version": "v1.0",
        "calls": [
            {
                "scenario_id": "demo-call",
                "elapsed_seconds": 10.0,
                "artifacts": {},
                "text_verdict": {
                    "pass_fail": True,
                    "overall_score": 0.72,
                    "summary": "ok",
                    "criteria": [
                        {"name": "relevance", "score": 0.8, "evidence": "e", "rationale": "r"}
                    ],
                },
            }
        ],
    }
    (suite_dir / "suite.json").write_text(json.dumps(suite), encoding="utf-8")

    job = {
        "id": "20260604T000000Z_abcd1234",
        "status": "done",
        "argv": ["python", "-m", "scripts.run_suite"],
        "started_at": "2026-06-04T00:00:00Z",
        "finished_at": "2026-06-04T00:01:00Z",
        "returncode": 0,
        "suite_dir": str(suite_dir),
        "error": None,
    }
    monkeypatch.setattr(job_manager, "list_jobs", lambda: [job])
    monkeypatch.setattr(job_manager, "get_job", lambda jid: job if jid == job["id"] else None)

    probe = tmp_path / "probe.py"
    probe.write_text(
        "from backend.report.views import run_suite\nrun_suite.render()\n", encoding="utf-8"
    )
    at = AppTest.from_file(str(probe), default_timeout=30).run()

    assert len(at.exception) == 0, at.exception
    labels = [m.label for m in at.metric]
    assert "Total" in labels and "Avg score" in labels
    assert any("done" in m.value for m in at.markdown)
    # the per-call detail (reused expander) is present
    assert len(at.expander) >= 1
