"""Scenario schema and the 8 dimensional axes.

A Scenario seeds a single QA call. It includes everything needed by:
  - the caller persona generator (turns text)
  - the orchestrator (call settings)
  - the judge (rubric weights, success criteria)
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Intent(str, Enum):
    pricing = "pricing-inquiry"
    services = "services-inquiry"
    booking = "booking-request"
    support = "technical-support"
    complaint = "complaint"
    fit_check = "product-fit-check"
    location = "location-hours"
    sales = "sales-objection"


class Persona(str, Enum):
    polite_buyer = "polite-buyer"
    pressed_founder = "time-pressed-founder"
    skeptical_eval = "skeptical-evaluator"
    confused_newbie = "confused-newbie"
    angry_customer = "angry-customer"
    bargain_hunter = "bargain-hunter"


class Accent(str, Enum):
    en_us = "en-US"
    en_gb = "en-GB"
    en_in = "en-IN"
    en_au = "en-AU"


class InterruptStyle(str, Enum):
    none = "none"
    early_interject = "early-interject"  # caller talks over bot mid-greeting
    polite_pause = "polite-pause"        # extra silence before each turn


class NoiseProfile(str, Enum):
    clean = "clean"
    moderate = "moderate"


class Complexity(str, Enum):
    single_turn = "single-turn"
    multi_turn = "multi-turn"
    branched = "branched"


class Language(str, Enum):
    english_only = "english"
    code_switch = "code-switch-light"  # primarily English with rare phrases


class Adversarial(str, Enum):
    none = "none"
    out_of_scope = "out-of-scope-question"
    prompt_injection = "prompt-injection"
    pii_probe = "pii-probe"


class CriterionWeight(BaseModel):
    name: Literal[
        "relevance",
        "factual_grounding",
        "instruction_adherence",
        "stt_quality",
        "tts_pronunciation",
        "latency",
        "interrupt_handling",
        "scope_safety",
        "long_context",
        "graceful_completion",
    ]
    weight: float = Field(1.0, ge=0.0, le=5.0)


class Scenario(BaseModel):
    """One QA scenario. Persists to scenarios/library/<id>.json."""

    id: str = Field(..., description="Stable slug used in artifact paths")
    title: str
    description: str

    # 8 axes
    intent: Intent
    persona: Persona
    accent: Accent = Accent.en_us
    interrupt: InterruptStyle = InterruptStyle.none
    noise: NoiseProfile = NoiseProfile.clean
    complexity: Complexity = Complexity.multi_turn
    language: Language = Language.english_only
    adversarial: Adversarial = Adversarial.none

    # Caller setup
    goal: str
    turn_count: int = 4
    constraints: list[str] = Field(default_factory=list)
    expected_outcome: str

    # Judge weights (defaults match Phase 1 even weighting)
    criterion_weights: list[CriterionWeight] = Field(default_factory=list)

    # Caller voice (TTS voice id)
    caller_voice: str | None = None  # None → provider default

    def axis_tuple(self) -> tuple:
        return (
            self.intent.value,
            self.persona.value,
            self.accent.value,
            self.interrupt.value,
            self.noise.value,
            self.complexity.value,
            self.language.value,
            self.adversarial.value,
        )
