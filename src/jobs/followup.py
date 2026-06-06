"""
ARQ job: multi-stage proactive follow-up for RED/ORANGE triage conversations.

Stage schedule:
  RED:    Stage 1 at T+2h, Stage 2 at T+24h, Stage 3 at T+48h
  ORANGE: Stage 1 at T+4h, Stage 2 at T+48h  (no stage 3)

Each stage checks whether the user sent any message since the *previous*
stage fired. If they replied, the cascade terminates. If not, we send a
check-in and enqueue the next stage.

Dedup uses ProactiveEvent (trigger_ref_id = triage_record_id + user_id hash,
stage = stage number) so concurrent workers cannot double-send.
"""

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from src.db.engine import get_session_factory
from src.db.models import MessageRole, ProactiveEventType, RawMessage
from src.proactive.dedup import already_sent, record_sent, record_skipped
from src.proactive.dispatcher import send_proactive_message
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Delays (hours) per triage level and stage
_STAGE_DELAYS: dict[str, list[int]] = {
    "RED":    [2, 24, 48],
    "ORANGE": [4, 48],
}

_FOLLOWUP_KEY = "followup_pending:{user_id}"


def _trigger_ref(user_id: str, triage_record_id: str) -> str:
    """Stable dedup key scoped to one triage episode."""
    raw = f"{user_id}:{triage_record_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def run_followup_check(
    ctx: dict,
    *,
    telegram_id: str,
    user_id: str,
    pet_id: str,
    pet_name: str,
    pet_species: str,
    triage_level: str,
    triage_record_id: str,
    symptom_tags: list[str],
    enqueued_at: str,
    stage: int = 1,
) -> dict[str, Any]:
    """
    Multi-stage follow-up check. Re-enqueues itself for the next stage if
    the user still hasn't replied and more stages remain.
    """
    if not telegram_id.lstrip("-").isdigit():
        return {"status": "skipped", "reason": "non_telegram_user"}

    level = triage_level.upper()
    delays = _STAGE_DELAYS.get(level, _STAGE_DELAYS["ORANGE"])

    if stage > len(delays):
        return {"status": "skipped", "reason": "no_more_stages"}

    # Strip timezone so the value is compatible with TIMESTAMP WITHOUT TIME ZONE columns.
    enqueued_dt = datetime.fromisoformat(enqueued_at).replace(tzinfo=None)
    ref_id = _trigger_ref(user_id, triage_record_id)

    # Dedup: skip if this stage was already sent
    if await already_sent(ProactiveEventType.TRIAGE_FOLLOWUP, ref_id, stage=stage):
        logger.info("followup: already sent for stage", user_id=user_id, stage=stage)
        return {"status": "skipped", "reason": "already_sent"}

    # Check if user replied since enqueue time
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(func.count(RawMessage.id)).where(
                RawMessage.user_id == user_id,
                RawMessage.role == MessageRole.USER,
                RawMessage.created_at > enqueued_dt,
            )
        )
        count = result.scalar_one()

    if count > 0:
        logger.info(
            "followup: user replied — cascade terminated",
            telegram_id=telegram_id,
            stage=stage,
        )
        await record_skipped(
            user_id=user_id,
            pet_id=pet_id,
            telegram_id=telegram_id,
            event_type=ProactiveEventType.TRIAGE_FOLLOWUP,
            trigger_ref_id=ref_id,
            stage=stage,
            reason="user_responded",
        )
        redis = ctx["redis"]
        await redis.delete(_FOLLOWUP_KEY.format(user_id=user_id))
        return {"status": "skipped", "reason": "user_responded"}

    # Generate and send check-in
    text = await _generate_message(
        pet_name=pet_name,
        pet_species=pet_species,
        triage_level=level,
        symptom_tags=symptom_tags,
        stage=stage,
    )

    sent = await send_proactive_message(telegram_id=telegram_id, text=text)

    if sent:
        await record_sent(
            user_id=user_id,
            pet_id=pet_id,
            telegram_id=telegram_id,
            event_type=ProactiveEventType.TRIAGE_FOLLOWUP,
            trigger_ref_id=ref_id,
            stage=stage,
            content_preview=text[:300],
        )
        # Store proactive context for the next /start
        import json as _json
        redis = ctx["redis"]
        await redis.setex(
            f"proactive_ctx:{telegram_id}",
            86400,
            _json.dumps({
                "pet_name": pet_name,
                "pet_species": pet_species,
                "triage_level": level,
                "symptom_tags": symptom_tags,
                "message_text": text,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }),
        )
        logger.info("followup: sent", stage=stage, triage_level=level, telegram_id=telegram_id)

    # Enqueue next stage if one exists
    next_stage = stage + 1
    if next_stage <= len(delays):
        next_delay_h = delays[next_stage - 1]
        # Naive UTC — compatible with TIMESTAMP WITHOUT TIME ZONE columns on next run.
        fire_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        # Stable job_id prevents duplicate enqueues if this stage is retried.
        next_job_id = f"followup:{user_id}:{triage_record_id}:{next_stage}"
        from src.jobs.pool import get_arq_pool
        enqueue_ok = False
        for attempt in range(3):
            try:
                pool = await get_arq_pool()
                await pool.enqueue_job(
                    "run_followup_check",
                    telegram_id=telegram_id,
                    user_id=user_id,
                    pet_id=pet_id,
                    pet_name=pet_name,
                    pet_species=pet_species,
                    triage_level=level,
                    triage_record_id=triage_record_id,
                    symptom_tags=symptom_tags,
                    enqueued_at=fire_at,
                    stage=next_stage,
                    _defer_by=timedelta(hours=next_delay_h),
                    _job_id=next_job_id,
                )
                logger.info(
                    "followup: next stage enqueued",
                    next_stage=next_stage,
                    delay_hours=next_delay_h,
                )
                enqueue_ok = True
                break
            except Exception as exc:
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error(
                        "followup: CRITICAL — next stage lost after 3 attempts",
                        error=str(exc),
                        user_id=user_id,
                        telegram_id=telegram_id,
                        triage_record_id=triage_record_id,
                        next_stage=next_stage,
                        next_delay_hours=next_delay_h,
                    )
        if not enqueue_ok and sent:
            return {"status": "next_stage_enqueue_failed", "stage": stage}

    if not sent:
        return {"status": "error", "stage": stage}

    return {"status": "sent", "stage": stage, "triage_level": level}


