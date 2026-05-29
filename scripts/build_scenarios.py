"""Seed the scenario library + (optionally) expand with OpenRouter.

Usage:
    uv run python -m scripts.build_scenarios            # seed baseline
    uv run python -m scripts.build_scenarios --expand   # + LLM expansion
"""

from __future__ import annotations

import asyncio

import typer
from loguru import logger

from backend.logging import setup_logging
from backend.scenarios import expand_library_llm, save_library, seed_library

app = typer.Typer(add_completion=False)


@app.command()
def main(
    expand: bool = typer.Option(False, "--expand", help="Also call OpenRouter to invent more"),
    n: int = typer.Option(16, "--n", help="Target additional scenarios when --expand"),
    biz: str = typer.Option(
        "FFTech SaaS — productivity web app for tracking daily habits and administering timed online exams; uses Google Calendar to schedule meetings.",
        "--biz",
    ),
) -> None:
    setup_logging()
    base = seed_library()
    paths = save_library(base)
    logger.success("Wrote {} baseline scenarios", len(paths))

    if expand:
        async def go():
            fresh = await expand_library_llm(n_target=n, business_summary=biz)
            paths2 = save_library(fresh)
            logger.success("Wrote {} additional LLM-generated scenarios", len(paths2))

        asyncio.run(go())


if __name__ == "__main__":
    app()
