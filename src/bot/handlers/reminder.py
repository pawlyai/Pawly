"""
Reminder command handlers.

/remind <text>    — parse and save a custom reminder
/reminders        — list upcoming unsent reminders
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.db.engine import get_session_factory
from src.db.models import Pet, Reminder, User
from src.utils.logger import get_logger

router = Router(name="reminder")
logger = get_logger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────


async def save_reminder(
    user: User,
    pet: Pet | None,
    content: str,
    remind_at: datetime,
) -> Reminder:
    factory = get_session_factory()
    async with factory() as db:
        reminder = Reminder(
            user_id=user.id,
            pet_id=pet.id if pet else None,
            telegram_id=user.telegram_id,
            content=content,
            remind_at=remind_at,
        )
        db.add(reminder)
        await db.commit()
        await db.refresh(reminder)
    return reminder


async def _parse_reminder_text(text: str, user: User) -> dict | None:
    """Use LLM extract to parse free-text reminder into content + remind_at (UTC ISO)."""
    from src.llm.client import get_gemini_client

    now_iso = datetime.now(timezone.utc).isoformat()
    tz = getattr(user, "timezone", None) or "UTC"

    system = (
        "Extract a reminder from the user's message. "
        f"Current UTC datetime: {now_iso}. User timezone: {tz}. "
        'Return ONLY valid JSON: {"content": "<what to remind>", "remind_at_iso": "<UTC ISO 8601>"}. '
        'If the time is unclear, return {"error": "unclear"}.'
    )
    client = get_gemini_client()
    try:
        raw = await client.extract(
            system_prompt=system,
            messages=[{"role": "user", "content": text}],
        )
        parsed = json.loads(raw["text"])
        if "error" in parsed:
            return None
        remind_at = datetime.fromisoformat(parsed["remind_at_iso"].replace("Z", "+00:00"))
        if remind_at.tzinfo is None:
            remind_at = remind_at.replace(tzinfo=timezone.utc)
        return {"content": parsed["content"].strip(), "remind_at": remind_at}
    except Exception as exc:
        logger.warning("reminder parse failed", error=str(exc))
        return None


def _format_dt(dt: datetime) -> str:
    return dt.strftime("%B %d, %Y at %I:%M %p UTC")


# ── /remind ───────────────────────────────────────────────────────────────────


@router.message(Command("remind"))
async def cmd_remind(
    message: Message,
    user: User,
    active_pet: Pet | None,
    session: dict[str, Any],
) -> None:
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer(
            "Tell me what to remind you about and when.\n"
            "Example: `/remind Give Max his vaccine in 3 months`\n"
            "Example: `/remind Vet appointment for Luna on June 10`",
            parse_mode="Markdown",
        )
        return

    reminder_text = args[1].strip()
    parsed = await _parse_reminder_text(reminder_text, user)

    if not parsed:
        await message.answer(
            "I couldn't figure out the date. Try: `/remind <what> on <date>` or `/remind <what> in <X> days/weeks`",
            parse_mode="Markdown",
        )
        return

    now = datetime.now(timezone.utc)
    if parsed["remind_at"] <= now:
        await message.answer("That date is in the past. Please give me a future date.")
        return

    await save_reminder(user, active_pet, parsed["content"], parsed["remind_at"])
    date_str = _format_dt(parsed["remind_at"])
    await message.answer(
        f"Done! I'll remind you: *{parsed['content']}* on {date_str} 🔔",
        parse_mode="Markdown",
    )
    logger.info("reminder saved via /remind", telegram_id=user.telegram_id)


# ── /reminders ────────────────────────────────────────────────────────────────


@router.message(Command("reminders"))
async def cmd_reminders(
    message: Message,
    user: User,
    **_: object,
) -> None:
    from sqlalchemy import select

    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(Reminder)
            .where(
                Reminder.user_id == user.id,
                Reminder.is_sent.is_(False),
            )
            .order_by(Reminder.remind_at)
            .limit(10)
        )
        reminders = list(result.scalars().all())

    if not reminders:
        await message.answer("You have no upcoming reminders.")
        return

    lines = ["*Your upcoming reminders:*\n"]
    for i, r in enumerate(reminders, 1):
        lines.append(f"{i}. {r.content} — {_format_dt(r.remind_at)}")

    await message.answer("\n".join(lines), parse_mode="Markdown")
