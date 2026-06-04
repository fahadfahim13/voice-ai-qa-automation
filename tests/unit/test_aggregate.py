"""Unit tests for the Reports aggregation helpers."""

from __future__ import annotations

import math

from backend.report.aggregate import pass_rate, per_criterion_averages


def _call(*criteria, pass_fail=False):
    return {
        "text_verdict": {
            "pass_fail": pass_fail,
            "criteria": [{"name": n, "score": s} for n, s in criteria],
        }
    }


def test_per_criterion_averages_exact_means():
    suite = {
        "calls": [
            _call(("relevance", 0.4), ("latency", 1.0)),
            _call(("relevance", 0.6), ("latency", 0.0)),
        ]
    }
    avg = per_criterion_averages(suite)
    assert math.isclose(avg["relevance"], 0.5)
    assert math.isclose(avg["latency"], 0.5)


def test_criterion_present_in_one_call_averages_over_present_only():
    suite = {
        "calls": [
            _call(("relevance", 0.4), ("stt_quality", 1.0)),
            _call(("relevance", 0.6)),  # no stt_quality here
        ]
    }
    avg = per_criterion_averages(suite)
    assert math.isclose(avg["relevance"], 0.5)
    assert math.isclose(avg["stt_quality"], 1.0)  # averaged over the one present value


def test_calls_without_verdict_are_skipped_not_zero():
    suite = {
        "calls": [
            _call(("relevance", 0.8)),
            {"text_verdict": None, "error": "boom"},  # skipped, not counted as 0
        ]
    }
    avg = per_criterion_averages(suite)
    assert math.isclose(avg["relevance"], 0.8)


def test_per_criterion_averages_empty_suite():
    assert per_criterion_averages({"calls": []}) == {}
    assert per_criterion_averages({}) == {}


def test_pass_rate_basic():
    assert math.isclose(pass_rate({"n_passed": 3, "n_total": 4}), 0.75)


def test_pass_rate_zero_total_no_division_error():
    assert pass_rate({"n_passed": 0, "n_total": 0}) == 0.0
    assert pass_rate({}) == 0.0
