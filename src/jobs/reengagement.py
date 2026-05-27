"""
ARQ cron job: re-engage users who have been silent for ≥2 days.

Runs daily at 11:00 UTC. Finds users whose last inbound Telegram message
is more than 2 days ago, then sends one friendly check-in per user.

Dedup: one message per user per 4-day bucket (trigger_ref rotates every
4 days so a user can be re-engaged again after the window resets).
"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from src.db.engine import get_session_factory
from src.db.models import MessageRole, Pet, ProactiveEventType, RawMessage, User
from src.proactive.dedup import already_sent, record_sent, record_skipped
from src.proactive.dispatcher import send_proactive_message
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SILENCE_DAYS = 2
_DEDUP_BUCKET_DAYS = 4
_EPOCH = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _trigger_ref(user_id: int) -> str:
    bucket = (datetime.now(timezone.utc) - _EPOCH).days // _DEDUP_BUCKET_DAYS
    raw = f"{user_id}:reengagement:{bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def run_reengagement_check(ctx: dict) -> dict[str, Any]:
    """Cron job: message users silent ≥2 days. Runs daily at 11:00 UTC."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    silence_cutoff = now - timedelta(days=_SILENCE_DAYS)

    factory = get_session_factory()
    async with factory() as db:
        last_msg_sq = (
            select(
                RawMessage.user_id,
                func.max(RawMessage.created_at).label("last_msg_at"),
            )
            .where(
                RawMessage.role == MessageRole.USER,
                RawMessage.channel == "telegram",
            )
            .group_by(RawMessage.user_id)
            .subquery()
        )

        rows = (
            await db.execute(
                select(
                    User.id,
                    User.telegram_id,
                    Pet.id.label("pet_id"),
                    Pet.name.label("pet_name"),
                    Pet.species,
                )
                .join(last_msg_sq, last_msg_sq.c.user_id == User.id)
                .join(Pet, Pet.user_id == User.id)
                .where(
                    User.telegram_id.isnot(None),
                    last_msg_sq.c.last_msg_at < silence_cutoff,
                )
                .distinct(User.id)
            )
        ).fetchall()

    sent = 0
    skipped = 0
    for row in rows:
        user_id = row.id
        telegram_id = str(row.telegram_id)
        pet_id = str(row.pet_id)
        pet_name = row.pet_name
        species = (row.species or "pet").lower()

        trigger_ref = _trigger_ref(user_id)

        if await already_sent(ProactiveEventType.REENGAGEMENT, trigger_ref, stage=1):
            skipped += 1
            continue

        text = (
            f"Hey! It's been a couple of days — how is {pet_name} doing? 🐾\n"
            f"Feel free to share any updates or questions about your {species}!"
        )

        ok = await send_proactive_message(telegram_id, text)
        if ok:
            await record_sent(
                user_id=user_id,
                pet_id=pet_id,
                telegram_id=telegram_id,
                event_type=ProactiveEventType.REENGAGEMENT,
                trigger_ref_id=trigger_ref,
                stage=1,
                content_preview=text[:120],
            )
            sent += 1
            logger.info("reengagement sent", user_id=user_id, pet_name=pet_name)
        else:
            await record_skipped(
                user_id=user_id,
                pet_id=pet_id,
                telegram_id=telegram_id,
                event_type=ProactiveEventType.REENGAGEMENT,
                trigger_ref_id=trigger_ref,
                stage=1,
                reason="send_failed",
            )
            skipped += 1

    logger.info("run_reengagement_check complete", sent=sent, skipped=skipped)
    return {"status": "ok", "sent": sent, "skipped": skipped}
