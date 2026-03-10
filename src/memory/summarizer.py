"""
Daily and weekly memory compression / summarisation.

Public API:
    generate_daily_summary(pet_id, user_id, target_date)  — loads messages, calls LLM, upserts
    generate_weekly_summary(pet_id, user_id, week_start)  — loads daily rows, calls LLM, upserts

Prompt text lives in module-level constants (DAILY_PROMPT, WEEKLY_PROMPT) so it can be
edited without touching the logic below the separator line.
"""

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import distinct, select
from sqlalchemy.dialects.postgresql import insert

from src.db.engine import get_session_factory
from src.db.models import DailySummary, Pet, RawMessage, WeeklySummary
from src.llm.client import get_claude_client
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# EDITABLE PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

DAILY_PROMPT = """\
Compress this day's pet care conversation into a structured summary.
Pet: {pet_name} ({species}, {breed}, {age})
Date: {date}

Conversation:
{messages}

Return ONLY this JSON, no markdown:
{{
  "core_issues": ["main problems discussed"],
  "new_symptoms": ["symptoms first mentioned today"],
  "severity_changes": "improved|stable|worsened|unknown",
  "interventions_today": ["actions taken"],
  "risk_level": "red|orange|green|none",
  "unresolved_questions": ["pending items"],
  "follow_up_needed": true,
  "follow_up_reason": "string or null"
}}\
"""

WEEKLY_PROMPT = """\
Aggregate daily pet health summaries into a weekly digest.
Pet: {pet_name}
Week: {start} to {end}

Daily summaries:
{summaries}

Return ONLY this JSON, no markdown:
{{
  "has_persistent_symptoms": false,
  "symptom_days_count": 0,
  "is_worsening": false,
  "had_vet_visit": false,
  "formed_episode": false,
  "episode_type": null,
  "main_concerns": ["top issues"],
  "suspected_triggers": ["potential causes"],
  "owner_compliance": "high|medium|low"
}}\
"""

# ── Assembler — no prompt text below this line ────────────────────────────────

_MIN_MESSAGES_FOR_DAILY = 2  # skip if fewer user messages
_DEFAULT_DAILY: dict = {
    "core_issues": [],
    "new_symptoms": [],
    "severity_changes": "unknown",
    "interventions_today": [],
    "risk_level": "none",
    "unresolved_questions": [],
    "follow_up_needed": False,
    "follow_up_reason": None,
}
_DEFAULT_WEEKLY: dict = {
    "has_persistent_symptoms": False,
    "symptom_days_count": 0,
    "is_worsening": False,
    "had_vet_visit": False,
    "formed_episode": False,
    "episode_type": None,
    "main_concerns": [],
    "suspected_triggers": [],
    "owner_compliance": "medium",
}


# ── Public API ────────────────────────────────────────────────────────────────


async def generate_daily_summary(
    pet_id: str,
    user_id: str,
    target_date: date,
) -> Optional[dict]:
    """
    Load the day's raw messages for *pet_id* + *user_id*, call Claude Haiku to
    compress them, then upsert the result into DailySummary.

    Returns the summary dict, or None if skipped (too few messages).
    """
    factory = get_session_factory()

    async with factory() as db:
        # Load pet for prompt context
        pet = await db.get(Pet, uuid.UUID(pet_id))
        if pet is None:
            logger.warning("generate_daily_summary: pet not found", pet_id=pet_id)
            return None

        # Load raw messages for this pet+user on target_date
        day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        msg_result = await db.execute(
            select(RawMessage)
            .where(
                RawMessage.pet_id == pet_id,
                RawMessage.user_id == user_id,
                RawMessage.created_at >= day_start,
                RawMessage.created_at < day_end,
            )
            .order_by(RawMessage.created_at)
        )
        messages = list(msg_result.scalars().all())

    user_messages = [m for m in messages if m.role.value == "user"]
    if len(user_messages) < _MIN_MESSAGES_FOR_DAILY:
        logger.info(
            "generate_daily_summary: skipped (too few messages)",
            pet_id=pet_id,
            date=str(target_date),
            count=len(user_messages),
        )
        return None

    # Format conversation
    convo_lines = [
        f"{'User' if m.role.value == 'user' else 'Pawly'}: {m.raw_content}"
        for m in messages
    ]
    convo = "\n".join(convo_lines)

    filled = DAILY_PROMPT.format(
        pet_name=pet.name,
        species=pet.species.value,
        breed=pet.breed or "unknown",
        age=_fmt_age(pet.age_in_months),
        date=target_date.isoformat(),
        messages=convo,
    )

    client = get_claude_client()
    try:
        raw = await client.extract(
            system_prompt=filled,
            messages=[{"role": "user", "content": "Generate the summary now."}],
        )
        summary_data = json.loads(_strip_fences(raw["text"]))
    except Exception as exc:
        logger.error("daily summarization failed", error=str(exc), pet_id=pet_id, date=str(target_date))
        summary_data = _DEFAULT_DAILY.copy()

    # Upsert DailySummary
    async with factory() as db:
        stmt = (
            insert(DailySummary)
            .values(
                id=uuid.uuid4(),
                pet_id=pet_id,
                user_id=user_id,
                date=target_date,
                summary=summary_data,
                message_count=len(user_messages),
            )
            .on_conflict_do_update(
                constraint="uq_daily_summary_pet_date",
                set_={"summary": summary_data, "message_count": len(user_messages)},
            )
        )
        await db.execute(stmt)
        await db.commit()

    logger.info("daily summary saved", pet_id=pet_id, date=str(target_date), msg_count=len(user_messages))
    return summary_data


