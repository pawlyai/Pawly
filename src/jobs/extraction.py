"""
ARQ background job: extract memories from a conversation turn.

Enqueued by the bot message handler after the user receives their response.

Job function:
    run_extraction(ctx, user_id, pet_id, dialogue_id, message_ids)

Pipeline:
    1. Load Message rows by ID
    2. Load Pet + all active PetMemory rows
    3. extract_memories()     → list[MemoryProposal]
    4. validate_proposal()    → list[(MemoryProposal, ValidationResult)]
    5. commit_proposals()     → persists in one transaction
    6. Structured log
"""

import uuid
from typing import Any

from sqlalchemy import select

from src.db.engine import get_session_factory
from src.db.models import Message, Pet, PetMemory, User
from src.memory.committer import commit_proposals
from src.memory.extractor import extract_memories
from src.memory.validator import validate_proposal
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def run_extraction(
    ctx: dict,
    user_id: str,
    pet_id: str,
    dialogue_id: str,
    message_ids: list[str],
) -> dict[str, Any]:
    """
    Background job: extract and stage memory changes from a conversation turn.

    Args:
        ctx:         ARQ context dict (contains Redis pool, startup state, etc.)
        user_id:     DB UUID string of the User
        pet_id:      DB UUID string of the Pet
        dialogue_id: UUID string of the Dialogue (for logging only)
        message_ids: UUIDs of Message rows from this turn to analyse

    Returns:
        dict with "status" and extraction counts
    """
    factory = get_session_factory()

    # ── 1. Load messages ──────────────────────────────────────────────────────
    async with factory() as db:
        msg_result = await db.execute(
            select(Message).where(
                Message.id.in_([uuid.UUID(mid) for mid in message_ids])
            )
        )
        messages = list(msg_result.scalars().all())

        if not messages:
            logger.warning(
                "run_extraction: no messages found",
                message_ids=message_ids,
                dialogue_id=dialogue_id,
            )
            return {"status": "no_messages"}

        # ── 2. Load pet + existing active memories ────────────────────────────
        pet = await db.get(Pet, uuid.UUID(pet_id))
        if pet is None:
            logger.warning("run_extraction: pet not found", pet_id=pet_id)
            return {"status": "pet_not_found"}

        user = await db.get(User, uuid.UUID(user_id))
        if user is None:
            logger.warning("run_extraction: user not found", user_id=user_id)
            return {"status": "user_not_found"}

        mem_result = await db.execute(
            select(PetMemory).where(
                PetMemory.pet_id == uuid.UUID(pet_id),
                PetMemory.is_active.is_(True),
            )
        )
        existing_memories = list(mem_result.scalars().all())

    # Build message list for extractor, sorted chronologically
    raw_messages = [
        {
            "role": "user" if m.role.value == "user" else "assistant",
            "content": m.content,
        }
        for m in sorted(messages, key=lambda m: m.created_at)
    ]
    source_message_id = message_ids[0] if message_ids else ""

    # ── 3. Extract ────────────────────────────────────────────────────────────
    proposals = await extract_memories(raw_messages, pet, existing_memories)

    if not proposals:
        logger.info(
            "run_extraction: nothing to extract",
            pet_id=pet_id,
            dialogue_id=dialogue_id,
        )
        return {
            "status": "ok",
            "extracted": 0,
            "auto_approved": 0,
            "needs_confirmation": 0,
            "rejected": 0,
        }

    # ── 4. Validate ───────────────────────────────────────────────────────────
    proposals_with_results = [
        (proposal, validate_proposal(proposal, existing_memories, pet))
        for proposal in proposals
    ]

    # ── 5. Commit ─────────────────────────────────────────────────────────────
    counts = await commit_proposals(
        proposals_with_results=proposals_with_results,
        pet_id=pet_id,
        user_id=user_id,
        source_message_id=source_message_id,
    )

    # ── 6. Log ────────────────────────────────────────────────────────────────
    logger.info(
        "extraction_complete",
        pet_id=pet_id,
        dialogue_id=dialogue_id,
        extracted=len(proposals),
        auto_approved=counts["auto_approved"],
        needs_confirmation=counts["needs_confirmation"],
        rejected=counts["rejected"],
    )

    return {
        "status": "ok",
        "extracted": len(proposals),
        **counts,
    }
