"""
Unit tests for src/jobs/followup.py — _generate_message().

Covers:
  - RED: no emoji at ALL stages
  - ORANGE stage 1: emoji allowed
  - Stage 2: "has not responded" note in prompt
  - Stage 3: "third check-in" escalation + no-hedging note
  - Symptom tags in prompt
  - Fallback message on LLM exception / empty response
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def _call_generate(
    triage_level: str,
    stage: int,
    pet_name: str = "Milo",
    pet_species: str = "dog",
    symptom_tags: list[str] | None = None,
    llm_response: str = "How is Milo doing?",
) -> tuple[str, list[str]]:
    """Call _generate_message and return (text, captured_prompts)."""
    from src.jobs.followup import _generate_message

    captured: list[str] = []

    async def _fake_chat(system_prompt, messages, **kwargs):
        captured.append(messages[0]["content"])
        return {"text": llm_response}

    mock_client = MagicMock()
    mock_client.chat = _fake_chat

    with (
        patch("src.llm.providers.get_chat_client", return_value=mock_client),
        patch("src.llm.orchestrator._active_chat_model", return_value="test-model"),
    ):
        text = await _generate_message(
            pet_name=pet_name,
            pet_species=pet_species,
            triage_level=triage_level,
            symptom_tags=["vomiting"] if symptom_tags is None else symptom_tags,
            stage=stage,
        )
    return text, captured


# ── Emoji logic ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_red_stage1_prompt_says_no_emoji():
    _, prompts = await _call_generate("RED", stage=1)
    assert prompts, "LLM was not called"
    assert "No emoji" in prompts[0]


@pytest.mark.asyncio
async def test_red_stage2_prompt_says_no_emoji():
    _, prompts = await _call_generate("RED", stage=2)
    assert "No emoji" in prompts[0]


@pytest.mark.asyncio
async def test_red_stage3_prompt_says_no_emoji():
    _, prompts = await _call_generate("RED", stage=3)
    assert "No emoji" in prompts[0]


@pytest.mark.asyncio
async def test_orange_stage1_prompt_allows_emoji():
    _, prompts = await _call_generate("ORANGE", stage=1)
    assert "One emoji is fine" in prompts[0]


# ── Stage escalation notes ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stage1_no_escalation_note():
    _, prompts = await _call_generate("RED", stage=1)
    prompt = prompts[0]
    assert "third check-in" not in prompt
    assert "has not responded" not in prompt.lower()


@pytest.mark.asyncio
async def test_stage2_has_not_responded_note():
    _, prompts = await _call_generate("RED", stage=2)
    assert "has not responded" in prompts[0].lower()


@pytest.mark.asyncio
async def test_stage3_third_checkin_note():
    _, prompts = await _call_generate("RED", stage=3)
    assert "third" in prompts[0].lower() and "check-in" in prompts[0].lower()


@pytest.mark.asyncio
async def test_stage3_no_hedging_instruction():
    _, prompts = await _call_generate("RED", stage=3)
    assert "if you get a chance" in prompts[0].lower() or "hedging" in prompts[0].lower()


# ── Symptom tags ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_symptom_tags_appear_in_prompt():
    _, prompts = await _call_generate("RED", stage=1, symptom_tags=["seizure", "collapse"])
    prompt = prompts[0]
    assert "seizure" in prompt or "collapse" in prompt


@pytest.mark.asyncio
async def test_empty_symptom_tags_fallback():
    _, prompts = await _call_generate("ORANGE", stage=1, symptom_tags=[])
    assert "health concerns" in prompts[0]


# ── LLM error fallback ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fallback_message_on_llm_exception():
    from src.jobs.followup import _generate_message

    mock_client = MagicMock()
    mock_client.chat = AsyncMock(side_effect=RuntimeError("LLM down"))

    with (
        patch("src.llm.providers.get_chat_client", return_value=mock_client),
        patch("src.llm.orchestrator._active_chat_model", return_value="test-model"),
    ):
        text = await _generate_message(
            pet_name="Milo",
            pet_species="dog",
            triage_level="RED",
            symptom_tags=["vomiting"],
            stage=1,
        )

    assert "Milo" in text


@pytest.mark.asyncio
async def test_fallback_on_empty_llm_response():
    from src.jobs.followup import _generate_message

    mock_client = MagicMock()
    mock_client.chat = AsyncMock(return_value={"text": ""})

    with (
        patch("src.llm.providers.get_chat_client", return_value=mock_client),
        patch("src.llm.orchestrator._active_chat_model", return_value="test-model"),
    ):
        text = await _generate_message(
            pet_name="Luna",
            pet_species="cat",
            triage_level="ORANGE",
            symptom_tags=["diarrhea"],
            stage=1,
        )

    assert "Luna" in text
