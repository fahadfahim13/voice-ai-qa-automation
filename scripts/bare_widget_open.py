"""Step 2 verifier: open BizFinder preview, click Talk to us, screenshot in-call.

Run:
    uv run python -m scripts.bare_widget_open
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

from backend.browser import hangup, launch_browser, new_page, open_widget, widget_context
from backend.logging import setup_logging
from backend.settings import get_settings


async def run() -> int:
    setup_logging()
    s = get_settings()

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = s.harness_recordings_dir / f"bare_widget_open_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    origin = f"{urlparse(s.qa_preview_url).scheme}://{urlparse(s.qa_preview_url).netloc}"
    logger.info("Preview URL: {}  origin={}", s.qa_preview_url, origin)
    logger.info("Artifacts -> {}", out_dir)

    rc = 0
    async with launch_browser(headless=False, slow_mo_ms=150) as browser:
        async with widget_context(browser, origin=origin) as ctx:
            page = await new_page(ctx)
            try:
                state = await open_widget(page, s.qa_preview_url, screenshot_dir=out_dir)
                logger.success(
                    "In-call screenshot: {}  roomUrl={}  session_id={}",
                    state.screenshot_path,
                    state.room_url,
                    state.session_id,
                )
                # Linger a few seconds so the bot's greeting hits the wire.
                await page.wait_for_timeout(8000)
                await page.screenshot(
                    path=str(out_dir / "03_after_greeting.png"), full_page=True
                )
                await hangup(page)
                await page.wait_for_timeout(1500)
                await page.screenshot(
                    path=str(out_dir / "04_after_hangup.png"), full_page=True
                )
            except Exception as e:
                logger.error("Bare flow failed: {}", e)
                try:
                    await page.screenshot(path=str(out_dir / "fail.png"), full_page=True)
                except Exception:
                    pass
                rc = 1

    Path(out_dir / "summary.txt").write_text(
        f"preview_url={s.qa_preview_url}\nartifacts_dir={out_dir}\nexit={rc}\n",
        encoding="utf-8",
    )
    return rc


def main() -> None:
    import sys

    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
