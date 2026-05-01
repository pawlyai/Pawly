"""
Support / feedback handler.

Flow:
  1. /support  → show category keyboard
  2. User picks category → "Please describe your issue" + sets session flag
  3. Next free-text message (intercepted in message.py) → email sent → confirm

Commands:
  /support   — start a support request
"""

from datetime import datetime, timezone
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.db.models import Pet, User
from src.utils.logger import get_logger
from src.utils.mailer import send_support_email

router = Router(name="support")
logger = get_logger(__name__)

_CATEGORIES = {
    "support:bug": "🐛 Bug Report",
    "support:feature": "💡 Feature Request",
    "support:question": "❓ General Question",
    "support:other": "📋 Other",
}


def _category_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🐛 Bug Report", callback_data="support:bug"),
                InlineKeyboardButton(text="💡 Feature Request", callback_data="support:feature"),
            ],
            [
                InlineKeyboardButton(text="❓ General Question", callback_data="support:question"),
                InlineKeyboardButton(text="📋 Other", callback_data="support:other"),
            ],
        ]
    )


@router.message(Command("support"))
async def cmd_support(
    message: Message,
    user: User,
    **_: object,
) -> None:
    await message.answer(
        "Hi! How can we help? Please choose a category:",
        reply_markup=_category_keyboard(),
    )


@router.callback_query(F.data.startswith("support:"))
async def support_category_chosen(
    callback: CallbackQuery,
    user: User,
    session: dict[str, Any],
    **_: object,
) -> None:
    category = _CATEGORIES.get(callback.data, "📋 Other")
    session["awaiting_support_message"] = True
    session["support_category"] = category

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"*{category}* — please describe your issue in detail.\n\n"
        "Our team will get back to you within *12 hours* 🕐",
        parse_mode="Markdown",
    )
    await callback.answer()
    logger.info("support category chosen", telegram_id=user.telegram_id, category=category)


async def handle_support_submission(
    message: Message,
    user: User,
    active_pet: Pet | None,
    category: str,
) -> None:
    """Called from message.py when awaiting_support_message is set."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pet_info = "No pet profile"
    if active_pet:
        age = f"{active_pet.age_in_months}mo" if active_pet.age_in_months else "unknown age"
        pet_info = f"{active_pet.name} ({active_pet.species.value}, {age})"

    username = f"@{user.telegram_username}" if user.telegram_username else user.display_name or "—"

    # Build a clickable reply link — prefer t.me/username, fall back to tg://user?id=
    if user.telegram_username:
        reply_link = f"https://t.me/{user.telegram_username}"
    else:
        reply_link = f"tg://user?id={user.telegram_id}"

    subject = f"[Pawly Support] {category} from {username}"
    body = (
        f"Category:   {category}\n"
        f"From:       {username}\n"
        f"Telegram:   {reply_link}\n"
        f"User ID:    {user.telegram_id}\n"
        f"Pet:        {pet_info}\n"
        f"Time:       {now}\n"
        f"\n{'—' * 40}\n"
        f"{message.text}\n"
        f"{'—' * 40}\n"
        f"\nTo reply: click the Telegram link above and message the user directly.\n"
    )

    sent = await send_support_email(subject, body)

    if sent:
        confirm = (
            "✅ Your message has been sent to our support team.\n"
            "We'll get back to you within *12 hours*. Thank you! 🙏"
        )
    else:
        # Email not configured or failed — still reassure the user
        confirm = (
            "✅ Your message has been received.\n"
            "We'll get back to you within *12 hours*. Thank you! 🙏"
        )

    await message.answer(confirm, parse_mode="Markdown")
    logger.info(
        "support submission handled",
        telegram_id=user.telegram_id,
        category=category,
        email_sent=sent,
    )
