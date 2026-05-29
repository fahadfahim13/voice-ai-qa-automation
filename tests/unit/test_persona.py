"""Unit test for caller persona generation (mocked OpenRouter)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from backend.caller import ScenarioSeed, generate_script
from backend.openrouter import OpenRouterClient


@pytest.mark.asyncio
@respx.mock
async def test_generate_script_parses_openrouter_response():
    fake_response = {
        "id": "x",
        "object": "chat.completion",
        "created": 1,
        "model": "deepseek/deepseek-chat",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "persona": "Curious founder",
                            "goal": "Check iOS support",
                            "turns": [
                                {"text": "Hi, quick question about your app?", "expected_bot_reply_seconds": 5},
                                {"text": "Does it work on iPhone?", "expected_bot_reply_seconds": 6},
                                {"text": "Great, thanks!", "expected_bot_reply_seconds": 3},
                            ],
                        }
                    ),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
    }
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=fake_response)
    )

    client = OpenRouterClient(api_key="test-key", base_url="https://openrouter.ai/api/v1")
    script = await generate_script(
        ScenarioSeed(
            persona="Curious founder",
            goal="Check iOS support",
            intent="product-fit",
            business_summary="FFTech SaaS",
            desired_turn_count=3,
        ),
        client=client,
    )
    assert script.persona == "Curious founder"
    assert len(script.turns) == 3
    assert script.turns[1].text == "Does it work on iPhone?"
