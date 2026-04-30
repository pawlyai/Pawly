"""
Writes agent memory proposals to the database.

Agent memories are lighter-weight than pet memories: there is no user
confirmation step. Proposals above the confidence threshold are committed
directly; low-confidence proposals are silently dropped.

Public API:
    commit_agent_proposals(proposals, user_id, source_message_id)
        -> {"committed": N, "skipped": N}
"""

import uuid
from datetime import datetime, timedelta, timezone

from src.db.engine import get_session_factory
from src.db.models import AgentMemory, AgentMemoryScope
from src.memory.agent.extractor import AgentMemoryProposal
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Minimum confidence to auto-commit per scope
_MIN_CONFIDENCE: dict[AgentMemoryScope, float] = {
    AgentMemoryScope.LONG:  0.75,
    AgentMemoryScope.SHORT: 0.60,
}

# TTL for ephemeral agent memories
_SHORT_TTL = timedelta(days=7)

# Cooldown — skip re-writing the same field if updated within this window
_FRESHNESS_WINDOW = timedelta(hours=1)


# ── Public API ────────────────────────────────────────────────────────────────


async def commit_agent_proposals(
    proposals: list[AgentMemoryProposal],
    user_id: str,
    source_message_id: str = "",
) -> dict[str, int]:
    """
    Persist agent memory proposals in one transaction.

    For each proposal:
    - If confidence < threshold for its scope → skip (no write at all)
    - If an active record exists for the same field and was updated within the
      freshness window → skip
    - Otherwise → deactivate the old record and write a new one

    Returns:
        {"committed": N, "skipped": N}
    """
    counts: dict[str, int] = {"committed": 0, "skipped": 0}
    if not proposals:
        return counts

    user_uuid = uuid.UUID(user_id)
    now = datetime.now(timezone.utc)

    factory = get_session_factory()
    async with factory() as db:
        async with db.begin():
            for proposal in proposals:
                min_conf = _MIN_CONFIDENCE.get(proposal.scope, 0.75)
                if proposal.confidence < min_conf:
                    counts["skipped"] += 1
                    continue

                # Check for an existing active record
                from sqlalchemy import select
                result = await db.execute(
                    select(AgentMemory)
                    .where(
                        AgentMemory.user_id == user_uuid,
                        AgentMemory.field == proposal.field,
                        AgentMemory.is_active.is_(True),
                    )
                    .limit(1)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    anchor = existing.updated_at or existing.created_at
                    if anchor:
                        ts = anchor if anchor.tzinfo else anchor.replace(tzinfo=timezone.utc)
                        if (now - ts) < _FRESHNESS_WINDOW:
                            counts["skipped"] += 1
                            continue

                    stored_norm = _normalise(proposal.value)
                    if existing.value == stored_norm:
                        counts["skipped"] += 1
                        continue

                    existing.is_active = False

                expires_at = (now + _SHORT_TTL) if proposal.scope == AgentMemoryScope.SHORT else None

                db.add(AgentMemory(
                    user_id=user_uuid,
                    category=proposal.category,
                    scope=proposal.scope,
                    field=proposal.field,
                    value=_normalise(proposal.value),
                    confidence_score=proposal.confidence,
                    source_message_id=source_message_id or None,
                    is_active=True,
                    expires_at=expires_at,
                ))
                counts["committed"] += 1

    logger.info("commit_agent_proposals done", user_id=user_id, **counts)
    return counts


# ── Internal ──────────────────────────────────────────────────────────────────


def _normalise(value: object) -> object:
    """Wrap scalar values consistently with the pet memory committer."""
    return value if isinstance(value, dict) else {"v": value}
