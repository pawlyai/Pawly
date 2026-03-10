"""
ARQ job: consolidated housekeeping for expired/stale database rows.

run_cleanup(ctx) is the cron entry point. It handles all four operations in
a single session:
    1. Soft-delete short/mid-term memories whose expires_at has passed
    2. Mark expired NEEDS_CONFIRMATION pending changes as EXPIRED
    3. Hard-delete DailySummary rows older than 30 days
    4. Hard-delete WeeklySummary rows older than 180 days

The two legacy functions (expire_old_memories, expire_pending_changes) are
kept for backward compat and individual invocation.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, update

from src.db.engine import get_session_factory
from src.db.models import DailySummary, PendingMemoryChange, PendingStatus, PetMemory, WeeklySummary
from src.utils.logger import get_logger

logger = get_logger(__name__)

_DAILY_RETENTION_DAYS = 30
_WEEKLY_RETENTION_DAYS = 180


async def run_cleanup(ctx: dict) -> dict[str, Any]:
    """
    Consolidated housekeeping job. Run every 6 hours via cron.

    Returns counts for each operation performed.
    """
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=_DAILY_RETENTION_DAYS)
    six_months_ago = now - timedelta(days=_WEEKLY_RETENTION_DAYS)

    factory = get_session_factory()
    async with factory() as db:
        # 1. Soft-delete expired memories
        mem_result = await db.execute(
            update(PetMemory)
            .where(
                PetMemory.expires_at < now,
                PetMemory.is_active.is_(True),
            )
            .values(is_active=False)
            .returning(PetMemory.id)
        )
        memories_expired = len(mem_result.fetchall())

        # 2. Mark expired pending changes as EXPIRED
        pending_result = await db.execute(
            update(PendingMemoryChange)
            .where(
                PendingMemoryChange.expires_at < now,
                PendingMemoryChange.validation_status == PendingStatus.NEEDS_CONFIRMATION,
            )
            .values(validation_status=PendingStatus.EXPIRED)
            .returning(PendingMemoryChange.id)
        )
        pending_expired = len(pending_result.fetchall())

        # 3. Delete old daily summaries
        daily_result = await db.execute(
            delete(DailySummary).where(DailySummary.created_at < thirty_days_ago)
        )
        daily_deleted = daily_result.rowcount

        # 4. Delete old weekly summaries
        weekly_result = await db.execute(
            delete(WeeklySummary).where(WeeklySummary.created_at < six_months_ago)
        )
        weekly_deleted = weekly_result.rowcount

        await db.commit()

    logger.info(
        "run_cleanup complete",
        memories_expired=memories_expired,
        pending_expired=pending_expired,
        daily_deleted=daily_deleted,
        weekly_deleted=weekly_deleted,
    )
    return {
        "status": "ok",
        "memories_expired": memories_expired,
        "pending_expired": pending_expired,
        "daily_deleted": daily_deleted,
        "weekly_deleted": weekly_deleted,
    }


# ── Legacy helpers (kept for individual invocation / backward compat) ─────────


async def expire_pending_changes(ctx: dict) -> dict[str, Any]:
    """Mark expired NEEDS_CONFIRMATION pending changes as EXPIRED."""
    now = datetime.now(timezone.utc)
    factory = get_session_factory()

    async with factory() as db:
        result = await db.execute(
            update(PendingMemoryChange)
            .where(
                PendingMemoryChange.expires_at < now,
                PendingMemoryChange.validation_status.in_([
                    PendingStatus.NEEDS_CONFIRMATION,
                    PendingStatus.AUTO_APPROVED,
                ]),
            )
            .values(validation_status=PendingStatus.EXPIRED)
            .returning(PendingMemoryChange.id)
        )
        count = len(result.fetchall())
        await db.commit()

    logger.info("pending changes expired", count=count)
    return {"status": "ok", "expired": count}


async def expire_old_memories(ctx: dict) -> dict[str, Any]:
    """Deactivate PetMemory entries whose expires_at has passed."""
    now = datetime.now(timezone.utc)
    factory = get_session_factory()

    async with factory() as db:
        result = await db.execute(
            update(PetMemory)
            .where(
                PetMemory.expires_at < now,
                PetMemory.is_active.is_(True),
            )
            .values(is_active=False)
            .returning(PetMemory.id)
        )
        count = len(result.fetchall())
        await db.commit()

    logger.info("memories expired", count=count)
    return {"status": "ok", "expired": count}
