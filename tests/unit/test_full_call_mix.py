"""Unit tests for the stereo full-call mix (C10 part 2)."""

from __future__ import annotations

import json

import numpy as np
import soundfile as sf

from backend import audio_mix

SR = 100  # tiny sample rate keeps the synthetic arrays small


def _write_scenario(path, samples):
    sf.write(str(path), np.asarray(samples, dtype=np.float32), samplerate=SR, subtype="PCM_16")


def _write_audio_log(path, *, gum_ms, rec_ms):
    path.write_text(
        json.dumps([{"evt": "gUM", "ts": gum_ms}, {"evt": "recorder_start", "ts": rec_ms}]),
        encoding="utf-8",
    )


def test_build_full_call_is_stereo_caller_left_bot_right(tmp_path, monkeypatch):
    caller = np.full(200, 0.5, dtype=np.float32)
    bot = np.full(50, -0.5, dtype=np.float32)
    # Avoid the real ffmpeg decode — feed a known bot PCM array.
    monkeypatch.setattr(audio_mix, "_decode_to_pcm", lambda *a, **k: bot)

    scenario = tmp_path / "scenario.wav"
    _write_scenario(scenario, caller)
    log = tmp_path / "audio_log.json"
    _write_audio_log(log, gum_ms=0, rec_ms=1000)  # 1.0s offset -> 100-sample pad
    out = tmp_path / "full_call.wav"

    audio_mix.build_full_call(scenario, tmp_path / "bot.webm", log, out, sample_rate=SR)

    data, sr = sf.read(str(out), always_2d=True)
    assert sr == SR
    assert data.shape[1] == 2  # stereo
    assert data.shape[0] == 200  # max(caller=200, bot+pad=150)
    left, right = data[:, 0], data[:, 1]
    assert np.allclose(left, 0.5, atol=1e-3)  # caller fills the left channel
    assert np.allclose(right[:100], 0.0, atol=1e-3)  # bot padded by the 1.0s offset
    assert np.allclose(right[100:150], -0.5, atol=1e-3)  # then bot audio
    assert np.allclose(right[150:], 0.0, atol=1e-3)  # tail silence


def test_backfill_full_call_happy_path(tmp_path, monkeypatch):
    monkeypatch.setattr(
        audio_mix, "_decode_to_pcm", lambda *a, **k: np.full(30, 0.25, dtype=np.float32)
    )
    _write_scenario(tmp_path / "scenario.wav", np.full(60, 0.1, dtype=np.float32))
    (tmp_path / "bot.webm").write_bytes(b"\x00")  # presence is enough; decode is mocked
    _write_audio_log(tmp_path / "audio_log.json", gum_ms=0, rec_ms=0)

    out = audio_mix.backfill_full_call(tmp_path, sample_rate=SR)
    assert out is not None and out.exists()


def test_backfill_missing_inputs_returns_none(tmp_path):
    assert audio_mix.backfill_full_call(tmp_path) is None  # empty dir, no scenario/bot


def test_backfill_ffmpeg_failure_returns_none(tmp_path, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("ffmpeg not found")

    monkeypatch.setattr(audio_mix, "_decode_to_pcm", _boom)
    _write_scenario(tmp_path / "scenario.wav", np.full(10, 0.1, dtype=np.float32))
    (tmp_path / "bot.webm").write_bytes(b"\x00")
    assert audio_mix.backfill_full_call(tmp_path, sample_rate=SR) is None  # no exception
