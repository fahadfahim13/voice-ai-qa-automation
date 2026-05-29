"""Step 4 PoC: capture bot audio via MediaRecorder.

Reuses the Step 3 flow (pre-rendered user utterance) and additionally:
  - Attaches a MediaRecorder to each inbound audio track on every PC
  - Stops recorders before hangup
  - Exfils the webm/opus audio bytes and saves bot.webm
  - Asserts the file is non-empty

Run:
    uv run python -m scripts.capture_bot_audio_poc
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from loguru import logger

from backend.audio import DEFAULT_SR, Turn, compose_scenario_wav
from backend.browser import (
    audio_log,
    collect_bot_audio,
    hangup,
    install_fake_mic,
    launch_browser,
    new_page,
    open_widget,
    stop_bot_recording,
    widget_context,
)
from backend.logging import setup_logging
from backend.qa_api import QaApiClient
from backend.settings import get_settings
from backend.tts import get_tts

UTTERANCE = "Hi, what services do you offer?"


async def _find_conversation(site_id, since, max_wait_s=25.0):
    deadline = asyncio.get_event_loop().time() + max_wait_s
    async with QaApiClient() as q:
        while asyncio.get_event_loop().time() < deadline:
            page = await q.list_conversations(site_id=site_id, since=since, limit=5)
            if page.conversations:
                full = await q.get_conversation(page.conversations[0].sessionId)
                return full.model_dump(mode="json")
            await asyncio.sleep(1.5)
    return None


async def run() -> int:
    setup_logging()
    s = get_settings()

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = s.harness_recordings_dir / f"capture_bot_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    origin = f"{urlparse(s.qa_preview_url).scheme}://{urlparse(s.qa_preview_url).netloc}"
    since = datetime.now(UTC) - timedelta(seconds=5)

    tts = get_tts(target_sample_rate=DEFAULT_SR)
    res = await tts.synthesize(UTTERANCE)
    wav = out_dir / "scenario.wav"
    compose_scenario_wav(
        [Turn(text=UTTERANCE, pcm=res.pcm, sample_rate=res.sample_rate, post_pause_sec=10.0)],
        wav,
        leading_silence_sec=6.0,
    )
    logger.info("Scenario WAV: {} ({:.1f} KB)", wav, wav.stat().st_size / 1024)

    rc = 0
    resolved_site_id = None
    bot_bytes = b""
    mime = ""

    async with launch_browser(headless=False, slow_mo_ms=80, fake_audio_wav=wav) as browser:
        async with widget_context(browser, origin=origin) as ctx:
            # install_fake_mic still pulls in the PC instrumentation (which now
            # also attaches the bot-audio recorders on every track event).
            await install_fake_mic(ctx)
            page = await new_page(ctx)
            try:
                state = await open_widget(
                    page, s.qa_preview_url, screenshot_dir=out_dir, call_setup_wait_ms=4000
                )
                resolved_site_id = state.resolved_site_id

                logger.info("Recording bot audio for ~22s")
                await page.wait_for_timeout(22_000)
                await page.screenshot(path=str(out_dir / "after.png"), full_page=False)

                stop = await stop_bot_recording(page)
                logger.info("stop_bot_recording: {}", stop)
                bot_bytes, mime = await collect_bot_audio(page)
                logger.info("Collected {} bytes  mime={}", len(bot_bytes), mime)

                log = await audio_log(page)
                (out_dir / "audio_log.json").write_text(
                    json.dumps(log, indent=2, default=str), encoding="utf-8"
                )

                await hangup(page)
                await page.wait_for_timeout(1500)
            except Exception as e:
                logger.error("PoC failed: {}", e)
                rc = 1

    # Save bot audio.
    ext = ".webm" if "webm" in mime else (".ogg" if "ogg" in mime else ".bin")
    bot_path = out_dir / f"bot{ext}"
    if bot_bytes:
        bot_path.write_bytes(bot_bytes)
        logger.success("Saved bot audio -> {}  ({:.1f} KB)", bot_path, len(bot_bytes) / 1024)
    else:
        logger.warning("No bot audio captured")
        rc = 1

    # Cross-check with QA API.
    if resolved_site_id:
        conv = await _find_conversation(resolved_site_id, since)
        if conv:
            (out_dir / "conversation.json").write_text(
                json.dumps(conv, indent=2, default=str), encoding="utf-8"
            )
            for m in conv.get("messages", []):
                logger.info("  [{}] {!r}", m["role"], m["content"][:120])

    return rc


def main() -> None:
    import sys

    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
