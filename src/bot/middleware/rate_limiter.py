"""
Middleware: per-user rate limiting backed by Redis.

Key:   f"ratelimit:{telegram_user_id}"
Window: 60 seconds (sliding)
Limit:  settings.max_messages_per_minute

Exceeding the limit sends a friendly message and stops propagation.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from src.config import settings
from src.db.redis import get_redis
from src.utils.logger import get_logger

logger = get_logger(__name__)

_WINDOW = 60  # seconds


class RateLimiterMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or event.from_user is None:
            return await handler(event, data)

        telegram_id = str(event.from_user.id)
        redis = get_redis()
        key = f"ratelimit:{telegram_id}"

        count_raw = await redis.get(key)
        count = int(count_raw) if count_raw else 0

        if count >= settings.max_messages_per_minute:
            logger.warning("rate limit exceeded", telegram_id=telegram_id, count=count)
            await event.answer(
                "I need a moment to catch up! Please wait a bit before sending more messages."
            )
            return None

        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, _WINDOW)
        await pipe.execute()

        return await handler(event, data)
