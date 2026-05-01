"""
Unit tests for the reminder system.

Tests cover:
  - _extract_reminder(): regex parsing and text cleanup
  - pending_reminder session yes/no detection
  - save/deliver reminder logic (mocked DB)
  - edge cases: past dates, malformed markers, no marker
"""

import os
import types
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-bot-token")
os.environ.setdefault("GOOGLE_API_KEY", "")


from src.bot.handlers.message import (
    _AFFIRMATIVE,
    _NEGATIVE,
    _REMINDER_RE,
    _extract_reminder,
)


# ── _extract_reminder ─────────────────────────────────────────────────────────


class TestExtractReminder:
    def test_extracts_date_and_content(self):
        text = "Give Max his annual vaccine.\n[SET_REMINDER: Annual vaccine for Max | 2026-08-15]"
        clean, data = _extract_reminder(text)
        assert data is not None
        assert data["content"] == "Annual vaccine for Max"
        remind_at = datetime.fromisoformat(data["remind_at"])
        assert remind_at.year == 2026
        assert remind_at.month == 8
        assert remind_at.day == 15
        assert remind_at.tzinfo == timezone.utc

    def test_strips_marker_from_response(self):
        text = "Book a vet appointment soon.\n[SET_REMINDER: Vet checkup | 2026-06-01]"
        clean, data = _extract_reminder(text)
        assert "[SET_REMINDER" not in clean
        assert "Book a vet appointment soon." in clean

    def test_no_marker_returns_original(self):
        text = "Looks like Max is doing great! No concerns today."
        clean, data = _extract_reminder(text)
        assert data is None
        assert clean == text

    def test_case_insensitive(self):
        text = "Reminder time!\n[set_reminder: Flea treatment | 2026-07-10]"
        clean, data = _extract_reminder(text)
        assert data is not None
        assert data["content"] == "Flea treatment"

    def test_extra_whitespace_around_fields(self):
        text = "[SET_REMINDER:  Deworming treatment  |  2026-09-20  ]"
        clean, data = _extract_reminder(text)
        assert data is not None
        assert data["content"] == "Deworming treatment"
        remind_at = datetime.fromisoformat(data["remind_at"])
        assert remind_at.month == 9

    def test_defaults_to_9am_utc(self):
        text = "[SET_REMINDER: Grooming appointment | 2026-10-05]"
        clean, data = _extract_reminder(text)
        assert data is not None
        remind_at = datetime.fromisoformat(data["remind_at"])
        assert remind_at.hour == 9
        assert remind_at.minute == 0

    def test_malformed_date_returns_none(self):
        text = "[SET_REMINDER: Something | not-a-date]"
        clean, data = _extract_reminder(text)
        assert data is None

    def test_marker_only_response(self):
        text = "[SET_REMINDER: Vaccine booster | 2026-11-01]"
        clean, data = _extract_reminder(text)
        assert data is not None
        assert clean.strip() == ""

    def test_multiline_response_strips_only_marker(self):
        text = (
            "Your dog needs a vaccine booster in 3 months.\n"
            "Make sure to call your vet to schedule.\n"
            "[SET_REMINDER: Vaccine booster | 2026-08-01]"
        )
        clean, data = _extract_reminder(text)
        assert data is not None
        assert "Your dog needs a vaccine booster" in clean
        assert "Make sure to call" in clean
        assert "[SET_REMINDER" not in clean


# ── Affirmative / negative word sets ─────────────────────────────────────────


class TestConfirmationWords:
    @pytest.mark.parametrize("word", ["yes", "y", "yeah", "yep", "ok", "okay", "sure", "confirm", "yup"])
    def test_affirmative_words(self, word):
        assert word in _AFFIRMATIVE

    @pytest.mark.parametrize("word", ["no", "n", "nope", "nah", "skip", "cancel"])
    def test_negative_words(self, word):
        assert word in _NEGATIVE

    def test_sets_are_disjoint(self):
        assert _AFFIRMATIVE.isdisjoint(_NEGATIVE)


# ── _extract_reminder: real conversation examples ────────────────────────────


