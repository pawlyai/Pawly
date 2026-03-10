"""
Outer middleware: Redis-backed JSON session per Telegram user.

Session schema (stored as JSON, key = f"session:{telegram_user_id}"):
{
    "user_id":              str | None,
    "active_pet_id":        str | None,
    "current_dialogue_id":  str | None,
    "current_session_id":   str | None,
    "last_message_at":      float,
    "marketing_context":    {"channel", "campaign", "theme", "creative"} | None,
    "turn_count":           int
}
TTL: 86400 seconds (24 hours).

As an outer middleware the session is loaded BEFORE the handler runs and
saved back to Redis AFTER the handler returns (even on error).
"""

import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from src.db.redis import get_redis
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SESSION_TTL = 86_400  # 24 hours in seconds

_DEFAULT_SESSION: dict[str, Any] = {
    "user_id": None,
    "active_pet_id": None,
    "current_dialogue_id": None,
    "current_session_id": None,
    "last_message_at": 0.0,
    "marketing_context": None,
    "turn_count": 0,
}


def _session_key(telegram_user_id: str) -> str:
    return f"session:{telegram_user_id}"


class SessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = None
        if isinstance(event, Message) and event.from_user:
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            tg_user = event.from_user

        if tg_user is None:
            return await handler(event, data)

        telegram_id = str(tg_user.id)
        redis = get_redis()
        key = _session_key(telegram_id)

        # Load existing session or start fresh
        raw = await redis.get(key)
        if raw:
            try:
                session: dict[str, Any] = json.loads(raw)
                # Back-fill any missing keys added in later releases
                for k, v in _DEFAULT_SESSION.items():
                    session.setdefault(k, v)
            except (json.JSONDecodeError, TypeError):
                logger.warning("corrupted session, resetting", telegram_id=telegram_id)
                session = dict(_DEFAULT_SESSION)
        else:
            session = dict(_DEFAULT_SESSION)

        data["session"] = session

        try:
            result = await handler(event, data)
        finally:
            # Persist session back to Redis regardless of handler outcome
            try:
                await redis.set(key, json.dumps(session), ex=_SESSION_TTL)
            except Exception as exc:
                logger.error("failed to save session", telegram_id=telegram_id, error=str(exc))

        return result
