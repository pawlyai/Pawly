"""
Langfuse tracing helpers (SDK v2, compatible with langfuse/langfuse:2 server).

Wraps the Langfuse v2 decorator API so that:
  - Misconfiguration (missing keys) produces a no-op — app keeps running.
  - Any exception inside an update call is swallowed and logged — tracing
    failures never propagate to user-facing traffic.

Public API:
  observe_generation  — @observe decorator pre-configured for LLM generation spans
  observe_span        — @observe decorator for non-generation spans
  update_generation   — safely update active generation's model/tokens/IO
  update_span         — safely update active span's input/output/metadata
  update_trace        — safely set trace-level user_id/session_id/tags
"""

import os
from collections.abc import Callable
from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── Initialise ────────────────────────────────────────────────────────────────
# SDK v2 reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST from env.

try:
    from langfuse.decorators import langfuse_context
    from langfuse.decorators import observe as _lf_observe

    _LANGFUSE_ENABLED = True
    logger.info("langfuse tracing enabled", host=os.environ.get("LANGFUSE_HOST", ""))
except Exception as exc:
    langfuse_context = None  # type: ignore[assignment]
    _LANGFUSE_ENABLED = False
    logger.warning("langfuse tracing disabled", reason=str(exc))


# ── No-op fallback ────────────────────────────────────────────────────────────

def _noop_observe(**_kwargs: Any) -> Callable:
    def decorator(fn: Callable) -> Callable:
        return fn
    return decorator


# ── Public decorators ─────────────────────────────────────────────────────────

def observe_generation(name: str) -> Callable:
    """Decorator that marks a function as a Langfuse generation span."""
    if not _LANGFUSE_ENABLED:
        return _noop_observe(name=name)
    return _lf_observe(name=name, as_type="generation", capture_input=False, capture_output=False)


def observe_span(name: str) -> Callable:
    """Decorator that marks a function as a Langfuse span."""
    if not _LANGFUSE_ENABLED:
        return _noop_observe(name=name)
    return _lf_observe(name=name, capture_input=False, capture_output=False)


# ── Safe update helpers ───────────────────────────────────────────────────────

def update_generation(**kwargs: Any) -> None:
    """
    Update the active Langfuse generation observation.
    Accepted kwargs: model, input, output, usage_details, metadata.
    Swallows all exceptions — tracing must never block user traffic.
    """
    if not _LANGFUSE_ENABLED or langfuse_context is None:
        return
    try:
        langfuse_context.update_current_observation(**kwargs)
    except Exception as exc:
        logger.debug("langfuse update_generation failed", error=str(exc))


def update_span(**kwargs: Any) -> None:
    """
    Update the active Langfuse span observation.
    Accepted kwargs: input, output, metadata.
    Swallows all exceptions — tracing must never block user traffic.
    """
    if not _LANGFUSE_ENABLED or langfuse_context is None:
        return
    try:
        langfuse_context.update_current_observation(**kwargs)
    except Exception as exc:
        logger.debug("langfuse update_span failed", error=str(exc))


def update_trace(**kwargs: Any) -> None:
    """
    Update trace-level fields: user_id, session_id, tags, metadata.
    Must be called from within an @observe-decorated function.
    Swallows all exceptions — tracing must never block user traffic.
    """
    if not _LANGFUSE_ENABLED or langfuse_context is None:
        return
    try:
        langfuse_context.update_current_trace(**kwargs)
    except Exception as exc:
        logger.debug("langfuse update_trace failed", error=str(exc))


def is_enabled() -> bool:
    return _LANGFUSE_ENABLED
