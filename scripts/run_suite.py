"""Run a QA suite end-to-end.

Usage:
    uv run python -m scripts.run_suite                  # full library
    uv run python -m scripts.run_suite --max 5          # first 5 scenarios
    uv run python -m scripts.run_suite --only pricing-inquiry__simple-pricing-question
    uv run python -m scripts.run_suite --headless
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from loguru import logger

from backend.logging import setup_logging
from backend.orchestrator import run_suite
from backend.report import write_report
from backend.scenarios import load_library
from backend.settings import get_settings

DEFAULT_BIZ = (
    "FFTech SaaS — productivity web app for tracking daily habits and administering "
    "timed online exams; uses Google Calendar to schedule meetings between recruiters "
    "and candidates."
)


app = typer.Typer(add_completion=False)


@app.command()
def main(
    biz: str = typer.Option(DEFAULT_BIZ, "--biz"),
    max_n: int = typer.Option(None, "--max"),
    only: str = typer.Option(None, "--only", help="Run a single scenario by id"),
    headless: bool = typer.Option(False, "--headless"),
    audio_judge: bool = typer.Option(True, "--audio-judge/--no-audio-judge"),
    concurrency: int = typer.Option(1, "--concurrency"),
) -> None:
    setup_logging()
    s = get_settings()
    scenarios = load_library()
    if only:
        scenarios = [sc for sc in scenarios if sc.id == only]
        if not scenarios:
            raise typer.BadParameter(f"No scenario with id {only!r}")
    elif max_n:
        scenarios = scenarios[:max_n]
    logger.info("Running {} scenarios", len(scenarios))

    asyncio.run(
        run_suite(
            scenarios,
            business_summary=biz,
            headless=headless,
            do_audio_judge=audio_judge,
            concurrency=concurrency,
        )
    )
    suite_dir = Path(s.harness_reports_dir)
    # The suite created its own subdir; find the latest one with a suite.json
    candidates = sorted(suite_dir.glob("suite_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if candidates:
        html_path, pdf_path = write_report(candidates[0])
        logger.info("HTML report: {}", html_path)
        if pdf_path:
            logger.info("PDF report : {}", pdf_path)


if __name__ == "__main__":
    app()
