import asyncio
import json
import os
import re
import sys
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from threading import Lock
from typing import Any

import pytest
from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.types import Chat, Message, TelegramObject, Update, User as TgUser
from aiogram.fsm.storage.memory import MemoryStorage

# Make sibling helper modules importable (matches the pattern used by
# tests/blackbox_multiturn/pages/*.py for `lang.py`).
sys.path.insert(0, str(Path(__file__).parent))
from _validation import ValidationReport, validate_dataset  # noqa: E402

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-bot-token")
os.environ.setdefault("GOOGLE_API_KEY", "")
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")

from src.config import settings
from src.bot.handlers import message as message_handler
from src.bot.middleware.rate_limiter import RateLimiterMiddleware
from src.bot.middleware.session import SessionMiddleware
from src.db.models import (
    Gender,
    MemorySource,
    MemoryTerm,
    MemoryType,
    NeuteredStatus,
    Pet,
    PetMemory,
    Species,
    SubscriptionTier,
    User,
)
from src.llm.client import GeminiClient, get_gemini_client


TEST_DATA_DIR = Path(__file__).parent / "test_data"
RESULTS_DIR = Path(__file__).parent / "results"
LOGS_DIR = Path(__file__).parent / "logs"
RUN_TIMESTAMP_ENV = "PAWLY_BLACKBOX_RUN_TIMESTAMP"


def _detach_router(router: Any) -> None:
    parent = getattr(router, "parent_router", None)
    if parent is None:
        return
    if router in parent.sub_routers:
        parent.sub_routers.remove(router)
    router._parent_router = None


def _species(value: str) -> Species:
    return Species(value)


def _gender(value: str) -> Gender:
    return Gender(value)


def _neutered_status(value: str) -> NeuteredStatus:
    normalized = str(value).strip().lower()
    aliases = {
        "neutered": NeuteredStatus.YES,
        "spayed": NeuteredStatus.YES,
        "fixed": NeuteredStatus.YES,
        "desexed": NeuteredStatus.YES,
        "intact": NeuteredStatus.NO,
        "entire": NeuteredStatus.NO,
    }
    if normalized in aliases:
        return aliases[normalized]
    return NeuteredStatus(normalized)


def _memory_type(value: str) -> MemoryType:
    return MemoryType(value)


def _memory_term(value: str) -> MemoryTerm:
    return MemoryTerm(value)


def _build_pet_memory(pet_id: uuid.UUID, item: dict[str, Any]) -> PetMemory:
    # Defaults match production extractor.py:185 so a partial fixture entry
    # never crashes the whole eval run (preflight validation surfaces the
    # missing fields separately).
    return PetMemory(
        id=uuid.uuid4(),
        pet_id=pet_id,
        memory_type=_memory_type(item.get("memory_type", "snapshot")),
        memory_term=_memory_term(item.get("memory_term", "short")),
        field=item.get("field", ""),
        value=item.get("value", ""),
        confidence_score=item.get("confidence_score", 0.9),
        source=MemorySource.AI_EXTRACTED,
        source_message_id=None,
        is_active=True,
    )


