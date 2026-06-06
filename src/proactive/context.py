"""
Shared helpers for proactive message generation.

  build_pet_context_snippet  — compact pet profile string for prompt injection
  get_last_conversation_topic — last DailySummary highlight for reengagement
  locale_to_language_instruction — language-aware prompt suffix
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import or_, select

from src.db.engine import get_session_factory
from src.db.models import DailySummary, MemoryTerm, MemoryType, Pet, PetMemory
from src.utils.logger import get_logger

logger = get_logger(__name__)

_LOCALE_TO_LANGUAGE: dict[str, str] = {
    "zh": "Chinese (Simplified)",
    "zh-hans": "Chinese (Simplified)",
    "zh-hant": "Chinese (Traditional)",
    "ms": "Malay",
    "ta": "Tamil",
    "ja": "Japanese",
    "ko": "Korean",
    "id": "Indonesian",
    "th": "Thai",
    "vi": "Vietnamese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "ar": "Arabic",
}


def locale_to_language_instruction(locale: str) -> str:
    """Return 'Respond in X.' for non-English locales, or '' for English."""
    if not locale or locale.lower().startswith("en"):
        return ""
    lower = locale.lower()
    # Check full locale first (e.g. "zh-hant") before falling back to base code ("zh")
    lang = _LOCALE_TO_LANGUAGE.get(lower) or _LOCALE_TO_LANGUAGE.get(lower.split("-")[0])
    return f"Respond in {lang}." if lang else ""


def _fmt_memory_value(value: Any) -> str:
    if isinstance(value, dict):
        v = value.get("value") or value.get("raw") or value.get("name")
        if v:
            return str(v)
        return ", ".join(f"{k}:{val}" for k, val in list(value.items())[:3])
    if isinstance(value, list):
        return "/".join(str(x) for x in value[:3])
    return str(value)


def _format_age(age_in_months: Optional[int]) -> str:
    if not age_in_months:
        return ""
    years, months = divmod(age_in_months, 12)
    if years and months:
        return f"{years}y{months}m "
    if years:
        return f"{years}y "
    return f"{months}mo "


async def build_pet_context_snippet(pet: Pet, pet_id: str) -> str:
    """
    Return a compact one-liner with pet identity, known conditions,
    active medications, and the latest daily summary highlights.

    Example:
        Milo (4y male Poodle) | Known: IBD | Meds: Metronidazole | Recent: vomiting resolved
    """
    factory = get_session_factory()
    async with factory() as db:
        chronic_result = await db.execute(
            select(PetMemory)
            .where(
                PetMemory.pet_id == uuid.UUID(pet_id),
                PetMemory.memory_term == MemoryTerm.LONG,
                PetMemory.memory_type.in_([MemoryType.CHRONIC, MemoryType.SAFETY]),
                PetMemory.is_active.is_(True),
                or_(
                    PetMemory.expires_at.is_(None),
                    PetMemory.expires_at > datetime.now(timezone.utc),
                ),
            )
            .order_by(PetMemory.created_at.desc())
            .limit(5)
        )
        chronic_mems = list(chronic_result.scalars().all())

        meds_result = await db.execute(
            select(PetMemory)
            .where(
                PetMemory.pet_id == uuid.UUID(pet_id),
                PetMemory.field.in_(["medication_history", "current_medication"]),
                PetMemory.is_active.is_(True),
            )
            .order_by(PetMemory.created_at.desc())
            .limit(2)
        )
        meds_mems = list(meds_result.scalars().all())

        summary_result = await db.execute(
            select(DailySummary)
            .where(DailySummary.pet_id == pet_id)
            .order_by(DailySummary.date.desc())
            .limit(1)
        )
        daily_summary = summary_result.scalar_one_or_none()

    parts: list[str] = []

    age_str = _format_age(getattr(pet, "age_in_months", None))
    gender = f"{pet.gender.value} " if getattr(pet, "gender", None) else ""
    species = pet.species.value if pet.species else "pet"
    breed = f" {pet.breed}" if getattr(pet, "breed", None) else ""
    parts.append(f"{pet.name} ({age_str}{gender}{species}{breed})")

    if chronic_mems:
        conditions = "; ".join(_fmt_memory_value(m.value) for m in chronic_mems[:3])
        parts.append(f"Known: {conditions}")

    if meds_mems:
        meds = "; ".join(_fmt_memory_value(m.value) for m in meds_mems[:2])
        parts.append(f"Meds: {meds}")

    if daily_summary:
        highlights = (
            daily_summary.summary.get("highlights")
            or daily_summary.summary.get("core_issues")
        )
        if highlights:
            if isinstance(highlights, list):
                highlights = "; ".join(str(x) for x in highlights[:2])
            parts.append(f"Recent: {highlights}")

    return " | ".join(parts)


async def get_last_conversation_topic(pet_id: str) -> str:
    """
    Return the first highlight from the latest DailySummary, or '' if none.
    Used by reengagement to reference the last conversation topic.
    """
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(DailySummary)
            .where(DailySummary.pet_id == pet_id)
            .order_by(DailySummary.date.desc())
            .limit(1)
        )
        summary = result.scalar_one_or_none()

    if summary is None:
        return ""
    highlights = (
        summary.summary.get("highlights")
        or summary.summary.get("core_issues")
        or summary.summary.get("topics")
    )
    if not highlights:
        return ""
    if isinstance(highlights, list):
        return str(highlights[0]) if highlights else ""
    return str(highlights)
