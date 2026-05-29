"""Probe the BizFinder preview to discover the actual Talk-to-us button + API.

Outputs:
  - list of buttons/links matching voice/call keywords (with selector + bounding box)
  - all POST requests fired in the first 25s after navigation + click
  - a screenshot before and after click
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from urllib.parse import urlparse

from loguru import logger

from backend.browser import launch_browser, new_page, widget_context
from backend.logging import setup_logging
from backend.settings import get_settings

VOICE_RE = re.compile(r"talk|call|voice|speak|mic|ask|assistant|chat", re.I)


async def run() -> int:
    setup_logging()
    s = get_settings()

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = s.harness_recordings_dir / f"probe_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    origin = f"{urlparse(s.qa_preview_url).scheme}://{urlparse(s.qa_preview_url).netloc}"

    network_log: list[dict] = []

    async with launch_browser(headless=False, slow_mo_ms=50) as browser:
        async with widget_context(browser, origin=origin) as ctx:
            page = await new_page(ctx)

            def on_request(req):
                if req.method != "GET":
                    network_log.append(
                        {"method": req.method, "url": req.url, "post_data": req.post_data}
                    )

            async def on_response(resp):
                try:
                    if resp.request.method != "GET" or "/api/" in resp.url:
                        body = ""
                        try:
                            body = (await resp.text())[:500]
                        except Exception:
                            pass
                        network_log.append(
                            {
                                "kind": "response",
                                "status": resp.status,
                                "method": resp.request.method,
                                "url": resp.url,
                                "body_snippet": body,
                            }
                        )
                except Exception:
                    pass

            page.on("request", on_request)
            page.on("response", on_response)

            await page.goto(s.qa_preview_url, wait_until="networkidle", timeout=45_000)
            await page.wait_for_timeout(3000)
            await page.screenshot(path=str(out_dir / "pre.png"), full_page=False)

            # Enumerate clickable candidates across all frames
            candidates: list[dict] = []
            for frame in page.frames:
                for sel in ["button", "[role=button]", "a"]:
                    handles = await frame.query_selector_all(sel)
                    for h in handles:
                        try:
                            txt = (await h.inner_text()).strip()
                            if not txt or len(txt) > 80:
                                continue
                            if VOICE_RE.search(txt):
                                box = await h.bounding_box()
                                candidates.append(
                                    {
                                        "frame": frame.url,
                                        "selector": sel,
                                        "text": txt,
                                        "bbox": box,
                                    }
                                )
                        except Exception:
                            continue

            logger.info("Voice-keyword candidates: {}", len(candidates))
            (out_dir / "candidates.json").write_text(
                json.dumps(candidates, indent=2, default=str), encoding="utf-8"
            )

            # Click the first plausible candidate (prefer ones with bbox in viewport)
            chosen = next(
                (c for c in candidates if c.get("bbox")),
                candidates[0] if candidates else None,
            )
            if chosen:
                logger.info("Clicking: {!r} in frame {}", chosen["text"], chosen["frame"])
                frame = next(f for f in page.frames if f.url == chosen["frame"])
                btn = frame.get_by_text(chosen["text"], exact=False).first
                try:
                    await btn.click(timeout=5000)
                except Exception as e:
                    logger.warning("Click failed via locator, falling back to bbox click: {}", e)
                    bb = chosen["bbox"]
                    await page.mouse.click(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2)
            else:
                logger.error("No voice-keyword candidate found")

            await page.wait_for_timeout(12_000)
            await page.screenshot(path=str(out_dir / "post.png"), full_page=False)

    (out_dir / "network.json").write_text(
        json.dumps(network_log, indent=2, default=str), encoding="utf-8"
    )
    logger.success("Probe artifacts -> {}", out_dir)
    return 0


def main() -> None:
    import sys

    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
