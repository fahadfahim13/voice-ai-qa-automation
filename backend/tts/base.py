"""TTS provider interface.

A provider returns mono Float32 PCM at a target sample rate, suitable for
window.__qa_speakPcm injection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass
class TtsResult:
    pcm: np.ndarray  # float32 mono in [-1, 1]
    sample_rate: int
    provider: str
    voice: str
    cost_usd: float = 0.0


class TtsProvider(Protocol):
    name: str

    async def synthesize(self, text: str, *, voice: str | None = None) -> TtsResult: ...
