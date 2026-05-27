"""
ARQ cron job: daily analytics report sent to all admin Telegram IDs.

Runs at 06:00 UTC daily, covering yesterday (UTC).

Metrics reported:
  - DAU  — distinct users who sent at least one message
  - New users joined yesterday
  - Total user messages + bot messages
  - Avg messages per active user
  - Triage breakdown (RED / ORANGE / GREEN counts)
  - Proactive messages sent + reply rate (replied within 24h)
  - Subscription tier breakdown (snapshot of all users)
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import distinct, func, select

from src.config import settings
from src.db.engine import get_session_factory
from src.db.models import (
    MessageRole,
    ProactiveEvent,
    RawMessage,
    SubscriptionTier,
    TriageRecord,
    User,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def run_analytics_report(ctx: dict) -> dict[str, Any]:
    """
    Cron job: compute yesterday's engagement metrics and push to all admins.
    """
    admin_ids = [
        tid.strip()
        for tid in settings.admin_telegram_ids.split(",")
        if tid.strip()
    ]
    if not admin_ids:
        logger.warning("analytics_report: no admin_telegram_ids configured — skipping")
        return {"status": "skipped", "reason": "no_admins"}

    yesterday = date.today() - timedelta(days=1)
    day_start = datetime(yesterday.year, yesterday.month, yesterday.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    metrics = await _compute_metrics(yesterday, day_start, day_end)
    text = _format_report(yesterday, metrics)

    sent = 0
    errors = 0
    try:
        from aiogram import Bot

        bot = Bot(token=settings.telegram_bot_token)
        async with bot:
            for admin_id in admin_ids:
                try:
                    await bot.send_message(
                        chat_id=int(admin_id),
                        text=text,
                        parse_mode="HTML",
                    )
                    sent += 1
                except Exception as exc:
                    errors += 1
                    logger.error(
                        "analytics_report: failed to send to admin",
                        admin_id=admin_id,
                        error=str(exc),
                    )
    except Exception as exc:
        logger.error("analytics_report: bot init failed", error=str(exc))
        return {"status": "error", "reason": str(exc)}

    logger.info(
        "analytics_report: sent",
        date=str(yesterday),
        admins_sent=sent,
        admins_failed=errors,
    )
    return {"status": "ok", "date": str(yesterday), "sent": sent, "errors": errors}


async def _compute_metrics(
    yesterday: date,
    day_start: datetime,
    day_end: datetime,
) -> dict:
    factory = get_session_factory()

    async with factory() as db:
        # ── User messages ────────────────────────────────────────────────────
        dau_result = await db.execute(
            select(func.count(distinct(RawMessage.user_id))).where(
                RawMessage.role == MessageRole.USER,
                RawMessage.created_at >= day_start,
                RawMessage.created_at < day_end,
                RawMessage.channel == "telegram",
            )
        )
        dau = dau_result.scalar_one()

        user_msgs_result = await db.execute(
            select(func.count(RawMessage.id)).where(
                RawMessage.role == MessageRole.USER,
                RawMessage.created_at >= day_start,
                RawMessage.created_at < day_end,
                RawMessage.channel == "telegram",
            )
        )
        user_msgs = user_msgs_result.scalar_one()

        bot_msgs_result = await db.execute(
            select(func.count(RawMessage.id)).where(
                RawMessage.role == MessageRole.BOT,
                RawMessage.created_at >= day_start,
                RawMessage.created_at < day_end,
            )
        )
        bot_msgs = bot_msgs_result.scalar_one()

        # ── New users ────────────────────────────────────────────────────────
        new_users_result = await db.execute(
            select(func.count(User.id)).where(
                User.created_at >= day_start,
                User.created_at < day_end,
            )
        )
        new_users = new_users_result.scalar_one()

        # ── Triage breakdown (yesterday's records) ───────────────────────────
        triage_result = await db.execute(
            select(
                TriageRecord.final_classification,
                func.count(TriageRecord.id).label("cnt"),
            )
            .where(
                TriageRecord.created_at >= day_start,
                TriageRecord.created_at < day_end,
            )
            .group_by(TriageRecord.final_classification)
        )
        triage_rows = triage_result.fetchall()
        triage = {row.final_classification.value: row.cnt for row in triage_rows}

        # ── Proactive messages sent yesterday ────────────────────────────────
        proactive_sent_result = await db.execute(
            select(func.count(ProactiveEvent.id)).where(
                ProactiveEvent.sent_at >= day_start.replace(tzinfo=None),
                ProactiveEvent.sent_at < day_end.replace(tzinfo=None),
            )
        )
        proactive_sent = proactive_sent_result.scalar_one()

        # Reply rate: proactive recipients who replied within 24h of receiving it
        # Join ProactiveEvent → RawMessage where user sent a message after sent_at
        replied_result = await db.execute(
            select(func.count(distinct(ProactiveEvent.user_id))).where(
                ProactiveEvent.sent_at >= day_start.replace(tzinfo=None),
                ProactiveEvent.sent_at < day_end.replace(tzinfo=None),
                ProactiveEvent.user_id.in_(
                    select(RawMessage.user_id).where(
                        RawMessage.role == MessageRole.USER,
                        RawMessage.created_at >= day_start,
                        RawMessage.created_at < day_end + timedelta(hours=24),
                        RawMessage.channel == "telegram",
                    )
                ),
            )
        )
        proactive_replied = replied_result.scalar_one()

        proactive_recipients_result = await db.execute(
            select(func.count(distinct(ProactiveEvent.user_id))).where(
                ProactiveEvent.sent_at >= day_start.replace(tzinfo=None),
                ProactiveEvent.sent_at < day_end.replace(tzinfo=None),
            )
        )
        proactive_recipients = proactive_recipients_result.scalar_one()

        # ── Subscription tier snapshot ───────────────────────────────────────
        tier_result = await db.execute(
            select(
                User.subscription_tier,
                func.count(User.id).label("cnt"),
            ).group_by(User.subscription_tier)
        )
        tier_rows = tier_result.fetchall()
        tiers = {row.subscription_tier.value: row.cnt for row in tier_rows}

    avg_msgs = round(user_msgs / dau, 1) if dau else 0

    reply_rate = (
        round(proactive_replied / proactive_recipients * 100)
        if proactive_recipients > 0
        else None
    )

    return {
        "dau": dau,
        "new_users": new_users,
        "user_msgs": user_msgs,
        "bot_msgs": bot_msgs,
        "avg_msgs_per_user": avg_msgs,
        "triage": triage,
        "proactive_sent": proactive_sent,
        "proactive_recipients": proactive_recipients,
        "proactive_replied": proactive_replied,
        "proactive_reply_rate": reply_rate,
        "tiers": tiers,
    }


def _format_report(report_date: date, m: dict) -> str:
    date_str = report_date.strftime("%b %d, %Y")

    # Triage
    red = m["triage"].get("red", 0)
    orange = m["triage"].get("orange", 0)
    green = m["triage"].get("green", 0)
    triage_total = red + orange + green

    # Proactive reply rate
    if m["proactive_reply_rate"] is not None:
        reply_str = f"{m['proactive_reply_rate']}% ({m['proactive_replied']}/{m['proactive_recipients']} users replied)"
    elif m["proactive_sent"] == 0:
        reply_str = "no proactives sent"
    else:
        reply_str = "n/a"

    # Subscription tiers
    tier_lines = []
    tier_order = [
        (SubscriptionTier.PRO.value, "Pro"),
        (SubscriptionTier.PLUS.value, "Plus"),
        (SubscriptionTier.OLD_FREE.value, "Free (legacy)"),
        (SubscriptionTier.NEW_FREE.value, "Free"),
    ]
    for key, label in tier_order:
        count = m["tiers"].get(key, 0)
        if count:
            tier_lines.append(f"  {label}: {count}")
    tier_str = "\n".join(tier_lines) or "  (no users)"

    total_users = sum(m["tiers"].values())

    return (
        f"<b>📊 Pawly Daily Report — {date_str}</b>\n"
        f"\n"
        f"<b>👥 Users</b>\n"
        f"  Active today (DAU): <b>{m['dau']}</b>\n"
        f"  New sign-ups: <b>{m['new_users']}</b>\n"
        f"  Total users: <b>{total_users}</b>\n"
        f"\n"
        f"<b>💬 Messages</b>\n"
        f"  User messages: <b>{m['user_msgs']}</b>\n"
        f"  Bot replies: <b>{m['bot_msgs']}</b>\n"
        f"  Avg messages/active user: <b>{m['avg_msgs_per_user']}</b>\n"
        f"\n"
        f"<b>🏥 Triage</b> ({triage_total} events)\n"
        f"  🔴 RED: {red}  🟠 ORANGE: {orange}  🟢 GREEN: {green}\n"
        f"\n"
        f"<b>📣 Proactive Messages</b>\n"
        f"  Sent: <b>{m['proactive_sent']}</b>\n"
        f"  Reply rate: <b>{reply_str}</b>\n"
        f"\n"
        f"<b>💳 Subscriptions</b>\n"
        f"{tier_str}"
    )
