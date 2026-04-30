"""
Read-only agent memory loader.

The orchestrator calls load_agent_context() to inject per-user interaction
preferences into the system prompt before each LLM turn.
Nothing here writes to the database.

Public API:
    load_agent_context(user_id) -> dict
"""

import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session_factory
from src.db.models import AgentMemory, AgentMemoryScope
from src.utils.logger import get_logger

logger = get_logger(__name__)

# LONG fields that most directly shape every response — load these first
_PRIORITY_FIELDS = [
    "response_verbosity",
    "technical_level",
    "preferred_language",
    "communication_tone",
    "emoji_preference",
]


# ── Public API ────────────────────────────────────────────────────────────────


async def load_agent_context(user_id: str) -> dict:
    """
    Load the agent memory context bundle for one conversation turn.

    Returns:
        {
            "long_term":  list[AgentMemory],   # persistent style/preference facts
            "short_term": list[AgentMemory],   # ephemeral session state
        }
    """
    factory = get_session_factory()
    async with factory() as db:
        long_term = await _load_agent_memories(db, user_id, AgentMemoryScope.LONG, limit=20)
        short_term = await _load_agent_memories(db, user_id, AgentMemoryScope.SHORT, limit=10)

    return {
        "long_term": long_term,
        "short_term": short_term,
    }


async def load_agent_memory_field(
    db: AsyncSession,
    user_id: str,
    field: str,
) -> Optional[AgentMemory]:
    """Return the single active AgentMemory for *user_id* + *field*, or None."""
    result = await db.execute(
        select(AgentMemory)
        .where(
            AgentMemory.user_id == uuid.UUID(user_id),
            AgentMemory.field == field,
            AgentMemory.is_active.is_(True),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


def format_agent_context_for_prompt(context: dict) -> str:
    """
    Render the agent context bundle as a compact string for injection into the
    system prompt. Priority fields appear first.

    Returns an empty string when there are no memories to inject.
    """
    all_memories: list[AgentMemory] = context.get("long_term", []) + context.get("short_term", [])
    if not all_memories:
        return ""

    priority = {m.field: m for m in all_memories if m.field in _PRIORITY_FIELDS}
    rest = [m for m in all_memories if m.field not in _PRIORITY_FIELDS]

    lines: list[str] = []
    for field in _PRIORITY_FIELDS:
        if field in priority:
            m = priority[field]
            v = m.value.get("v", m.value) if isinstance(m.value, dict) else m.value
            lines.append(f"  {field}: {v}")
    for m in rest:
        v = m.value.get("v", m.value) if isinstance(m.value, dict) else m.value
        lines.append(f"  {m.field}: {v}")

    return "User interaction preferences:\n" + "\n".join(lines)


# ── Private helpers ───────────────────────────────────────────────────────────


async def _load_agent_memories(
    db: AsyncSession,
    user_id: str,
    scope: AgentMemoryScope,
    limit: int = 20,
) -> list[AgentMemory]:
    """Return active, non-expired AgentMemory rows for *user_id* and *scope*."""
    result = await db.execute(
        select(AgentMemory)
        .where(
            AgentMemory.user_id == uuid.UUID(user_id),
            AgentMemory.scope == scope,
            AgentMemory.is_active.is_(True),
            or_(
                AgentMemory.expires_at.is_(None),
                AgentMemory.expires_at > func.now(),
            ),
        )
        .order_by(AgentMemory.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
