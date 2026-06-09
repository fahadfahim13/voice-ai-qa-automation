"""Run a QA suite end-to-end.

Usage:
    uv run python -m scripts.run_suite                  # full library
    uv run python -m scripts.run_suite --max 5          # first 5 scenarios
    uv run python -m scripts.run_suite --only pricing-inquiry__simple-pricing-question
    uv run python -m scripts.run_suite --headless
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path

import typer
from loguru import logger

from backend.logging import setup_logging
from backend.orchestrator import run_suite, write_dry_run_suite
from backend.report import write_report
from backend.scenarios import load_library
from backend.settings import get_settings
from backend.url_builder import build_preview_url

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
    site: str = typer.Option(
        None, "--site", help="Target website hostname (e.g. webwaala.com). Overrides .env QA_PREVIEW_URL."
    ),
    preview_url: str = typer.Option(
        None, "--preview-url", help="Full preview URL override; trumps --site."
    ),
    url_pattern: str = typer.Option(
        "preview_id", "--url-pattern", help="URL shape: preview_id (/preview?id=) or preview_query (/?preview=)."
    ),
    suite_version: str = typer.Option(
        "v1.0", "--suite-version", help="Version tag stamped into suite.json for grouping/pinning."
    ),
    suite_dir: str = typer.Option(
        None, "--suite-dir", help="Explicit output dir for this suite (no 'find latest' race)."
    ),
    ids: str = typer.Option(
        None, "--ids", help="Comma-separated scenario ids to run (superset of --only)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Skip browser/LLM; write a valid 0-call suite.json and exit 0."
    ),
) -> None:
    # Runs are spawned by the dashboard (subprocess), inheriting its umask. If that
    # umask strips the execute bit, the suite_*/call_* dirs we mkdir below become
    # untraversable (drw-------) — the dashboard then can't read its own output and
    # the Reports/Overview pages crash with PermissionError. Force a sane umask so
    # every dir this run creates is owner+group readable/traversable.
    os.umask(0o022)
    setup_logging()
    s = get_settings()
    scenarios = load_library()
    if ids:
        wanted = {i.strip() for i in ids.split(",") if i.strip()}
        scenarios = [sc for sc in scenarios if sc.id in wanted]
        missing = wanted - {sc.id for sc in scenarios}
        if missing:
            raise typer.BadParameter(f"No scenario(s) with id: {', '.join(sorted(missing))}")
    elif only:
        scenarios = [sc for sc in scenarios if sc.id == only]
        if not scenarios:
            raise typer.BadParameter(f"No scenario with id {only!r}")
    elif max_n:
        scenarios = scenarios[:max_n]
    logger.info("Running {} scenarios", len(scenarios))

    out_dir = Path(suite_dir) if suite_dir else None

    if dry_run:
        target = out_dir or (
            s.harness_reports_dir / f"suite_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
        )
        write_dry_run_suite(
            scenarios, business_summary=biz, suite_dir=target, suite_version=suite_version
        )
        logger.success("Dry-run complete: {}", target / "suite.json")
        return

    resolved_preview = preview_url or (
        build_preview_url(s.qa_base_url, site, pattern=url_pattern) if site else None
    )
    # Target the chosen siteId for transcript lookup regardless of the .env default.
    site_override = site or None

    asyncio.run(
        run_suite(
            scenarios,
            business_summary=biz,
            suite_dir=out_dir,
            headless=headless,
            do_audio_judge=audio_judge,
            concurrency=concurrency,
            preview_url=resolved_preview,
            site_id_override=site_override,
            suite_version=suite_version,
        )
    )
    # Use the explicit suite dir if given; otherwise find the latest one.
    if out_dir is not None:
        report_target = out_dir
    else:
        candidates = sorted(
            Path(s.harness_reports_dir).glob("suite_*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        report_target = candidates[0] if candidates else None
    if report_target is not None:
        html_path, pdf_path = write_report(report_target)
        logger.info("HTML report: {}", html_path)
        if pdf_path:
            logger.info("PDF report : {}", pdf_path)


if __name__ == "__main__":
    app()
