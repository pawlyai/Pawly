"""
Unit tests for src/jobs/episode_checkin.py — _generate_episode_checkin().

Covers:
  - intervention_str built from dict / list / None
  - Symptom and days appear in prompt
  - LLM fallback on exception / empty response
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def _call_generate(
    pet_name: str = "Milo",
    pet_species: str = "dog",
    symptom_type: str = "vomiting",
    severity: str = "moderate",
    days_ongoing: int = 5,
    interventions=None,
    llm_response: str = "How is Milo doing with the vomiting?",
) -> tuple[str, list[str]]:
    from src.jobs.episode_checkin import _generate_episode_checkin

    captured: list[str] = []

    async def _fake_extract(system_prompt, messages, **kwargs):
        captured.append(messages[0]["content"] if messages else system_prompt)
        return {"text": llm_response}

    mock_client = MagicMock()
    mock_client.extract = _fake_extract

    with patch("src.llm.client.get_gemini_client", return_value=mock_client):
        text = await _generate_episode_checkin(
            pet_name=pet_name,
            pet_species=pet_species,
            symptom_type=symptom_type,
            severity=severity,
            days_ongoing=days_ongoing,
            interventions=interventions,
        )
    return text, captured


# ── Intervention string ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_interventions_produces_no_intervention_str():
    _, prompts = await _call_generate(interventions=None)
    assert "Interventions tried" not in prompts[0]


@pytest.mark.asyncio
async def test_dict_interventions_appear_in_prompt():
    _, prompts = await _call_generate(interventions={"food": "bland diet", "meds": "probiotic"})
    assert "Interventions tried" in prompts[0]
    assert "bland diet" in prompts[0] or "probiotic" in prompts[0]


@pytest.mark.asyncio
async def test_list_interventions_appear_in_prompt():
    _, prompts = await _call_generate(interventions=["fasting", "rice diet"])
    assert "Interventions tried" in prompts[0]
    assert "fasting" in prompts[0] or "rice diet" in prompts[0]


@pytest.mark.asyncio
async def test_empty_dict_interventions_no_str():
    _, prompts = await _call_generate(interventions={})
    assert "Interventions tried" not in prompts[0]


# ── Symptom and duration ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_symptom_type_in_prompt():
    _, prompts = await _call_generate(symptom_type="diarrhea")
    assert "diarrhea" in prompts[0]


@pytest.mark.asyncio
async def test_days_ongoing_in_prompt():
    _, prompts = await _call_generate(days_ongoing=7)
    assert "7" in prompts[0]


@pytest.mark.asyncio
async def test_pet_name_and_species_in_prompt():
    _, prompts = await _call_generate(pet_name="Luna", pet_species="cat")
    assert "Luna" in prompts[0]
    assert "cat" in prompts[0]


# ── LLM fallback ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fallback_on_llm_exception():
    from src.jobs.episode_checkin import _generate_episode_checkin

    mock_client = MagicMock()
    mock_client.extract = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    with patch("src.llm.client.get_gemini_client", return_value=mock_client):
        text = await _generate_episode_checkin(
            pet_name="Milo",
            pet_species="dog",
            symptom_type="vomiting",
            severity="moderate",
            days_ongoing=4,
            interventions=None,
        )

    assert "Milo" in text
    assert "vomiting" in text


@pytest.mark.asyncio
async def test_fallback_mentions_days_ongoing():
    from src.jobs.episode_checkin import _generate_episode_checkin

    mock_client = MagicMock()
    mock_client.extract = AsyncMock(side_effect=ValueError("empty"))

    with patch("src.llm.client.get_gemini_client", return_value=mock_client):
        text = await _generate_episode_checkin(
            pet_name="Buddy",
            pet_species="dog",
            symptom_type="diarrhea",
            severity="mild",
            days_ongoing=3,
            interventions=None,
        )

    assert "3" in text
