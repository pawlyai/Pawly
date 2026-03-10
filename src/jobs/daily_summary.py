"""
ARQ job: generate daily health summaries for all active pets.

run_daily_summary(ctx) is the cron entry point. It finds every distinct
(pet_id, user_id) pair that had raw messages yesterday and fans out to
generate_daily_summary() for each.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import distinct, select

from src.db.engine import get_session_factory
from src.db.models import RawMessage
from src.memory.summarizer import generate_daily_summary
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def run_daily_summary(ctx: dict) -> dict[str, Any]:
    """
    Cron job: generate yesterday's summary for every pet that had conversations.

    Finds all distinct (pet_id, user_id) pairs in RawMessage where
    created_at falls within yesterday (UTC), then calls generate_daily_summary
    for each. Errors per pet are caught and logged without aborting the batch.
    """
    yesterday = date.today() - timedelta(days=1)
    day_start = datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(RawMessage.pet_id, RawMessage.user_id)
            .where(
                RawMessage.pet_id.isnot(None),
                RawMessage.created_at >= day_start,
                RawMessage.created_at < day_end,
            )
            .distinct()
        )
        pairs = result.fetchall()  # list of (pet_id, user_id) rows

    total = len(pairs)
    succeeded = 0
    skipped = 0
    failed = 0

    for pet_id, user_id in pairs:
        try:
            summary = await generate_daily_summary(
                pet_id=pet_id,
                user_id=user_id,
                target_date=yesterday,
            )
            if summary is None:
                skipped += 1
            else:
                succeeded += 1
        except Exception as exc:
            failed += 1
            logger.error(
                "run_daily_summary: pet failed",
                pet_id=pet_id,
                date=str(yesterday),
                error=str(exc),
            )

    logger.info(
        "run_daily_summary complete",
        date=str(yesterday),
        total=total,
        succeeded=succeeded,
        skipped=skipped,
        failed=failed,
    )
    return {
        "status": "ok",
        "date": str(yesterday),
        "total": total,
        "succeeded": succeeded,
        "skipped": skipped,
        "failed": failed,
    }
