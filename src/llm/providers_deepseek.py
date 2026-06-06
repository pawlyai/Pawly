"""
DeepSeek adapter exposing the same interface as GeminiClient.

DeepSeek serves an OpenAI-compatible REST API at https://api.deepseek.com,
so the adapter reuses the `openai` SDK with a custom base_url.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from src.config import settings
from src.llm.client import STRUCTURED_SCHEMA_INSTRUCTION
from src.llm.retry import run_with_retry
from src.observability.tracing import observe_generation, update_generation
from src.utils.logger import get_logger

logger = get_logger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-v4-flash"


# DeepSeek's `response_format=json_object` only guarantees parseable JSON,
# not strict adherence to the prompt's field schema, and in practice the
# model sometimes wraps the JSON in prose or markdown fences anyway. These
# helpers extract a usable structured payload from any of the shapes we've
# observed in production.
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)```", re.DOTALL | re.IGNORECASE)


def _first_balanced_object(text: str) -> str | None:
    """Return the first balanced `{...}` substring of *text*, ignoring braces
    that appear inside string literals. Returns None when no balanced object
    is present (e.g. text is plain prose with no JSON at all)."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse_structured_payload(text: str) -> tuple[dict[str, Any], str]:
    """Best-effort JSON parser for chat_structured responses.

    Returns (payload_dict, parse_status) where parse_status is one of:
      "json"           — text parsed as JSON directly
      "fenced"         — text contained ```json ... ``` block that parsed
      "balanced"       — first balanced {...} block parsed
      "prose_fallback" — JSON could not be parsed; payload is empty and the
                         caller should treat the original text as
                         `response_text` (model returned prose instead of
                         JSON, which is salvageable for chat purposes)
      "empty"          — text was empty
    """
    if not text or not text.strip():
        return {}, "empty"
    stripped = text.strip()

    # Candidate 1: the raw text as-is
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj, "json"
    except json.JSONDecodeError:
        pass

    # Candidate 2: any markdown-fenced blocks
    for match in _JSON_FENCE_RE.finditer(stripped):
        block = match.group(1).strip()
        if not block:
            continue
        try:
            obj = json.loads(block)
            if isinstance(obj, dict):
                return obj, "fenced"
        except json.JSONDecodeError:
            continue

    # Candidate 3: first balanced {...} substring
    balanced = _first_balanced_object(stripped)
    if balanced:
        try:
            obj = json.loads(balanced)
            if isinstance(obj, dict):
                return obj, "balanced"
        except json.JSONDecodeError:
            pass

    # Nothing parsed — caller can still use the raw text as response_text.
    return {}, "prose_fallback"


class DeepSeekClient:
    def __init__(self, api_key: str) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai SDK not installed. Add `openai>=1.40` to dev extras."
            ) from exc
        self._client = AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)

    @observe_generation(name="deepseek-call")
    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
        **_: Any,
    ) -> dict[str, Any]:
        msgs: list[dict[str, str]] = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        for m in messages:
            role = "user" if m.get("role") == "user" else "assistant"
            msgs.append({"role": role, "content": str(m.get("content", ""))})

        primary = model or DEFAULT_MODEL

        async def _do(m: str) -> Any:
            return await self._client.chat.completions.create(
                model=m,
                messages=msgs,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        resp = await run_with_retry(
            _do,
            primary_model=primary,
            fallback_model=settings.fallback_model,
            label="deepseek",
        )
        text = resp.choices[0].message.content or ""
        result = {
            "text": text,
            "input_tokens": resp.usage.prompt_tokens,
            "output_tokens": resp.usage.completion_tokens,
        }
        update_generation(
            model=primary,
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
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        # DeepSeek's response_format=json_object does not enforce a schema, so we
        # append explicit field instructions to the system prompt.
        augmented_system = (system_prompt or "") + STRUCTURED_SCHEMA_INSTRUCTION
        msgs: list[dict[str, str]] = [{"role": "system", "content": augmented_system}]
        for m in messages:
            role = "user" if m.get("role") == "user" else "assistant"
            msgs.append({"role": role, "content": str(m.get("content", ""))})

        primary = model or DEFAULT_MODEL

        async def _do(m: str) -> Any:
            return await self._client.chat.completions.create(
                model=m,
                messages=msgs,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
            )

        resp = await run_with_retry(
            _do,
            primary_model=primary,
            fallback_model=settings.fallback_model,
            label="deepseek",
        )
        text = resp.choices[0].message.content or ""
        payload, parse_status = _parse_structured_payload(text)

        # If JSON couldn't be parsed at all but the model returned prose,
        # salvage the prose as the user-facing response_text. The rule
        # engine will still provide the triage decision; structured
        # metadata fields default conservatively (GREEN / general / CALM).
        if parse_status == "prose_fallback":
            logger.warning(
                "deepseek chat_structured returned unparseable JSON - using raw text as response_text",
                snippet=text[:200],
            )
            payload = {"response_text": text.strip()}
        elif parse_status == "empty":
            logger.warning("deepseek chat_structured returned empty content")
        elif parse_status != "json":
            # Recovered via fenced or balanced extraction; useful diagnostic
            # for prompt tuning but not user-impacting.
            logger.info(
                "deepseek chat_structured JSON recovered via fallback parser",
                status=parse_status,
            )

        response_text = (payload.get("response_text") or "").strip()
        # Last-resort salvage: payload has metadata but no response_text. If
        # the raw text contains usable prose outside the JSON block, fall
        # back to that so we don't return an empty reply to the user.
        if not response_text and parse_status in ("fenced", "balanced"):
            outside = text
            if parse_status == "balanced":
                bal = _first_balanced_object(text)
                if bal:
                    outside = text.replace(bal, "").strip()
            else:
                outside = _JSON_FENCE_RE.sub("", text).strip()
            if outside:
                response_text = outside

        return {
            "response_text": response_text,
            "triage_level": payload.get("triage_level") or "GREEN",
            "intent": payload.get("intent") or "general_chat",
            "sentiment": payload.get("sentiment") or "CALM",
            "symptom_tags": payload.get("symptom_tags") or [],
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


_client: DeepSeekClient | None = None


def get_deepseek_client() -> DeepSeekClient:
    global _client
    if _client is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "") or settings.deepseek_api_key
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not set — required for DeepSeek models.")
        _client = DeepSeekClient(api_key=api_key)
    return _client
