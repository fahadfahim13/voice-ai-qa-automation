"""Mix scenario.wav (caller) and bot.webm into stereo full_call.wav.

Left = caller (what we fed the fake mic). Right = bot (what came back).

Timing is approximated from audio_log.json: caller starts at the first `gUM`
event (when Chrome began reading the fake-mic file), bot at `recorder_start`
(when the inbound MediaRecorder started). Browser-clock accurate, not
sample-accurate — good enough for a human to listen and judge.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from loguru import logger

from backend.audio import DEFAULT_SR


def _decode_to_pcm(src: Path, *, sample_rate: int = DEFAULT_SR) -> np.ndarray:
    """Decode webm/opus → mono float32 PCM at `sample_rate` via ffmpeg."""
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "f32le",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def _bot_offset_sec(audio_log_path: Path) -> float:
    if not audio_log_path.exists():
        return 0.0
    try:
        log = json.loads(audio_log_path.read_text(encoding="utf-8"))
    except Exception:
        return 0.0
    gum_ts = next((e["ts"] for e in log if e.get("evt") == "gUM"), None)
    rec_ts = next((e["ts"] for e in log if e.get("evt") == "recorder_start"), None)
    if gum_ts is None or rec_ts is None:
        return 0.0
    return max(0.0, (rec_ts - gum_ts) / 1000.0)


def build_full_call(
    scenario_wav: Path,
    bot_audio: Path,
    audio_log_path: Path,
    out_path: Path,
    *,
    sample_rate: int = DEFAULT_SR,
) -> Path:
    """Write a stereo WAV: left=caller, right=bot. Returns out_path."""
    caller, caller_sr = sf.read(str(scenario_wav), dtype="float32", always_2d=False)
    if caller.ndim > 1:
        caller = caller.mean(axis=1)
    if caller_sr != sample_rate:
        logger.warning(
            "scenario.wav sample rate {} != target {}; not resampling",
            caller_sr, sample_rate,
        )

    bot = _decode_to_pcm(bot_audio, sample_rate=sample_rate)
    offset_sec = _bot_offset_sec(audio_log_path)
    pad = int(round(offset_sec * sample_rate))
    bot_padded = np.concatenate([np.zeros(pad, dtype=np.float32), bot]).astype(np.float32)

    n = max(caller.shape[0], bot_padded.shape[0])
    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)
    left[: caller.shape[0]] = caller
    right[: bot_padded.shape[0]] = bot_padded
    stereo = np.stack([left, right], axis=1)
    np.clip(stereo, -1.0, 1.0, out=stereo)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), stereo, samplerate=sample_rate, subtype="PCM_16")
    logger.info(
        "full_call.wav: {:.1f}s stereo (caller L / bot R), bot offset {:.2f}s -> {}",
        n / sample_rate, offset_sec, out_path,
    )
    return out_path
