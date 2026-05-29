"""Playwright browser launch helpers.

The voice widget needs:
  - mic permission auto-granted (--use-fake-ui-for-media-stream)
  - a fake mic source backed by a WAV on disk
    (--use-file-for-fake-audio-capture=<wav>); the file is read once at
    browser start, so the harness pre-renders the full caller-side scenario
    audio before launching.
  - WebRTC + autoplay friendly defaults
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from loguru import logger
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

BASE_CHROMIUM_FLAGS = [
    # Auto-accept the mic permission prompt (no dialog).
    "--use-fake-ui-for-media-stream",
    # Use a synthetic audio capture device. When paired with
    # --use-file-for-fake-audio-capture below it sources from our WAV.
    "--use-fake-device-for-media-stream",
    # Let the bot greeting auto-play.
    "--autoplay-policy=no-user-gesture-required",
    # WebRTC needs these to actually negotiate.
    "--enable-features=NetworkService,NetworkServiceInProcess",
]


@asynccontextmanager
async def launch_browser(
    *,
    headless: bool = False,
    slow_mo_ms: int = 0,
    fake_audio_wav: Path | str | None = None,
) -> AsyncIterator[Browser]:
    """Yield a Chromium configured for the voice widget.

    If `fake_audio_wav` is given, Chrome reads that file as the synthetic mic
    source. The file MUST exist before launch and must be a standard PCM WAV.
    """
    flags = list(BASE_CHROMIUM_FLAGS)
    if fake_audio_wav is not None:
        wav_path = Path(fake_audio_wav).resolve()
        if not wav_path.exists():
            raise FileNotFoundError(f"Fake audio WAV not found: {wav_path}")
        flags.append(f"--use-file-for-fake-audio-capture={wav_path}")
        logger.info("Using fake audio capture file: {}", wav_path)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            slow_mo=slow_mo_ms,
            args=flags,
        )
        logger.debug("Chromium launched (headless={}, fake_audio={})", headless, bool(fake_audio_wav))
        try:
            yield browser
        finally:
            await browser.close()


@asynccontextmanager
async def widget_context(browser: Browser, *, origin: str) -> AsyncIterator[BrowserContext]:
    """Context with mic permission granted for the given origin."""
    ctx = await browser.new_context(
        viewport={"width": 1366, "height": 900},
        permissions=["microphone"],
        ignore_https_errors=False,
        # Use the bundled Chromium's default UA; some widgets do feature
        # detection against the UA string.
    )
    await ctx.grant_permissions(["microphone"], origin=origin)
    try:
        yield ctx
    finally:
        await ctx.close()


async def new_page(ctx: BrowserContext) -> Page:
    page = await ctx.new_page()

    page.on(
        "console",
        lambda msg: logger.debug("[browser console:{}] {}", msg.type, msg.text),
    )
    page.on("pageerror", lambda exc: logger.warning("[browser pageerror] {}", exc))
    return page
