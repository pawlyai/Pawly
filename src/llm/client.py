"""
Google Gen AI wrapper - GeminiClient.

chat()    -> main conversation (Gemini Flash)
extract() -> structured extraction (Gemini Flash)

Both return {"text": str, "input_tokens": int, "output_tokens": int}.

Singleton: get_gemini_client()
"""

import asyncio
from typing import Any

from src.config import settings


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
            response = await asyncio.to_thread(
                self._sync_call_genai,
                model,
                system_prompt,
                contents,
                max_tokens,
                temperature,
            )
            return self._format_response_genai(response)

        payload = self._build_legacy_messages(system_prompt, messages)
        response = await asyncio.to_thread(
            self._sync_call_legacy,
            model,
            payload,
            max_tokens,
            temperature,
        )
        return self._format_response_legacy(response)

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

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
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
