"""Unit tests for the C8 QA-API smoke evaluation.

(Auth moved from a shared-password gate to per-user JWT auth in C9 —
see ``tests/unit/test_auth.py``.)
"""

from __future__ import annotations

from scripts.qa_smoke_test import evaluate_smoke


def _gate_check(result):
    return next(c for c in result.checks if "auth gate" in c.name)


def test_smoke_all_green():
    res = evaluate_smoke(health_status=200, health_ok=True, list_status=200, wrong_secret_status=401)
    assert res.ok is True
    assert res.failures == []
    assert _gate_check(res).detail == "AUTH GATE OK"


def test_smoke_wrong_secret_not_401_fails_naming_gate():
    res = evaluate_smoke(health_status=200, health_ok=True, list_status=200, wrong_secret_status=200)
    assert res.ok is False
    failed = res.failures
    assert len(failed) == 1
    assert "auth gate" in failed[0].name  # offending check named


def test_smoke_health_down_fails():
    res = evaluate_smoke(health_status=500, health_ok=False, list_status=200, wrong_secret_status=401)
    assert res.ok is False
    assert any(c.name == "health" and not c.ok for c in res.checks)


def test_smoke_list_down_fails():
    res = evaluate_smoke(health_status=200, health_ok=True, list_status=503, wrong_secret_status=401)
    assert res.ok is False
    assert any(c.name == "list conversations" and not c.ok for c in res.checks)


def test_smoke_health_200_but_not_ok_fails():
    res = evaluate_smoke(health_status=200, health_ok=False, list_status=200, wrong_secret_status=401)
    assert res.ok is False
