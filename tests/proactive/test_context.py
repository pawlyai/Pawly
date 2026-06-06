"""
Unit tests for src/proactive/context.py.

Covers:
  - locale_to_language_instruction (pure function)
  - _format_age / _fmt_memory_value (private helpers)
  - build_pet_context_snippet (mocked DB)
  - get_last_conversation_topic (mocked DB)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.proactive.context import (
    _fmt_memory_value,
    _format_age,
    build_pet_context_snippet,
    get_last_conversation_topic,
    locale_to_language_instruction,
)
from tests.proactive.conftest import _AsyncCM, _empty_execute_result


# ── locale_to_language_instruction ───────────────────────────────────────────

def test_locale_english_returns_empty():
    assert locale_to_language_instruction("en") == ""

def test_locale_english_region_returns_empty():
    assert locale_to_language_instruction("en-SG") == ""

def test_locale_empty_returns_empty():
    assert locale_to_language_instruction("") == ""

def test_locale_chinese_simplified():
    assert locale_to_language_instruction("zh") == "Respond in Chinese (Simplified)."

def test_locale_zh_hans():
    assert locale_to_language_instruction("zh-hans") == "Respond in Chinese (Simplified)."

def test_locale_zh_hant():
    assert locale_to_language_instruction("zh-hant") == "Respond in Chinese (Traditional)."

def test_locale_malay():
    assert locale_to_language_instruction("ms") == "Respond in Malay."

def test_locale_tamil():
    assert locale_to_language_instruction("ta") == "Respond in Tamil."

def test_locale_unknown_returns_empty():
    assert locale_to_language_instruction("xx") == ""

def test_locale_case_insensitive():
    assert locale_to_language_instruction("ZH") == "Respond in Chinese (Simplified)."


# ── _format_age ───────────────────────────────────────────────────────────────

def test_format_age_none_returns_empty():
    assert _format_age(None) == ""

def test_format_age_zero_returns_empty():
    assert _format_age(0) == ""

def test_format_age_months_only():
    assert _format_age(6) == "6mo "

def test_format_age_one_year():
    assert _format_age(12) == "1y "

def test_format_age_years_only():
    assert _format_age(24) == "2y "

def test_format_age_years_and_months():
    assert _format_age(14) == "1y2m "


# ── _fmt_memory_value ─────────────────────────────────────────────────────────

def test_fmt_dict_with_value_key():
    assert _fmt_memory_value({"value": "IBD"}) == "IBD"

def test_fmt_dict_with_raw_key():
    assert _fmt_memory_value({"raw": "Metronidazole"}) == "Metronidazole"

def test_fmt_dict_fallback_to_items():
    result = _fmt_memory_value({"condition": "diabetes"})
    assert "condition:diabetes" in result

def test_fmt_list():
    assert _fmt_memory_value(["allergy", "IBD"]) == "allergy/IBD"

def test_fmt_string():
    assert _fmt_memory_value("normal") == "normal"


# ── build_pet_context_snippet ─────────────────────────────────────────────────

def _make_factory_no_data():
    """Session factory: all queries return empty results."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_empty_execute_result())

    def _factory():
        return _AsyncCM(db)

    return lambda: _factory, db


def _make_factory_with_chronic(chronic_value: str = "IBD"):
    """Session factory: first execute returns one chronic memory; rest are empty."""
    from src.db.models import MemorySource, MemoryTerm, MemoryType, PetMemory

    mem = PetMemory(
        id=uuid.uuid4(),
        pet_id=uuid.uuid4(),
        memory_type=MemoryType.CHRONIC,
        memory_term=MemoryTerm.LONG,
        field="chronic_conditions",
        value={"value": chronic_value},
        confidence_score=0.95,
        source=MemorySource.AI_EXTRACTED,
        is_active=True,
    )

    call_count = {"n": 0}

    def _make_result():
        call_count["n"] += 1
        result = MagicMock()
        if call_count["n"] == 1:
            # First execute: chronic memories query
            result.scalars.return_value.all.return_value = [mem]
        else:
            result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        return result

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=lambda *a, **kw: _make_result())

    def _factory():
        return _AsyncCM(db)

    return lambda: _factory, db


@pytest.mark.asyncio
async def test_build_snippet_contains_pet_name(mock_pet, pet_id):
    factory_fn, _ = _make_factory_no_data()
    with patch("src.proactive.context.get_session_factory", factory_fn):
        result = await build_pet_context_snippet(mock_pet, pet_id)
    assert "Milo" in result


@pytest.mark.asyncio
async def test_build_snippet_contains_species(mock_pet, pet_id):
    factory_fn, _ = _make_factory_no_data()
    with patch("src.proactive.context.get_session_factory", factory_fn):
        result = await build_pet_context_snippet(mock_pet, pet_id)
    assert "dog" in result.lower()


@pytest.mark.asyncio
async def test_build_snippet_contains_breed(mock_pet, pet_id):
    factory_fn, _ = _make_factory_no_data()
    with patch("src.proactive.context.get_session_factory", factory_fn):
        result = await build_pet_context_snippet(mock_pet, pet_id)
    assert "Poodle" in result


@pytest.mark.asyncio
async def test_build_snippet_contains_age(mock_pet, pet_id):
    factory_fn, _ = _make_factory_no_data()
    with patch("src.proactive.context.get_session_factory", factory_fn):
        result = await build_pet_context_snippet(mock_pet, pet_id)
    assert "3y" in result  # 36 months = 3y


@pytest.mark.asyncio
async def test_build_snippet_with_chronic_condition(mock_pet, pet_id):
    factory_fn, _ = _make_factory_with_chronic("IBD")
    with patch("src.proactive.context.get_session_factory", factory_fn):
        result = await build_pet_context_snippet(mock_pet, pet_id)
    assert "Known:" in result
    assert "IBD" in result


# ── get_last_conversation_topic ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_last_topic_no_summary():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_empty_execute_result())

    def _factory():
        return _AsyncCM(db)

    with patch("src.proactive.context.get_session_factory", lambda: _factory):
        result = await get_last_conversation_topic("any-pet-id")
    assert result == ""


@pytest.mark.asyncio
async def test_get_last_topic_with_highlights():
    from src.db.models import DailySummary

    summary = MagicMock(spec=DailySummary)
    summary.summary = {"highlights": ["vomiting episode", "vet visit scheduled"]}

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = summary

    db = AsyncMock()
    db.execute = AsyncMock(return_value=scalar_result)

    def _factory():
        return _AsyncCM(db)

    with patch("src.proactive.context.get_session_factory", lambda: _factory):
        result = await get_last_conversation_topic("any-pet-id")
    assert result == "vomiting episode"


@pytest.mark.asyncio
async def test_get_last_topic_with_core_issues_fallback():
    from src.db.models import DailySummary

    summary = MagicMock(spec=DailySummary)
    summary.summary = {"core_issues": ["appetite loss"]}

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = summary

    db = AsyncMock()
    db.execute = AsyncMock(return_value=scalar_result)

    def _factory():
        return _AsyncCM(db)

    with patch("src.proactive.context.get_session_factory", lambda: _factory):
        result = await get_last_conversation_topic("any-pet-id")
    assert result == "appetite loss"
