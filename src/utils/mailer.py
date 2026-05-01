"""
Async email helper for support submissions.

Uses smtplib (stdlib) via asyncio.to_thread — no extra dependencies.
Set SMTP_HOST to enable; leave empty to log-only mode (graceful degradation).
"""

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def send_support_email(subject: str, body: str) -> bool:
    """Send email to support_email. Returns True on success, False on failure/not-configured."""
    if not settings.smtp_host or not settings.smtp_user:
        logger.warning("SMTP not configured — logging support message only", subject=subject)
        logger.info("support_message_body", body=body)
        return False
    try:
        await asyncio.to_thread(_send_sync, subject, body)
        logger.info("support email sent", subject=subject, to=settings.support_email)
        return True
    except Exception as exc:
        logger.error("support email failed", error=str(exc), subject=subject)
        return False


def _send_sync(subject: str, body: str) -> None:
    sender = settings.smtp_from or settings.smtp_user
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = settings.support_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # Port 465 uses implicit SSL; port 587 uses STARTTLS
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as server:
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
