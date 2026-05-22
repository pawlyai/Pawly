"""
Send a proactive Telegram message on behalf of Pawly.

All outbound proactive messages go through send_proactive_message() so
parse-mode fallback and logging are centralised in one place.
"""

from src.utils.logger import get_logger

logger = get_logger(__name__)


async def send_proactive_message(
    telegram_id: str,
    text: str,
    parse_mode: str | None = None,
) -> bool:
    """
    Send *text* to *telegram_id*.

    Returns True on success, False on failure (caller decides whether to
    mark the ProactiveEvent as sent or as failed).
    """
    try:
        from aiogram import Bot
        from src.config import settings

        bot = Bot(token=settings.telegram_bot_token)
        async with bot:
            try:
                await bot.send_message(
                    chat_id=int(telegram_id),
                    text=text,
                    parse_mode=parse_mode,
                )
            except Exception:
                # Retry without parse_mode if formatting caused the error
                if parse_mode is not None:
                    await bot.send_message(
                        chat_id=int(telegram_id),
                        text=text,
                        parse_mode=None,
                    )
                else:
                    raise
        return True
    except Exception as exc:
        logger.error(
            "proactive: send failed",
            telegram_id=telegram_id,
            error=str(exc),
        )
        return False
