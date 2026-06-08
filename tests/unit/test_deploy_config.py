"""C11 deploy-config unit tests: headless argv, the new settings, nav gating."""

from __future__ import annotations

import pytest

import backend.settings as settings_mod
from backend.orchestrator import job_manager
from backend.report.nav import PageSpec, visible_specs
from backend.settings import get_settings


# --------------------------------------------------------------------------- #
# build_run_argv — --headless driven by the headless bool (← harness_headless)
# --------------------------------------------------------------------------- #
def test_build_run_argv_headless_true_includes_flag(tmp_path):
    argv = job_manager.build_run_argv(
        "jid", tmp_path / "s", ids=None, max_n=1, site_id=None,
        suite_version="v1.0", headless=True, audio_judge=False, dry_run=True,
    )
    assert "--headless" in argv


def test_build_run_argv_headless_false_omits_flag(tmp_path):
    argv = job_manager.build_run_argv(
        "jid", tmp_path / "s", ids=None, max_n=1, site_id=None,
        suite_version="v1.0", headless=False, audio_judge=False, dry_run=True,
    )
    assert "--headless" not in argv


# --------------------------------------------------------------------------- #
# settings — HARNESS_RUNS_ENABLED / HARNESS_HEADLESS parsing + defaults
# --------------------------------------------------------------------------- #
@pytest.fixture
def fresh_settings(monkeypatch):
    """Reset the cached Settings + provide the one required field."""
    monkeypatch.setenv("QA_SHARED_SECRET", "x")
    monkeypatch.setattr(settings_mod, "_settings", None)
    yield
    monkeypatch.setattr(settings_mod, "_settings", None)


def test_settings_defaults(fresh_settings, monkeypatch):
    monkeypatch.delenv("HARNESS_RUNS_ENABLED", raising=False)
    monkeypatch.delenv("HARNESS_HEADLESS", raising=False)
    s = get_settings()
    assert s.harness_runs_enabled is True
    assert s.harness_headless is False


@pytest.mark.parametrize(
    ("runs_env", "headless_env", "runs", "headless"),
    [
        ("false", "1", False, True),
        ("0", "true", False, True),
        ("true", "0", True, False),
        ("yes", "no", True, False),
    ],
)
def test_settings_env_parsing(fresh_settings, monkeypatch, runs_env, headless_env, runs, headless):
    monkeypatch.setenv("HARNESS_RUNS_ENABLED", runs_env)
    monkeypatch.setenv("HARNESS_HEADLESS", headless_env)
    s = get_settings()
    assert s.harness_runs_enabled is runs
    assert s.harness_headless is headless


# --------------------------------------------------------------------------- #
# nav gating — run-only pages hidden when runs are disabled
# --------------------------------------------------------------------------- #
def _specs() -> list[PageSpec]:
    noop = lambda: None  # noqa: E731 — trivial test stub
    return [
        PageSpec(noop, "Overview", "📊", "overview", default=True),
        PageSpec(noop, "Reports", "📄", "reports"),
        PageSpec(noop, "Run suite", "▶️", "run-suite", requires_runs=True),
        PageSpec(noop, "Re-run", "🔁", "re-run", requires_runs=True),
    ]


def test_visible_specs_hides_run_pages_when_disabled():
    titles = [s.title for s in visible_specs(_specs(), runs_enabled=False)]
    assert titles == ["Overview", "Reports"]


def test_visible_specs_keeps_all_when_enabled():
    titles = [s.title for s in visible_specs(_specs(), runs_enabled=True)]
    assert titles == ["Overview", "Reports", "Run suite", "Re-run"]
