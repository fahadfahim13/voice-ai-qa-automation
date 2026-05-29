"""Audio I/O helpers (WAV write + scenario WAV composition)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

# Chrome's --use-file-for-fake-audio-capture wants standard 16 kHz / 32 kHz /
# 44.1 kHz / 48 kHz mono PCM_16 WAV. 48 kHz mono is a safe default.
DEFAULT_SR = 48_000


def write_wav(path: Path | str, pcm: np.ndarray, sample_rate: int = DEFAULT_SR) -> Path:
    """Write float PCM (mono, [-1, 1]) to a 16-bit PCM WAV."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.asarray(pcm, dtype=np.float32)
    if pcm.ndim > 1:
        pcm = pcm.mean(axis=1)
    # Clip to [-1, 1] then encode as int16.
    pcm = np.clip(pcm, -1.0, 1.0)
    sf.write(str(p), pcm, samplerate=sample_rate, subtype="PCM_16")
    return p


def silence(seconds: float, sample_rate: int = DEFAULT_SR) -> np.ndarray:
    return np.zeros(int(round(seconds * sample_rate)), dtype=np.float32)


@dataclass
class Turn:
    """One scripted caller turn for scenario WAV composition."""

    text: str
    pcm: np.ndarray
    sample_rate: int
    pre_pause_sec: float = 0.0  # silence inserted before this turn
    post_pause_sec: float = 2.0  # silence after (lets the bot reply)


def compose_scenario_wav(
    turns: list[Turn],
    out_path: Path | str,
    *,
    leading_silence_sec: float = 5.0,
    sample_rate: int = DEFAULT_SR,
) -> Path:
    """Concatenate caller turns into one scenario WAV.

    `leading_silence_sec` is appended at the start so the bot's greeting can
    finish before the caller "speaks" — Chrome starts reading the file the
    moment getUserMedia is called, which is before the bot dials in.
    """
    parts: list[np.ndarray] = [silence(leading_silence_sec, sample_rate)]
    for t in turns:
        if t.sample_rate != sample_rate:
            from backend.tts.openai_tts import _linear_resample  # local import to avoid cycle

            pcm = _linear_resample(t.pcm, t.sample_rate, sample_rate)
        else:
            pcm = t.pcm.astype(np.float32, copy=False)
        if t.pre_pause_sec > 0:
            parts.append(silence(t.pre_pause_sec, sample_rate))
        # Peak-normalize to 0.9 so Daily's AGC sees plenty of signal.
        peak = float(np.max(np.abs(pcm))) or 1.0
        parts.append((pcm / peak) * 0.9)
        if t.post_pause_sec > 0:
            parts.append(silence(t.post_pause_sec, sample_rate))
    full = np.concatenate(parts).astype(np.float32)
    return write_wav(out_path, full, sample_rate)