def _extract_json_payload(text: str) -> str:
    stripped = text.strip()
    candidates: list[str] = [stripped]

    fenced_blocks = re.findall(r"```(?:json)?\s*(.*?)```", stripped, flags=re.DOTALL | re.IGNORECASE)
    candidates.extend(block.strip() for block in fenced_blocks if block.strip())

    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines:
            body = "\n".join(lines[1:]).strip()
            if body:
                candidates.append(body)
                candidates.append(body.removesuffix("```").strip())

    def _first_balanced_json_chunk(value: str, opener: str, closer: str) -> str | None:
        start = value.find(opener)
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(value)):
            char = value[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    return value[start : index + 1].strip()
        return None

    for opener, closer in (("{", "}"), ("[", "]")):
        start = stripped.find(opener)
        end = stripped.rfind(closer)
        if start != -1 and end != -1 and end > start:
            candidates.append(stripped[start : end + 1].strip())
        balanced = _first_balanced_json_chunk(stripped, opener, closer)
        if balanced:
            candidates.append(balanced)

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            continue

    return stripped


def _recover_reason_score_payload(text: str) -> str | None:
    score_match = re.search(r'"score"\s*:\s*(-?\d+(?:\.\d+)?)', text)
    reason_match = re.search(r'"reason"\s*:\s*"', text)
    if score_match is None or reason_match is None:
        return None

    score_raw = score_match.group(1)
    reason_start = reason_match.end()
    reason_text = text[reason_start:].strip()

    # If the response was truncated mid-string, keep the surviving suffix and
    # rebuild a valid JSON object for the target schema.
    reason_text = reason_text.removesuffix("}").rstrip()
    if reason_text.endswith('"'):
        reason_text = reason_text[:-1].rstrip()

    try:
        score_value = float(score_raw)
    except ValueError:
        return None

    repaired_payload = {
        "score": score_value,
        "reason": reason_text,
    }
    return json.dumps(repaired_payload, ensure_ascii=True)


class GeminiDeepEvalModelMixin:
    def __init__(self, client: GeminiClient, model_name: str | None = None) -> None:
        self._client = client
        super().__init__(model=model_name)

    def load_model(self) -> "GeminiDeepEvalModelMixin":
        return self

    def _schema_prompt(self, prompt: str) -> str:
        return (
            f"{prompt}\n\n"
            "Return ONLY valid JSON that matches the requested schema. "
            "Do not use markdown code fences. "
            "Do not add any commentary before or after the JSON."
        )

    def _validate_schema_response(self, schema: Any, text: str) -> Any:
        payload = _extract_json_payload(text)
        try:
            return schema.model_validate_json(payload)
        except Exception as exc:
            if getattr(schema, "__name__", "") == "ReasonScore":
                repaired_payload = _recover_reason_score_payload(payload)
                if repaired_payload is not None:
                    try:
                        return schema.model_validate_json(repaired_payload)
                    except Exception:
                        pass
            raise RuntimeError(
                f"DeepEval judge response could not be parsed as JSON. "
                f"Extracted payload: {payload!r}. Raw response: {text!r}"
            ) from exc

    def _generate_with_schema_retry(self, prompt: str, schema: Any) -> Any:
        attempts = [
            prompt,
            self._schema_prompt(prompt),
            self._schema_prompt(
                f"{prompt}\n\nYour previous answer was invalid or truncated. "
                "Retry and output the full JSON object only."
            ),
        ]
        last_error: Exception | None = None
        for attempt_prompt in attempts:
            result = asyncio.run(
                self._client.chat(
                    system_prompt="",
                    messages=[{"role": "user", "content": attempt_prompt}],
                    temperature=0,
                    max_tokens=4096,
                )
            )
            text = result["text"]
            try:
                return self._validate_schema_response(schema, text)
            except Exception as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    def generate(self, prompt: str, schema: Any = None) -> Any:
        if schema is None:
            result = asyncio.run(
                self._client.chat(
                    system_prompt="",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                )
            )
            return result["text"]
        return self._generate_with_schema_retry(prompt, schema)

    async def _a_generate_with_schema_retry(self, prompt: str, schema: Any) -> Any:
        attempts = [
            prompt,
            self._schema_prompt(prompt),
            self._schema_prompt(
                f"{prompt}\n\nYour previous answer was invalid or truncated. "
                "Retry and output the full JSON object only."
            ),
        ]
        last_error: Exception | None = None
        for attempt_prompt in attempts:
            result = await self._client.chat(
                system_prompt="",
                messages=[{"role": "user", "content": attempt_prompt}],
                temperature=0,
                max_tokens=4096,
            )
            text = result["text"]
            try:
                return self._validate_schema_response(schema, text)
            except Exception as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    async def a_generate(self, prompt: str, schema: Any = None) -> Any:
        if schema is None:
            result = await self._client.chat(
                system_prompt="",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            return result["text"]
        return await self._a_generate_with_schema_retry(prompt, schema)

    def get_model_name(self) -> str:
        return "gemini-deepeval-judge"


class ResilientGeminiClient:
    def __init__(
        self,
        client: GeminiClient,
        *,
        min_interval_seconds: float = 5.0,
        retry_delay_seconds: float = 1.0,
        max_attempts: int = 3,
    ) -> None:
        self._client = client
        self._min_interval_seconds = min_interval_seconds
        self._retry_delay_seconds = retry_delay_seconds
        self._max_attempts = max_attempts
        self._rate_lock = Lock()
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        with self._rate_lock:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self._min_interval_seconds:
                time.sleep(self._min_interval_seconds - elapsed)
            self._last_request_at = time.monotonic()

    def _is_retryable(self, exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int) and status_code in {429, 500, 502, 503, 504}:
            return True

        message = str(exc).upper()
        transient_markers = (
            "429",
            "500",
            "502",
            "503",
            "504",
            "RESOURCE_EXHAUSTED",
            "UNAVAILABLE",
            "HIGH DEMAND",
            "CONNECTERROR",
            "NODENAME NOR SERVNAME",
            "TIMED OUT",
            "TIMEOUT",
            "TRY AGAIN LATER",
        )
        return any(marker in message for marker in transient_markers)

    def _retry_delay_for_attempt(self, attempt: int) -> float:
        schedule = (5.0, 10.0, 15.0)
        index = min(max(attempt - 1, 0), len(schedule) - 1)
        return schedule[index]

    async def _call_with_retry(self, method_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        last_error: Exception | None = None
        method = getattr(self._client, method_name)
        for attempt in range(1, self._max_attempts + 1):
            self._throttle()
            try:
                return await method(*args, **kwargs)
            except Exception as exc:
                last_error = exc
                if attempt >= self._max_attempts or not self._is_retryable(exc):
                    raise
                time.sleep(self._retry_delay_for_attempt(attempt))

        assert last_error is not None
        raise last_error

    async def chat(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return await self._call_with_retry("chat", *args, **kwargs)

    async def chat_structured(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return await self._call_with_retry("chat_structured", *args, **kwargs)

    async def extract(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return await self._call_with_retry("extract", *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class FakeBot:
    def __init__(self) -> None:
        self.chat_actions: list[dict[str, Any]] = []
        self.sent_messages: list[dict[str, Any]] = []
        self.deleted_messages: list[dict[str, Any]] = []
        self.edited_messages: list[dict[str, Any]] = []


class InMemoryPipeline:
    def __init__(self, redis: "InMemoryRedis") -> None:
        self.redis = redis
        self.ops: list[tuple[str, tuple[Any, ...]]] = []

    def incr(self, key: str) -> "InMemoryPipeline":
        self.ops.append(("incr", (key,)))
        return self

    def expire(self, key: str, ttl: int) -> "InMemoryPipeline":
        self.ops.append(("expire", (key, ttl)))
        return self

    async def execute(self) -> list[Any]:
        results: list[Any] = []
        for op, args in self.ops:
            if op == "incr":
                results.append(await self.redis.incr(*args))
            elif op == "expire":
                results.append(await self.redis.expire(*args))
        self.ops.clear()
        return results


class InMemoryRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.store[key] = value
        return True

    async def incr(self, key: str) -> int:
        current = int(self.store.get(key, "0"))
        current += 1
        self.store[key] = str(current)
        return current

    async def expire(self, key: str, ttl: int) -> bool:
        return True

    def pipeline(self) -> InMemoryPipeline:
        return InMemoryPipeline(self)


class TestUserContextMiddleware(BaseMiddleware):
    def __init__(self, user: User, pet: Pet) -> None:
        self.user = user
        self.pet = pet

    async def __call__(self, handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        session = data.setdefault("session", {})
        session["user_id"] = str(self.user.id)
        session["active_pet_id"] = str(self.pet.id)
        data["user"] = self.user
        data["active_pet"] = self.pet
        return await handler(event, data)


class ConversationRuntime:
    def __init__(self, pet: Pet, memories: list[PetMemory], recent_turns: list[dict[str, str]]) -> None:
        self.pet = pet
        self.memories = memories
        self.recent_turns = list(recent_turns)

    def record_exchange(self, user_text: str, assistant_text: str) -> None:
        self.recent_turns.append({"role": "user", "content": user_text})
        self.recent_turns.append({"role": "assistant", "content": assistant_text})


@pytest.fixture(scope="session")
def active_model_name(request: pytest.FixtureRequest) -> str:
    """Model name to evaluate. Resolved from --model CLI, then PAWLY_MODEL env, then settings."""
    cli = request.config.getoption("--model", default=None)
    if cli:
        return cli
    return os.environ.get("PAWLY_MODEL") or settings.main_model


@pytest.fixture(scope="session")
def underlying_chat_client(active_model_name: str) -> Any:
    """Resolve the chat client for the chosen model. Skips if API key missing."""
    from src.llm.providers import provider_for, get_chat_client
    provider = provider_for(active_model_name)

    if provider == "Gemini":
        if not settings.google_api_key.strip():
            pytest.skip("GOOGLE_API_KEY is required for Gemini models.")
    elif provider == "Anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
            pytest.skip("ANTHROPIC_API_KEY is required for Claude models.")
    elif provider == "OpenAI":
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            pytest.skip("OPENAI_API_KEY is required for GPT models.")
    elif provider == "DeepSeek":
        if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
            pytest.skip("DEEPSEEK_API_KEY is required for DeepSeek models.")

    # Force settings.main_model so orchestrator passes the right model name to the client.
    settings.main_model = active_model_name
    settings.extraction_model = active_model_name
    settings.fallback_model = active_model_name
    return get_chat_client(active_model_name)


@pytest.fixture(scope="session")
def resilient_gemini_client(underlying_chat_client: Any) -> ResilientGeminiClient:
    """Retains the historical fixture name; wraps any provider in retry logic."""
    return ResilientGeminiClient(underlying_chat_client)


@pytest.fixture(autouse=True)
def patch_blackbox_gemini_client(
    monkeypatch: pytest.MonkeyPatch,
    resilient_gemini_client: ResilientGeminiClient,
) -> None:
    monkeypatch.setattr("src.llm.client.get_gemini_client", lambda: resilient_gemini_client)
    monkeypatch.setattr("src.memory.summarizer.get_gemini_client", lambda: resilient_gemini_client)
    # Orchestrator, LangGraph, and the memory extractor now dispatch through
    # get_chat_client; route every provider lookup at the resilient wrapper so
    # the multiturn runner can keep swapping models via the PAWLY_MODEL env var.
    monkeypatch.setattr(
        "src.llm.providers.get_chat_client",
        lambda model=None: resilient_gemini_client,
    )
    monkeypatch.setattr(
        "src.llm.orchestrator.get_chat_client",
        lambda model=None: resilient_gemini_client,
    )
    monkeypatch.setattr(
        "src.llm.graph.nodes.get_chat_client",
        lambda model=None: resilient_gemini_client,
    )
    monkeypatch.setattr(
        "src.memory.extractor.get_chat_client",
        lambda model=None: resilient_gemini_client,
    )


@pytest.fixture(scope="session")
def deepeval_model(resilient_gemini_client: ResilientGeminiClient, active_model_name: str) -> Any:
    deepeval = pytest.importorskip("deepeval.models")
    base_cls = getattr(deepeval, "DeepEvalBaseLLM")
    model_cls = type("GeminiDeepEvalModel", (GeminiDeepEvalModelMixin, base_cls), {})
    instance = model_cls(resilient_gemini_client)
    # Override the reported model name so the report filename reflects the active model.
    setattr(instance, "model", active_model_name)
    return instance


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--multiturn-topic",
        action="store",
        default="multiturn_text_robustness",
        help="Topic name for multiturn tests (e.g., multiturn_triage, multiturn_ethics)",
    )
    parser.addoption(
        "--model",
        action="store",
        default=None,
        help="LLM model to evaluate (e.g. gemini-2.0-flash, claude-sonnet-4-6, gpt-4o-mini).",
    )
    parser.addoption(
        "--strict-validation",
        action="store_true",
        default=False,
        help=(
            "Fail the session if any case in the dataset has schema errors. "
            "Default is warn-only: errors are printed but the run continues "
            "(combined with .get(default) hardening in fixture builders)."
        ),
    )
    parser.addoption(
        "--keep-worker-reports",
        action="store_true",
        default=False,
        help=(
            "Keep per-worker partial report files after the master merges them. "
            "Off by default — partials are removed after a successful merge."
        ),
    )


@pytest.fixture(scope="session")
def multiturn_topic(request: pytest.FixtureRequest) -> str:
    return request.config.getoption("--multiturn-topic")


@pytest.fixture(scope="session")
def load_test_cases(
    request: pytest.FixtureRequest,
) -> Callable[[str], list[dict[str, Any]]]:
    strict = bool(request.config.getoption("--strict-validation"))
    validated: set[str] = set()

    def _loader(filename: str) -> list[dict[str, Any]]:
        path = TEST_DATA_DIR / filename
        with path.open("r", encoding="utf-8") as handle:
            cases = json.load(handle)

        # Validate each dataset at most once per session.
        if filename not in validated:
            validated.add(filename)
            report: ValidationReport = validate_dataset(cases)
            if report.has_errors or report.warnings:
                print(
                    "\n"
                    + report.format_summary(
                        header=f"Preflight validation: {filename}"
                    )
                )
            if report.has_errors and strict:
                pytest.fail(
                    f"dataset {filename} has {report.error_count} schema error(s); "
                    "fix the dataset or rerun without --strict-validation.",
                    pytrace=False,
                )

        return cases

    return _loader


@pytest.fixture
def build_user_and_pet() -> Callable[[dict[str, Any]], tuple[User, Pet]]:
    def _builder(case: dict[str, Any]) -> tuple[User, Pet]:
        user_id = uuid.uuid4()
        pet_id = uuid.uuid4()
        # Tolerate partial pet_profile (preflight reports the gaps separately).
        pet_profile = case.get("pet_profile", {}) or {}

        user = User(
            id=user_id,
            telegram_id=f"eval-{user_id.hex[:10]}",
            display_name=case.get("user_display_name", "Eval User"),
            subscription_tier=SubscriptionTier.PLUS,
        )
        pet = Pet(
            id=pet_id,
            user_id=user_id,
            name=pet_profile.get("name", "Unnamed"),
            species=_species(pet_profile.get("species", "dog")),
            breed=pet_profile.get("breed"),
            age_in_months=pet_profile.get("age_in_months"),
            gender=_gender(pet_profile.get("gender", "unknown")),
            neutered_status=_neutered_status(pet_profile.get("neutered_status", "unknown")),
            weight_latest=pet_profile.get("weight_latest"),
        )
        return user, pet

    return _builder


@pytest.fixture
def build_update() -> Callable[[str, int, int], Update]:
    def _builder(text: str, message_id: int, telegram_user_id: int) -> Update:
        return Update(
            update_id=message_id,
            message=Message(
                message_id=message_id,
                date=datetime.now(),
                chat=Chat(id=telegram_user_id, type="private"),
                from_user=TgUser(
                    id=telegram_user_id,
                    is_bot=False,
                    first_name="Margaret",
                    username="margaret_eval",
                    language_code="en",
                ),
                text=text,
            ),
        )

    return _builder


@pytest.fixture
def mock_multiturn_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[dict[str, Any], User, Pet], ConversationRuntime]:
    from src.llm import orchestrator

    def _apply(case: dict[str, Any], user: User, pet: Pet) -> ConversationRuntime:
        memories = [_build_pet_memory(pet.id, item) for item in case.get("memories", [])]
        runtime = ConversationRuntime(
            pet=pet,
            memories=memories,
            recent_turns=case.get("recent_turns", []),
        )
        fake_session_id = uuid.uuid4()
        fake_dialogue_id = uuid.uuid4()

        async def _fake_load_pet_context(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {
                "pet": pet,
                "long_term_memories": [m for m in runtime.memories if m.memory_term == MemoryTerm.LONG],
                "mid_term_memories": [m for m in runtime.memories if m.memory_term == MemoryTerm.MID],
                "short_term_memories": [m for m in runtime.memories if m.memory_term == MemoryTerm.SHORT],
                "recent_turns": runtime.recent_turns,
                "daily_summary": None,
                "weekly_summary": None,
                "pending_confirmations": [],
            }

        async def _fake_load_related_memories(*args: Any, **kwargs: Any) -> list[PetMemory]:
            return [m for m in runtime.memories if m.memory_term == MemoryTerm.SHORT]

        async def _fake_store_triage_record(*args: Any, **kwargs: Any) -> None:
            return None

        async def _fake_load_user_pets(user_id: str) -> list[Pet]:
            return [pet]

        async def _fake_store_raw_message(*args: Any, **kwargs: Any) -> Any:
            return SimpleNamespace(id=uuid.uuid4())

        async def _fake_get_or_create_session(user_id: str) -> Any:
            return SimpleNamespace(id=fake_session_id)

        async def _fake_get_or_create_dialogue(session_id: str, pet_id: str | None) -> Any:
            return SimpleNamespace(id=fake_dialogue_id)

        async def _fake_store_enriched_messages(*args: Any, **kwargs: Any) -> None:
            return None

        async def _fake_enqueue_extraction(*args: Any, **kwargs: Any) -> None:
            return None

        monkeypatch.setattr(orchestrator, "load_pet_context", _fake_load_pet_context)
        monkeypatch.setattr(orchestrator, "load_related_memories", _fake_load_related_memories)
        monkeypatch.setattr(orchestrator, "_store_triage_record", _fake_store_triage_record)
        monkeypatch.setattr(message_handler, "load_user_pets", _fake_load_user_pets)
        monkeypatch.setattr(message_handler, "store_raw_message", _fake_store_raw_message)
        monkeypatch.setattr(message_handler, "get_or_create_session", _fake_get_or_create_session)
        monkeypatch.setattr(message_handler, "get_or_create_dialogue", _fake_get_or_create_dialogue)
        monkeypatch.setattr(message_handler, "store_enriched_messages", _fake_store_enriched_messages)
        monkeypatch.setattr(message_handler, "enqueue_extraction", _fake_enqueue_extraction)
        return runtime

    return _apply


@pytest.fixture
def build_router_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[User, Pet], tuple[Bot, Dispatcher, FakeBot, InMemoryRedis]]:
    async def _fake_bot_call(self: Bot, method: Any, request_timeout: int | None = None) -> Any:
        api: FakeBot = getattr(self, "_fake_api")
        method_name = method.__class__.__name__
        if method_name == "SendChatAction":
            api.chat_actions.append({"chat_id": method.chat_id, "action": method.action})
            return True
        if method_name == "SendMessage":
            payload = {
                "chat_id": method.chat_id,
                "text": method.text,
                "reply_markup": method.reply_markup,
                "parse_mode": method.parse_mode,
            }
            api.sent_messages.append(payload)
            return Message(
                message_id=len(api.sent_messages) + 1000,
                date=datetime.now(),
                chat=Chat(id=method.chat_id, type="private"),
                from_user=TgUser(id=999999, is_bot=True, first_name="Pawly", username="pawly_test_bot"),
                text=method.text,
            )
        if method_name == "DeleteMessage":
            api.deleted_messages.append({"chat_id": method.chat_id, "message_id": method.message_id})
            return True
        if method_name == "EditMessageText":
            api.edited_messages.append(
                {
                    "chat_id": method.chat_id,
                    "message_id": method.message_id,
                    "text": method.text,
                }
            )
            return True
        return True

    def _builder(user: User, pet: Pet) -> tuple[Bot, Dispatcher, FakeBot, InMemoryRedis]:
        fake_api = FakeBot()
        fake_redis = InMemoryRedis()
        bot = Bot(token="123456:TESTTOKEN")
        setattr(bot, "_fake_api", fake_api)
        monkeypatch.setattr(Bot, "__call__", _fake_bot_call)

        monkeypatch.setattr("src.db.redis.get_redis", lambda: fake_redis)
        monkeypatch.setattr("src.bot.middleware.session.get_redis", lambda: fake_redis)
        monkeypatch.setattr("src.bot.middleware.rate_limiter.get_redis", lambda: fake_redis)

        dp = Dispatcher(storage=MemoryStorage())
        dp.message.middleware(SessionMiddleware())
        dp.message.middleware(TestUserContextMiddleware(user, pet))
        dp.message.middleware(RateLimiterMiddleware())
        _detach_router(message_handler.router)
        dp.include_router(message_handler.router)
        return bot, dp, fake_api, fake_redis

    return _builder


# ===========================================================================
# Run-level identity + xdist parallelization support
#
# All workers in one pytest invocation must agree on a single run identity
# (timestamp + paths) so the master can post-merge per-worker partial reports
# into one canonical file matching the historical schema. The master sets a
# timestamp env var in pytest_configure; xdist forks workers which inherit env.
# ===========================================================================


def _xdist_worker_id() -> str:
    """'master' when running serially, 'gw0'/'gw1'/... under pytest-xdist."""
    return os.environ.get("PYTEST_XDIST_WORKER", "master")


def _resolve_model_name_for_run(config: pytest.Config) -> str:
    """Mirrors test_message_handler_multiturn._resolve_model_name but works
    without instantiating fixtures (needed by master's post-merge hook)."""
    cli = config.getoption("--model", default=None)
    raw = cli or os.environ.get("PAWLY_MODEL") or settings.main_model
    if isinstance(raw, str) and raw.strip():
        return raw.replace("/", "-")
    return "gemini-2.5-flash"


def _run_paths(config: pytest.Config) -> dict[str, Any]:
    topic = config.getoption("--multiturn-topic")
    model_name = _resolve_model_name_for_run(config)
    timestamp = os.environ.get(RUN_TIMESTAMP_ENV, "00000000_000000")
    worker = _xdist_worker_id()
    base = f"{topic}_report_{model_name}_v{timestamp}"
    log_base = f"{topic}_run_{model_name}_v{timestamp}"
    return {
        "topic": topic,
        "model_name": model_name,
        "timestamp": timestamp,
        "worker_id": worker,
        "partial_report": RESULTS_DIR / f"{base}_worker-{worker}.json",
        "partial_log": LOGS_DIR / f"{log_base}_worker-{worker}.jsonl",
        "partial_report_glob": f"{base}_worker-*.json",
        "partial_log_glob": f"{log_base}_worker-*.jsonl",
        "final_report": RESULTS_DIR / f"{base}.json",
        "final_log": LOGS_DIR / f"{log_base}.jsonl",
    }


def pytest_configure(config: pytest.Config) -> None:
    # Generate run timestamp once on master so xdist workers (which inherit
    # env on fork) write their partial files under the same run identity.
    if not os.environ.get(RUN_TIMESTAMP_ENV):
        os.environ[RUN_TIMESTAMP_ENV] = datetime.now().strftime("%Y%m%d_%H%M%S")


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize the multiturn test with one entry per case in the dataset.

    Runs at collection time so --strict-validation can fail before any LLM
    call is made. Longitudinal cases are pinned to the same xdist worker via
    xdist_group so per-pet ordering is preserved when running with -n N.
    """
    if "case" not in metafunc.fixturenames:
        return
    topic = metafunc.config.getoption("--multiturn-topic")
    filename = f"{topic}_cases.json"
    path = TEST_DATA_DIR / filename
    if not path.exists():
        # Defer to the fixture's error path so the missing-file message is consistent.
        return
    with path.open("r", encoding="utf-8") as handle:
        cases = json.load(handle)

    report = validate_dataset(cases)
    if report.has_errors or report.warnings:
        print("\n" + report.format_summary(header=f"Preflight validation: {filename}"))
    if report.has_errors and metafunc.config.getoption("--strict-validation"):
        pytest.fail(
            f"dataset {filename} has {report.error_count} schema error(s); "
            "fix the dataset or rerun without --strict-validation.",
            pytrace=False,
        )

    if not isinstance(cases, list):
        # Validation already flagged this; let the test fixture surface it.
        return

    params: list[Any] = []
    seen_ids: set[str] = set()
    for index, case in enumerate(cases):
        case_id = (
            case.get("name") if isinstance(case, dict) and isinstance(case.get("name"), str) else None
        ) or f"case_{index}"
        # pytest requires unique parametrize ids; suffix duplicates rather than crashing.
        original = case_id
        dedup = 1
        while case_id in seen_ids:
            dedup += 1
            case_id = f"{original}__dup{dedup}"
        seen_ids.add(case_id)

        marks: list[Any] = []
        meta = (case.get("metadata") if isinstance(case, dict) else None) or {}
        if meta.get("category") == "longitudinal":
            pet_profile = (case.get("pet_profile") if isinstance(case, dict) else None) or {}
            pet_name = pet_profile.get("name", "unknown")
            marks.append(pytest.mark.xdist_group(name=f"longitudinal_{pet_name}"))
        params.append(pytest.param(case, id=case_id, marks=marks))

    metafunc.parametrize("case", params)


@pytest.fixture(scope="session")
def run_context(request: pytest.FixtureRequest) -> dict[str, Any]:
    return _run_paths(request.config)


@pytest.fixture(scope="session")
def report_state(request: pytest.FixtureRequest) -> dict[str, Any]:
    """Per-worker accumulator. Each test appends its case_result; the worker's
    pytest_sessionfinish writes a partial report; master then merges."""
    state: dict[str, Any] = {"cases": [], "started_logged": False}
    # Stash on config so pytest_sessionfinish (which can't request fixtures) can
    # see the accumulated cases.
    setattr(request.config, "_pawly_report_state", state)
    return state


def _build_summary(state: dict[str, Any], paths: dict[str, Any]) -> dict[str, Any]:
    cases = state["cases"]
    return {
        "report_path": str(paths["final_report"]),
        "log_path": str(paths["final_log"]),
        "llm_model": paths["model_name"],
        "timestamp": paths["timestamp"],
        "total_cases": len(cases),
        "passed_threshold": sum(1 for c in cases if c.get("status") == "passed_threshold"),
        "below_threshold": sum(1 for c in cases if c.get("status") == "below_threshold"),
        "errored": sum(1 for c in cases if c.get("status") == "errored"),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


def _is_master(config: pytest.Config) -> bool:
    """True for serial runs and for the xdist coordinator; False for xdist workers."""
    return not hasattr(config, "workerinput")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Write per-worker partial report; on master, merge all partials into the
    canonical (no-suffix) file so downstream Streamlit / compare_reports.py
    see the same schema as before parametrization."""
    config = session.config
    paths = _run_paths(config)

    state = getattr(config, "_pawly_report_state", None)
    if state is not None and state["cases"]:
        partial_report = {
            "summary": _build_summary(state, paths),
            "cases": state["cases"],
        }
        _write_json(paths["partial_report"], partial_report)

    if not _is_master(config):
        return

    # Master path — merge all partials this run produced into one canonical file.
    partial_files = sorted(RESULTS_DIR.glob(paths["partial_report_glob"]))
    if not partial_files:
        return  # no eval ran (e.g. only unit tests)

    merged_cases: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for partial_path in partial_files:
        try:
            with partial_path.open("r", encoding="utf-8") as handle:
                partial = json.load(handle)
        except (json.JSONDecodeError, OSError):
            continue
        for case_result in partial.get("cases", []):
            name = case_result.get("name") or f"<anon_{len(merged_cases)}>"
            # If two workers somehow processed the same case, keep the first
            # and skip the duplicate (xdist_group already prevents this for
            # longitudinal; this is just defense in depth).
            if name in seen_names:
                continue
            seen_names.add(name)
            merged_cases.append(case_result)

    merged_cases.sort(key=lambda c: c.get("name", ""))

    merged_state = {"cases": merged_cases}
    final_report = {
        "summary": _build_summary(merged_state, paths),
        "cases": merged_cases,
    }
    _write_json(paths["final_report"], final_report)

    # Also concatenate per-worker jsonl logs into the canonical log, sorted by
    # timestamp so cases are interleaved by wall-clock order.
    log_files = sorted(LOGS_DIR.glob(paths["partial_log_glob"]))
    if log_files:
        all_lines: list[tuple[str, str]] = []
        for log_path in log_files:
            try:
                for line in log_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    try:
                        ts = json.loads(line).get("logged_at", "")
                    except json.JSONDecodeError:
                        ts = ""
                    all_lines.append((ts, line))
            except OSError:
                continue
        all_lines.sort(key=lambda x: x[0])
        paths["final_log"].parent.mkdir(parents=True, exist_ok=True)
        with paths["final_log"].open("w", encoding="utf-8") as handle:
            for _, line in all_lines:
                handle.write(line + "\n")
        # Append a single test_finished event reflecting the full merged run.
        finished_event = {
            "logged_at": datetime.now().isoformat(),
            "event": "test_finished",
            "total_cases": len(merged_cases),
            "passed_threshold": sum(
                1 for c in merged_cases if c.get("status") == "passed_threshold"
            ),
            "below_threshold": sum(
                1 for c in merged_cases if c.get("status") == "below_threshold"
            ),
            "errored": sum(1 for c in merged_cases if c.get("status") == "errored"),
            "worker_count": len(log_files),
        }
        with paths["final_log"].open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(finished_event, ensure_ascii=True) + "\n")

    if not config.getoption("--keep-worker-reports"):
        for partial_path in partial_files:
            try:
                partial_path.unlink()
            except OSError:
                pass
        for log_path in log_files:
            try:
                log_path.unlink()
            except OSError:
                pass
