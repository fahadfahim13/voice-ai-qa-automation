"""Suite runner: orchestrate scenario library → per-call run → judges → results."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from backend.caller import (
    ScenarioSeed,
    generate_script,
    script_to_scripted_turns,
)
from backend.judge import AudioVerdict, JudgeVerdict, judge_audio, judge_call
from backend.openrouter import OpenRouterClient
from backend.orchestrator.call_runner import run_call
from backend.scenarios import Scenario
from backend.settings import get_settings


@dataclass
class CallResult:
    scenario_id: str
    out_dir: Path
    script_json: Path
    artifacts: dict  # CallArtifacts.to_dict()
    text_verdict: dict | None = None
    audio_verdict: dict | None = None
    error: str | None = None
    elapsed_seconds: float = 0.0


@dataclass
class SuiteResult:
    started_at: str
    finished_at: str
    business_summary: str
    n_total: int
    n_passed: int
    n_failed: int
    n_errors: int
    avg_overall_score: float
    calls: list[CallResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            **{k: v for k, v in asdict(self).items() if k != "calls"},
            "calls": [
                {**asdict(c), "out_dir": str(c.out_dir), "script_json": str(c.script_json)}
                for c in self.calls
            ],
        }


async def _run_one(
    scenario: Scenario,
    *,
    suite_dir: Path,
    business_summary: str,
    headless: bool,
    or_client: OpenRouterClient,
    do_audio_judge: bool,
) -> CallResult:
    start = datetime.now(UTC)
    out_dir = suite_dir / f"call_{scenario.id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    result = CallResult(
        scenario_id=scenario.id,
        out_dir=out_dir,
        script_json=out_dir / "script.json",
        artifacts={},
    )
    try:
        seed = ScenarioSeed(
            persona=f"{scenario.persona.value} with {scenario.accent.value} accent",
            goal=scenario.goal,
            intent=scenario.intent.value,
            business_summary=business_summary,
            constraints=scenario.constraints,
            desired_turn_count=scenario.turn_count,
        )
        script = await generate_script(seed, client=or_client)
        result.script_json.write_text(script.model_dump_json(indent=2), encoding="utf-8")

        artifacts = await run_call(
            script_to_scripted_turns(script),
            out_dir=out_dir,
            headless=headless,
            voice=scenario.caller_voice,
        )
        result.artifacts = artifacts.to_dict()

        verdict: JudgeVerdict = await judge_call(
            scenario=scenario,
            script=script,
            artifacts=artifacts,
            client=or_client,
        )
        result.text_verdict = verdict.model_dump()
        (out_dir / "text_verdict.json").write_text(
            verdict.model_dump_json(indent=2), encoding="utf-8"
        )

        if do_audio_judge and artifacts.bot_audio:
            try:
                av: AudioVerdict = await judge_audio(
                    audio_path=Path(artifacts.bot_audio),
                    expected_transcript=" ".join(
                        m["content"] for m in artifacts.qa_messages if m["role"] == "assistant"
                    ),
                    client=or_client,
                )
                result.audio_verdict = av.model_dump()
                (out_dir / "audio_verdict.json").write_text(
                    av.model_dump_json(indent=2), encoding="utf-8"
                )
            except Exception as e:
                logger.warning("Audio judge failed for {}: {}", scenario.id, e)
                result.audio_verdict = {"error": repr(e)}
    except Exception as e:
        logger.exception("Call run failed for {}", scenario.id)
        result.error = repr(e)
    finally:
        result.elapsed_seconds = (datetime.now(UTC) - start).total_seconds()
    return result


async def run_suite(
    scenarios: Iterable[Scenario],
    *,
    business_summary: str,
    suite_dir: Path | None = None,
    headless: bool = False,
    do_audio_judge: bool = True,
    concurrency: int = 1,
) -> SuiteResult:
    """Run a list of scenarios sequentially (default) or with a small concurrency.

    Browser concurrency > 1 is risky on a single dev box (Daily.co rate-limits
    the same IP and Chromium+audio is heavy). Default 1.
    """
    s = get_settings()
    started = datetime.now(UTC)
    suite_dir = suite_dir or s.harness_reports_dir / f"suite_{started.strftime('%Y%m%dT%H%M%SZ')}"
    suite_dir.mkdir(parents=True, exist_ok=True)
    or_client = OpenRouterClient()
    scenario_list = list(scenarios)
    logger.info("Suite: {} scenarios → {}", len(scenario_list), suite_dir)

    results: list[CallResult] = []
    if concurrency <= 1:
        for sc in scenario_list:
            r = await _run_one(
                sc,
                suite_dir=suite_dir,
                business_summary=business_summary,
                headless=headless,
                or_client=or_client,
                do_audio_judge=do_audio_judge,
            )
            results.append(r)
    else:
        sem = asyncio.Semaphore(concurrency)

        async def _bounded(sc):
            async with sem:
                return await _run_one(
                    sc,
                    suite_dir=suite_dir,
                    business_summary=business_summary,
                    headless=headless,
                    or_client=or_client,
                    do_audio_judge=do_audio_judge,
                )

        results = await asyncio.gather(*[_bounded(sc) for sc in scenario_list])

    finished = datetime.now(UTC)
    scores = [
        r.text_verdict["overall_score"]
        for r in results
        if r.text_verdict and "overall_score" in r.text_verdict
    ]
    n_passed = sum(1 for r in results if r.text_verdict and r.text_verdict.get("pass_fail"))
    n_failed = sum(
        1 for r in results if r.text_verdict and not r.text_verdict.get("pass_fail", False)
    )
    n_errors = sum(1 for r in results if r.error)

    suite = SuiteResult(
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        business_summary=business_summary,
        n_total=len(results),
        n_passed=n_passed,
        n_failed=n_failed,
        n_errors=n_errors,
        avg_overall_score=(sum(scores) / len(scores)) if scores else 0.0,
        calls=results,
    )
    (suite_dir / "suite.json").write_text(
        json.dumps(suite.to_dict(), indent=2, default=str), encoding="utf-8"
    )
    logger.success(
        "Suite done: {} total, {} passed, {} failed, {} errors  avg={:.2f}",
        suite.n_total, suite.n_passed, suite.n_failed, suite.n_errors, suite.avg_overall_score,
    )
    return suite
