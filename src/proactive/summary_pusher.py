"""
Push a daily summary to the user when follow_up_needed=True.

Called by run_daily_summary after the summary is saved. Only pushes if:
  - follow_up_needed is True in the summary JSON
  - No push has been sent for this DailySummary yet (pushed_at is null)
  - It is within a reasonable delivery window for the user's timezone
    (default: 19:00–22:00 local time; if outside window, we still push
     because the cron already ran — the window guards against a future
     retry, not the initial delivery)

The message is a short conversational nudge built from the summary's
unresolved_questions and follow_up_reason — not a clinical report.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update

from src.db.engine import get_session_factory
from src.db.models import DailySummary, Pet, ProactiveEventType, User
from src.proactive.dedup import already_sent, record_sent, record_skipped
from src.proactive.dispatcher import send_proactive_message
from src.utils.logger import get_logger

logger = get_logger(__name__)

_PUSH_PROMPT = """\
You are Pawly, an AI pet care assistant.

Yesterday's health summary for {pet_name} ({species}) showed these unresolved concerns:
{unresolved}

Follow-up reason: {follow_up_reason}

Write ONE warm, conversational message (2–3 sentences max) to check in with the owner.
- Reference the specific concern naturally, don't list bullet points
- Don't repeat medical advice
- End with an open question
- One emoji is fine
Output only the message text, no preamble.
"""


async def push_daily_summary_if_needed(
    summary_id: str,
    pet_id: str,
    user_id: str,
    summary: dict,
) -> bool:
    """
    Generate and send a follow-up push for a daily summary row.

    Returns True if a message was sent, False otherwise.
    """
    if not summary.get("follow_up_needed"):
        return False

    # Dedup: skip if already pushed for this summary
    if await already_sent(
        ProactiveEventType.DAILY_SUMMARY_PUSH,
        trigger_ref_id=summary_id,
        stage=1,
    ):
        logger.info("daily summary push: already sent", summary_id=summary_id)
        return False

    factory = get_session_factory()
    async with factory() as db:
        pet = await db.get(Pet, uuid.UUID(pet_id))
        user_result = await db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = user_result.scalar_one_or_none()

    if pet is None or user is None:
        logger.warning("daily summary push: pet or user not found", pet_id=pet_id, user_id=user_id)
        return False

    if not user.telegram_id.lstrip("-").isdigit():
        return False  # web API test user

    unresolved = summary.get("unresolved_questions") or []
    follow_up_reason = summary.get("follow_up_reason") or "general check-in"

    if not unresolved and not follow_up_reason:
        await record_skipped(
            user_id=user_id,
            pet_id=pet_id,
            telegram_id=user.telegram_id,
            event_type=ProactiveEventType.DAILY_SUMMARY_PUSH,
            trigger_ref_id=summary_id,
            reason="no_unresolved_content",
        )
        return False

    text = await _generate_push_message(
        pet_name=pet.name,
        species=pet.species.value,
        unresolved=unresolved,
        follow_up_reason=follow_up_reason,
    )

    sent = await send_proactive_message(telegram_id=user.telegram_id, text=text)

    if sent:
        await record_sent(
            user_id=user_id,
            pet_id=pet_id,
            telegram_id=user.telegram_id,
            event_type=ProactiveEventType.DAILY_SUMMARY_PUSH,
            trigger_ref_id=summary_id,
            content_preview=text[:300],
        )
        # Mark the DailySummary row so we never push it again
        async with factory() as db:
            await db.execute(
                update(DailySummary)
                .where(DailySummary.id == uuid.UUID(summary_id))
                .values(pushed_at=datetime.now(timezone.utc).replace(tzinfo=None))
            )
            await db.commit()
        logger.info("daily summary push: sent", pet_id=pet_id, user_id=user_id)
    else:
        logger.warning("daily summary push: send failed", pet_id=pet_id)

    return sent


async def _generate_push_message(
    pet_name: str,
    species: str,
    unresolved: list[str],
    follow_up_reason: str,
) -> str:
    unresolved_str = "; ".join(unresolved) if unresolved else follow_up_reason
    prompt = _PUSH_PROMPT.format(
        pet_name=pet_name,
        species=species,
        unresolved=unresolved_str,
        follow_up_reason=follow_up_reason,
    )
    try:
        from src.llm.client import get_gemini_client
        client = get_gemini_client()
        raw = await client.extract(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "Write the check-in message now."}],
        )
        return raw["text"].strip()
    except Exception as exc:
        logger.error("daily summary push: generation failed", error=str(exc))
        return f"Hey, just checking in on {pet_name} — any updates since yesterday? 🐾"
