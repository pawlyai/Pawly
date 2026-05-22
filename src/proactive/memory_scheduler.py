"""
Schedule Telegram reminders from extracted PetMemory facts.

Called after commit_proposals() in run_extraction. Watches for changes to:
  - vaccination_date     → reminder 30d, 7d, 1d before due date
  - deworming_status     → reminder if value contains "due" or a date
  - medication_history   → recurring reminder parsed from "every Xh/Xd" pattern

Creates rows in the Reminder table (delivered by run_reminder_check every minute).
Existing undelivered reminders for the same field are replaced to avoid noise
when a fact is updated.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select

from src.db.engine import get_session_factory
from src.db.models import Pet, Reminder, User
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Fields that trigger reminder scheduling
_WATCHED_FIELDS = {"vaccination_date", "deworming_status", "medication_history"}

# Regex to detect "every Xh" or "every X days/hours" in medication instructions
_EVERY_PATTERN = re.compile(
    r"every\s+(\d+)\s*(h(?:our)?s?|d(?:ay)?s?)",
    re.IGNORECASE,
)
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


async def schedule_reminders_from_memories(
    pet_id: str,
    user_id: str,
    changed_fields: list[str],
) -> None:
    """
    Re-evaluate reminder schedules for any changed field that we watch.
    Silently no-ops if the pet/user cannot be found or the value is unparseable.
    """
    relevant = [f for f in changed_fields if f in _WATCHED_FIELDS]
    if not relevant:
        return

    factory = get_session_factory()
    async with factory() as db:
        pet = await db.get(Pet, uuid.UUID(pet_id))
        user_result = await db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = user_result.scalar_one_or_none()

        if pet is None or user is None:
            return
        if not user.telegram_id.lstrip("-").isdigit():
            return

        from src.db.models import PetMemory
        mem_result = await db.execute(
            select(PetMemory).where(
                PetMemory.pet_id == uuid.UUID(pet_id),
                PetMemory.field.in_(relevant),
                PetMemory.is_active.is_(True),
            )
        )
        memories = list(mem_result.scalars().all())

    for mem in memories:
        await _schedule_for_field(
            field=mem.field,
            value=mem.value,
            pet=pet,
            user=user,
        )


async def _schedule_for_field(
    field: str,
    value: object,
    pet: Pet,
    user: User,
) -> None:
    factory = get_session_factory()
    user_id_uuid = user.id
    pet_id_uuid = pet.id

    if field == "vaccination_date":
        await _schedule_vaccination(value, pet, user, factory, user_id_uuid, pet_id_uuid)
    elif field == "deworming_status":
        await _schedule_deworming(value, pet, user, factory, user_id_uuid, pet_id_uuid)
    elif field == "medication_history":
        await _schedule_medication(value, pet, user, factory, user_id_uuid, pet_id_uuid)


async def _replace_pending_reminders(
    factory,
    user_id_uuid: uuid.UUID,
    pet_id_uuid: uuid.UUID,
    content_prefix: str,
    new_reminders: list[dict],
) -> None:
    """Delete undelivered reminders matching the prefix, then insert new ones."""
    async with factory() as db:
        await db.execute(
            delete(Reminder).where(
                Reminder.user_id == user_id_uuid,
                Reminder.pet_id == pet_id_uuid,
                Reminder.is_sent.is_(False),
                Reminder.content.like(f"{content_prefix}%"),
            )
        )
        for r in new_reminders:
            db.add(Reminder(
                id=uuid.uuid4(),
                user_id=user_id_uuid,
                pet_id=pet_id_uuid,
                telegram_id=r["telegram_id"],
                content=r["content"],
                remind_at=r["remind_at"],
            ))
        await db.commit()


async def _schedule_vaccination(value, pet, user, factory, user_id_uuid, pet_id_uuid) -> None:
    raw = value if isinstance(value, str) else str(value.get("value", "")) if isinstance(value, dict) else ""
    match = _DATE_PATTERN.search(raw)
    if not match:
        return
    try:
        due_date = datetime.fromisoformat(match.group()).replace(tzinfo=timezone.utc)
    except ValueError:
        return

    now = datetime.now(timezone.utc)
    reminders = []
    for days_before in (30, 7, 1):
        remind_at = due_date - timedelta(days=days_before)
        if remind_at > now:
            label = {30: "in 1 month", 7: "in 1 week", 1: "tomorrow"}[days_before]
            reminders.append({
                "telegram_id": user.telegram_id,
                "content": (
                    f"{pet.name}'s vaccination is due {label} ({due_date.strftime('%B %d, %Y')}). "
                    f"Time to book with your vet! 💉"
                ),
                "remind_at": remind_at,
            })

    if reminders:
        await _replace_pending_reminders(
            factory, user_id_uuid, pet_id_uuid,
            content_prefix=f"{pet.name}'s vaccination",
            new_reminders=reminders,
        )
        logger.info("vaccination reminders scheduled", pet_id=str(pet_id_uuid), count=len(reminders))


async def _schedule_deworming(value, pet, user, factory, user_id_uuid, pet_id_uuid) -> None:
    raw = value if isinstance(value, str) else str(value.get("value", "")) if isinstance(value, dict) else ""
    raw_lower = raw.lower()

    # Look for an explicit date first
    date_match = _DATE_PATTERN.search(raw)
    remind_at: Optional[datetime] = None
    if date_match:
        try:
            remind_at = datetime.fromisoformat(date_match.group()).replace(tzinfo=timezone.utc) - timedelta(days=7)
        except ValueError:
            pass

    # Fallback: if "due" keyword present and no date, default to 30 days from now
    if remind_at is None and "due" in raw_lower:
        remind_at = datetime.now(timezone.utc) + timedelta(days=30)

    if remind_at is None or remind_at <= datetime.now(timezone.utc):
        return

    reminders = [{
        "telegram_id": user.telegram_id,
        "content": (
            f"Reminder: {pet.name}'s deworming treatment is coming up soon. "
            f"Check with your vet if you haven't already! 🐛"
        ),
        "remind_at": remind_at,
    }]
    await _replace_pending_reminders(
        factory, user_id_uuid, pet_id_uuid,
        content_prefix=f"Reminder: {pet.name}'s deworming",
        new_reminders=reminders,
    )
    logger.info("deworming reminder scheduled", pet_id=str(pet_id_uuid))


async def _schedule_medication(value, pet, user, factory, user_id_uuid, pet_id_uuid) -> None:
    raw = value if isinstance(value, str) else str(value.get("value", "")) if isinstance(value, dict) else ""
    match = _EVERY_PATTERN.search(raw)
    if not match:
        return

    amount = int(match.group(1))
    unit = match.group(2).lower()
    interval_hours = amount if unit.startswith("h") else amount * 24

    # Don't schedule high-frequency medication reminders (< 6h) — too noisy
    if interval_hours < 6:
        return

    now = datetime.now(timezone.utc)
    # Schedule the next 3 occurrences
    reminders = []
    med_name = _extract_med_name(raw)
    for i in range(1, 4):
        remind_at = now + timedelta(hours=interval_hours * i)
        reminders.append({
            "telegram_id": user.telegram_id,
            "content": (
                f"Time for {pet.name}'s{' ' + med_name if med_name else ''} medication! 💊"
            ),
            "remind_at": remind_at,
        })

    await _replace_pending_reminders(
        factory, user_id_uuid, pet_id_uuid,
        content_prefix=f"Time for {pet.name}'s",
        new_reminders=reminders,
    )
    logger.info(
        "medication reminders scheduled",
        pet_id=str(pet_id_uuid),
        interval_hours=interval_hours,
        count=len(reminders),
    )


def _extract_med_name(text: str) -> str:
    """Pull a capitalised word that looks like a drug name from text."""
    for word in text.split():
        clean = re.sub(r"[^a-zA-Z]", "", word)
        if len(clean) >= 4 and clean[0].isupper():
            return clean
    return ""
