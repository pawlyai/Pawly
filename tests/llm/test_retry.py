"""
Unit tests for the shared LLM retry helper.

Validates:
- Transient HTTP error codes trigger retry with exponential backoff.
- Non-transient errors propagate immediately (no retry).
- After MAX_ATTEMPTS, swap to fallback_model for one final try.
- run_sync_with_retry adapts sync callables via asyncio.to_thread.
"""

from __future__ import annotations

import pytest

from src.llm import retry as retry_mod
from src.llm.retry import (
    MAX_ATTEMPTS,
    is_transient,
    run_sync_with_retry,
    run_with_retry,
)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fast_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(retry_mod.asyncio, "sleep", _fast_sleep)


class _TransientError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"transient {code}")
        self.code = code


class _NonTransientError(Exception):
    def __init__(self) -> None:
        super().__init__("invalid_argument")
        self.code = 400


def test_is_transient_recognises_status_codes() -> None:
    assert is_transient(_TransientError(429))
    assert is_transient(_TransientError(503))
    assert not is_transient(_NonTransientError())


async def test_run_with_retry_returns_immediately_on_success() -> None:
    calls: list[str] = []

    async def _do(model: str) -> str:
        calls.append(model)
        return "ok"

    result = await run_with_retry(_do, primary_model="m", fallback_model=None, label="t")
    assert result == "ok"
    assert calls == ["m"]


async def test_run_with_retry_propagates_non_transient() -> None:
    async def _do(model: str) -> str:
        raise _NonTransientError()

    with pytest.raises(_NonTransientError):
        await run_with_retry(_do, primary_model="m", label="t")


async def test_run_with_retry_swaps_to_fallback_after_exhaustion() -> None:
    attempts: list[str] = []

    async def _do(model: str) -> str:
        attempts.append(model)
        if model == "primary":
            raise _TransientError(503)
        return "ok-from-fallback"

    result = await run_with_retry(
        _do,
        primary_model="primary",
        fallback_model="backup",
        label="t",
    )
    assert result == "ok-from-fallback"
    # Exactly MAX_ATTEMPTS attempts on primary, then 1 on fallback.
    assert attempts.count("primary") == MAX_ATTEMPTS
    assert attempts.count("backup") == 1


async def test_run_with_retry_no_fallback_raises_after_max_attempts() -> None:
    attempts: list[str] = []

    async def _do(model: str) -> str:
        attempts.append(model)
        raise _TransientError(429)

    with pytest.raises(_TransientError):
        await run_with_retry(_do, primary_model="m", fallback_model=None, label="t")
    assert len(attempts) == MAX_ATTEMPTS


async def test_run_sync_with_retry_invokes_sync_callable() -> None:
    calls: list[str] = []

    def _sync(model: str, value: int) -> str:
        calls.append(model)
        return f"{model}:{value}"

    result = await run_sync_with_retry(
        _sync,
        42,
        primary_model="m",
        label="t",
    )
    assert result == "m:42"
    assert calls == ["m"]
