"""Suite versioning primitives.

Stamp every suite run with a deterministic fingerprint of the scenario set and a
snapshot of the provider config the harness used, so runs can be grouped and
pinned by version (Next Phase Plan 4a/4b).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from backend.scenarios import Scenario
from backend.settings import get_settings


def scenario_set_hash(scenarios: Iterable[Scenario]) -> str:
    """SHA-256 over the full content of a scenario set.

    Deterministic and order-independent: each scenario is dumped to canonical
    JSON (sorted keys, enum values as strings), the per-scenario blobs are sorted,
    then hashed. Any meaningful edit — an added/removed scenario, an axis change,
    or a content change (goal, expected_outcome, constraints, weights) — produces
    a different hash.
    """
    reps = [
        json.dumps(s.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        for s in scenarios
    ]
    reps.sort()
    return hashlib.sha256("\n".join(reps).encode("utf-8")).hexdigest()


def provider_snapshot() -> dict:
    """Flat snapshot of the provider config the harness ran with.

    Records what *the harness* used (judge/caller models, tts/stt provider, target
    API) — not the live-bot VPS config — so two runs can be compared like for like.
    """
    s = get_settings()
    return {
        "openrouter_model_caller": s.openrouter_model_caller,
        "openrouter_model_scenario": s.openrouter_model_scenario,
        "openrouter_model_judge_text": s.openrouter_model_judge_text,
        "openrouter_model_judge_audio": s.openrouter_model_judge_audio,
        "tts_provider": s.tts_provider,
        "stt_provider": s.stt_provider,
        "qa_base_url": s.qa_base_url,
        "qa_site_id": s.qa_site_id,
    }
