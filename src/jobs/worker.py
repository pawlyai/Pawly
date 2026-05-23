"""
ARQ worker settings and job registry.
"""

from arq import cron
from arq.connections import RedisSettings

from src.config import settings
from src.jobs.cleanup import expire_old_memories, expire_pending_changes, run_cleanup
from src.jobs.daily_summary import run_daily_summary
from src.jobs.episode_checkin import run_episode_checkin
from src.jobs.extraction import run_extraction
from src.jobs.followup import run_followup_check
from src.jobs.pending_nudge import run_pending_nudge
from src.jobs.reminder import run_reminder_check
from src.jobs.weekly_summary import run_weekly_summary


async def startup(ctx: dict) -> None:
    from src.db.engine import init_engine
    from src.db.redis import init_redis

    await init_engine()
    await init_redis()


async def shutdown(ctx: dict) -> None:
    from src.db.engine import close_engine
    from src.db.redis import close_redis

    await close_redis()
    await close_engine()


class WorkerSettings:
    functions = [
        run_extraction,
        run_followup_check,
        run_reminder_check,
        run_daily_summary,
        run_weekly_summary,
        run_cleanup,
        run_episode_checkin,
        run_pending_nudge,
        expire_old_memories,    # kept for individual invocation
        expire_pending_changes,  # kept for individual invocation
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    job_timeout = 60  # seconds
    max_jobs = 10
    cron_jobs = [
        cron(run_reminder_check),                               # every minute
        cron(run_daily_summary, hour=2, minute=0),
        cron(run_weekly_summary, weekday=0, hour=3, minute=0),  # Monday
        cron(run_cleanup, hour=4, minute=0),
        cron(run_episode_checkin, hour=9, minute=0),            # daily 09:00 UTC
        cron(run_pending_nudge, hour=10, minute=0),             # daily 10:00 UTC
    ]
