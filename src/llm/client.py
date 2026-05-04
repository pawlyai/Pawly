"""
Google Gen AI wrapper - GeminiClient.

chat()            -> plain conversation (Gemini Flash)
chat_structured() -> conversation with JSON-schema-constrained output
extract()         -> structured extraction (Gemini Flash)

Singleton: get_gemini_client()
"""

import asyncio
import json
import random
from collections.abc import Callable
from typing import Any

from src.config import settings
from src.observability.tracing import observe_generation, update_generation
from src.utils.logger import get_logger

logger = get_logger(__name__)

_TRANSIENT_CODES = (429, 503, 504)
_MAX_ATTEMPTS = 4
_BASE_BACKOFF = 1.5


def _is_transient(exc: BaseException) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int) and code in _TRANSIENT_CODES:
        return True
    msg = str(exc)
    return any(str(c) in msg for c in _TRANSIENT_CODES) or "UNAVAILABLE" in msg


async def _run_with_retry(fn: Callable[..., Any], *args: Any) -> Any:
    """Retry transient errors, then fall back to FALLBACK_MODEL if still failing."""
    backoff = _BASE_BACKOFF
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return await asyncio.to_thread(fn, *args)
        except Exception as exc:
            if not _is_transient(exc):
                raise
            if attempt >= _MAX_ATTEMPTS:
                # All retries on primary model exhausted — try fallback once.
                fallback = settings.fallback_model
                # args[0] is always the model name in our sync call signatures.
                primary = args[0] if args else ""
                if fallback and fallback != primary:
                    logger.warning(
                        "primary model exhausted — trying fallback",
                        primary=primary,
                        fallback=fallback,
                    )
                    return await asyncio.to_thread(fn, fallback, *args[1:])
                raise
            delay = backoff + random.uniform(0, 0.5)
            logger.warning(
                "gemini transient error — retrying",
                attempt=attempt,
                delay=round(delay, 1),
                error=str(exc)[:120],
            )
            await asyncio.sleep(delay)
            backoff *= 2


# ── Structured response schema ────────────────────────────────────────────────
# Used by chat_structured() to force Gemini to return both the user-facing
# response text and classification metadata in a single call.

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "response_text": {
            "type": "STRING",
            "description": "The user-facing response message. Plain text only — no emoji headers or visual chrome.",
        },
        "triage_level": {
            "type": "STRING",
            "enum": ["RED", "ORANGE", "GREEN"],
            "description": "Triage classification: RED (emergency), ORANGE (concerning), GREEN (routine).",
        },
        "confidence": {
            "type": "NUMBER",
            "description": "Self-rated confidence in the triage decision, 0.0-1.0. High = enough information to commit; low = a clarification turn is needed.",
        },
        "missing_info": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Information still needed to raise confidence (e.g. 'duration', 'breathing pattern'). Empty when confident.",
        },
        "clarification_question": {
            "type": "STRING",
            "description": "ONE focused follow-up question to fill the most important missing_info. Empty string when confident.",
        },
        "intent": {
            "type": "STRING",
            "enum": ["symptom_report", "nutrition", "exercise", "grooming", "behavior", "question", "general"],
            "description": "The primary intent of the user message.",
        },
        "sentiment": {
            "type": "STRING",
            "enum": ["CALM", "ANXIOUS", "PANIC"],
            "description": "The owner's emotional state inferred from their message.",
        },
        "symptom_tags": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Symptom keywords mentioned or implied (e.g. 'vomiting', 'lethargy'). Empty list if none.",
        },
    },
    "required": [
        "response_text", "triage_level", "confidence",
        "missing_info", "clarification_question",
        "intent", "sentiment", "symptom_tags",
    ],
}


