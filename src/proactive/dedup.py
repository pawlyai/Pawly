"""
ProactiveEvent dedup helpers.

already_sent()   — check if an event was already delivered
record_sent()    — mark an event as delivered
record_skipped() — mark an event as skipped (user replied, etc.)

All three are upsert-safe: they use INSERT … ON CONFLICT DO UPDATE so
concurrent job executions don't race to double-send.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.db.engine import get_session_factory
from src.db.models import ProactiveEvent, ProactiveEventType
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def already_sent(
    event_type: ProactiveEventType,
    trigger_ref_id: str,
    stage: int = 1,
) -> bool:
    """Return True if this (event_type, trigger_ref_id, stage) was already sent."""
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(ProactiveEvent.sent_at).where(
                ProactiveEvent.event_type == event_type,
                ProactiveEvent.trigger_ref_id == trigger_ref_id,
                ProactiveEvent.stage == stage,
                ProactiveEvent.sent_at.isnot(None),
            )
        )
        return result.scalar_one_or_none() is not None


async def record_sent(
    *,
    user_id: str,
    pet_id: str,
    telegram_id: str,
    event_type: ProactiveEventType,
    trigger_ref_id: str,
    stage: int = 1,
    content_preview: Optional[str] = None,
) -> None:
    """Insert or update a ProactiveEvent row marking it as sent."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    factory = get_session_factory()
    async with factory() as db:
        stmt = (
            insert(ProactiveEvent)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                pet_id=pet_id,
                telegram_id=telegram_id,
                event_type=event_type,
                trigger_ref_id=trigger_ref_id,
                stage=stage,
                scheduled_at=now,
                sent_at=now,
                skipped=False,
                content_preview=(content_preview or "")[:300] if content_preview else None,
            )
            .on_conflict_do_update(
                constraint="uq_proactive_event_type_ref_stage",
                set_={"sent_at": now, "skipped": False},
            )
        )
        await db.execute(stmt)
        await db.commit()


async def record_skipped(
    *,
    user_id: str,
    pet_id: str,
    telegram_id: str,
    event_type: ProactiveEventType,
    trigger_ref_id: str,
    stage: int = 1,
    reason: str,
) -> None:
    """Insert or update a ProactiveEvent row marking it as skipped."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    factory = get_session_factory()
    async with factory() as db:
        stmt = (
            insert(ProactiveEvent)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                pet_id=pet_id,
                telegram_id=telegram_id,
                event_type=event_type,
                trigger_ref_id=trigger_ref_id,
                stage=stage,
                scheduled_at=now,
                sent_at=None,
                skipped=True,
                skipped_reason=reason,
            )
            .on_conflict_do_update(
                constraint="uq_proactive_event_type_ref_stage",
                set_={"skipped": True, "skipped_reason": reason},
            )
        )
        await db.execute(stmt)
        await db.commit()
