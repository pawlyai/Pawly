"""
ARQ job: proactive follow-up for RED/ORANGE triage conversations.

Enqueued by the message handler with a delay (2h RED, 4h ORANGE).
When the job fires it checks whether the user has sent any message since
it was enqueued. If they have, skip silently. If not, send a warm
LLM-generated check-in via Telegram.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from src.db.engine import get_session_factory
from src.db.models import MessageRole, RawMessage
from src.utils.logger import get_logger

logger = get_logger(__name__)

_FOLLOWUP_KEY = "followup_pending:{user_id}"


async def run_followup_check(
    ctx: dict,
    *,
    telegram_id: str,
    user_id: str,
    pet_name: str,
    pet_species: str,
    triage_level: str,
    symptom_tags: list[str],
    enqueued_at: str,
) -> dict[str, Any]:
    """
    Check if the user went silent after a RED/ORANGE triage response.
    Sends a proactive follow-up if no message was received since enqueue time.
    """
    # Skip web API test users — they have no real Telegram chat
    if not telegram_id.lstrip("-").isdigit():
        return {"status": "skipped", "reason": "non_telegram_user"}

    enqueued_dt = datetime.fromisoformat(enqueued_at)

    # Check for any user message since the job was enqueued
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(func.count(RawMessage.id)).where(
                RawMessage.user_id == uuid.UUID(user_id),
                RawMessage.role == MessageRole.USER,
                RawMessage.created_at > enqueued_dt,
            )
        )
        count = result.scalar_one()

    if count > 0:
        logger.info(
            "followup: user already responded — skipping",
            telegram_id=telegram_id,
            triage_level=triage_level,
        )
        # Clear the dedup key so future triage events can schedule new follow-ups
        redis = ctx["redis"]
        await redis.delete(_FOLLOWUP_KEY.format(user_id=user_id))
        return {"status": "skipped", "reason": "user_responded"}

    # Generate follow-up text
    from src.llm.orchestrator import generate_followup_message

    try:
        text = await generate_followup_message(
            pet_name=pet_name,
            pet_species=pet_species,
            triage_level=triage_level,
            symptom_tags=symptom_tags,
        )
    except Exception as exc:
        logger.error("followup: message generation failed", error=str(exc))
        text = f"Hey, just checking in — how is {pet_name} doing? 🐾"

    # Send via Telegram
    try:
        from aiogram import Bot
        from src.config import settings

        bot = Bot(token=settings.telegram_bot_token)
        async with bot:
            await bot.send_message(chat_id=int(telegram_id), text=text)
    except Exception as exc:
        logger.error("followup: send failed", error=str(exc), telegram_id=telegram_id)
        return {"status": "error", "reason": str(exc)}

    # Clear dedup key so future RED/ORANGE events can schedule a new follow-up
    redis = ctx["redis"]
    await redis.delete(_FOLLOWUP_KEY.format(user_id=user_id))

    logger.info(
        "followup: check-in sent",
        telegram_id=telegram_id,
        triage_level=triage_level,
        pet_name=pet_name,
    )
    return {"status": "sent", "triage_level": triage_level}
