"""
Inline button callback handlers.
"""

from typing import Any

from aiogram import Router
from aiogram.types import CallbackQuery

from src.db.models import Pet, User
from src.utils.logger import get_logger

router = Router(name="callbacks")
logger = get_logger(__name__)


@router.callback_query()
async def handle_callback(
    callback: CallbackQuery,
    user: User,
    active_pet: Pet | None,
    session: dict[str, Any],
) -> None:
    data = callback.data or ""
    logger.info("callback received", data=data, telegram_id=user.telegram_id)

    # Placeholder: echo the callback data back
    await callback.answer(f"Action: {data}", show_alert=False)

    if callback.message:
        await callback.message.answer(f"You selected: *{data}*")
