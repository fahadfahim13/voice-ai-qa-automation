"""Step 6: persona-driven call.

OpenRouter generates the caller script from a ScenarioSeed; we then render +
drive the call exactly like scripts/run_call.py.

Usage:
    uv run python -m scripts.run_persona_call
        --persona "Curious founder evaluating SaaS productivity tools"
        --goal "Find out if FFTech SaaS works on iPhone"
        --intent product-fit-check
        --turns 4
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import typer
from loguru import logger

from backend.caller import (
    ScenarioSeed,
    generate_script,
    script_to_json,
    script_to_scripted_turns,
)
from backend.logging import setup_logging
from backend.orchestrator import run_call
from backend.settings import get_settings

DEFAULT_BIZ_SUMMARY = (
    "FFTech SaaS — a productivity web app for tracking daily habits and "
    "administering timed online exams; uses Google Calendar to schedule "
    "meetings between recruiters and candidates."
)


app = typer.Typer(add_completion=False)


@app.command()
def main(
    persona: str = typer.Option(..., "--persona", "-p"),
    goal: str = typer.Option(..., "--goal", "-g"),
    intent: str = typer.Option("general-inquiry", "--intent", "-i"),
    turns: int = typer.Option(4, "--turns", "-n"),
    biz_summary: str = typer.Option(DEFAULT_BIZ_SUMMARY, "--biz"),
    name: str = typer.Option(None, "--name"),
    headless: bool = typer.Option(False, "--headless"),
) -> None:
    setup_logging()

    seed = ScenarioSeed(
        persona=persona,
        goal=goal,
        intent=intent,
        business_summary=biz_summary,
        desired_turn_count=turns,
    )

    async def go() -> None:
        script = await generate_script(seed)
        logger.info("Generated script with {} turns", len(script.turns))
        for i, t in enumerate(script.turns):
            logger.info("  turn {}: {!r}", i, t.text)

        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        label = f"{ts}_{name}" if name else f"{ts}_{intent}"
        out_dir = get_settings().harness_recordings_dir / f"persona_{label}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "script.json").write_text(script_to_json(script), encoding="utf-8")
        (out_dir / "seed.json").write_text(
            json.dumps(seed.__dict__, indent=2), encoding="utf-8"
        )

        artifacts = await run_call(
            script_to_scripted_turns(script),
            out_dir=out_dir,
            headless=headless,
        )
        logger.info("=" * 70)
        for m in artifacts.qa_messages:
            logger.info("  [{}] {!r}", m["role"], m["content"][:140])

    asyncio.run(go())


if __name__ == "__main__":
    app()
