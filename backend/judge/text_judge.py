"""Text judge: grades a call from transcript + scenario + metrics."""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from backend.caller import CallerScript
from backend.judge.rubric import JUDGE_SCHEMA_HINT, JudgeVerdict
from backend.openrouter import OpenRouterClient
from backend.orchestrator import CallArtifacts
from backend.scenarios import Scenario
from backend.settings import get_settings


def _format_qa_messages(messages: list[dict]) -> str:
    lines = []
    for m in messages:
        ts = m.get("createdAt", "?")
        lines.append(f"[{m['role']}] {m['content']}  (at {ts})")
    return "\n".join(lines)


async def judge_call(
    *,
    scenario: Scenario,
    script: CallerScript,
    artifacts: CallArtifacts,
    client: OpenRouterClient | None = None,
    model: str | None = None,
) -> JudgeVerdict:
    s = get_settings()
    client = client or OpenRouterClient()
    model = model or s.openrouter_model_judge_text

    transcript = _format_qa_messages(artifacts.qa_messages)
    metrics_excerpt = ""
    if artifacts.conversation_json and Path(artifacts.conversation_json).exists():
        try:
            conv = json.loads(Path(artifacts.conversation_json).read_text(encoding="utf-8"))
            metrics_excerpt = json.dumps(conv.get("metrics") or {}, indent=2)[:1200]
        except Exception:
            pass

    scripted = "\n".join(f"- {t.text}" for t in script.turns)

    system = (
        "You are an exacting QA judge for a small-business voice receptionist. "
        "Score the call against the 10-criterion rubric. Always justify each score "
        "with one short piece of evidence from the transcript and one rationale sentence."
    )
    user = (
        f"Scenario: {scenario.title}\n"
        f"Goal: {scenario.goal}\n"
        f"Expected outcome: {scenario.expected_outcome}\n"
        f"Persona: {scenario.persona.value}\n"
        f"Intent: {scenario.intent.value}\n"
        f"Adversarial: {scenario.adversarial.value}\n\n"
        f"Scripted caller turns (what the caller was *supposed* to say):\n{scripted}\n\n"
        f"Transcript (from QA Read API, isVoice):\n{transcript or '(empty)'}\n\n"
        f"Per-turn metrics (latency etc.):\n{metrics_excerpt or '(none)'}\n\n"
        "Grade now."
    )
    logger.info("Text judge via {} ({} messages)", model, len(artifacts.qa_messages))
    data = await client.chat_json(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        schema_hint=JUDGE_SCHEMA_HINT,
        temperature=0.2,
        max_tokens=2000,
    )
    return JudgeVerdict.model_validate(data)
