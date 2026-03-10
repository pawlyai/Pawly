"""
Middleware: load or create the User + active Pet for every incoming event.

Injects into handler data:
    data["user"]        — User ORM object (created if first time)
    data["active_pet"]  — most-recently-used Pet, or None
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select

from src.db.engine import get_session_factory
from src.db.models import Pet, User
from src.utils.logger import get_logger

logger = get_logger(__name__)


class UserLoaderMiddleware(BaseMiddleware):
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
        factory = get_session_factory()

        async with factory() as db:
            # ── Load or create User ──────────────────────────────────────────
            result = await db.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if user is None:
                user = User(
                    telegram_id=telegram_id,
                    telegram_username=tg_user.username,
                    display_name=tg_user.full_name,
                    locale=tg_user.language_code or "en",
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)
                logger.info("new user created", telegram_id=telegram_id)

            # ── Load active pet ──────────────────────────────────────────────
            # Prefer the pet updated most recently (last used).
            # Falls back to created_at desc so a user with a single pet always
            # gets that pet without ambiguity.
            pet_result = await db.execute(
                select(Pet)
                .where(Pet.user_id == user.id, Pet.is_active.is_(True))
                .order_by(Pet.updated_at.desc().nulls_last(), Pet.created_at.desc())
                .limit(1)
            )
            active_pet = pet_result.scalar_one_or_none()

        # Sync session cache with resolved IDs (session already in data from
        # SessionMiddleware which runs before this middleware).
        session: dict = data.get("session", {})
        session["user_id"] = str(user.id)
        if active_pet:
            session["active_pet_id"] = str(active_pet.id)

        data["user"] = user
        data["active_pet"] = active_pet
        return await handler(event, data)
