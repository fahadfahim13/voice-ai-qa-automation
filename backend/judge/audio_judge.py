"""Audio judge: feeds the captured bot.webm into a multimodal OpenRouter model
to detect pronunciation issues, robotic artefacts, abrupt cut-offs.

Phase 1 uses Gemini 2.0 Flash via OpenRouter (audio_url in user content).
Output schema: a small subset of the rubric focused on TTS-quality dimensions.
"""

from __future__ import annotations

import base64
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field

from backend.openrouter import OpenRouterClient
from backend.settings import get_settings

AUDIO_SCHEMA_HINT = """
{
  "tts_pronunciation": 0.0,
  "audio_quality": 0.0,
  "naturalness": 0.0,
  "issues": ["short tag strings, e.g. 'mispronounced-name', 'choppy-prosody'"],
  "transcript_audio": "<plain transcript of what you actually heard in the audio>",
  "notes": "<one short paragraph summarising audio-side issues>"
}
Scale: 0 = severe issues, 0.5 = noticeable, 1 = clean.
""".strip()


class AudioVerdict(BaseModel):
    tts_pronunciation: float = Field(..., ge=0.0, le=1.0)
    audio_quality: float = Field(..., ge=0.0, le=1.0)
    naturalness: float = Field(..., ge=0.0, le=1.0)
    issues: list[str] = Field(default_factory=list)
    transcript_audio: str = ""
    notes: str = ""


def _audio_data_url(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    if path.suffix == ".webm":
        mime = "audio/webm"
    elif path.suffix == ".ogg":
        mime = "audio/ogg"
    else:
        mime = "audio/mpeg"
    return f"data:{mime};base64,{b64}", mime


async def judge_audio(
    *,
    audio_path: Path,
    expected_transcript: str | None = None,
    client: OpenRouterClient | None = None,
    model: str | None = None,
) -> AudioVerdict:
    s = get_settings()
    client = client or OpenRouterClient()
    model = model or s.openrouter_model_judge_audio

    data_url, mime = _audio_data_url(audio_path)
    logger.info(
        "Audio judge via {}  file={}  ({:.1f} KB, {})",
        model, audio_path.name, audio_path.stat().st_size / 1024, mime,
    )

    user_content: list[dict] = [
        {
            "type": "text",
            "text": (
                "You are grading a recorded voice-AI bot's audio output. Score TTS pronunciation, "
                "audio quality, and naturalness on 0–1. Also transcribe what you actually hear and "
                "list short issue tags. If an expected transcript is provided, focus on whether the "
                "audio matches it."
            ),
        },
        {"type": "input_audio", "input_audio": {"data": data_url, "format": mime.split("/")[1]}},
    ]
    if expected_transcript:
        user_content.append(
            {
                "type": "text",
                "text": f"Expected transcript: {expected_transcript[:1500]}",
            }
        )

    data = await client.chat_json(
        model=model,
        messages=[
            {"role": "system", "content": "You are an exacting audio-quality QA judge."},
            {"role": "user", "content": user_content},
        ],
        schema_hint=AUDIO_SCHEMA_HINT,
        temperature=0.2,
        max_tokens=1200,
    )
    return AudioVerdict.model_validate(data)
