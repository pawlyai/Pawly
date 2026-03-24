"""
Telegram Mini App data handler.

Receives the JSON payload sent by the Mini App via Telegram.WebApp.sendData()
and creates the pet profile in the database.
"""

import json
from typing import Any

from aiogram import F, Router
from aiogram.types import Message

from src.bot.handlers.callbacks import _create_pet_in_db
from src.db.models import Pet, User
from src.utils.logger import get_logger

router = Router(name="webapp")
logger = get_logger(__name__)


@router.message(F.web_app_data)
async def handle_web_app_data(
    message: Message,
    user: User,
    active_pet: Pet | None,
    session: dict[str, Any],
) -> None:
    """Handle form data submitted from the Mini App."""
    raw = message.web_app_data.data if message.web_app_data else None
    if not raw:
        logger.warning("empty web_app_data received", telegram_id=user.telegram_id)
        await message.answer("Something went wrong. Please try again.")
        return

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("invalid web_app_data JSON", telegram_id=user.telegram_id, raw=raw)
        await message.answer("Something went wrong. Please try again.")
        return

    logger.info("web_app_data received", telegram_id=user.telegram_id, fields=list(data.keys()))

    pet = await _create_pet_in_db(user.id, data)
    if not pet:
        await message.answer(
            "Could not create the profile — please make sure name and species are filled in."
        )
        return

    is_additional = active_pet is not None

    session["active_pet_id"]        = str(pet.id)
    session["awaiting_pet_profile"]  = False
    session["is_new_user"]           = False
    session["profile_wizard_step"]   = None
    session["profile_wizard_data"]   = {}

    if is_additional:
        await message.answer(
            f"✅ {pet.name}'s profile created! "
            f"I've switched to {pet.name} — what would you like to know?"
        )
    else:
        await message.answer(
            f"✅ Profile created for {pet.name}!\n\n"
            "How can I help you today?"
        )
