"""Python-side helpers for the in-page browser shim.

Pairs with backend/browser/fake_mic_init.js (added via add_init_script).
Provides bot-side audio capture and (legacy / debug) mic injection helpers.
"""

from __future__ import annotations

import base64
from pathlib import Path

import numpy as np
from playwright.async_api import BrowserContext, Page

_INIT_JS = (Path(__file__).parent / "fake_mic_init.js").read_text(encoding="utf-8")


async def install_fake_mic(ctx: BrowserContext) -> None:
    """Install the shim into every page created from this context."""
    await ctx.add_init_script(_INIT_JS)


def pcm_to_b64(pcm: np.ndarray) -> str:
    """Float32 mono PCM (range [-1, 1]) -> base64 of little-endian raw bytes."""
    if pcm.dtype != np.float32:
        pcm = pcm.astype(np.float32, copy=False)
    pcm = np.ascontiguousarray(pcm)
    return base64.b64encode(pcm.tobytes()).decode("ascii")


async def speak_pcm(
    page: Page, pcm: np.ndarray, sample_rate: int, gain: float = 1.0
) -> dict:
    """Stream the given PCM through the page's virtual mic. Blocks until done."""
    b64 = pcm_to_b64(pcm)
    return await page.evaluate(
        "([b64, sr, g]) => window.__qa_speakPcm(b64, sr, g)",
        [b64, sample_rate, gain],
    )


async def speak_tone(page: Page, freq_hz: float, duration_sec: float) -> dict:
    return await page.evaluate(
        "([f, d]) => window.__qa_speakTone(f, d)",
        [freq_hz, duration_sec],
    )


async def audio_log(page: Page) -> list[dict]:
    return await page.evaluate("() => window.__qa_audio_log || []")


async def force_inject_track(page: Page) -> dict:
    """Legacy: try to replace each PC audio sender's track with our dest track.

    Retained for debugging; in the WAV-on-mic flow (post-pivot) we don't call this.
    """
    return await page.evaluate("() => window.__qa_force_inject_track()")


async def stop_bot_recording(page: Page) -> dict:
    """Stop all attached MediaRecorders and return a summary."""
    return await page.evaluate("() => window.__qa_stop_bot_recording()")


async def collect_bot_audio(page: Page) -> tuple[bytes, str]:
    """Fetch concatenated bot audio bytes + mime type from the page.

    Returns (bytes, mime). The container is webm or ogg; encoder is opus.
    Decode downstream with ffmpeg/soundfile.
    """
    chunks_b64 = await page.evaluate(
        "() => ({chunks: window.__qa_bot_chunks_b64 || [], mime: window.__qa_bot_mime || ''})"
    )
    import base64

    parts = [base64.b64decode(c) for c in chunks_b64.get("chunks", [])]
    return b"".join(parts), chunks_b64.get("mime", "")
