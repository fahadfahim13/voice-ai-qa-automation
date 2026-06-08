"""C11 deploy smoke tests.

- Keyless dry-run proves the deployed default flags drive the harness end to end
  with no secrets and no browser (the Phase-A guarantee before the ops Chromium step).
- The process-script test (Linux only) proves vps_start.sh / vps_stop.sh bring the
  dashboard up on 127.0.0.1, serve /_stcore/health, and stop cleanly.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from backend.settings import REPO_ROOT


@pytest.mark.slow
def test_keyless_dry_run_writes_suite_json(tmp_path):
    """`run_suite --dry-run --headless --max 1` → exit 0 + a suite.json, no secrets."""
    env = {**os.environ, "QA_SHARED_SECRET": "x", "HARNESS_REPORTS_DIR": str(tmp_path)}
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.run_suite", "--dry-run", "--headless", "--max", "1"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    suites = list(tmp_path.glob("suite_*/suite.json"))
    assert suites, f"no suite.json written under {tmp_path}"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.slow
@pytest.mark.linux
@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="deploy scripts are POSIX/Linux")
@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("uv") is None, reason="needs bash + uv")
def test_start_stop_scripts_serve_health(tmp_path):
    """vps_start.sh serves /_stcore/health on 127.0.0.1, vps_stop.sh clears the PID."""
    port = _free_port()
    env = {
        **os.environ,
        "APP_DIR": str(REPO_ROOT),  # run streamlit from the repo
        "PORT": str(port),
        "QA_SHARED_SECRET": "x",
    }
    pid_file = REPO_ROOT / "dashboard.pid"
    log_file = REPO_ROOT / "dashboard.log"
    health = f"http://127.0.0.1:{port}/_stcore/health"
    try:
        subprocess.run(["bash", "scripts/vps_start.sh"], cwd=str(REPO_ROOT), env=env, check=True, timeout=60)
        ok = False
        for _ in range(80):  # up to ~40s for Streamlit to boot
            try:
                with urllib.request.urlopen(health, timeout=2) as r:
                    if r.status == 200:
                        ok = True
                        break
            except Exception:
                time.sleep(0.5)
        assert ok, "dashboard never became healthy"
    finally:
        subprocess.run(["bash", "scripts/vps_stop.sh"], cwd=str(REPO_ROOT), env=env, timeout=60)
        for p in (pid_file, log_file):
            Path(p).unlink(missing_ok=True)
    assert not pid_file.exists(), "PID file should be gone after stop"
