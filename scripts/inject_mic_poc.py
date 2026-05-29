"""Step 3 PoC: pre-render a scripted utterance to WAV, launch Chrome with
--use-file-for-fake-audio-capture, drive the widget, verify the QA Read API
records a user message.

Flow:
  1. TTS-render UTTERANCE to a 48 kHz mono PCM_16 WAV (with leading silence
     so the bot greeting plays first)
  2. Launch Chromium with the WAV bound as the synthetic mic
  3. Open BizFinder preview, click Talk to us -> CALL
  4. Wait through greeting + utterance play-through (~5s lead + 3s speech + 8s for bot reply)
  5. Hang up
  6. Poll QA Read API for the new conversation; success if a user message lands

Run:
    uv run python -m scripts.inject_mic_poc
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

from backend.audio import DEFAULT_SR, Turn, compose_scenario_wav
from backend.browser import hangup, launch_browser, new_page, open_widget, widget_context
from backend.logging import setup_logging
from backend.qa_api import QaApiClient
from backend.settings import get_settings
from backend.tts import get_tts

UTTERANCE = "Hello, can you hear me clearly?"


async def _find_conversation(
    site_id: str, since: datetime, max_wait_s: float = 25.0
) -> dict | None:
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
    out_dir = s.harness_recordings_dir / f"inject_mic_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    origin = f"{urlparse(s.qa_preview_url).scheme}://{urlparse(s.qa_preview_url).netloc}"
    since = datetime.now(UTC) - timedelta(seconds=5)

    # 1. TTS-render the utterance and compose the scenario WAV.
    tts = get_tts(target_sample_rate=DEFAULT_SR)
    logger.info("TTS provider: {}", tts.name)
    tts_result = await tts.synthesize(UTTERANCE)
    logger.info(
        "Synthesized {:.2f}s of audio at {} Hz",
        tts_result.pcm.shape[0] / tts_result.sample_rate,
        tts_result.sample_rate,
    )
    wav_path = out_dir / "scenario.wav"
    compose_scenario_wav(
        [
            Turn(
                text=UTTERANCE,
                pcm=tts_result.pcm,
                sample_rate=tts_result.sample_rate,
                pre_pause_sec=0.0,
                post_pause_sec=8.0,  # let bot reply
            )
        ],
        wav_path,
        leading_silence_sec=6.0,  # bot greeting takes ~5s
    )
    logger.info("Scenario WAV -> {}  ({:.1f} KB)", wav_path, wav_path.stat().st_size / 1024)

    rc = 0
    resolved_site_id = None
    state = None
    async with launch_browser(headless=False, slow_mo_ms=80, fake_audio_wav=wav_path) as browser:
        async with widget_context(browser, origin=origin) as ctx:
            page = await new_page(ctx)
            try:
                state = await open_widget(
                    page, s.qa_preview_url, screenshot_dir=out_dir, call_setup_wait_ms=4000
                )
                resolved_site_id = state.resolved_site_id

                # Wait long enough for: leading silence (6s) + utterance (~3s)
                # + bot reply (~6-10s).
                logger.info("Waiting for utterance play-through + bot reply")
                await page.wait_for_timeout(22_000)
                await page.screenshot(path=str(out_dir / "04_after_inject.png"), full_page=False)

                await hangup(page)
                await page.wait_for_timeout(1500)
            except Exception as e:
                logger.error("PoC flow failed: {}", e)
                try:
                    await page.screenshot(path=str(out_dir / "fail.png"), full_page=False)
                except Exception:
                    pass
                rc = 1

    if resolved_site_id:
        logger.info("Looking up conversation via QA API for siteId={}", resolved_site_id)
        conv = await _find_conversation(resolved_site_id, since)
        if conv is None:
            logger.warning("No conversation appeared within window")
            rc = 1
        else:
            (out_dir / "conversation.json").write_text(
                json.dumps(conv, indent=2, default=str), encoding="utf-8"
            )
            user_msgs = [m for m in conv.get("messages", []) if m.get("role") == "user"]
            assistant_msgs = [m for m in conv.get("messages", []) if m.get("role") == "assistant"]
            logger.info(
                "Conversation has {} messages ({} user, {} assistant)",
                len(conv.get("messages", [])),
                len(user_msgs),
                len(assistant_msgs),
            )
            for m in conv.get("messages", []):
                logger.info("  [{}] {!r}", m["role"], m["content"][:120])
            if not user_msgs:
                logger.warning("No user message landed — bot didn't hear us")
                rc = 1
            else:
                logger.success("Injection PoC succeeded: bot transcribed our audio")
    else:
        logger.warning("resolved_site_id was never captured")
        rc = 1

    Path(out_dir / "summary.txt").write_text(
        f"utterance={UTTERANCE}\ntts_provider={tts.name}\n"
        f"resolved_site_id={resolved_site_id}\n"
        f"session_id={state.session_id if state else None}\n"
        f"wav={wav_path}\nexit={rc}\n",
        encoding="utf-8",
    )
    return rc


def main() -> None:
    import sys

    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
