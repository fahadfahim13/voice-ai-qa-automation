"""Thin OpenRouter client (OpenAI-compatible REST).

We route caller persona, scenario generation, and the text/audio judges
through OpenRouter so a single key + spend gate covers all three roles.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from backend.settings import get_settings


@dataclass
class LlmReply:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


class OpenRouterClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        s = get_settings()
        key = api_key or s.openrouter_api_key
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY not set")
        self.client = AsyncOpenAI(
            api_key=key,
            base_url=base_url or s.openrouter_base_url,
            default_headers={
                "HTTP-Referer": "https://github.com/bizfinder-qa",
                "X-Title": "BizFinder Voice QA",
            },
        )

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = 800,
        response_format: dict | None = None,
        timeout: float = 60.0,
    ) -> LlmReply:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "timeout": timeout,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if response_format is not None:
            kwargs["response_format"] = response_format
        logger.debug("OpenRouter chat model={} msgs={}", model, len(messages))
        resp = await self.client.chat.completions.create(**kwargs)
        choice = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        return LlmReply(
            text=choice,
            model=model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        )

    async def chat_json(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        schema_hint: str,
        temperature: float = 0.4,
        max_tokens: int = 1200,
    ) -> dict:
        """Chat asking for JSON output. Strips ```json fences if the model adds them."""
        sys = messages[0] if messages and messages[0]["role"] == "system" else None
        sys_text = (sys["content"] + "\n\n") if sys else ""
        sys_text += (
            "Respond with ONLY valid JSON that matches this schema. "
            "No prose, no markdown fences.\n\n" + schema_hint
        )
        msgs = [{"role": "system", "content": sys_text}] + [m for m in messages if m["role"] != "system"]
        reply = await self.chat(
            model=model,
            messages=msgs,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        text = reply.text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].lstrip()
        return json.loads(text)
