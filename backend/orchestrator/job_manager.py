"""Background job manager for suite runs.

A blocking ``asyncio.run`` that drives Playwright for minutes cannot live inside a
Streamlit request — the page would freeze and Streamlit reruns would relaunch it.
This module wraps the runner as a managed **subprocess** with persisted state:
``start_job`` returns immediately with a ``job_id``; ``get_job`` / ``list_jobs`` /
``tail_log`` let the dashboard poll status and tail the log across reruns without
holding the process.

Each job persists to ``reports/jobs/<job_id>.json`` and streams the subprocess
stdout/stderr to ``reports/jobs/<job_id>.log``. A daemon thread in the launching
process (the Streamlit server, which survives reruns) waits on the subprocess and
flips the record to ``done``/``error`` on exit.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.settings import REPO_ROOT, get_settings

Status = str  # one of: queued | running | done | error


def _jobs_dir() -> Path:
    return get_settings().harness_reports_dir / "jobs"


def _job_path(job_id: str) -> Path:
    return _jobs_dir() / f"{job_id}.json"


def _log_path(job_id: str) -> Path:
    return _jobs_dir() / f"{job_id}.log"


def _write_job(record: dict) -> None:
    """Atomically persist a job record (tmp file + os.replace)."""
    _jobs_dir().mkdir(parents=True, exist_ok=True)
    path = _job_path(record["id"])
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def build_run_argv(
    job_id: str,
    suite_dir: Path,
    *,
    ids: list[str] | None,
    max_n: int | None,
    site_id: str | None,
    suite_version: str,
    headless: bool,
    audio_judge: bool,
    dry_run: bool,
) -> list[str]:
    """Build the ``python -m scripts.run_suite`` argv for a job.

    Factored out so tests can monkeypatch it to a trivial fast command.
    """
    argv = [
        sys.executable,
        "-m",
        "scripts.run_suite",
        "--suite-dir",
        str(suite_dir),
        "--suite-version",
        suite_version,
    ]
    if dry_run:
        argv.append("--dry-run")
    if headless:
        argv.append("--headless")
    argv.append("--audio-judge" if audio_judge else "--no-audio-judge")
    if ids:
        argv += ["--ids", ",".join(ids)]
    elif max_n is not None:
        argv += ["--max", str(max_n)]
    if site_id:
        argv += ["--site", site_id]
    return argv


def start_job(
    *,
    ids: list[str] | None = None,
    max_n: int | None = None,
    site_id: str | None = None,
    suite_version: str = "v1.0",
    headless: bool = True,
    audio_judge: bool = True,
    dry_run: bool = False,
) -> str:
    """Launch a suite run as a background subprocess; return its ``job_id``.

    Returns immediately — poll with :func:`get_job`.
    """
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    job_id = f"{ts}_{uuid4().hex[:8]}"
    suite_dir = get_settings().harness_reports_dir / f"suite_{job_id}"

    argv = build_run_argv(
        job_id,
        suite_dir,
        ids=ids,
        max_n=max_n,
        site_id=site_id,
        suite_version=suite_version,
        headless=headless,
        audio_judge=audio_judge,
        dry_run=dry_run,
    )

    record = {
        "id": job_id,
        "status": "queued",
        "argv": argv,
        "started_at": datetime.now(UTC).isoformat(),
        "finished_at": None,
        "returncode": None,
        "suite_dir": str(suite_dir),
        "error": None,
    }
    _write_job(record)

    logf = _log_path(job_id).open("w", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            argv,
            stdout=logf,
            stderr=subprocess.STDOUT,
            cwd=str(REPO_ROOT),
        )
    except Exception as exc:  # launch failure → mark error immediately
        logf.close()
        record["status"] = "error"
        record["error"] = f"failed to launch: {exc}"
        record["finished_at"] = datetime.now(UTC).isoformat()
        _write_job(record)
        return job_id

    record["status"] = "running"
    _write_job(record)

    threading.Thread(
        target=_wait_and_finalize, args=(job_id, proc, logf), daemon=True
    ).start()
    return job_id


def _wait_and_finalize(job_id: str, proc: subprocess.Popen, logf) -> None:
    rc = proc.wait()
    logf.close()
    record = get_job(job_id) or {"id": job_id}
    record["returncode"] = rc
    record["finished_at"] = datetime.now(UTC).isoformat()
    if rc == 0:
        record["status"] = "done"
        record["error"] = None
    else:
        record["status"] = "error"
        record["error"] = f"subprocess exited with code {rc}"
    _write_job(record)


def get_job(job_id: str) -> dict | None:
    """Read a job record from disk, or ``None`` if unknown."""
    path = _job_path(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def list_jobs() -> list[dict]:
    """All job records, newest first (by ``started_at``)."""
    jobs_dir = _jobs_dir()
    if not jobs_dir.exists():
        return []
    out = []
    for p in jobs_dir.glob("*.json"):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    out.sort(key=lambda r: (r.get("started_at") or "", r.get("id") or ""), reverse=True)
    return out


def tail_log(job_id: str, n: int = 50) -> str:
    """Last ``n`` lines of a job's log, or ``""`` if none yet."""
    path = _log_path(job_id)
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-n:])
