"""Central settings loaded from .env.

Single source of truth for credentials, endpoints, model choices.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    qa_shared_secret: str = Field(..., description="X-QA-Secret header value")
    qa_base_url: str = "https://bizfinder.ai"
    qa_site_id: str = "qa-judge"
    qa_preview_url: str = "https://bizfinder.ai/"
    qa_preview_url_pattern: Literal["preview_id", "preview_query"] = "preview_id"
    qa_rate_limit_rps: float = 1.0

    # Dashboard auth gate (C8). Empty = open with a warning (local-use only).
    dashboard_password: str = ""

    # Per-user auth + DB (C9). Empty jwt_secret → ephemeral per-process key + a
    # warning banner (tokens won't survive a restart). admin_* seeds the first user.
    jwt_secret: str = ""
    jwt_access_minutes: int = 720
    allow_signup: bool = True  # env ALLOW_SIGNUP — self-service registration page
    qa_db_url: str = f"sqlite:///{(REPO_ROOT / 'reports' / 'qa.db').as_posix()}"
    admin_email: str = ""
    admin_password: str = ""

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model_caller: str = "deepseek/deepseek-chat"
    openrouter_model_scenario: str = "deepseek/deepseek-chat"
    openrouter_model_judge_text: str = "anthropic/claude-haiku-4.5"
    openrouter_model_judge_audio: str = "google/gemini-2.0-flash-001"

    tts_provider: str = "openai"
    openai_api_key: str = ""
    openai_tts_model: str = "tts-1"
    openai_tts_voice: str = "alloy"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    stt_provider: str = "openai"
    openai_stt_model: str = "whisper-1"

    harness_log_level: str = "INFO"
    harness_concurrency: int = 2
    harness_recordings_dir: Path = REPO_ROOT / "recordings"
    harness_reports_dir: Path = REPO_ROOT / "reports"

    # Deploy controls (C11). On the rootless analytics VPS, Chromium system libs are
    # missing until an ops root step, so live runs are gated off there (Phase A =
    # reporting-only); headless is forced on for any host with no display.
    harness_runs_enabled: bool = True  # env HARNESS_RUNS_ENABLED — hide Run/Re-run when false
    harness_headless: bool = False  # env HARNESS_HEADLESS — default --headless for jobs


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
