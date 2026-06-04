"""Back-compat: old suites (no version fields) load with safe defaults."""

from __future__ import annotations

import shutil
from pathlib import Path

from backend.report import data

REPO_ROOT = Path(__file__).resolve().parents[2]
OLD_SUITE = REPO_ROOT / "reports" / "suite_20260601T094100Z" / "suite.json"


def test_old_suite_loads_with_version_defaults(tmp_path):
    assert OLD_SUITE.exists(), "expected committed old-format suite fixture"
    suite_dir = tmp_path / "suite_old"
    suite_dir.mkdir()
    shutil.copyfile(OLD_SUITE, suite_dir / "suite.json")

    loaded = data.load_suite(suite_dir)

    # no exception, real data preserved
    assert loaded["business_summary"]
    # version fields default sensibly for pre-versioning suites
    assert loaded["suite_version"] == "unversioned"
    assert loaded["scenario_set_hash"] == ""
    assert loaded["provider_snapshot"] == {}
