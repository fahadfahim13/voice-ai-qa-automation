"""Caller persona — pre-generates a multi-turn caller script.

Phase 1 architecture (post-pivot): we render the full caller side of the call
into a single WAV before launching the browser. So the "persona" produces a
deterministic script up front based on a scenario seed.

The script is a list of utterances with per-turn pauses (which control how long
we expect the bot to spend on its reply between our turns).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from loguru import logger
from pydantic import BaseModel, Field

from backend.openrouter import OpenRouterClient
from backend.settings import get_settings


class CallerTurn(BaseModel):
    text: str
    expected_bot_reply_seconds: float = Field(
        4.5, description="How long to wait silently after this turn for the bot to reply"
    )


class CallerScript(BaseModel):
    persona: str
    goal: str
    turns: list[CallerTurn]


@dataclass
class ScenarioSeed:
    """The minimum a scenario needs to seed a persona script."""

    persona: str  # e.g. "Time-pressed founder evaluating SaaS"
    goal: str  # e.g. "Find out if FFTech has monthly pricing"
    intent: str  # e.g. "pricing-inquiry"
    business_summary: str  # what we know about the embedded business
    constraints: list[str] = ()  # e.g. ["never reveal email"]
    desired_turn_count: int = 4


SCHEMA_HINT = """
{
  "persona": "<one sentence persona>",
  "goal": "<one sentence call goal>",
  "turns": [
    {"text": "<what the caller says>", "expected_bot_reply_seconds": 4.5},
    ...
  ]
}
The first turn should be a polite opener that lands AFTER the bot's greeting.
The last turn should be a polite goodbye. Turns must be short conversational
sentences a person would actually say on a phone call. Avoid lists and
markdown. Avoid stage directions in brackets. Each turn under 30 words.
""".strip()


async def generate_script(
    seed: ScenarioSeed,
    *,
    client: OpenRouterClient | None = None,
    model: str | None = None,
) -> CallerScript:
    """Ask an LLM to produce a CallerScript matching the scenario seed."""
    s = get_settings()
    client = client or OpenRouterClient()
    model = model or s.openrouter_model_caller

    system = (
        "You write realistic CALLER scripts for QA-testing a small-business voice receptionist. "
        "You only write what the caller says. The bot will respond in between — you do not write "
        "the bot's side. Keep it natural, brief, and consistent with the persona and goal."
    )
    user = (
        f"Persona: {seed.persona}\n"
        f"Goal: {seed.goal}\n"
        f"Intent label: {seed.intent}\n"
        f"Target turn count: {seed.desired_turn_count}\n"
        f"Business being called: {seed.business_summary}\n"
        + (f"Constraints: {', '.join(seed.constraints)}\n" if seed.constraints else "")
        + "\nWrite the caller's lines."
    )
    logger.info("Generating caller script via {} ({} turns target)", model, seed.desired_turn_count)
    data = await client.chat_json(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        schema_hint=SCHEMA_HINT,
    )
    return CallerScript.model_validate(data)


def script_to_scripted_turns(script: CallerScript):
    """Convert CallerScript to orchestrator ScriptedTurn list."""
    from backend.orchestrator import ScriptedTurn

    return [
        ScriptedTurn(text=t.text, post_pause_sec=max(2.5, t.expected_bot_reply_seconds))
        for t in script.turns
    ]


def script_to_json(script: CallerScript) -> str:
    return json.dumps(script.model_dump(), indent=2)
