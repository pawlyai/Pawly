"""
ARQ job: generate weekly health digests for all active pets.

run_weekly_summary(ctx) is the cron entry point. It finds every distinct
(pet_id, user_id) pair that has DailySummary rows in the past 7 days and
fans out to generate_weekly_summary() for each.
"""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select

from src.db.engine import get_session_factory
from src.db.models import DailySummary, Pet
from src.memory.summarizer import generate_weekly_summary
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def run_weekly_summary(ctx: dict) -> dict[str, Any]:
    """
    Cron job: generate a weekly digest for every pet with daily data in the
    past 7 days.

    week_start is set to today - 7 days so the window covers the last full week.
    Errors per pet are caught and logged without aborting the batch.
    """
    week_start = date.today() - timedelta(days=7)

    factory = get_session_factory()
    async with factory() as db:
        # Find distinct pet_ids that have daily summaries in the window
        result = await db.execute(
            select(DailySummary.pet_id, DailySummary.user_id)
            .where(DailySummary.date >= week_start)
            .distinct()
        )
        pairs = result.fetchall()  # list of (pet_id, user_id)

    total = len(pairs)
    succeeded = 0
    skipped = 0
    failed = 0

    for pet_id, user_id in pairs:
        try:
            summary = await generate_weekly_summary(
                pet_id=pet_id,
                user_id=user_id,
                week_start=week_start,
            )
            if summary is None:
                skipped += 1
            else:
                succeeded += 1
        except Exception as exc:
            failed += 1
            logger.error(
                "run_weekly_summary: pet failed",
                pet_id=pet_id,
                week_start=str(week_start),
                error=str(exc),
            )

    logger.info(
        "run_weekly_summary complete",
        week_start=str(week_start),
        total=total,
        succeeded=succeeded,
        skipped=skipped,
        failed=failed,
    )
    return {
        "status": "ok",
        "week_start": str(week_start),
        "total": total,
        "succeeded": succeeded,
        "skipped": skipped,
        "failed": failed,
    }
