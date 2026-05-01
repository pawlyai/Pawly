"""
Anthropic Claude adapter exposing the same interface as GeminiClient.

Returns dicts shaped like Gemini responses so the orchestrator works
unchanged. Structured output uses tool-use to enforce the JSON schema.
"""

from __future__ import annotations

import json
import os
from typing import Any

from src.llm.client import RESPONSE_SCHEMA
from src.observability.langfuse_decorator import observe_generation, update_generation
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AnthropicClient:
    def __init__(self, api_key: str) -> None:
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise RuntimeError(
                "anthropic SDK not installed. Add `anthropic>=0.40` to dev extras."
            ) from exc
        self._client = AsyncAnthropic(api_key=api_key)

    @observe_generation(name="anthropic-call")
    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **_: Any,
    ) -> dict[str, Any]:
        msgs = self._format_messages(messages)
        resp = await self._client.messages.create(
            model=model or "claude-sonnet-4-6",
            system=system_prompt or "",
            messages=msgs,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        result = {
            "text": text,
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
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
        """Force JSON output via tool-use; returns same fields as Gemini's structured call."""
        msgs = self._format_messages(messages)
        tool = {
            "name": "respond",
            "description": "Return the structured response.",
            "input_schema": _strip_response_mime(RESPONSE_SCHEMA),
        }
        resp = await self._client.messages.create(
            model=model or "claude-sonnet-4-6",
            system=system_prompt or "",
            messages=msgs,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=[tool],
            tool_choice={"type": "tool", "name": "respond"},
        )
        payload: dict[str, Any] = {}
        for block in resp.content:
            if getattr(block, "type", "") == "tool_use" and block.name == "respond":
                payload = block.input or {}
                break

        return {
            "response_text": payload.get("response_text", ""),
            "triage_level": payload.get("triage_level", "GREEN"),
            "intent": payload.get("intent", "general_chat"),
            "sentiment": payload.get("sentiment", "CALM"),
            "symptom_tags": payload.get("symptom_tags", []),
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
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

    @staticmethod
    def _format_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for m in messages:
            role = "user" if m.get("role") == "user" else "assistant"
            out.append({"role": role, "content": str(m.get("content", ""))})
        return out


def _strip_response_mime(schema: dict[str, Any]) -> dict[str, Any]:
    """Anthropic tool input_schema is plain JSON Schema — no Gemini-specific keys."""
    if isinstance(schema, dict):
        return {k: _strip_response_mime(v) for k, v in schema.items() if k != "response_mime_type"}
    if isinstance(schema, list):
        return [_strip_response_mime(v) for v in schema]
    return schema


_client: AnthropicClient | None = None


def get_anthropic_client() -> AnthropicClient:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set — required for Claude models.")
        _client = AnthropicClient(api_key=api_key)
    return _client
