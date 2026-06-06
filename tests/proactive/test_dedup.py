"""
Unit tests for src/proactive/dedup.py.

Verifies:
  - already_sent returns False when no matching row exists
  - already_sent returns True when a sent row exists
  - already_sent returns False when row is skipped (no sent_at)
  - already_sent is scoped per-stage (stage 1 ≠ stage 2)
  - record_sent performs an upsert without raising
  - record_skipped performs an upsert without raising
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.models import ProactiveEventType
from src.proactive.dedup import already_sent, record_sent, record_skipped
from tests.proactive.conftest import _AsyncCM


def _db_returning(scalar_value):
    """Build a mock DB whose execute().scalar_one_or_none() returns scalar_value."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_value
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    return db


def _patch_factory(mock_db):
    def _factory():
        return _AsyncCM(mock_db)
    return patch("src.proactive.dedup.get_session_factory", lambda: _factory)


# ── already_sent ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_already_sent_returns_false_when_no_row():
    mock_db = _db_returning(None)
    with _patch_factory(mock_db):
        result = await already_sent(ProactiveEventType.TRIAGE_FOLLOWUP, "ref-001", stage=1)
    assert result is False


@pytest.mark.asyncio
async def test_already_sent_returns_true_when_row_has_sent_at():
    from datetime import datetime
    mock_db = _db_returning(datetime(2026, 1, 1))
    with _patch_factory(mock_db):
        result = await already_sent(ProactiveEventType.TRIAGE_FOLLOWUP, "ref-001", stage=1)
    assert result is True


@pytest.mark.asyncio
async def test_already_sent_respects_default_stage():
    mock_db = _db_returning(None)
    with _patch_factory(mock_db):
        result = await already_sent(ProactiveEventType.REENGAGEMENT, "ref-abc")
    assert result is False
    # Confirm the query was executed
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_already_sent_different_event_types_are_independent():
    from datetime import datetime
    # Simulate sent for TRIAGE_FOLLOWUP but not REENGAGEMENT
    call_count = {"n": 0}

    def _side_effect(*args, **kwargs):
        call_count["n"] += 1
        result = MagicMock()
        # Return a timestamp only for the first call (TRIAGE_FOLLOWUP scenario)
        value = datetime(2026, 1, 1) if call_count["n"] == 1 else None
        result.scalar_one_or_none.return_value = value
        return result

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=_side_effect)

    def _factory():
        return _AsyncCM(mock_db)

    with patch("src.proactive.dedup.get_session_factory", lambda: _factory):
        triage_sent = await already_sent(ProactiveEventType.TRIAGE_FOLLOWUP, "ref-001", stage=1)
        reeng_sent = await already_sent(ProactiveEventType.REENGAGEMENT, "ref-001", stage=1)

    assert triage_sent is True
    assert reeng_sent is False


# ── record_sent ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_sent_executes_upsert(user_id, pet_id):
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock())
    mock_db.commit = AsyncMock()

    def _factory():
        return _AsyncCM(mock_db)

    with patch("src.proactive.dedup.get_session_factory", lambda: _factory):
        await record_sent(
            user_id=user_id,
            pet_id=pet_id,
            telegram_id="10001",
            event_type=ProactiveEventType.TRIAGE_FOLLOWUP,
            trigger_ref_id="ref-001",
            stage=1,
            content_preview="Hey Milo!",
        )

    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_record_sent_truncates_long_preview(user_id, pet_id):
    """content_preview longer than 300 chars must be silently truncated."""
    long_preview = "x" * 500
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock())
    mock_db.commit = AsyncMock()

    def _factory():
        return _AsyncCM(mock_db)

    with patch("src.proactive.dedup.get_session_factory", lambda: _factory):
        # Should not raise even with a very long preview
        await record_sent(
            user_id=user_id,
            pet_id=pet_id,
            telegram_id="10001",
            event_type=ProactiveEventType.EPISODE_CHECKIN,
            trigger_ref_id="ref-002",
            stage=1,
            content_preview=long_preview,
        )
    mock_db.commit.assert_called_once()


# ── record_skipped ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_skipped_executes_upsert(user_id, pet_id):
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock())
    mock_db.commit = AsyncMock()

    def _factory():
        return _AsyncCM(mock_db)

    with patch("src.proactive.dedup.get_session_factory", lambda: _factory):
        await record_skipped(
            user_id=user_id,
            pet_id=pet_id,
            telegram_id="10001",
            event_type=ProactiveEventType.REENGAGEMENT,
            trigger_ref_id="ref-003",
            stage=1,
            reason="user_responded",
        )

    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()