async def generate_weekly_summary(
    pet_id: str,
    user_id: str,
    week_start: date,
) -> Optional[dict]:
    """
    Load the past 7 DailySummary rows for *pet_id*, call Claude Haiku to
    aggregate them, then upsert into WeeklySummary.

    Returns the summary dict, or None if no daily data exists.
    """
    week_end = week_start + timedelta(days=6)
    factory = get_session_factory()

    async with factory() as db:
        pet = await db.get(Pet, uuid.UUID(pet_id))
        if pet is None:
            logger.warning("generate_weekly_summary: pet not found", pet_id=pet_id)
            return None

        daily_result = await db.execute(
            select(DailySummary)
            .where(
                DailySummary.pet_id == pet_id,
                DailySummary.date >= week_start,
                DailySummary.date <= week_end,
            )
            .order_by(DailySummary.date)
        )
        daily_rows = list(daily_result.scalars().all())

    if not daily_rows:
        logger.info("generate_weekly_summary: no daily data", pet_id=pet_id, week_start=str(week_start))
        return None

    # Format daily summaries for prompt
    summaries_block = "\n".join(
        f"{row.date}: {json.dumps(row.summary)}"
        for row in daily_rows
    )

    filled = WEEKLY_PROMPT.format(
        pet_name=pet.name,
        start=week_start.isoformat(),
        end=week_end.isoformat(),
        summaries=summaries_block,
    )

    client = get_claude_client()
    try:
        raw = await client.extract(
            system_prompt=filled,
            messages=[{"role": "user", "content": "Generate the weekly digest now."}],
        )
        summary_data = json.loads(_strip_fences(raw["text"]))
    except Exception as exc:
        logger.error("weekly summarization failed", error=str(exc), pet_id=pet_id, week_start=str(week_start))
        summary_data = _DEFAULT_WEEKLY.copy()

    # Upsert WeeklySummary
    async with factory() as db:
        stmt = (
            insert(WeeklySummary)
            .values(
                id=uuid.uuid4(),
                pet_id=pet_id,
                user_id=user_id,
                week_start=week_start,
                week_end=week_end,
                summary=summary_data,
            )
            .on_conflict_do_update(
                constraint="uq_weekly_summary_pet_week",
                set_={"summary": summary_data},
            )
        )
        await db.execute(stmt)
        await db.commit()

    logger.info(
        "weekly summary saved",
        pet_id=pet_id,
        week_start=str(week_start),
        week_end=str(week_end),
        days_covered=len(daily_rows),
    )
    return summary_data


# ── Internal helpers ──────────────────────────────────────────────────────────


def _fmt_age(age_in_months: Optional[int]) -> str:
    if not age_in_months:
        return "unknown age"
    years, months = divmod(age_in_months, 12)
    if years and months:
        return f"{years}y {months}m"
    if years:
        return f"{years} year{'s' if years > 1 else ''}"
    return f"{months} month{'s' if months > 1 else ''}"


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```", 2)
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()
