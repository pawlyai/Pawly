"""
Writes validated memory proposals to the database.

Public API:
    commit_proposals(proposals_with_results, pet_id, user_id, source_message_id)
        → {"auto_approved": N, "needs_confirmation": N, "rejected": N}

    commit_change(db, pending, reason)  ← legacy helper for user-confirmation callbacks

All writes in commit_proposals() happen inside a single SQLAlchemy transaction.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session_factory
from src.db.models import (
    ChangeReason,
    MemorySource,
    PendingMemoryChange,
    PendingStatus,
    PetMemory,
    PetMemoryChangeLog,
)
from src.memory.extractor import MemoryProposal
from src.memory.validator import ValidationResult
from src.utils.logger import get_logger

logger = get_logger(__name__)

_PENDING_CONFIRM_TTL = timedelta(days=7)


# ── Public API ────────────────────────────────────────────────────────────────


async def commit_proposals(
    proposals_with_results: list[tuple[MemoryProposal, ValidationResult]],
    pet_id: str,
    user_id: str,
    source_message_id: str = "",
) -> dict[str, int]:
    """
    Persist a batch of validated memory proposals in one transaction.

    AUTO_APPROVED  → deactivate old memory (if conflict) + write PetMemory +
                     PetMemoryChangeLog + COMMITTED PendingMemoryChange
    NEEDS_CONFIRMATION → write NEEDS_CONFIRMATION PendingMemoryChange only
    REJECTED           → write REJECTED PendingMemoryChange for audit trail

    Returns:
        {"auto_approved": N, "needs_confirmation": N, "rejected": N}
    """
    counts: dict[str, int] = {"auto_approved": 0, "needs_confirmation": 0, "rejected": 0}

    factory = get_session_factory()
    async with factory() as db:
        async with db.begin():
            for proposal, result in proposals_with_results:
                if result.status == PendingStatus.AUTO_APPROVED:
                    await _apply_auto(db, proposal, result, pet_id, user_id, source_message_id)
                    counts["auto_approved"] += 1

                elif result.status == PendingStatus.NEEDS_CONFIRMATION:
                    _add_pending(db, proposal, result, pet_id, user_id, source_message_id)
                    counts["needs_confirmation"] += 1

                else:  # REJECTED — audit record only
                    _add_rejected(db, proposal, result, pet_id, user_id, source_message_id)
                    counts["rejected"] += 1

    logger.info(
        "commit_proposals done",
        pet_id=pet_id,
        **counts,
    )
    return counts


# ── Internal helpers ──────────────────────────────────────────────────────────


async def _apply_auto(
    db: AsyncSession,
    proposal: MemoryProposal,
    result: ValidationResult,
    pet_id: str,
    user_id: str,
    source_message_id: str,
) -> None:
    """Deactivate old → create PetMemory → log → COMMITTED PendingMemoryChange."""
    pet_uuid = uuid.UUID(pet_id)
    now = datetime.now(timezone.utc)
    stored_value = _normalise(proposal.value)
    old_value: Optional[object] = None

    if result.conflict_with_id:
        old = await db.get(PetMemory, uuid.UUID(result.conflict_with_id))
        if old:
            old_value = old.value
            old.is_active = False

    memory = PetMemory(
        pet_id=pet_uuid,
        memory_type=proposal.memory_type,
        memory_term=proposal.memory_term,
        field=proposal.field,
        value=stored_value,
        confidence_score=proposal.confidence,
        source=MemorySource.AI_EXTRACTED,
        source_message_id=source_message_id or None,
        observed_at=proposal.observed_at,
        is_active=True,
        expires_at=result.expires_at,
    )
    db.add(memory)

    db.add(PetMemoryChangeLog(
        pet_id=pet_id,
        field_changed=proposal.field,
        old_value=old_value,
        new_value=stored_value,
        reason=ChangeReason.AUTO_UPDATE,
        related_message_id=source_message_id or None,
    ))

    db.add(PendingMemoryChange(
        pet_id=pet_id,
        user_id=user_id,
        field=proposal.field,
        proposed_value=stored_value,
        confidence=proposal.confidence,
        source_quote=proposal.source_quote,
        source_message_id=source_message_id or str(uuid.uuid4()),
        memory_type=proposal.memory_type,
        memory_term=proposal.memory_term,
        validation_status=PendingStatus.COMMITTED,
        validation_reason=result.reason,
        conflict_with_id=result.conflict_with_id,
        committed_at=now,
        expires_at=now,  # already committed; expiry is irrelevant
    ))


def _add_pending(
    db: AsyncSession,
    proposal: MemoryProposal,
    result: ValidationResult,
    pet_id: str,
    user_id: str,
    source_message_id: str,
) -> None:
    now = datetime.now(timezone.utc)
    stored_value = _normalise(proposal.value)
    db.add(PendingMemoryChange(
        pet_id=pet_id,
        user_id=user_id,
        field=proposal.field,
        proposed_value=stored_value,
        confidence=proposal.confidence,
        source_quote=proposal.source_quote,
        source_message_id=source_message_id or str(uuid.uuid4()),
        memory_type=proposal.memory_type,
        memory_term=proposal.memory_term,
        validation_status=PendingStatus.NEEDS_CONFIRMATION,
        validation_reason=result.reason,
        conflict_with_id=result.conflict_with_id,
        expires_at=result.expires_at or (now + _PENDING_CONFIRM_TTL),
    ))


def _add_rejected(
    db: AsyncSession,
    proposal: MemoryProposal,
    result: ValidationResult,
    pet_id: str,
    user_id: str,
    source_message_id: str,
) -> None:
    now = datetime.now(timezone.utc)
    stored_value = _normalise(proposal.value)
    db.add(PendingMemoryChange(
        pet_id=pet_id,
        user_id=user_id,
        field=proposal.field,
        proposed_value=stored_value,
        confidence=proposal.confidence,
        source_quote=proposal.source_quote,
        source_message_id=source_message_id or str(uuid.uuid4()),
        memory_type=proposal.memory_type,
        memory_term=proposal.memory_term,
        validation_status=PendingStatus.REJECTED,
        validation_reason=result.reason,
        conflict_with_id=result.conflict_with_id,
        expires_at=now,  # rejected records expire immediately (audit only)
    ))


def _normalise(value: object) -> object:
    return value if isinstance(value, dict) else {"v": value}


# ── Legacy helper (used by user-confirmation callback handlers) ───────────────


async def commit_change(
    db: AsyncSession,
    pending: PendingMemoryChange,
    reason: ChangeReason = ChangeReason.USER_CONFIRMED,
) -> PetMemory:
    """
    Commit a single pending change (e.g. after the user taps 'Confirm').

    Deactivates any existing active memory for the same field, creates the new
    PetMemory row, writes a changelog entry, and marks the pending row COMMITTED.
    """
    pet_uuid = uuid.UUID(pending.pet_id)

    existing_result = await db.execute(
        select(PetMemory)
        .where(
            PetMemory.pet_id == pet_uuid,
            PetMemory.field == pending.field,
            PetMemory.is_active.is_(True),
        )
        .limit(1)
    )
    existing = existing_result.scalar_one_or_none()
    old_value = None
    if existing:
        old_value = existing.value
        existing.is_active = False

    memory = PetMemory(
        pet_id=pet_uuid,
        memory_type=pending.memory_type,
        memory_term=pending.memory_term,
        field=pending.field,
        value=pending.proposed_value,
        confidence_score=pending.confidence,
        source=MemorySource.AI_EXTRACTED,
        source_message_id=pending.source_message_id,
        is_active=True,
    )
    db.add(memory)

    db.add(PetMemoryChangeLog(
        pet_id=pending.pet_id,
        field_changed=pending.field,
        old_value=old_value,
        new_value=pending.proposed_value,
        reason=reason,
        related_message_id=pending.source_message_id,
    ))

    pending.validation_status = PendingStatus.COMMITTED
    pending.committed_at = datetime.now(timezone.utc)

    logger.info("memory committed", pet_id=pending.pet_id, field=pending.field, reason=reason.value)
    return memory
