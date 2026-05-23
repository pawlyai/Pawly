"""
ARQ cron job: nudge users about NEEDS_CONFIRMATION memory changes expiring soon.

Runs daily at 10:00 UTC. Finds PendingMemoryChange rows where:
  - validation_status = NEEDS_CONFIRMATION
  - expires_at is within the next 24 hours
  - No nudge has been sent for this row yet (ProactiveEvent dedup)

Sends one message per pending change (not per user) — keeps it specific so
the user knows exactly what they're confirming.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from src.db.engine import get_session_factory
from src.db.models import (
    PendingMemoryChange,
    PendingStatus,
    Pet,
    ProactiveEventType,
    User,
)
from src.proactive.dedup import already_sent, record_sent
from src.proactive.dispatcher import send_proactive_message
from src.utils.logger import get_logger

logger = get_logger(__name__)

_LOOK_AHEAD_HOURS = 24


async def run_pending_nudge(ctx: dict) -> dict[str, Any]:
    """
    Cron job: remind users about pending memory confirmations expiring soon.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # DB stores naive UTC
    expiry_window = now + timedelta(hours=_LOOK_AHEAD_HOURS)

    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(PendingMemoryChange).where(
                PendingMemoryChange.validation_status == PendingStatus.NEEDS_CONFIRMATION,
                PendingMemoryChange.expires_at <= expiry_window,
                PendingMemoryChange.expires_at > now,
            )
        )
        pending = list(result.scalars().all())

    total = len(pending)
    sent_count = 0
    skipped_count = 0

    for change in pending:
        try:
            outcome = await _process_pending(change, factory)
            if outcome == "sent":
                sent_count += 1
            else:
                skipped_count += 1
        except Exception as exc:
            logger.error(
                "pending_nudge: error",
                change_id=str(change.id),
                error=str(exc),
            )
            skipped_count += 1

    logger.info(
        "run_pending_nudge complete",
        total=total,
        sent=sent_count,
        skipped=skipped_count,
    )
    return {"status": "ok", "total": total, "sent": sent_count, "skipped": skipped_count}


async def _process_pending(change: PendingMemoryChange, factory) -> str:
    ref_id = str(change.id)

    if await already_sent(ProactiveEventType.PENDING_MEMORY_NUDGE, ref_id, stage=1):
        return "skipped_already_sent"

    factory = get_session_factory()
    async with factory() as db:
        import uuid
        pet = await db.get(Pet, uuid.UUID(change.pet_id))
        user_result = await db.execute(
            select(User).where(User.id == uuid.UUID(change.user_id))
        )
        user = user_result.scalar_one_or_none()

    if pet is None or user is None:
        return "skipped_no_entity"
    if not user.telegram_id.lstrip("-").isdigit():
        return "skipped_non_telegram"

    text = _build_nudge_text(
        pet_name=pet.name,
        field=change.field,
        proposed_value=change.proposed_value,
        source_quote=change.source_quote,
    )

    sent = await send_proactive_message(telegram_id=user.telegram_id, text=text)
    if sent:
        await record_sent(
            user_id=change.user_id,
            pet_id=change.pet_id,
            telegram_id=user.telegram_id,
            event_type=ProactiveEventType.PENDING_MEMORY_NUDGE,
            trigger_ref_id=ref_id,
            stage=1,
            content_preview=text[:300],
        )
        logger.info("pending_nudge: sent", change_id=ref_id, field=change.field)
        return "sent"
    return "error"


def _build_nudge_text(
    pet_name: str,
    field: str,
    proposed_value: dict,
    source_quote: str,
) -> str:
    readable_field = field.replace("_", " ")
    value_str = ""
    if isinstance(proposed_value, dict):
        v = proposed_value.get("value") or proposed_value.get("raw") or ""
        if v:
            value_str = f' — "{v}"'
    elif proposed_value:
        value_str = f' — "{proposed_value}"'

    return (
        f"Quick heads-up: I noted a possible update to {pet_name}'s {readable_field}"
        f"{value_str} based on our conversation. "
        f"Could you confirm this is correct? This helps me keep {pet_name}'s health record accurate. "
        f"Reply to this chat and I'll ask you directly 🐾"
    )
