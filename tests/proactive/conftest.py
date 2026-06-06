"""
Shared fixtures for proactive module unit tests.

All tests in this directory run without a real database or LLM API — external
calls are replaced by lightweight mocks so the suite stays fast and offline.
"""

import os
import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-bot-token")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-key")


# ── Async context-manager helper ──────────────────────────────────────────────

class _AsyncCM:
    """Minimal async context manager that yields a fixed value."""
    def __init__(self, value: Any) -> None:
        self._value = value

    async def __aenter__(self) -> Any:
        return self._value

    async def __aexit__(self, *_: Any) -> None:
        pass


def make_session_factory(mock_db: Any):
    """Return a callable that behaves like get_session_factory()()."""
    def _factory():
        return _AsyncCM(mock_db)
    return lambda: _factory


def _empty_execute_result() -> MagicMock:
    """SQLAlchemy execute result that returns empty lists / None."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    result.scalar_one_or_none.return_value = None
    result.scalar_one.return_value = 0
    result.fetchall.return_value = []
    return result


# ── Pet / User / Memory fixtures ─────────────────────────────────────────────

@pytest.fixture
def pet_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def user_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def mock_pet(pet_id: str) -> SimpleNamespace:
    from src.db.models import Gender, NeuteredStatus, Species
    return SimpleNamespace(
        id=uuid.UUID(pet_id),
        name="Milo",
        species=Species.DOG,
        breed="Poodle",
        gender=Gender.MALE,
        neutered_status=NeuteredStatus.YES,
        age_in_months=36,
        weight_latest=5.5,
    )


@pytest.fixture
def mock_user(user_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID(user_id),
        telegram_id="10001",
        display_name="Test Owner",
        locale="en",
        timezone=None,
        country="SG",
    )


@pytest.fixture
def mock_db() -> AsyncMock:
    """AsyncMock DB session with sensible empty defaults."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_empty_execute_result())
    db.get = AsyncMock(return_value=None)
    db.commit = AsyncMock()
    return db


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """LLM client mock that returns a fixed proactive message."""
    client = MagicMock()
    client.chat = AsyncMock(return_value={"text": "Hey, just checking in — how is Milo doing? 🐾"})
    return client
