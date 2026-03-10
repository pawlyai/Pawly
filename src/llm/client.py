"""
Anthropic SDK wrapper — ClaudeClient.

chat()    → main conversation (Sonnet), 30s timeout, 3-attempt exponential backoff
extract() → structured extraction (Haiku), 10s timeout, 3-attempt exponential backoff

Both return {"text": str, "input_tokens": int, "output_tokens": int}.

Singleton: get_claude_client()
"""

import asyncio
import logging
from typing import Any

import anthropic

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Anthropic error types that warrant a retry
_RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
)


class ClaudeClient:
    def __init__(self, api_key: str) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _call(
        self,
        model: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
        timeout: float,
    ) -> dict[str, Any]:
        """Call the API with exponential-backoff retry (3 attempts)."""
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
            "timeout": timeout,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        # temperature is not a top-level param for Claude messages API,
        # but is supported via the `temperature` arg in newer SDK versions.
        # Keep it for future use.

        last_exc: Exception = RuntimeError("No attempts made")
        for attempt in range(3):
            try:
                response = await self.client.messages.create(**kwargs)
                text = response.content[0].text  # type: ignore[union-attr]
                return {
                    "text": text,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                }
            except _RETRYABLE as exc:
                last_exc = exc
                if attempt < 2:
                    wait = 2 ** attempt  # 1s, 2s
                    logger.warning(
                        "llm call retrying",
                        model=model,
                        attempt=attempt + 1,
                        error=str(exc),
                        wait_s=wait,
                    )
                    await asyncio.sleep(wait)
            except anthropic.APIStatusError as exc:
                # 4xx errors other than rate-limit are not retryable
                raise

        raise last_exc

    # ── Public ────────────────────────────────────────────────────────────────

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """
        Main conversation call (Sonnet by default).
        Returns {"text": str, "input_tokens": int, "output_tokens": int}.
        """
        return await self._call(
            model=model or settings.main_model,
            system_prompt=system_prompt,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=30.0,
        )

    async def extract(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Cheap structured extraction call (Haiku).
        Returns {"text": str, "input_tokens": int, "output_tokens": int}.
        """
        return await self._call(
            model=settings.extraction_model,
            system_prompt=system_prompt,
            messages=messages,
            max_tokens=1024,
            temperature=0.2,
            timeout=10.0,
        )


# ── Singleton ─────────────────────────────────────────────────────────────────

_client: ClaudeClient | None = None


def get_claude_client() -> ClaudeClient:
    global _client
    if _client is None:
        _client = ClaudeClient(api_key=settings.anthropic_api_key)
    return _client
