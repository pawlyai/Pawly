"""
Telegram Mini App data handler.

Receives the JSON payload sent by the Mini App via Telegram.WebApp.sendData()
and creates the pet profile in the database.

Expected payload fields (all strings):
    name, species, breed, age, age_unit, gender, neutered,
    weight (optional), weight_unit (optional),
    medical_history (optional),
    start_param (optional) — forwarded from Telegram.WebApp.initDataUnsafe.start_param
                             so marketing context from ?startapp= links is preserved.
"""

import json
from typing import Any

from aiogram import F, Router
from aiogram.types import Message

from src.bot.handlers.callbacks import _create_pet_in_db
from src.bot.handlers.start import parse_start_param
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

    # Capture marketing context forwarded from the ?startapp= deep-link parameter.
    # The mini-app JS should include: { ..., start_param: Telegram.WebApp.initDataUnsafe.start_param }
    start_param = data.pop("start_param", None)
    if start_param:
        marketing_context = parse_start_param(str(start_param))
        if marketing_context:
            session["marketing_context"] = marketing_context
            logger.info(
                "marketing context from startapp",
                telegram_id=user.telegram_id,
                context=marketing_context,
            )

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
    session.pop("pending_new_pet_name", None)

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
