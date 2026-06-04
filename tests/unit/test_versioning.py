"""Unit tests for suite versioning helpers."""

from __future__ import annotations

from types import SimpleNamespace

from backend.orchestrator import versioning
from backend.orchestrator.suite import SuiteResult
from backend.scenarios import Accent, load_library


def _scenarios():
    lib = load_library()
    assert len(lib) >= 2, "library fixture should have scenarios"
    return lib


def test_hash_is_deterministic():
    scenarios = _scenarios()
    assert versioning.scenario_set_hash(scenarios) == versioning.scenario_set_hash(scenarios)


def test_hash_is_order_independent():
    scenarios = _scenarios()
    assert versioning.scenario_set_hash(scenarios) == versioning.scenario_set_hash(
        list(reversed(scenarios))
    )


def test_adding_a_scenario_changes_hash():
    scenarios = _scenarios()
    extra = scenarios[0].model_copy(update={"id": "synthetic-extra-scenario"})
    assert versioning.scenario_set_hash(scenarios) != versioning.scenario_set_hash(
        [*scenarios, extra]
    )


def test_editing_an_axis_changes_hash():
    scenarios = _scenarios()
    first = scenarios[0]
    flipped = Accent.en_gb if first.accent == Accent.en_us else Accent.en_us
    edited = [first.model_copy(update={"accent": flipped}), *scenarios[1:]]
    assert versioning.scenario_set_hash(scenarios) != versioning.scenario_set_hash(edited)


def test_editing_content_changes_hash():
    # Non-axis content edit must also bust the hash (full-content scope).
    scenarios = _scenarios()
    edited = [scenarios[0].model_copy(update={"goal": "totally different goal"}), *scenarios[1:]]
    assert versioning.scenario_set_hash(scenarios) != versioning.scenario_set_hash(edited)


def test_hash_is_64_hex():
    h = versioning.scenario_set_hash(_scenarios())
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


def test_provider_snapshot_keys_and_values(monkeypatch):
    fake = SimpleNamespace(
        openrouter_model_caller="caller-model",
        openrouter_model_scenario="scenario-model",
        openrouter_model_judge_text="judge-text-model",
        openrouter_model_judge_audio="judge-audio-model",
        tts_provider="my-tts",
        stt_provider="my-stt",
        qa_base_url="https://example.test",
        qa_site_id="site-123",
    )
    monkeypatch.setattr(versioning, "get_settings", lambda: fake)
    snap = versioning.provider_snapshot()
    assert snap == {
        "openrouter_model_caller": "caller-model",
        "openrouter_model_scenario": "scenario-model",
        "openrouter_model_judge_text": "judge-text-model",
        "openrouter_model_judge_audio": "judge-audio-model",
        "tts_provider": "my-tts",
        "stt_provider": "my-stt",
        "qa_base_url": "https://example.test",
        "qa_site_id": "site-123",
    }


def test_suite_result_to_dict_includes_new_fields():
    suite = SuiteResult(
        started_at="2026-06-04T00:00:00Z",
        finished_at="2026-06-04T00:01:00Z",
        business_summary="biz",
        n_total=0,
        n_passed=0,
        n_failed=0,
        n_errors=0,
        avg_overall_score=0.0,
        suite_version="v1.0",
        scenario_set_hash="abc",
        provider_snapshot={"tts_provider": "openai"},
    )
    d = suite.to_dict()
    assert d["suite_version"] == "v1.0"
    assert d["scenario_set_hash"] == "abc"
    assert d["provider_snapshot"] == {"tts_provider": "openai"}
