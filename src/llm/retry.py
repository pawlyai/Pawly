"""
Shared retry helper for LLM API calls.

All adapters (Gemini, DeepSeek, Anthropic, OpenAI) use this for bounded
exponential backoff on transient errors and a single fallback-model attempt
when retries are exhausted.

Usage:

    from src.llm.retry import run_with_retry

    async def _do(model: str):
        return await self._client.chat.completions.create(model=model, ...)

    return await run_with_retry(
        _do,
        primary_model=model,
        fallback_model=settings.fallback_model,
        label="deepseek",
    )
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Status codes universally treated as transient across vendors.
TRANSIENT_CODES: tuple[int, ...] = (429, 500, 502, 503, 504)
MAX_ATTEMPTS = 4
BASE_BACKOFF = 1.5

T = TypeVar("T")


def is_transient(exc: BaseException) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int) and code in TRANSIENT_CODES:
        return True
    msg = str(exc)
    if any(str(c) in msg for c in TRANSIENT_CODES):
        return True
    if "UNAVAILABLE" in msg:
        return True
    if "rate_limit" in msg.lower():
        return True
    return False


async def run_with_retry(
    call: Callable[[str], Awaitable[T]],
    *,
    primary_model: str,
    fallback_model: str | None = None,
    label: str = "llm",
) -> T:
    """Invoke ``call(model)``; retry transient failures with exponential backoff.

    On the final attempt, swap to *fallback_model* if it is set and different
    from *primary_model* and try once more. Non-transient exceptions propagate
    immediately.
    """
    backoff = BASE_BACKOFF
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return await call(primary_model)
        except Exception as exc:
            if not is_transient(exc):
                raise
            if attempt >= MAX_ATTEMPTS:
                if fallback_model and fallback_model != primary_model:
                    logger.warning(
                        "primary model exhausted - trying fallback",
                        provider=label,
                        primary=primary_model,
                        fallback=fallback_model,
                    )
                    return await call(fallback_model)
                raise
            delay = backoff + random.uniform(0, 0.5)
            logger.warning(
                "llm transient error - retrying",
                provider=label,
                attempt=attempt,
                delay=round(delay, 1),
                error=str(exc)[:120],
            )
            await asyncio.sleep(delay)
            backoff *= 2
    raise RuntimeError("run_with_retry: unreachable")


async def run_sync_with_retry(
    sync_fn: Callable[..., Any],
    *args: Any,
    primary_model: str,
    fallback_model: str | None = None,
    label: str = "llm",
) -> Any:
    """Like :func:`run_with_retry` but for sync callables (wrapped in to_thread).

    *sync_fn* must take ``(model, *args)`` as its first parameter.
    """
    async def _do(model: str) -> Any:
        return await asyncio.to_thread(sync_fn, model, *args)

    return await run_with_retry(
        _do,
        primary_model=primary_model,
        fallback_model=fallback_model,
        label=label,
    )
