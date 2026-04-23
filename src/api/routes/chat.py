"""
POST /chat — web interface for testing the classic orchestrator path.

Accepts a plain message plus optional pet profile fields; constructs transient
User and Pet objects (not persisted) and drives _generate_response_classic
directly.  Intended for local testing and the Langfuse tracing demo — not a
production user-facing endpoint.
"""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from src.db.models import (
    Gender,
    MessageType,
    NeuteredStatus,
    Pet,
    Species,
    SubscriptionTier,
    User,
)
from src.llm.orchestrator import generate_response
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    # Optional pet context — defaults produce a generic adult dog
    pet_name: str = "Demo Pet"
    pet_species: str = "dog"
    pet_age_months: int | None = 24
    # Optional identifiers for trace correlation in Langfuse
    user_id: str | None = None
    dialogue_id: str | None = None


class ChatResponse(BaseModel):
    response_text: str
    triage_level: str | None
    intent: str | None
    symptom_tags: list[str]
    input_tokens: int
    output_tokens: int
    user_id: str
    dialogue_id: str


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    user_id = uuid.UUID(req.user_id) if req.user_id else uuid.uuid4()
    pet_id = uuid.uuid4()
    dialogue_id = req.dialogue_id or str(uuid.uuid4())

    user = User(
        id=user_id,
        telegram_id=f"web-{user_id.hex[:10]}",
        display_name="Web Test User",
        subscription_tier=SubscriptionTier.NEW_FREE,
    )

    try:
        species = Species(req.pet_species.lower())
    except ValueError:
        species = Species.DOG

    pet = Pet(
        id=pet_id,
        user_id=user_id,
        name=req.pet_name,
        species=species,
        age_in_months=req.pet_age_months,
        gender=Gender.UNKNOWN,
        neutered_status=NeuteredStatus.UNKNOWN,
    )

    result = await generate_response(
        user=user,
        pet=pet,
        dialogue_id=dialogue_id,
        user_message=req.message,
        message_type=MessageType.TEXT,
    )

    triage_level = result.triage_result["final"] if result.triage_result else None

    return ChatResponse(
        response_text=result.response_text,
        triage_level=triage_level,
        intent=result.intent,
        symptom_tags=result.symptom_tags,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        user_id=str(user_id),
        dialogue_id=dialogue_id,
    )
