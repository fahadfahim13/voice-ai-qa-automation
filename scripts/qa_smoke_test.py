"""QA Read API smoke test (health + list + wrong-secret → 401).

Python port of the handover's ``qa-smoke-test.sh``. Reuses the typed QA client
(``health`` / ``list_conversations`` / ``auth_gate_check``). The result-evaluation
lives in the pure :func:`evaluate_smoke` so it is unit-testable; :func:`run_smoke`
runs the live probes (never raises) and is reused by the Overview page button.

Run:
    uv run python -m scripts.qa_smoke_test
Exits 0 when all checks pass, 1 otherwise.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass


@dataclass
class SmokeCheck:
    name: str
    ok: bool
    detail: str


@dataclass
class SmokeResult:
    ok: bool
    checks: list[SmokeCheck]

    @property
    def failures(self) -> list[SmokeCheck]:
        return [c for c in self.checks if not c.ok]


def evaluate_smoke(
    *,
    health_status: int,
    health_ok: bool,
    list_status: int,
    wrong_secret_status: int,
) -> SmokeResult:
    """Pure pass/fail evaluation of the three smoke observations.

    health ok ⇔ ``status == 200 and ok:true``; list ok ⇔ ``status == 200``;
    auth gate ok ⇔ wrong secret returned ``401``. Overall = all three.
    """
    checks = [
        SmokeCheck(
            "health",
            health_status == 200 and bool(health_ok),
            f"status={health_status} ok={health_ok}",
        ),
        SmokeCheck(
            "list conversations",
            list_status == 200,
            f"status={list_status}",
        ),
        SmokeCheck(
            "auth gate (wrong secret -> 401)",
            wrong_secret_status == 401,
            "AUTH GATE OK" if wrong_secret_status == 401
            else f"status={wrong_secret_status} (gate NOT enforced)",
        ),
    ]
    return SmokeResult(ok=all(c.ok for c in checks), checks=checks)


async def _probe() -> SmokeResult:
    from backend.qa_api import QaApiClient, QaApiError

    health_status, health_ok, list_status, wrong = 0, False, 0, 0
    async with QaApiClient() as client:
        try:
            health = await client.health()
            health_status, health_ok = 200, health.ok
        except QaApiError as e:
            health_status = e.status
        except Exception:
            health_status = 0

        try:
            await client.list_conversations(limit=5)
            list_status = 200
        except QaApiError as e:
            list_status = e.status
        except Exception:
            list_status = 0

        try:
            wrong = 401 if await client.auth_gate_check() else 200
        except Exception:
            wrong = 0

    return evaluate_smoke(
        health_status=health_status,
        health_ok=health_ok,
        list_status=list_status,
        wrong_secret_status=wrong,
    )


def run_smoke() -> SmokeResult:
    """Run the live smoke probes synchronously. Never raises (UI-safe)."""
    try:
        return asyncio.run(_probe())
    except Exception as exc:  # never bubble into a caller/UI
        return SmokeResult(ok=False, checks=[SmokeCheck("smoke", False, f"unexpected: {exc}")])


def main() -> None:
    result = run_smoke()
    for c in result.checks:
        print(f"[{'PASS' if c.ok else 'FAIL'}] {c.name}: {c.detail}")
    print("ALL GREEN" if result.ok else f"SMOKE FAILED ({len(result.failures)} check(s))")
    sys.exit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
