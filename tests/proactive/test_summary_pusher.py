"""
Unit tests for src/proactive/summary_pusher.py.

Covers:
  - push_daily_summary_if_needed short-circuit on follow_up_needed=False
  - push_daily_summary_if_needed short-circuit on already_sent=True
  - _generate_push_message includes unresolved, follow_up_reason in prompt
  - _generate_push_message fallback on LLM exception
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── push_daily_summary_if_needed short-circuit checks ─────────────────────────

@pytest.mark.asyncio
async def test_returns_false_when_no_follow_up_needed():
    from src.proactive.summary_pusher import push_daily_summary_if_needed

    result = await push_daily_summary_if_needed(
        summary_id="sum-001",
        pet_id="pet-001",
        user_id="user-001",
        summary={"follow_up_needed": False, "highlights": []},
    )
    assert result is False


@pytest.mark.asyncio
async def test_returns_false_when_already_sent():
    from src.proactive.summary_pusher import push_daily_summary_if_needed

    with patch(
        "src.proactive.summary_pusher.already_sent",
        AsyncMock(return_value=True),
    ):
        result = await push_daily_summary_if_needed(
            summary_id="sum-001",
            pet_id="pet-001",
            user_id="user-001",
            summary={"follow_up_needed": True},
        )
    assert result is False


# ── _generate_push_message prompt construction ────────────────────────────────

async def _call_generate_push(
    pet_name: str = "Milo",
    species: str = "dog",
    unresolved: list[str] | None = None,
    follow_up_reason: str = "appetite loss persists",
    llm_response: str = "Any updates on Milo?",
) -> tuple[str, list[str]]:
    from src.proactive.summary_pusher import _generate_push_message

    captured: list[str] = []

    async def _fake_extract(system_prompt, messages, **kwargs):
        captured.append(system_prompt)
        return {"text": llm_response}

    mock_client = MagicMock()
    mock_client.extract = _fake_extract

    with patch("src.llm.client.get_gemini_client", return_value=mock_client):
        text = await _generate_push_message(
            pet_name=pet_name,
            species=species,
            unresolved=unresolved or [],
            follow_up_reason=follow_up_reason,
        )
    return text, captured


@pytest.mark.asyncio
async def test_unresolved_questions_in_prompt():
    _, prompts = await _call_generate_push(unresolved=["is vomiting resolved?", "eating normal?"])
    assert "vomiting resolved" in prompts[0] or "eating normal" in prompts[0]


@pytest.mark.asyncio
async def test_follow_up_reason_in_prompt():
    _, prompts = await _call_generate_push(follow_up_reason="appetite loss persists")
    assert "appetite loss persists" in prompts[0]


@pytest.mark.asyncio
async def test_pet_name_in_prompt():
    _, prompts = await _call_generate_push(pet_name="Luna", species="cat")
    assert "Luna" in prompts[0]
    assert "cat" in prompts[0]


@pytest.mark.asyncio
async def test_fallback_on_llm_exception():
    from src.proactive.summary_pusher import _generate_push_message

    mock_client = MagicMock()
    mock_client.extract = AsyncMock(side_effect=RuntimeError("service down"))

    with patch("src.llm.client.get_gemini_client", return_value=mock_client):
        text = await _generate_push_message(
            pet_name="Milo",
            species="dog",
            unresolved=[],
            follow_up_reason="check-in",
        )

    assert "Milo" in text
