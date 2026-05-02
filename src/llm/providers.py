"""
Multi-provider LLM dispatch.

Returns a chat client whose `.chat()` / `.chat_structured()` interface matches
GeminiClient, dispatched by model name prefix:

    gemini-*    → GeminiClient    (existing)
    claude-*    → AnthropicClient (requires `anthropic` SDK + ANTHROPIC_API_KEY)
    gpt-*       → OpenAIClient    (requires `openai` SDK + OPENAI_API_KEY)
    deepseek-*  → DeepSeekClient  (requires `openai` SDK + DEEPSEEK_API_KEY)

Used by the orchestrator and the multiturn test runner so the same
conversation pipeline can be evaluated across providers without touching
business logic.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

from src.config import settings
from src.llm.client import get_gemini_client


class ChatClient(Protocol):
    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> dict[str, Any]: ...

    async def chat_structured(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> dict[str, Any]: ...


# Models grouped by provider for the Streamlit picker.
SUPPORTED_MODELS: dict[str, list[str]] = {
    "Gemini": [
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ],
    "Anthropic": [
        "claude-sonnet-4-6",
        "claude-opus-4-7",
        "claude-haiku-4-5",
    ],
    "OpenAI": [
        "gpt-4o",
        "gpt-4o-mini",
    ],
    "DeepSeek": [
        "deepseek-chat",
        "deepseek-reasoner",
    ],
}


def all_models() -> list[str]:
    return [m for group in SUPPORTED_MODELS.values() for m in group]


def provider_for(model: str) -> str:
    if model.startswith("gemini"):
        return "Gemini"
    if model.startswith("claude"):
        return "Anthropic"
    if model.startswith("gpt"):
        return "OpenAI"
    if model.startswith("deepseek"):
        return "DeepSeek"
    return "Gemini"


def get_chat_client(model: str | None = None) -> ChatClient:
    """Resolve the chat client for *model* (or default `settings.main_model`)."""
    name = model or settings.main_model
    provider = provider_for(name)

    if provider == "Anthropic":
        from src.llm.providers_anthropic import get_anthropic_client
        return get_anthropic_client()
    if provider == "OpenAI":
        from src.llm.providers_openai import get_openai_client
        return get_openai_client()
    if provider == "DeepSeek":
        from src.llm.providers_deepseek import get_deepseek_client
        return get_deepseek_client()
    return get_gemini_client()


def resolve_active_model() -> str:
    """Return the model the orchestrator should currently use.

    Honours `PAWLY_MODEL` env override (set by the test runner) before
    falling back to `settings.main_model`.
    """
    return os.environ.get("PAWLY_MODEL") or settings.main_model
