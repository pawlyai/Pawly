"""
POST /miniapp/create-pet

Receives pet profile data submitted by the Telegram Mini App via fetch()
(replaces tg.sendData() which only works with reply-keyboard buttons).

Validates the Telegram initData HMAC so only real Telegram users can call this.
Creates the pet in the database and returns the pet ID.
"""

import hashlib
import hmac
import json
import urllib.parse
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.bot.handlers.callbacks import _create_pet_in_db
from src.bot.handlers.start import parse_start_param
from src.config import settings
from src.db.engine import get_session_factory
from src.db.models import User
from src.utils.logger import get_logger
from sqlalchemy import select

logger = get_logger(__name__)
router = APIRouter(prefix="/miniapp", tags=["miniapp"])


class PetProfileRequest(BaseModel):
    init_data: str = ""     # Telegram.WebApp.initData (for HMAC validation)
    dev_telegram_id: str = ""  # dev-only bypass when initData is empty
    name: str
    species: str
    breed: str | None = None
    age: str | None = None
    age_unit: str = "Y"
    gender: str | None = None
    neutered: str | None = None
    weight: str | None = None
    weight_unit: str = "kg"
    medical_history: str | None = None
    start_param: str | None = None


def _validate_init_data(init_data: str, bot_token: str) -> dict | None:
    """Validate Telegram WebApp initData HMAC. Returns parsed fields or None."""
    params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = params.pop("hash", None)
    if not received_hash:
        return None
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, received_hash):
        return None
    return params


@router.post("/create-pet")
async def create_pet(req: PetProfileRequest) -> dict:
    # ── Validate initData (dev bypass when initData is empty) ───────────────
    is_dev = settings.node_env != "production"
    tg_user: dict = {}

    if req.init_data:
        validated = _validate_init_data(req.init_data, settings.telegram_bot_token)
        if validated is None:
            raise HTTPException(status_code=401, detail="Invalid Telegram initData")
        try:
            tg_user = json.loads(validated.get("user", "{}"))
        except (json.JSONDecodeError, AttributeError):
            raise HTTPException(status_code=400, detail="Could not parse user from initData")
        telegram_id = str(tg_user.get("id", ""))
    elif is_dev and req.dev_telegram_id:
        # Dev-only: skip HMAC, use provided telegram_id directly
        telegram_id = req.dev_telegram_id
        logger.warning("dev bypass used for miniapp", telegram_id=telegram_id)
    else:
        raise HTTPException(status_code=401, detail="initData required")

    if not telegram_id:
        raise HTTPException(status_code=400, detail="No user ID in initData")

    # ── Load or create User ─────────────────────────────────────────────────
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                telegram_id=telegram_id,
                telegram_username=tg_user.get("username"),
                display_name=tg_user.get("first_name", ""),
                locale=tg_user.get("language_code", "en"),
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info("new user via miniapp", telegram_id=telegram_id)

    # ── Parse marketing context if present ──────────────────────────────────
    marketing_context = parse_start_param(req.start_param or "") if req.start_param else None
    if marketing_context:
        logger.info("marketing context from miniapp", telegram_id=telegram_id, context=marketing_context)

    # ── Create pet ──────────────────────────────────────────────────────────
    profile_data = {
        "name":             req.name,
        "species":          req.species,
        "breed":            req.breed,
        "age":              req.age,
        "age_unit":         req.age_unit,
        "gender":           req.gender,
        "neutered":         req.neutered,
        "weight":           req.weight,
        "weight_unit":      req.weight_unit,
        "medical_history":  req.medical_history,
    }
    pet = await _create_pet_in_db(user.id, profile_data)
    if pet is None:
        raise HTTPException(status_code=422, detail="Could not create pet — name and species are required")

    logger.info("pet created via miniapp", telegram_id=telegram_id, pet_id=str(pet.id), name=pet.name)
    return {"ok": True, "pet_id": str(pet.id), "pet_name": pet.name}
