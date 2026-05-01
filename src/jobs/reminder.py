"""
ARQ cron job — deliver due reminders via Telegram.

Runs every minute. Queries reminders WHERE remind_at <= now AND is_sent = false,
sends each via Telegram, then marks as sent.
"""

from datetime import datetime, timezone

from sqlalchemy import select

from src.db.engine import get_session_factory
from src.db.models import Reminder
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def run_reminder_check(ctx: dict) -> dict:
    now = datetime.now(timezone.utc)
    factory = get_session_factory()

    async with factory() as db:
        result = await db.execute(
            select(Reminder).where(
                Reminder.remind_at <= now,
                Reminder.is_sent.is_(False),
            )
        )
        reminders = list(result.scalars().all())

    if not reminders:
        return {"sent": 0}

    from aiogram import Bot
    from src.config import settings

    bot = Bot(token=settings.telegram_bot_token)
    sent = 0
    errors = 0

    try:
        async with factory() as db:
            for reminder in reminders:
                try:
                    await bot.send_message(
                        chat_id=reminder.telegram_id,
                        text=f"🔔 Reminder: {reminder.content}",
                        parse_mode=None,
                    )
                    reminder.is_sent = True
                    reminder.sent_at = now
                    db.add(reminder)
                    sent += 1
                    logger.info(
                        "reminder sent",
                        reminder_id=str(reminder.id),
                        telegram_id=reminder.telegram_id,
                    )
                except Exception as exc:
                    errors += 1
                    logger.error(
                        "reminder send failed",
                        reminder_id=str(reminder.id),
                        error=str(exc),
                    )
            await db.commit()
    finally:
        await bot.session.close()

    return {"sent": sent, "errors": errors}
