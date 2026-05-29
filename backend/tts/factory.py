"""TTS provider factory."""

from __future__ import annotations

import numpy as np

from backend.settings import get_settings
from backend.tts.base import TtsResult


def get_tts(provider: str | None = None, target_sample_rate: int = 48_000):
    """Return a configured TTS provider.

    Preference order:
      - explicit `provider` argument
      - $TTS_PROVIDER from settings
      - if OPENAI_API_KEY set: openai
      - else: edge (Microsoft Edge cloud TTS, free, no key)
    """
    s = get_settings()
    p = (provider or s.tts_provider or "").lower()

    if not p:
        p = "openai" if s.openai_api_key else "edge"

    if p == "openai":
        try:
            from backend.tts.openai_tts import OpenAiTts

            return OpenAiTts(target_sample_rate=target_sample_rate)
        except RuntimeError:
            # No key — silently fall back to edge.
            p = "edge"

    if p == "edge":
        from backend.tts.edge_tts_provider import EdgeTts

        return EdgeTts(target_sample_rate=target_sample_rate)
    if p == "tone":
        return _ToneFallback(target_sample_rate)
    raise ValueError(f"Unknown TTS provider: {p}")


class _ToneFallback:
    """No-API fallback that synthesizes a short 440 Hz beep + frequency-modulated
    'speech-like' signal. STT will mostly transcribe this as nothing, but it
    proves the injection plumbing end-to-end.
    """

    name = "tone"

    def __init__(self, target_sample_rate: int = 48_000) -> None:
        self.sr = target_sample_rate

    async def synthesize(self, text: str, *, voice: str | None = None) -> TtsResult:
        seconds = max(1.0, min(6.0, len(text) / 15.0))
        t = np.linspace(0.0, seconds, int(self.sr * seconds), endpoint=False, dtype=np.float32)
        # Sweep between 220 and 880 Hz so VAD treats it as speech-like energy.
        f = 220.0 + (660.0 * (0.5 + 0.5 * np.sin(2.0 * np.pi * 0.5 * t)))
        phase = 2.0 * np.pi * np.cumsum(f) / self.sr
        pcm = 0.25 * np.sin(phase).astype(np.float32)
        # Apply a 50 ms attack/release to avoid clicks.
        fade = int(0.05 * self.sr)
        env = np.ones_like(pcm)
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
        pcm = pcm * env
        return TtsResult(pcm=pcm, sample_rate=self.sr, provider="tone", voice="sweep")
