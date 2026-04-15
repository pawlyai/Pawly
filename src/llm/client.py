"""
LiteLLM wrapper — LLMClient.

Replaces the Gemini-specific GeminiClient. Model names follow LiteLLM conventions:

    gemini/gemini-2.5-flash   → Google Gemini  (uses GEMINI_API_KEY)
    claude-opus-4-6           → Anthropic Claude (uses ANTHROPIC_API_KEY)

Switch providers by editing models_config.yaml — no code changes needed.
Set MODEL_HOT_RELOAD=true to pick up yaml changes without restarting.

Public interface (unchanged from before):
    chat()            -> plain conversation
    chat_structured() -> conversation returning JSON with triage/intent/sentiment
    extract()         -> structured extraction (uses extraction_model)

Singleton: get_llm_client()
get_gemini_client() is kept as a backward-compatible alias.
"""

import json
import os
from typing import Any

import litellm

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

litellm.suppress_debug_info = True

# ── Structured response prompt suffix ─────────────────────────────────────────
# Appended to the system prompt for chat_structured() calls.
# Works across providers (Gemini, Claude, OpenAI) via json_object response_format.

_STRUCTURED_SUFFIX = """
You MUST respond with a valid JSON object only. No markdown fences, no prose — raw JSON.
Required fields:
  "response_text"  – string: the user-facing reply, plain text only, no emoji headers
  "triage_level"   – string: one of "RED", "ORANGE", "GREEN"
  "intent"         – string: one of "symptom_report", "nutrition", "exercise", "grooming", "behavior", "question", "general"
  "sentiment"      – string: one of "CALM", "ANXIOUS", "PANIC"
  "symptom_tags"   – array of strings: symptom keywords mentioned (empty array if none)
"""


class LLMClient:
    async def _call(
        self,
        model: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        litellm_messages = [{"role": "system", "content": system_prompt}] + messages
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": litellm_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format

        try:
            response = await litellm.acompletion(**kwargs)
        except Exception as exc:
            logger.error(
                "litellm.acompletion failed",
                model=model,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise
        text = response.choices[0].message.content or ""
        usage = response.usage
        return {
            "text": text,
            "model": model,
            "input_tokens": getattr(usage, "prompt_tokens", 0),
            "output_tokens": getattr(usage, "completion_tokens", 0),
        }

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        fallback_model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> dict[str, Any]:
        from src.llm.model_registry import get_model
        primary = model or get_model("main_model", settings.main_model)
        try:
            return await self._call(
                model=primary,
                system_prompt=system_prompt,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception:
            if fallback_model:
                logger.warning("primary model failed, retrying with fallback", primary=primary, fallback=fallback_model)
                return await self._call(
                    model=fallback_model,
                    system_prompt=system_prompt,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            raise

    async def chat_structured(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        fallback_model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        from src.llm.model_registry import get_model
        primary = model or get_model("main_model", settings.main_model)
        # Claude follows JSON via prompting; response_format is Gemini/OpenAI only
        is_claude = primary.startswith("claude")
        try:
            raw = await self._call(
                model=primary,
                system_prompt=system_prompt + _STRUCTURED_SUFFIX,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=None if is_claude else {"type": "json_object"},
            )
        except Exception:
            if fallback_model:
                logger.warning("primary model failed, retrying with fallback", primary=primary, fallback=fallback_model)
                is_claude_fallback = fallback_model.startswith("claude")
                raw = await self._call(
                    model=fallback_model,
                    system_prompt=system_prompt + _STRUCTURED_SUFFIX,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format=None if is_claude_fallback else {"type": "json_object"},
                )
            else:
                raise

        # Strip markdown fences Claude sometimes wraps around JSON
        text = raw["text"].strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]  # drop the ```json opening line
            text = text.rsplit("```", 1)[0].strip()

        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            parsed = {"response_text": raw["text"]}

        parsed["model"] = raw["model"]
        parsed["input_tokens"] = raw["input_tokens"]
        parsed["output_tokens"] = raw["output_tokens"]
        return parsed

    async def extract(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        from src.llm.model_registry import get_model
        return await self._call(
            model=get_model("extraction_model", settings.extraction_model),
            system_prompt=system_prompt,
            messages=messages,
            max_tokens=1024,
            temperature=0.2,
        )


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        os.environ.setdefault("GEMINI_API_KEY", settings.google_api_key)
        if settings.anthropic_api_key:
            os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
        _client = LLMClient()
    return _client


# Backward-compatible alias
get_gemini_client = get_llm_client
