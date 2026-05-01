"""
OpenAI GPT adapter exposing the same interface as GeminiClient.
"""

from __future__ import annotations

import json
import os
from typing import Any

from src.llm.client import RESPONSE_SCHEMA
from src.observability.langfuse_decorator import observe_generation, update_generation
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIClient:
    def __init__(self, api_key: str) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai SDK not installed. Add `openai>=1.40` to dev extras."
            ) from exc
        self._client = AsyncOpenAI(api_key=api_key)

    @observe_generation(name="openai-call")
    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **_: Any,
    ) -> dict[str, Any]:
        msgs: list[dict[str, str]] = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        for m in messages:
            role = "user" if m.get("role") == "user" else "assistant"
            msgs.append({"role": role, "content": str(m.get("content", ""))})

        resp = await self._client.chat.completions.create(
            model=model or "gpt-4o-mini",
            messages=msgs,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = resp.choices[0].message.content or ""
        result = {
            "text": text,
            "input_tokens": resp.usage.prompt_tokens,
            "output_tokens": resp.usage.completion_tokens,
        }
        update_generation(
            model=model,
            input=messages,
            output=text,
            usage_details={"input": result["input_tokens"], "output": result["output_tokens"]},
        )
        return result

    async def chat_structured(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        msgs: list[dict[str, str]] = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        for m in messages:
            role = "user" if m.get("role") == "user" else "assistant"
            msgs.append({"role": role, "content": str(m.get("content", ""))})

        resp = await self._client.chat.completions.create(
            model=model or "gpt-4o-mini",
            messages=msgs,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content or "{}"
        payload = json.loads(text) if text else {}

        return {
            "response_text": payload.get("response_text", ""),
            "triage_level": payload.get("triage_level", "GREEN"),
            "intent": payload.get("intent", "general_chat"),
            "sentiment": payload.get("sentiment", "CALM"),
            "symptom_tags": payload.get("symptom_tags", []),
            "input_tokens": resp.usage.prompt_tokens,
            "output_tokens": resp.usage.completion_tokens,
        }

    async def extract(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self.chat(
            system_prompt=system_prompt,
            messages=messages,
            max_tokens=1024,
            temperature=0.2,
        )


_client: OpenAIClient | None = None


def get_openai_client() -> OpenAIClient:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set — required for GPT models.")
        _client = OpenAIClient(api_key=api_key)
    return _client
