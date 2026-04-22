"""
Unit tests for Langfuse tracing instrumentation.

A) Correct metadata is passed to Langfuse when _generate_response_classic runs.
B) A Langfuse timeout / exception does NOT propagate to the caller.

No network, no DB, no real Gemini calls.
"""

import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set env vars before any src imports so Settings initialises cleanly
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("GOOGLE_API_KEY", "test-key")
os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "lf-pk-test")
os.environ.setdefault("LANGFUSE_SECRET_KEY", "lf-sk-test")
os.environ.setdefault("LANGFUSE_HOST", "http://localhost:3000")

# Pre-import modules so patch() can resolve dotted attribute paths
import src.llm.orchestrator  # noqa: F401
import src.llm.client  # noqa: F401
import src.observability.tracing  # noqa: F401

from src.db.models import (
    Gender,
    MessageType,
    NeuteredStatus,
    Pet,
    Species,
    SubscriptionTier,
    TriageLevel,
    User,
)


# ── Shared fixtures ───────────────────────────────────────────────────────────

def _make_user() -> User:
    return User(
        id=uuid.uuid4(),
        telegram_id="test-tg-123",
        display_name="Test User",
        subscription_tier=SubscriptionTier.NEW_FREE,
    )


def _make_pet(user_id: uuid.UUID) -> Pet:
    return Pet(
        id=uuid.uuid4(),
        user_id=user_id,
        name="Buddy",
        species=Species.DOG,
        age_in_months=24,
        gender=Gender.MALE,
        neutered_status=NeuteredStatus.UNKNOWN,
    )


def _raw_llm_response(text: str = "Buddy looks healthy!") -> dict:
    return {"text": text, "input_tokens": 100, "output_tokens": 50}


# ── Test A: Langfuse receives correct metadata ────────────────────────────────

class TestLangfuseMetadataCaptured:
    """Assert that update_span is called with the right fields."""

    @pytest.mark.asyncio
    async def test_user_id_and_dialogue_id_sent_to_langfuse(self):
        user = _make_user()
        pet = _make_pet(user.id)
        dialogue_id = str(uuid.uuid4())

        trace_calls: list[dict] = []

        with (
            patch("src.llm.orchestrator.load_pet_context", new_callable=AsyncMock, return_value={}),
            patch("src.llm.orchestrator.load_related_memories", new_callable=AsyncMock, return_value=[]),
            patch("src.llm.orchestrator._store_triage_record", new_callable=AsyncMock),
            patch("src.llm.orchestrator.get_gemini_client") as mock_client_factory,
            patch("src.llm.orchestrator.update_span"),
            patch("src.llm.orchestrator.update_trace", side_effect=lambda **kw: trace_calls.append(kw)),
        ):
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=_raw_llm_response())
            mock_client_factory.return_value = mock_client

            from src.llm.orchestrator import _generate_response_classic
            await _generate_response_classic(
                user=user,
                pet=pet,
                dialogue_id=dialogue_id,
                user_message="Is my dog okay?",
            )

        assert len(trace_calls) >= 1
        first_call = trace_calls[0]
        assert first_call["user_id"] == str(user.id)
        assert first_call["session_id"] == dialogue_id

    @pytest.mark.asyncio
    async def test_pet_metadata_captured_in_span(self):
        user = _make_user()
        pet = _make_pet(user.id)

        trace_calls: list[dict] = []

        with (
            patch("src.llm.orchestrator.load_pet_context", new_callable=AsyncMock, return_value={}),
            patch("src.llm.orchestrator.load_related_memories", new_callable=AsyncMock, return_value=[]),
            patch("src.llm.orchestrator._store_triage_record", new_callable=AsyncMock),
            patch("src.llm.orchestrator.get_gemini_client") as mock_client_factory,
            patch("src.llm.orchestrator.update_span"),
            patch("src.llm.orchestrator.update_trace", side_effect=lambda **kw: trace_calls.append(kw)),
        ):
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=_raw_llm_response())
            mock_client_factory.return_value = mock_client

            from src.llm.orchestrator import _generate_response_classic
            await _generate_response_classic(
                user=user, pet=pet, dialogue_id="diag-1", user_message="routine question"
            )

        meta_call = next(c for c in trace_calls if "metadata" in c)
        assert meta_call["metadata"]["pet_id"] == str(pet.id)
        assert meta_call["metadata"]["pet_name"] == pet.name

    @pytest.mark.asyncio
    async def test_triage_outcome_captured_in_closing_span(self):
        user = _make_user()
        pet = _make_pet(user.id)

        span_calls: list[dict] = []

        with (
            patch("src.llm.orchestrator.load_pet_context", new_callable=AsyncMock, return_value={}),
            patch("src.llm.orchestrator.load_related_memories", new_callable=AsyncMock, return_value=[]),
            patch("src.llm.orchestrator._store_triage_record", new_callable=AsyncMock),
            patch("src.llm.orchestrator.get_gemini_client") as mock_client_factory,
            patch("src.llm.orchestrator.update_span", side_effect=lambda **kw: span_calls.append(kw)),
            patch("src.llm.orchestrator.update_trace"),
        ):
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=_raw_llm_response())
            mock_client_factory.return_value = mock_client

            from src.llm.orchestrator import _generate_response_classic
            await _generate_response_classic(
                user=user, pet=pet, dialogue_id="diag-2", user_message="routine question"
            )

        closing_call = next((c for c in span_calls if "output" in c), None)
        assert closing_call is not None
        assert "triage_final" in closing_call["metadata"]
        assert "input_tokens" in closing_call["metadata"]

    @pytest.mark.asyncio
    async def test_gemini_call_span_records_model_and_tokens(self):
        """update_generation receives model name and token counts from _call."""
        generation_calls: list[dict] = []

        with (
            patch(
                "src.llm.client.update_generation",
                side_effect=lambda **kw: generation_calls.append(kw),
            ),
        ):
            from src.llm.client import GeminiClient

            client = GeminiClient.__new__(GeminiClient)
            client._sdk_mode = "genai"
            client._types = MagicMock()
            client._client = MagicMock()

            fake_response = MagicMock()
            fake_response.text = "All good!"
            fake_response.candidates = []
            fake_response.usage_metadata = SimpleNamespace(
                prompt_token_count=80, candidates_token_count=40
            )

            with patch.object(client, "_sync_call_genai", return_value=fake_response):
                with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
                    mock_thread.return_value = fake_response
                    result = await client._call(
                        model="gemini-2.0-flash",
                        system_prompt="You are Pawly.",
                        messages=[{"role": "user", "content": "hello"}],
                        max_tokens=512,
                        temperature=0.7,
                    )

        assert len(generation_calls) == 1
        call = generation_calls[0]
        assert call["model"] == "gemini-2.0-flash"
        assert call["usage_details"]["input"] >= 0
        assert call["usage_details"]["output"] >= 0
        assert result["text"] == "All good!"


