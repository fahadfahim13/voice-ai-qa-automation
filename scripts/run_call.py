"""Step 5: run one scripted multi-turn call end-to-end.

Usage:
    uv run python -m scripts.run_call
        --turn "Hello, can you tell me about your services?"
        --turn "Do you offer monthly subscriptions?"
        --turn "Thanks, goodbye!"
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import typer
from loguru import logger

from backend.logging import setup_logging
from backend.orchestrator import ScriptedTurn, run_call
from backend.settings import get_settings

app = typer.Typer(add_completion=False)


DEFAULT_TURNS = [
    "Hello, can you tell me what services FFTech offers?",
    "Do you have monthly pricing plans?",
    "Thanks, that's all I needed. Goodbye!",
]


@app.command()
def main(
    turn: list[str] = typer.Option(
        None, "--turn", "-t", help="One scripted caller utterance per --turn flag"
    ),
    headless: bool = typer.Option(False, "--headless", help="Run Chromium headless"),
    name: str = typer.Option(None, "--name", help="Optional run name; goes into artifacts dir"),
) -> None:
    setup_logging()
    turns_text = turn or DEFAULT_TURNS
    turns = [ScriptedTurn(text=t) for t in turns_text]

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    label = f"{ts}_{name}" if name else ts
    out_dir = get_settings().harness_recordings_dir / f"call_{label}"

    artifacts = asyncio.run(run_call(turns, out_dir=out_dir, headless=headless))

    logger.info("=" * 70)
    logger.info("Run complete  out_dir={}", artifacts.out_dir)
    logger.info("session_id={}", artifacts.session_id)
    logger.info("resolved_site_id={}", artifacts.resolved_site_id)
    logger.info("bot_audio={}", artifacts.bot_audio)
    logger.info("cost_usd=${:.4f}", artifacts.cost_usd)
    logger.info("error={}", artifacts.error)
    logger.info("messages from QA API:")
    for m in artifacts.qa_messages:
        logger.info("  [{}] {!r}", m["role"], m["content"][:140])


if __name__ == "__main__":
    app()
