"""Per-call orchestrator: pre-render scenario WAV → drive widget → capture
bot audio → fetch QA Read API transcript → persist artifacts.

This is the workhorse used by both the one-shot CLI (scripts/run_call.py) and
the scenario suite runner (Step 8+).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
from backend.qa_api import QaApiClient
from backend.settings import get_settings
from backend.tts import get_tts


@dataclass
class ScriptedTurn:
    text: str
    pre_pause_sec: float = 0.0
    post_pause_sec: float = 4.5  # default reply window


@dataclass
class CallArtifacts:
    out_dir: Path
    scenario_wav: Path
    bot_audio: Path | None
    conversation_json: Path | None
    audio_log_json: Path
    session_id: str | None
    resolved_site_id: str | None
    room_url: str | None
    cost_usd: float = 0.0
    error: str | None = None
    qa_messages: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("out_dir", "scenario_wav", "bot_audio", "conversation_json", "audio_log_json"):
            if d[k] is not None:
                d[k] = str(d[k])
        return d


async def _find_conversation(
    site_id: str, since: datetime, max_wait_s: float = 30.0
) -> dict | None:
    # /api/widget/init reports the canonical siteId (e.g. "webwaala.com"),
    # but conversations are persisted under "<siteId>-preview" for preview
    # tenants. Try both.
    candidates = [site_id]
    if site_id and not site_id.endswith("-preview"):
        candidates.append(f"{site_id}-preview")
    deadline = asyncio.get_event_loop().time() + max_wait_s
    async with QaApiClient() as q:
        while asyncio.get_event_loop().time() < deadline:
            for sid in candidates:
                page = await q.list_conversations(site_id=sid, since=since, limit=5)
                if page.conversations:
                    full = await q.get_conversation(page.conversations[0].sessionId)
                    return full.model_dump(mode="json")
            await asyncio.sleep(1.5)
    return None


async def run_call(
    turns: list[ScriptedTurn],
    *,
    out_dir: Path,
    leading_silence_sec: float = 6.0,
    capture_bot_audio_flag: bool = True,
    voice: str | None = None,
    headless: bool = False,
    extra_silence_after_last_turn_sec: float = 6.0,
) -> CallArtifacts:
    """Execute one scripted call against the BizFinder voice widget."""
    s = get_settings()
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. TTS each turn.
    tts = get_tts(target_sample_rate=DEFAULT_SR)
    rendered_turns: list[Turn] = []
    total_cost = 0.0
    for i, t in enumerate(turns):
        res = await tts.synthesize(t.text, voice=voice)
        total_cost += res.cost_usd
        rendered_turns.append(
            Turn(
                text=t.text,
                pcm=res.pcm,
                sample_rate=res.sample_rate,
                pre_pause_sec=t.pre_pause_sec,
                post_pause_sec=t.post_pause_sec,
            )
        )
        logger.debug(
            "TTS turn {}: {:.2f}s, {} chars, cost=${:.4f}",
            i, res.pcm.shape[0] / res.sample_rate, len(t.text), res.cost_usd,
        )
    # Pad after last turn so the call lingers long enough for the bot to reply.
    if rendered_turns:
        rendered_turns[-1].post_pause_sec += extra_silence_after_last_turn_sec

    scenario_wav = out_dir / "scenario.wav"
    compose_scenario_wav(
        rendered_turns,
        scenario_wav,
        leading_silence_sec=leading_silence_sec,
    )
    wav_duration = sum(
        (t.pcm.shape[0] / t.sample_rate) + t.pre_pause_sec + t.post_pause_sec
        for t in rendered_turns
    ) + leading_silence_sec
    logger.info(
        "Scenario WAV {:.1f}s ({:.1f} KB)  cost=${:.4f}",
        wav_duration, scenario_wav.stat().st_size / 1024, total_cost,
    )

    origin = f"{urlparse(s.qa_preview_url).scheme}://{urlparse(s.qa_preview_url).netloc}"
    since = datetime.now(UTC) - timedelta(seconds=5)

    artifacts = CallArtifacts(
        out_dir=out_dir,
        scenario_wav=scenario_wav,
        bot_audio=None,
        conversation_json=None,
        audio_log_json=out_dir / "audio_log.json",
        session_id=None,
        resolved_site_id=None,
        room_url=None,
        cost_usd=total_cost,
    )

    async with launch_browser(headless=headless, fake_audio_wav=scenario_wav) as browser:
        async with widget_context(browser, origin=origin) as ctx:
            await install_fake_mic(ctx)
            page = await new_page(ctx)
            try:
                state = await open_widget(
                    page,
                    s.qa_preview_url,
                    screenshot_dir=out_dir,
                    call_setup_wait_ms=4000,
                )
                artifacts.session_id = state.session_id
                artifacts.resolved_site_id = state.resolved_site_id
                artifacts.room_url = state.room_url

                # Total wait = WAV play-through + 5s safety margin (already
                # included in extra_silence_after_last_turn_sec above).
                target_ms = int(wav_duration * 1000) + 2000
                logger.info("Letting the call run for ~{:.1f}s", target_ms / 1000)
                await page.wait_for_timeout(target_ms)
                await page.screenshot(path=str(out_dir / "after.png"), full_page=False)

                if capture_bot_audio_flag:
                    stop = await stop_bot_recording(page)
                    logger.info("stop_bot_recording: {}", stop)
                    bot_bytes, mime = await collect_bot_audio(page)
                    ext = ".webm" if "webm" in mime else (".ogg" if "ogg" in mime else ".bin")
                    bot_path = out_dir / f"bot{ext}"
                    bot_path.write_bytes(bot_bytes)
                    artifacts.bot_audio = bot_path
                    logger.info("Bot audio {} bytes -> {}", len(bot_bytes), bot_path)

                log = await audio_log(page)
                artifacts.audio_log_json.write_text(
                    json.dumps(log, indent=2, default=str), encoding="utf-8"
                )

                await hangup(page)
                await page.wait_for_timeout(1500)
            except Exception as e:
                artifacts.error = repr(e)
                logger.error("Call run failed: {}", e)
                try:
                    await page.screenshot(path=str(out_dir / "fail.png"), full_page=False)
                except Exception:
                    pass

    # Pull conversation from QA Read API.
    if artifacts.resolved_site_id:
        conv = await _find_conversation(artifacts.resolved_site_id, since)
        if conv is not None:
            artifacts.conversation_json = out_dir / "conversation.json"
            artifacts.conversation_json.write_text(
                json.dumps(conv, indent=2, default=str), encoding="utf-8"
            )
            artifacts.qa_messages = conv.get("messages", [])
            logger.info(
                "QA conversation pulled: {} messages",
                len(artifacts.qa_messages),
            )

    (out_dir / "run.json").write_text(
        json.dumps(artifacts.to_dict(), indent=2, default=str), encoding="utf-8"
    )
    return artifacts
