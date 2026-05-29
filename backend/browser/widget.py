"""Widget driver: navigate to the BizFinder preview, click Talk to us.

The button label may vary across tenants ("Talk to us", "Talk to us now",
"Call us") so we match on a regex. The widget also frequently lives inside an
iframe injected at runtime; we search frames as well as the main page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from playwright.async_api import (
    Locator,
    Page,
)
from playwright.async_api import (
    TimeoutError as PWTimeout,
)

TALK_BUTTON_RE = re.compile(r"(talk to us|call us|talk to.*now)", re.I)
# The green button inside the voice panel that actually starts the WebRTC call.
START_CALL_BUTTON_RE = re.compile(r"^\s*(call|start call|begin call)\s*$", re.I)


@dataclass
class InCallState:
    session_id: str | None
    room_url: str | None
    screenshot_path: Path
    resolved_site_id: str | None = None
    business_name: str | None = None


async def _find_talk_button(page: Page) -> Locator:
    """Return a Locator for the Talk-to-us button, scanning page + frames."""
    candidates: list[Locator] = []

    main = page.get_by_role("button", name=TALK_BUTTON_RE)
    candidates.append(main)

    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            candidates.append(frame.get_by_role("button", name=TALK_BUTTON_RE))
        except Exception:
            continue

    # Resolve the first candidate that has >=1 element.
    for loc in candidates:
        try:
            if await loc.count() > 0:
                return loc.first
        except Exception:
            continue

    # Fallback: text match anywhere
    return page.get_by_text(TALK_BUTTON_RE).first


async def _capture_widget_call_request(page: Page) -> dict:
    """Listen for the /api/widget/call response that returns the Daily.co room.

    Also captures /api/widget/init for the resolved siteId (preview tenants get
    a `-preview` suffix appended server-side).
    """
    captured: dict = {}

    async def on_response(resp):
        try:
            url = resp.url
            if "/api/widget/call" in url and resp.request.method == "POST" and resp.ok:
                body = await resp.json()
                captured.update(body)
                logger.info("Captured /api/widget/call: roomUrl={}", body.get("roomUrl"))
            elif "/api/widget/init" in url and resp.ok:
                try:
                    body = await resp.json()
                    captured["resolved_site_id"] = body.get("siteId")
                    captured["business_name"] = body.get("businessName")
                except Exception:
                    pass
        except Exception as e:
            logger.debug("on_response handler error: {}", e)

    page.on("response", on_response)
    return captured  # caller mutates as responses arrive


async def _find_start_call_button(page: Page) -> Locator:
    """The green CALL button inside the opened voice panel."""
    # Scope to recently-opened panels: prefer buttons containing only "CALL".
    return page.get_by_role("button", name=START_CALL_BUTTON_RE).first


async def open_widget(
    page: Page,
    preview_url: str,
    *,
    screenshot_dir: Path,
    panel_wait_ms: int = 1500,
    call_setup_wait_ms: int = 10_000,
) -> InCallState:
    """Open BizFinder preview, click Talk to us, click CALL, wait for dial-in.

    Two-step flow because the widget renders a panel first; the green CALL
    button inside the panel is what fires POST /api/widget/call.
    """
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    captured = await _capture_widget_call_request(page)

    logger.info("Navigating to {}", preview_url)
    await page.goto(preview_url, wait_until="networkidle", timeout=45_000)
    await page.wait_for_timeout(2000)
    await page.screenshot(path=str(screenshot_dir / "01_landed.png"), full_page=False)

    # Step 1 — open the panel
    btn = await _find_talk_button(page)
    try:
        await btn.wait_for(state="visible", timeout=15_000)
    except PWTimeout:
        await page.screenshot(path=str(screenshot_dir / "fail_no_talk_button.png"), full_page=True)
        raise RuntimeError("Could not locate the Talk to us button")

    logger.info("Clicking Talk to us (open panel)")
    await btn.click()
    await page.wait_for_timeout(panel_wait_ms)
    await page.screenshot(path=str(screenshot_dir / "02_panel_open.png"), full_page=False)

    # Step 2 — click the green CALL button inside the panel
    start = await _find_start_call_button(page)
    try:
        await start.wait_for(state="visible", timeout=10_000)
    except PWTimeout:
        await page.screenshot(
            path=str(screenshot_dir / "fail_no_call_button.png"), full_page=False
        )
        raise RuntimeError("Could not locate the CALL button inside the voice panel")

    logger.info("Clicking CALL (start call)")
    await start.click()

    # Wait for call provisioning (/api/widget/call response) + bot greeting.
    await page.wait_for_timeout(call_setup_wait_ms)
    await page.screenshot(path=str(screenshot_dir / "03_in_call.png"), full_page=False)

    room_url = captured.get("roomUrl")
    session_id = None
    if room_url:
        session_id = room_url.rstrip("/").rsplit("/", 1)[-1]

    logger.info(
        "open_widget complete  resolved_site_id={}  roomUrl={}  session_id={}",
        captured.get("resolved_site_id"),
        room_url,
        session_id,
    )
    return InCallState(
        session_id=session_id,
        room_url=room_url,
        screenshot_path=screenshot_dir / "03_in_call.png",
        resolved_site_id=captured.get("resolved_site_id"),
        business_name=captured.get("business_name"),
    )


async def hangup(page: Page) -> None:
    """Best-effort hangup: try a few label patterns, fallback to closing the page."""
    for pattern in (
        re.compile(r"hang up|end call|stop call|leave call", re.I),
        re.compile(r"close|x", re.I),
    ):
        try:
            loc = page.get_by_role("button", name=pattern).first
            if await loc.count() > 0:
                await loc.click()
                logger.info("Clicked hangup-style button: pattern={}", pattern.pattern)
                return
        except Exception:
            continue
    logger.warning("No hangup button found; closing page instead")
