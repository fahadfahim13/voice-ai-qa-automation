"""Suite-level coverage + failure-breakdown analytics.

`compute_coverage(results)` walks every CallResult, groups by each of the
8 scenario axes, and computes (total, passed, failed, errors, avg_score) per
axis value. It also extracts a flat list of failing criteria so the report
can show "which scenarios failed for which criterion".

`write_summary_csv(suite_dir, suite)` writes one row per call with axes +
per-criterion scores, for spreadsheet consumers.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from backend.orchestrator.suite import AXIS_NAMES, CallResult, SuiteResult

# Failing-criterion threshold matches JudgeVerdict.pass_fail logic
# (overall < 0.7 OR any criterion < 0.4 → fail).
FAIL_CRITERION_THRESHOLD = 0.4


def _axis_bucket() -> dict:
    return {"total": 0, "passed": 0, "failed": 0, "errors": 0, "score_sum": 0.0, "score_n": 0}


def compute_coverage(results: Iterable[CallResult]) -> dict[str, dict[str, dict]]:
    """Group calls by each axis value. Returns {axis: {value: stats}}."""
    buckets: dict[str, dict[str, dict]] = {a: {} for a in AXIS_NAMES}
    for r in results:
        for axis in AXIS_NAMES:
            value = r.axes.get(axis, "unknown")
            b = buckets[axis].setdefault(value, _axis_bucket())
            b["total"] += 1
            if r.error:
                b["errors"] += 1
            v = r.text_verdict or {}
            if v.get("pass_fail"):
                b["passed"] += 1
            elif v:
                b["failed"] += 1
            if "overall_score" in v:
                b["score_sum"] += float(v["overall_score"])
                b["score_n"] += 1
    # Finalize avg_score and drop accumulators.
    for axis, values in buckets.items():
        for v_name, b in values.items():
            avg = (b["score_sum"] / b["score_n"]) if b["score_n"] else 0.0
            b["avg_score"] = round(avg, 3)
            del b["score_sum"]
            del b["score_n"]
    return buckets


def compute_failure_breakdown(results: Iterable[CallResult]) -> list[dict]:
    """One row per (failing criterion × failing call). Sorted by criterion then scenario."""
    rows: list[dict] = []
    for r in results:
        v = r.text_verdict
        if not v or v.get("pass_fail"):
            continue
        for cr in v.get("criteria", []):
            score = float(cr.get("score", 1.0))
            if score < FAIL_CRITERION_THRESHOLD:
                rows.append(
                    {
                        "scenario_id": r.scenario_id,
                        "title": r.scenario_title,
                        "criterion": cr.get("name", ""),
                        "score": round(score, 3),
                        "evidence": (cr.get("evidence") or "")[:240],
                        "rationale": (cr.get("rationale") or "")[:240],
                    }
                )
    rows.sort(key=lambda x: (x["criterion"], x["scenario_id"]))
    return rows


def write_summary_csv(suite_dir: Path, suite: SuiteResult) -> Path:
    """One row per call: scenario_id, title, axes, pass/fail, overall, per-criterion."""
    criterion_names = sorted(
        {
            cr.get("name", "")
            for c in suite.calls
            if c.text_verdict
            for cr in c.text_verdict.get("criteria", [])
        }
    )
    header = (
        ["scenario_id", "title"]
        + list(AXIS_NAMES)
        + ["pass_fail", "overall_score", "elapsed_seconds", "error"]
        + [f"score__{n}" for n in criterion_names]
    )
    csv_path = suite_dir / "summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for c in suite.calls:
            v = c.text_verdict or {}
            row = [c.scenario_id, c.scenario_title]
            row += [c.axes.get(a, "") for a in AXIS_NAMES]
            row += [
                v.get("pass_fail", ""),
                v.get("overall_score", ""),
                round(c.elapsed_seconds, 2),
                c.error or "",
            ]
            scores = {cr.get("name"): cr.get("score") for cr in v.get("criteria", [])}
            row += [scores.get(n, "") for n in criterion_names]
            w.writerow(row)
    return csv_path
