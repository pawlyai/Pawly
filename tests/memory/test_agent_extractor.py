"""
Unit tests for src/memory/agent/extractor.py and src/memory/agent/reader.py.
No network or database required.
"""

import json
import uuid
from types import SimpleNamespace

import pytest

from src.db.models import AgentMemoryScope
from src.memory.agent.extractor import (
    ALLOWED_AGENT_FIELDS,
    _strip_fences,
    extract_agent_memories,
)
from src.memory.agent.reader import format_agent_context_for_prompt

# ── Helpers ───────────────────────────────────────────────────────────────────


def _agent_memory(*, field: str, value: object, scope: AgentMemoryScope = AgentMemoryScope.LONG) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        field=field,
        value=value if isinstance(value, dict) else {"v": value},
        scope=scope,
        is_active=True,
        created_at=None,
        updated_at=None,
    )


# ── extractor tests ───────────────────────────────────────────────────────────


def test_strip_fences_removes_markdown_json_wrapping() -> None:
    wrapped = "```json\n[{\"field\":\"response_verbosity\"}]\n```"
    assert _strip_fences(wrapped) == '[{"field":"response_verbosity"}]'


def test_strip_fences_passthrough_plain_json() -> None:
    plain = '[{"field":"technical_level","value":"expert"}]'
    assert _strip_fences(plain) == plain


def test_allowed_agent_fields_scopes() -> None:
    long_fields = [f for f, s in ALLOWED_AGENT_FIELDS.items() if s == AgentMemoryScope.LONG]
    short_fields = [f for f, s in ALLOWED_AGENT_FIELDS.items() if s == AgentMemoryScope.SHORT]
    assert "response_verbosity" in long_fields
    assert "communication_tone" in long_fields
    assert "session_concern_level" in short_fields
    assert "active_followup_topic" in short_fields


@pytest.mark.asyncio
async def test_extract_agent_memories_filters_low_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [
        {
            "field": "response_verbosity",
            "value": "brief",
            "confidence": 0.85,
            "source_quote": "please keep it short",
            "category": "preference",
            "scope": "long",
        },
        {
            "field": "session_concern_level",
            "value": "high",
            "confidence": 0.3,  # below threshold — should be dropped
            "source_quote": "...",
            "category": "relationship",
            "scope": "short",
        },
    ]

    class FakeClient:
        async def extract(self, system_prompt: str, messages: list[dict]) -> dict:
            return {"text": json.dumps(payload)}

    monkeypatch.setattr("src.memory.agent.extractor.get_gemini_client", lambda: FakeClient())

    results = await extract_agent_memories(
        raw_messages=[{"role": "user", "content": "please keep it short"}],
        user_id=str(uuid.uuid4()),
        existing_memories=[],
    )

    assert len(results) == 1
    assert results[0].field == "response_verbosity"
    assert results[0].value == "brief"
    assert results[0].scope == AgentMemoryScope.LONG


@pytest.mark.asyncio
async def test_extract_agent_memories_skips_unknown_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [
        {
            "field": "not_a_real_field",
            "value": "something",
            "confidence": 0.95,
            "source_quote": "...",
            "category": "preference",
            "scope": "long",
        },
    ]

    class FakeClient:
        async def extract(self, system_prompt: str, messages: list[dict]) -> dict:
            return {"text": json.dumps(payload)}

    monkeypatch.setattr("src.memory.agent.extractor.get_gemini_client", lambda: FakeClient())

    results = await extract_agent_memories(
        raw_messages=[{"role": "user", "content": "test message"}],
        user_id=str(uuid.uuid4()),
        existing_memories=[],
    )

    assert results == []


@pytest.mark.asyncio
async def test_extract_agent_memories_handles_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenClient:
        async def extract(self, system_prompt: str, messages: list[dict]) -> dict:
            raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("src.memory.agent.extractor.get_gemini_client", lambda: BrokenClient())

    results = await extract_agent_memories(
        raw_messages=[{"role": "user", "content": "test"}],
        user_id=str(uuid.uuid4()),
        existing_memories=[],
    )

    assert results == []


@pytest.mark.asyncio
async def test_extract_agent_memories_with_existing_memories_injected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing memories are injected into the prompt — verify the call succeeds."""
    existing = [
        _agent_memory(field="response_verbosity", value="detailed"),
    ]
    payload: list = []

    class FakeClient:
        async def extract(self, system_prompt: str, messages: list[dict]) -> dict:
            assert "response_verbosity: detailed" in system_prompt
            return {"text": json.dumps(payload)}

    monkeypatch.setattr("src.memory.agent.extractor.get_gemini_client", lambda: FakeClient())

    results = await extract_agent_memories(
        raw_messages=[{"role": "user", "content": "thanks"}],
        user_id=str(uuid.uuid4()),
        existing_memories=existing,
    )

    assert results == []


# ── reader tests ──────────────────────────────────────────────────────────────


def test_format_agent_context_empty_returns_empty_string() -> None:
    assert format_agent_context_for_prompt({"long_term": [], "short_term": []}) == ""


def test_format_agent_context_priority_fields_appear_first() -> None:
    memories = [
        _agent_memory(field="sensitivity_topics", value=["illness"]),
        _agent_memory(field="response_verbosity", value="brief"),
        _agent_memory(field="communication_tone", value="casual"),
    ]
    output = format_agent_context_for_prompt({"long_term": memories, "short_term": []})

    assert output.startswith("User interaction preferences:")
    lines = output.splitlines()
    # response_verbosity and communication_tone are priority fields — they must
    # appear before sensitivity_topics
    verbosity_idx = next(i for i, line in enumerate(lines) if "response_verbosity" in line)
    sensitivity_idx = next(i for i, line in enumerate(lines) if "sensitivity_topics" in line)
    assert verbosity_idx < sensitivity_idx


def test_format_agent_context_includes_short_term_fields() -> None:
    memories_long = [_agent_memory(field="technical_level", value="expert", scope=AgentMemoryScope.LONG)]
    memories_short = [_agent_memory(field="session_concern_level", value="high", scope=AgentMemoryScope.SHORT)]
    output = format_agent_context_for_prompt({"long_term": memories_long, "short_term": memories_short})

    assert "technical_level" in output
    assert "session_concern_level" in output
