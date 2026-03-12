import json
import uuid
from types import SimpleNamespace

import pytest

from src.db.models import Gender, NeuteredStatus, Species
from src.memory.extractor import _strip_fences, extract_memories


def _pet() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="Milo",
        species=Species.CAT,
        breed="Domestic Shorthair",
        age_in_months=24,
        gender=Gender.MALE,
        neutered_status=NeuteredStatus.YES,
        weight_latest=4.2,
    )


def _existing_memory() -> SimpleNamespace:
    return SimpleNamespace(field="current_energy_level", value={"v": "normal"})


def test_strip_fences_removes_markdown_json_wrapping() -> None:
    wrapped = "```json\n[{\"field\":\"current_appetite\"}]\n```"
    assert _strip_fences(wrapped) == '[{"field":"current_appetite"}]'


@pytest.mark.asyncio
async def test_extract_memories_filters_low_confidence_and_bad_items(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [
        {
            "field": "current_appetite",
            "value": "reduced",
            "confidence": 0.8,
            "source_quote": "He has less appetite today.",
            "memory_type": "SNAPSHOT",
            "memory_term": "SHORT",
            "observed_at": "2026-03-11T10:00:00",
        },
        {
            "field": "current_water_intake",
            "value": "normal",
            "confidence": 0.2,
            "source_quote": "Water seems normal.",
            "memory_type": "SNAPSHOT",
            "memory_term": "SHORT",
            "observed_at": None,
        },
        {
            "field": "bad_enum_item",
            "value": "x",
            "confidence": 0.9,
            "source_quote": "Bad enum.",
            "memory_type": "NOT_A_TYPE",
            "memory_term": "SHORT",
            "observed_at": None,
        },
    ]

    class FakeClient:
        async def extract(self, system_prompt: str, messages: list[dict]) -> dict:
            return {"text": f"```json\n{json.dumps(payload)}\n```"}

    monkeypatch.setattr("src.memory.extractor.get_gemini_client", lambda: FakeClient())

    results = await extract_memories(
        raw_messages=[{"role": "user", "content": "He is eating less today"}],
        pet=_pet(),
        existing_memories=[_existing_memory()],
    )

    assert len(results) == 1
    assert results[0].field == "current_appetite"
    assert results[0].confidence == 0.8
