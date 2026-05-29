"""Smoke test for the QA Read API + local environment.

Mirrors the 9 connectivity checks in the handover §5, minus the SFTP ones (those
require the analytics VPS and are outside Phase 1's browser-driven scope).

Run:
    uv run python -m scripts.verify_setup
"""

from __future__ import annotations

import asyncio
import sys

from rich.console import Console
from rich.table import Table

from backend.logging import setup_logging
from backend.qa_api import QaApiClient, QaApiError
from backend.settings import get_settings


async def run() -> int:
    setup_logging()
    s = get_settings()
    console = Console()

    console.print(f"[bold]QA Read API smoke test[/bold]  base={s.qa_base_url}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("#")
    table.add_column("Check")
    table.add_column("Result", overflow="fold")
    table.add_column("Verdict", justify="right")

    failures = 0

    async with QaApiClient() as client:
        # 1. health
        try:
            health = await client.health()
            table.add_row("1", "GET /api/qa/health", f"ok={health.ok} svc={health.service}", "[green]PASS[/]")
        except Exception as e:
            table.add_row("1", "GET /api/qa/health", repr(e), "[red]FAIL[/]")
            failures += 1

        # 2. auth gate (wrong secret -> 401)
        try:
            gated = await client.auth_gate_check()
            table.add_row(
                "2",
                "Auth gate (wrong secret -> 401)",
                "401 returned" if gated else "non-401 (gate broken)",
                "[green]PASS[/]" if gated else "[red]FAIL[/]",
            )
            if not gated:
                failures += 1
        except Exception as e:
            table.add_row("2", "Auth gate", repr(e), "[red]FAIL[/]")
            failures += 1

        # 3. list (default site)
        try:
            page = await client.list_conversations(limit=3)
            table.add_row(
                "3",
                "GET /api/qa/conversations?limit=3",
                f"count={page.count} cursor={'yes' if page.nextCursor else 'no'}",
                "[green]PASS[/]",
            )
        except Exception as e:
            page = None
            table.add_row("3", "GET /api/qa/conversations", repr(e), "[red]FAIL[/]")
            failures += 1

        # 4. list with siteId
        try:
            scoped = await client.list_conversations(site_id=s.qa_site_id, limit=3)
            note = f"count={scoped.count} for siteId={s.qa_site_id}"
            verdict = "[green]PASS[/]"
            if scoped.count == 0:
                note += "  (no conversations yet — fine for unprovisioned siteId)"
                verdict = "[yellow]EMPTY[/]"
            table.add_row("4", f"List filtered by siteId={s.qa_site_id}", note, verdict)
        except Exception as e:
            table.add_row("4", "List filtered by siteId", repr(e), "[red]FAIL[/]")
            failures += 1

        # 5. fetch one conversation if list returned any
        if page and page.conversations:
            sample = page.conversations[0]
            try:
                full = await client.get_conversation(sample.sessionId)
                table.add_row(
                    "5",
                    f"GET /api/qa/conversations/{sample.sessionId}",
                    f"messages={len(full.messages)} site={full.siteId}",
                    "[green]PASS[/]",
                )
            except Exception as e:
                table.add_row("5", "GET /api/qa/conversations/<id>", repr(e), "[red]FAIL[/]")
                failures += 1
        else:
            table.add_row("5", "GET /api/qa/conversations/<id>", "skipped (list empty)", "[yellow]SKIP[/]")

        # 6. 404 on bogus id
        try:
            await client.get_conversation("nope-not-a-real-session")
            table.add_row("6", "GET bogus sessionId -> 404", "no error raised (unexpected)", "[red]FAIL[/]")
            failures += 1
        except QaApiError as e:
            verdict = "[green]PASS[/]" if e.status == 404 else "[red]FAIL[/]"
            table.add_row("6", "GET bogus sessionId -> 404", f"status={e.status}", verdict)
            if e.status != 404:
                failures += 1
        except Exception as e:
            table.add_row("6", "GET bogus sessionId -> 404", repr(e), "[red]FAIL[/]")
            failures += 1

    console.print(table)

    if failures == 0:
        console.print("[bold green]All smoke checks green.[/bold green]")
        return 0
    console.print(f"[bold red]{failures} check(s) failed.[/bold red]")
    return 1


def main() -> None:
    rc = asyncio.run(run())
    sys.exit(rc)


if __name__ == "__main__":
    main()
