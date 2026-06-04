"""Integration: aggregation runs cleanly over the committed suite fixtures."""

from __future__ import annotations

from pathlib import Path

from backend.report import data
from backend.report.aggregate import pass_rate, per_criterion_averages

REPO_ROOT = Path(__file__).resolve().parents[2]


def _committed_suites():
    return sorted((REPO_ROOT / "reports").glob("suite_*"))


def test_aggregation_over_committed_fixtures():
    suites = _committed_suites()
    assert suites, "expected committed reports/suite_* fixtures"

    checked = 0
    for suite_dir in suites:
        suite = data.load_suite(suite_dir)
        if not suite:
            continue
        checked += 1

        pr = pass_rate(suite)
        assert 0.0 <= pr <= 1.0, f"{suite_dir.name}: pass_rate {pr} out of range"

        for name, avg in per_criterion_averages(suite).items():
            assert 0.0 <= avg <= 1.0, f"{suite_dir.name}: {name} avg {avg} out of range"

    assert checked > 0, "no readable suite fixtures were aggregated"
