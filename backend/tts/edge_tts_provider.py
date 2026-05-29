"""edge-tts adapter (Microsoft Edge cloud TTS, no API key required).

Returns mp3 bytes from the cloud; we decode via soundfile (which depends on
libsndfile; mp3 support is included in the wheels we depend on).
"""

from __future__ import annotations

import io

import edge_tts
import numpy as np
import soundfile as sf
from loguru import logger

from backend.tts.base import TtsResult


def _linear_resample(pcm: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return pcm.astype(np.float32, copy=False)
    duration = pcm.shape[0] / src_sr
    out_len = int(round(duration * dst_sr))
    x_old = np.linspace(0.0, duration, num=pcm.shape[0], endpoint=False)
    x_new = np.linspace(0.0, duration, num=out_len, endpoint=False)
    return np.interp(x_new, x_old, pcm).astype(np.float32)


class EdgeTts:
    name = "edge"

    def __init__(
        self, voice: str = "en-US-AriaNeural", target_sample_rate: int = 48_000
    ) -> None:
        self.default_voice = voice
        self.target_sr = target_sample_rate

    async def synthesize(self, text: str, *, voice: str | None = None) -> TtsResult:
        v = voice or self.default_voice
        logger.debug("edge-tts voice={} chars={}", v, len(text))
        communicate = edge_tts.Communicate(text, v)
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                buf.write(chunk["data"])
        buf.seek(0)
        # soundfile reads mp3 in recent wheels; fall back to raw resample if needed
        data, sr = sf.read(buf, dtype="float32", always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1).astype(np.float32)
        pcm = _linear_resample(data, sr, self.target_sr)
        return TtsResult(
            pcm=pcm,
            sample_rate=self.target_sr,
            provider="edge",
            voice=v,
            cost_usd=0.0,
        )