# ── Test B: Langfuse failure does not propagate ───────────────────────────────

class TestLangfuseFailureIsolation:
    """Assert that exceptions in tracing helpers never surface to the caller."""

    @pytest.mark.asyncio
    async def test_update_span_exception_does_not_raise(self):
        """
        A timeout inside the Langfuse client must not surface to the orchestrator caller.

        We patch the underlying _lf_client.update_current_span to raise rather than
        patching update_span itself — that would bypass the try/except in our wrapper.
        """
        user = _make_user()
        pet = _make_pet(user.id)

        failing_ctx = MagicMock()
        failing_ctx.update_current_observation.side_effect = TimeoutError("langfuse unreachable")
        failing_ctx.update_current_trace.side_effect = TimeoutError("langfuse unreachable")

        with (
            patch("src.llm.orchestrator.load_pet_context", new_callable=AsyncMock, return_value={}),
            patch("src.llm.orchestrator.load_related_memories", new_callable=AsyncMock, return_value=[]),
            patch("src.llm.orchestrator._store_triage_record", new_callable=AsyncMock),
            patch("src.llm.orchestrator.get_gemini_client") as mock_client_factory,
            patch("src.observability.tracing.langfuse_context", failing_ctx),
            patch("src.observability.tracing._LANGFUSE_ENABLED", True),
        ):
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=_raw_llm_response("paws look fine"))
            mock_client_factory.return_value = mock_client

            from src.llm.orchestrator import _generate_response_classic
            result = await _generate_response_classic(
                user=user, pet=pet, dialogue_id="diag-3", user_message="routine check"
            )

        # LLM response must be returned normally despite Langfuse timing out
        assert "paws look fine" in result.response_text

    @pytest.mark.asyncio
    async def test_update_generation_exception_does_not_raise(self):
        """
        A ConnectionError inside the Langfuse client must not surface from _call.

        Patches _lf_client.update_current_generation to raise so our wrapper's
        try/except is exercised, then verifies the LLM result is still returned.
        """
        failing_ctx = MagicMock()
        failing_ctx.update_current_observation.side_effect = ConnectionError("langfuse down")

        with (
            patch("src.observability.tracing.langfuse_context", failing_ctx),
            patch("src.observability.tracing._LANGFUSE_ENABLED", True),
        ):
            from src.llm.client import GeminiClient

            client = GeminiClient.__new__(GeminiClient)
            client._sdk_mode = "genai"
            client._types = MagicMock()
            client._client = MagicMock()

            fake_response = MagicMock()
            fake_response.text = "healthy"
            fake_response.candidates = []
            fake_response.usage_metadata = SimpleNamespace(
                prompt_token_count=10, candidates_token_count=5
            )

            with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=fake_response):
                result = await client._call(
                    model="gemini-2.0-flash",
                    system_prompt="sys",
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=256,
                    temperature=0.5,
                )

        assert result["text"] == "healthy"

    @pytest.mark.asyncio
    async def test_langfuse_completely_disabled_still_returns_response(self):
        """When Langfuse is disabled (noop decorators), orchestrator works normally."""
        user = _make_user()
        pet = _make_pet(user.id)

        with (
            patch("src.llm.orchestrator.load_pet_context", new_callable=AsyncMock, return_value={}),
            patch("src.llm.orchestrator.load_related_memories", new_callable=AsyncMock, return_value=[]),
            patch("src.llm.orchestrator._store_triage_record", new_callable=AsyncMock),
            patch("src.llm.orchestrator.get_gemini_client") as mock_client_factory,
            # Simulate Langfuse being fully disabled — update_span is a no-op
            patch("src.llm.orchestrator.update_span", return_value=None),
        ):
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=_raw_llm_response("all clear"))
            mock_client_factory.return_value = mock_client

            from src.llm.orchestrator import _generate_response_classic
            result = await _generate_response_classic(
                user=user, pet=pet, dialogue_id="diag-4", user_message="routine check"
            )

        assert result.response_text != ""
        assert result.input_tokens == 100
        assert result.output_tokens == 50