class GeminiClient:
    def __init__(self, api_key: str) -> None:
        try:
            from google import genai
            from google.genai import types
            self._sdk_mode = "genai"
            self._types = types
            self._client = genai.Client(api_key=api_key)
            return
        except ImportError:
            pass

        try:
            import google.generativeai as legacy_genai
            self._sdk_mode = "legacy"
            self._legacy = legacy_genai
            self._legacy.configure(api_key=api_key)
            return
        except ImportError as exc:
            raise RuntimeError(
                "No Gemini SDK found. Install `google-genai` (preferred) or `google-generativeai`."
            ) from exc

    @observe_generation(name="gemini-call")
    async def _call(
        self,
        model: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        """Call Gemini synchronously via asyncio.to_thread."""
        if self._sdk_mode == "genai":
            contents = self._build_contents(messages)
            response = await _run_with_retry(
                self._sync_call_genai,
                model,
                system_prompt,
                contents,
                max_tokens,
                temperature,
            )
            result = self._format_response_genai(response)
        else:
            payload = self._build_legacy_messages(system_prompt, messages)
            response = await _run_with_retry(
                self._sync_call_legacy,
                model,
                payload,
                max_tokens,
                temperature,
            )
            result = self._format_response_legacy(response)

        update_generation(
            model=model,
            input=messages,
            output=result["text"],
            usage_details={
                "input": result["input_tokens"],
                "output": result["output_tokens"],
            },
        )
        return result

    def _build_contents(self, messages: list[dict[str, Any]]) -> list[Any]:
        contents: list[Any] = []
        for msg in messages:
            role = "user" if msg.get("role") == "user" else "model"
            contents.append(
                self._types.Content(
                    role=role,
                    parts=[self._types.Part.from_text(text=str(msg.get("content", "")))],
                )
            )
        return contents

    def _build_legacy_messages(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        formatted: list[dict[str, str]] = []
        if system_prompt:
            formatted.append({"author": "system", "content": system_prompt})
        for msg in messages:
            author = "user" if msg.get("role") == "user" else "assistant"
            formatted.append({"author": author, "content": str(msg.get("content", ""))})
        return formatted

    def _sync_call_genai(
        self,
        model: str,
        system_prompt: str,
        contents: list[Any],
        max_tokens: int,
        temperature: float,
    ) -> Any:
        config = self._types.GenerateContentConfig(
            system_instruction=system_prompt or None,
            max_output_tokens=max_tokens,
            temperature=temperature,
        )
        return self._client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

    def _sync_call_legacy(
        self,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> Any:
        system_prompt = ""
        history: list[dict[str, Any]] = []
        for message in messages:
            author = message.get("author", "user")
            content = message.get("content", "")
            if author == "system":
                system_prompt = f"{system_prompt}\n{content}".strip()
                continue
            role = "user" if author == "user" else "model"
            history.append({"role": role, "parts": [content]})

        generation_config = self._legacy.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        )
        model_client = self._legacy.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt or None,
        )
        return model_client.generate_content(
            contents=history,
            generation_config=generation_config,
        )

    def _format_response_genai(self, response: Any) -> dict[str, Any]:
        text = self._extract_text(response)
        usage = getattr(response, "usage_metadata", None)
        input_tokens = self._extract_token_count(
            usage,
            ("prompt_token_count", "input_tokens", "prompt_tokens"),
        )
        output_tokens = self._extract_token_count(
            usage,
            ("candidates_token_count", "output_tokens", "completion_tokens"),
        )
        return {
            "text": text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    def _format_response_legacy(self, response: Any) -> dict[str, Any]:
        text = getattr(response, "text", "") or ""
        usage = getattr(response, "usage_metadata", None) or getattr(response, "usage", None)
        input_tokens = self._extract_token_count(
            usage,
            ("prompt_token_count", "prompt_tokens", "input_tokens"),
        )
        output_tokens = self._extract_token_count(
            usage,
            ("candidates_token_count", "completion_tokens", "output_tokens", "completion_token_count"),
        )
        return {
            "text": text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    def _extract_text(self, response: Any) -> str:
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text

        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return ""

        content = getattr(candidates[0], "content", None)
        parts = getattr(content, "parts", None) or []
        chunks: list[str] = []
        for part in parts:
            part_text = getattr(part, "text", None)
            if isinstance(part_text, str):
                chunks.append(part_text)
        return "\n".join(chunks).strip()

    def _extract_token_count(self, usage: Any, names: tuple[str, ...]) -> int:
        if usage is None:
            return 0
        if isinstance(usage, dict):
            for name in names:
                count = usage.get(name)
                if isinstance(count, int):
                    return count
            return 0
        for name in names:
            count = getattr(usage, name, None)
            if isinstance(count, int):
                return count
        return 0

    @observe_generation(name="gemini-call-structured")
    async def _call_structured(
        self,
        model: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
        response_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Call Gemini with JSON response_schema enforcement."""
        if self._sdk_mode == "genai":
            contents = self._build_contents(messages)
            response = await _run_with_retry(
                self._sync_call_genai_structured,
                model,
                system_prompt,
                contents,
                max_tokens,
                temperature,
                response_schema,
            )
            raw = self._format_response_genai(response)
            # Parse the JSON text into a dict and merge with token counts
            try:
                parsed = json.loads(raw["text"])
            except (json.JSONDecodeError, TypeError):
                parsed = {"response_text": raw["text"]}
            parsed["input_tokens"] = raw["input_tokens"]
            parsed["output_tokens"] = raw["output_tokens"]
        else:
            # Legacy SDK: fall back to regular call + manual JSON parse attempt
            result = await self._call(model, system_prompt, messages, max_tokens, temperature)
            try:
                parsed = json.loads(result["text"])
                parsed["input_tokens"] = result["input_tokens"]
                parsed["output_tokens"] = result["output_tokens"]
            except (json.JSONDecodeError, TypeError):
                parsed = {
                    "response_text": result["text"],
                    "input_tokens": result["input_tokens"],
                    "output_tokens": result["output_tokens"],
                }

        update_generation(
            model=model,
            input=messages,
            output=parsed.get("response_text", ""),
            usage_details={
                "input": parsed.get("input_tokens", 0),
                "output": parsed.get("output_tokens", 0),
            },
            metadata={
                "triage_level": parsed.get("triage_level"),
                "intent": parsed.get("intent"),
                "sentiment": parsed.get("sentiment"),
            },
        )
        return parsed

    def _sync_call_genai_structured(
        self,
        model: str,
        system_prompt: str,
        contents: list[Any],
        max_tokens: int,
        temperature: float,
        response_schema: dict[str, Any],
    ) -> Any:
        config = self._types.GenerateContentConfig(
            system_instruction=system_prompt or None,
            max_output_tokens=max_tokens,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=response_schema,
        )
        return self._client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Main conversation call (Gemini Flash by default).
        Returns {"text": str, "input_tokens": int, "output_tokens": int}.
        """
        return await self._call(
            model=model or settings.main_model,
            system_prompt=system_prompt,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def chat_structured(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """
        Conversation call with structured JSON output.

        Returns a dict with:
            response_text: str
            triage_level: "RED" | "ORANGE" | "GREEN"
            intent: str
            sentiment: "CALM" | "ANXIOUS" | "PANIC"
            symptom_tags: list[str]
            input_tokens: int
            output_tokens: int
        """
        return await self._call_structured(
            model=model or settings.main_model,
            system_prompt=system_prompt,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            response_schema=RESPONSE_SCHEMA,
        )

    async def chat_with_schema(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        response_schema: dict[str, Any],
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Structured call with a caller-supplied response_schema (Gemini-specific)."""
        return await self._call_structured(
            model=model or settings.main_model,
            system_prompt=system_prompt,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            response_schema=response_schema,
        )

    async def extract(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Structured extraction call (Gemini Flash).
        Returns {"text": str, "input_tokens": int, "output_tokens": int}.
        """
        return await self._call(
            model=settings.extraction_model,
            system_prompt=system_prompt,
            messages=messages,
            max_tokens=1024,
            temperature=0.2,
        )


_client: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    global _client
    if _client is None:
        _client = GeminiClient(api_key=settings.google_api_key)
    return _client
