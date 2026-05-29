"""OpenAI TTS adapter.

Wraps the openai.audio.speech endpoint, decodes returned audio with soundfile,
resamples (if needed) to the target sample rate via numpy/linear interpolation.
"""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf
from loguru import logger
from openai import AsyncOpenAI

from backend.settings import get_settings
from backend.tts.base import TtsResult


def _linear_resample(pcm: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return pcm.astype(np.float32, copy=False)
    duration = pcm.shape[0] / src_sr
    out_len = int(round(duration * dst_sr))
    x_old = np.linspace(0.0, duration, num=pcm.shape[0], endpoint=False)
    x_new = np.linspace(0.0, duration, num=out_len, endpoint=False)
    return np.interp(x_new, x_old, pcm).astype(np.float32)


class OpenAiTts:
    name = "openai"

    def __init__(self, target_sample_rate: int = 48_000) -> None:
        s = get_settings()
        if not s.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        self.client = AsyncOpenAI(api_key=s.openai_api_key)
        self.model = s.openai_tts_model
        self.default_voice = s.openai_tts_voice
        self.target_sr = target_sample_rate

    async def synthesize(self, text: str, *, voice: str | None = None) -> TtsResult:
        v = voice or self.default_voice
        logger.debug("OpenAI TTS  voice={} model={} chars={}", v, self.model, len(text))
        # Request WAV so we can decode with soundfile (mp3 would need ffmpeg).
        resp = await self.client.audio.speech.create(
            model=self.model,
            voice=v,
            input=text,
            response_format="wav",
        )
        raw = await resp.aread()
        data, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1).astype(np.float32)
        pcm = _linear_resample(data, sr, self.target_sr)
        # Coarse cost: tts-1 is $15/1M chars; tts-1-hd is $30/1M chars.
        per_million = 15.0 if "1" in self.model and "hd" not in self.model else 30.0
        cost = (len(text) / 1_000_000.0) * per_million
        return TtsResult(
            pcm=pcm,
            sample_rate=self.target_sr,
            provider="openai",
            voice=v,
            cost_usd=cost,
        )
