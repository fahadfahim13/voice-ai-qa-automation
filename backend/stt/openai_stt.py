"""OpenAI Whisper transcription adapter."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from openai import AsyncOpenAI

from backend.settings import get_settings


class OpenAiStt:
    name = "openai"

    def __init__(self) -> None:
        s = get_settings()
        if not s.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        self.client = AsyncOpenAI(api_key=s.openai_api_key)
        self.model = s.openai_stt_model

    async def transcribe(self, audio_path: Path | str, *, language: str = "en") -> str:
        path = Path(audio_path)
        logger.debug("Whisper transcribe {} ({} bytes)", path, path.stat().st_size)
        with path.open("rb") as f:
            resp = await self.client.audio.transcriptions.create(
                model=self.model,
                file=(path.name, f, "audio/webm"),
                language=language,
            )
        return resp.text