async def _generate_message(
    pet_name: str,
    pet_species: str,
    triage_level: str,
    symptom_tags: list[str],
    stage: int,
    pet_context: str = "",
    locale: str = "en",
) -> str:
    delays = _STAGE_DELAYS.get(triage_level, _STAGE_DELAYS["ORANGE"])
    hours_elapsed = sum(delays[:stage])
    urgency = "urgent" if triage_level == "RED" else "concerning"
    symptoms_str = ", ".join(symptom_tags) if symptom_tags else "health concerns"
    no_emoji = triage_level == "RED"  # all RED stages — situation may still be serious

    stage_note = ""
    if stage >= 3:
        stage_note = (
            f"This is your third unanswered check-in — the owner has not replied to two previous messages. "
            f"Explicitly acknowledge that you have reached out multiple times without a response. "
            f"The urgency has escalated — express clear, genuine alarm and worry. "
            f"The tone must be noticeably more urgent and serious than a first check-in. "
            f"Do NOT use hedging phrases like 'if you get a chance' or 'if possible'."
        )
    elif stage == 2:
        stage_note = (
            "The owner has not responded to your previous message. "
            "Explicitly acknowledge that you are following up after no reply. "
            "Be noticeably more concerned than a first check-in, but still warm."
        )

    from src.llm.prompts.system import get_proactive_prompt
    template = get_proactive_prompt("proactive_followup")
    prompt = template.format(
        hours_elapsed=hours_elapsed,
        pet_name=pet_name,
        pet_species=pet_species,
        symptoms_str=symptoms_str,
        urgency=urgency,
        stage=stage,
        emoji_rule="No emoji — situation may still be serious." if no_emoji else "One emoji is fine.",
        stage_note=f" {stage_note}" if stage_note else "",
    )
    if pet_context:
        prompt += f"\n\nPet profile context: {pet_context}"
    try:
        from src.llm.orchestrator import _active_chat_model  # type: ignore[attr-defined]
        from src.llm.providers import get_chat_client
        chat_model = _active_chat_model()
        client = get_chat_client(chat_model)
        raw = await client.chat(
            system_prompt="You are Pawly. Output only the message text — no preamble, no quotes.",
            messages=[{"role": "user", "content": prompt}],
            model=chat_model,
            max_tokens=2048,
            temperature=0.7,
        )
        text = raw["text"].strip()
        if not text:
            raise ValueError("LLM returned empty follow-up text")
        return text
    except Exception as exc:
        logger.error("followup: generation failed", stage=stage, error=str(exc))
        return f"Hey, just checking in — how is {pet_name} doing? 🐾"