class TestRealConversationExamples:
    def test_vaccine_scenario(self):
        """LLM suggests vaccine reminder after discussing vaccination schedule."""
        llm_response = (
            "Luna is due for her annual FVRCP booster. I'd recommend booking "
            "an appointment with your vet in the next few weeks.\n"
            "[SET_REMINDER: FVRCP booster for Luna | 2026-06-15]"
        )
        clean, data = _extract_reminder(llm_response)
        assert data is not None
        assert "Luna" in data["content"]
        assert "FVRCP" in data["content"]
        assert "[SET_REMINDER" not in clean

    def test_medication_scenario(self):
        """LLM suggests medication reminder."""
        llm_response = (
            "Max needs his monthly flea and tick prevention. "
            "Set a monthly reminder so you don't forget!\n"
            "[SET_REMINDER: Flea and tick prevention for Max | 2026-06-01]"
        )
        clean, data = _extract_reminder(llm_response)
        assert data is not None
        assert "Max" in data["content"]

    def test_no_reminder_for_general_advice(self):
        """LLM should not emit marker for general questions — test that no spurious marker."""
        llm_response = (
            "That sounds normal for a cat of Luna's age. "
            "Senior cats often sleep more and have lower energy. "
            "Keep monitoring and let me know if anything changes."
        )
        clean, data = _extract_reminder(llm_response)
        assert data is None
        assert clean == llm_response


# ── save_reminder (mocked DB) ─────────────────────────────────────────────────


class TestSaveReminder:
    @pytest.mark.asyncio
    async def test_save_reminder_stores_correctly(self):
        from src.bot.handlers.reminder import save_reminder

        user = types.SimpleNamespace(
            id=uuid.uuid4(),
            telegram_id="123456789",
        )
        pet = types.SimpleNamespace(id=uuid.uuid4())
        remind_at = datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc)

        mock_reminder = MagicMock()
        mock_reminder.content = "Annual vaccine for Max"
        mock_reminder.remind_at = remind_at

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_db)

        with patch("src.bot.handlers.reminder.get_session_factory", return_value=mock_factory):
            with patch("src.db.models.Reminder") as MockReminder:
                MockReminder.return_value = mock_reminder
                result = await save_reminder(user, pet, "Annual vaccine for Max", remind_at)
                mock_db.add.assert_called_once()
                mock_db.commit.assert_awaited_once()


# ── run_reminder_check (mocked) ───────────────────────────────────────────────


class TestReminderDeliveryJob:
    @pytest.mark.asyncio
    async def test_no_reminders_returns_zero(self):
        from src.jobs.reminder import run_reminder_check

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_db)

        with patch("src.jobs.reminder.get_session_factory", return_value=mock_factory):
            result = await run_reminder_check({})

        assert result == {"sent": 0}

    @pytest.mark.asyncio
    async def test_sends_due_reminder(self):
        from src.jobs.reminder import run_reminder_check

        fake_reminder = MagicMock()
        fake_reminder.id = uuid.uuid4()
        fake_reminder.telegram_id = "123456789"
        fake_reminder.content = "Vet appointment for Luna"
        fake_reminder.is_sent = False

        # First DB call: select due reminders
        mock_db_select = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [fake_reminder]
        mock_db_select.execute = AsyncMock(return_value=mock_result)
        mock_db_select.__aenter__ = AsyncMock(return_value=mock_db_select)
        mock_db_select.__aexit__ = AsyncMock(return_value=False)

        # Second DB call: update + commit
        mock_db_update = AsyncMock()
        mock_db_update.add = MagicMock()
        mock_db_update.commit = AsyncMock()
        mock_db_update.__aenter__ = AsyncMock(return_value=mock_db_update)
        mock_db_update.__aexit__ = AsyncMock(return_value=False)

        # get_session_factory() returns a factory callable; factory() returns the CM
        factory_calls = [0]

        def factory_fn():
            factory_calls[0] += 1
            return mock_db_select if factory_calls[0] == 1 else mock_db_update

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()
        mock_bot.session = AsyncMock()
        mock_bot.session.close = AsyncMock()

        with patch("src.jobs.reminder.get_session_factory", return_value=factory_fn):
            with patch("aiogram.Bot", return_value=mock_bot):
                result = await run_reminder_check({})

        mock_bot.send_message.assert_awaited_once_with(
            chat_id="123456789",
            text="🔔 Reminder: Vet appointment for Luna",
            parse_mode=None,
        )
        assert result["sent"] == 1
        assert result["errors"] == 0
        assert fake_reminder.is_sent is True
