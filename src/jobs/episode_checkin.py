"""
ARQ cron job: check in on ongoing episodes the user hasn't mentioned recently.

Runs daily after run_daily_summary. For each open Episode:
  - started >= 3 days ago (enough time to see if it resolves naturally)
  - user has sent no message in the last 48 hours (they haven't volunteered an update)
  - no episode check-in was already sent for this episode (ProactiveEvent dedup)

Generates a contextual check-in that references the specific symptom type,
how many days it has been going on, and any recorded interventions.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from src.db.engine import get_session_factory
from src.db.models import Episode, MessageRole, Pet, ProactiveEventType, RawMessage, User
from src.proactive.dedup import already_sent, record_sent, record_skipped
from src.proactive.dispatcher import send_proactive_message
from src.utils.logger import get_logger

logger = get_logger(__name__)

_MIN_EPISODE_AGE_DAYS = 3
_USER_SILENCE_HOURS = 48


async def run_episode_checkin(ctx: dict) -> dict[str, Any]:
    """
    Cron job: send a contextual check-in for ongoing silent episodes.
    """
    now = datetime.now(timezone.utc)
    episode_age_cutoff = now - timedelta(days=_MIN_EPISODE_AGE_DAYS)
    silence_cutoff = now - timedelta(hours=_USER_SILENCE_HOURS)

    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(Episode).where(
                Episode.is_ongoing.is_(True),
                Episode.start_date <= episode_age_cutoff,
            )
        )
        episodes = list(result.scalars().all())

    total = len(episodes)
    sent_count = 0
    skipped_count = 0

    for episode in episodes:
        try:
            outcome = await _process_episode(episode, silence_cutoff, factory)
            if outcome == "sent":
                sent_count += 1
            else:
                skipped_count += 1
        except Exception as exc:
            logger.error(
                "episode_checkin: error processing episode",
                episode_id=str(episode.id),
                error=str(exc),
            )
            skipped_count += 1

    logger.info(
        "run_episode_checkin complete",
        total=total,
        sent=sent_count,
        skipped=skipped_count,
    )
    return {"status": "ok", "total": total, "sent": sent_count, "skipped": skipped_count}


async def _process_episode(
    episode: Episode,
    silence_cutoff: datetime,
    factory,
) -> str:
    ref_id = str(episode.id)

    if await already_sent(ProactiveEventType.EPISODE_CHECKIN, ref_id, stage=1):
        return "skipped_already_sent"

    async with factory() as db:
        pet = await db.get(Pet, episode.pet_id)
        if pet is None:
            return "skipped_no_pet"

        user_result = await db.execute(
            select(User).where(User.id == pet.user_id)
        )
        user = user_result.scalar_one_or_none()
        if user is None or not user.telegram_id.lstrip("-").isdigit():
            return "skipped_no_user"

        # Check if user has been active recently (don't interrupt an active conversation)
        recent_msg = await db.execute(
            select(func.count(RawMessage.id)).where(
                RawMessage.user_id == str(user.id),
                RawMessage.role == MessageRole.USER,
                RawMessage.created_at > silence_cutoff,
            )
        )
        if recent_msg.scalar_one() > 0:
            await record_skipped(
                user_id=str(user.id),
                pet_id=str(pet.id),
                telegram_id=user.telegram_id,
                event_type=ProactiveEventType.EPISODE_CHECKIN,
                trigger_ref_id=ref_id,
                reason="user_recently_active",
            )
            return "skipped_user_active"

    days_ongoing = (datetime.now(timezone.utc) - episode.start_date.replace(tzinfo=timezone.utc)).days
    text = await _generate_episode_checkin(
        pet_name=pet.name,
        pet_species=pet.species.value,
        symptom_type=episode.symptom_type,
        severity=episode.severity.value,
        days_ongoing=days_ongoing,
        interventions=episode.interventions,
    )

    sent = await send_proactive_message(telegram_id=user.telegram_id, text=text)
    if sent:
        await record_sent(
            user_id=str(user.id),
            pet_id=str(pet.id),
            telegram_id=user.telegram_id,
            event_type=ProactiveEventType.EPISODE_CHECKIN,
            trigger_ref_id=ref_id,
            stage=1,
            content_preview=text[:300],
        )
        logger.info(
            "episode_checkin: sent",
            episode_id=ref_id,
            pet_id=str(pet.id),
            days_ongoing=days_ongoing,
        )
        return "sent"
    return "error"


async def _generate_episode_checkin(
    pet_name: str,
    pet_species: str,
    symptom_type: str,
    severity: str,
    days_ongoing: int,
    interventions: dict | None,
) -> str:
    intervention_str = ""
    if interventions:
        items = list(interventions.values()) if isinstance(interventions, dict) else interventions
        if items:
            intervention_str = f"Interventions tried: {', '.join(str(i) for i in items[:3])}. "

    from src.llm.prompts.system import get_proactive_prompt
    template = get_proactive_prompt("proactive_episode_checkin")
    prompt = template.format(
        pet_name=pet_name,
        pet_species=pet_species,
        symptom_type=symptom_type,
        severity=severity,
        days_ongoing=days_ongoing,
        intervention_str=intervention_str,
    )
    try:
        from src.llm.client import get_gemini_client
        client = get_gemini_client()
        raw = await client.extract(
            system_prompt="You are Pawly. Output only the message text — no preamble, no quotes.",
            messages=[{"role": "user", "content": prompt}],
        )
        return raw["text"].strip()
    except Exception as exc:
        logger.error("episode_checkin: generation failed", error=str(exc))
        return (
            f"Hey, just checking in — {pet_name}'s {symptom_type} has been going on for "
            f"{days_ongoing} days now. Any updates? 🐾"
        )
