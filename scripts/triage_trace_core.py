"""
Triage trace engine — shared between CLI and Streamlit UI.

run_trace()      async, returns TraceResult
run_trace_sync() thread-safe sync wrapper (safe to call from Streamlit)
list_case_names() list all case IDs from the regression JSON
load_case_meta()  lightweight metadata without running anything
"""

import asyncio
import concurrent.futures
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_DATA = (
    REPO_ROOT / "tests" / "blackbox_multiturn" / "test_data"
    / "multiturn_pawly_regression_cases.json"
)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class TurnTrace:
    turn_num: int
    user_text: str
    rule_classification: str = "GREEN"
    rule_score: float = 0.0
    rule_confidence: str = "LOW"
    rule_matched: list[str] = field(default_factory=list)
    llm_level: str | None = None
    final_level: str | None = None
    overridden: bool = False
    override_direction: str = ""
    safety_banner: bool = False
    response_preview: str = ""
    error: str | None = None


@dataclass
class CaseMeta:
    name: str
    scenario: str
    pet_summary: str
    turn_count: int


@dataclass
class TraceResult:
    case_name: str
    pet_summary: str
    scenario: str
    model: str
    turns: list[TurnTrace]


# ── Case discovery ─────────────────────────────────────────────────────────────

def list_case_names() -> list[str]:
    if not TEST_DATA.exists():
        return []
    with TEST_DATA.open(encoding="utf-8") as f:
        cases = json.load(f)
    return [c["name"] for c in cases if c.get("name")]


def load_case_meta(case_name: str) -> CaseMeta | None:
    """Return lightweight metadata without running any LLM calls."""
    if not TEST_DATA.exists():
        return None
    with TEST_DATA.open(encoding="utf-8") as f:
        cases = json.load(f)
    case = next((c for c in cases if c.get("name") == case_name), None)
    if case is None:
        return None
    pp = case.get("pet_profile") or {}
    pet_summary = (
        f"{pp.get('name','?')} | {pp.get('species','?')} | "
        f"{pp.get('gender','?')} | {pp.get('age_in_months','?')}mo | "
        f"{pp.get('weight_latest','?')}kg"
    )
    return CaseMeta(
        name=case_name,
        scenario=case.get("scenario", ""),
        pet_summary=pet_summary,
        turn_count=len(case.get("user_turns") or []),
    )


def _load_raw_case(case_name: str) -> dict[str, Any] | None:
    if not TEST_DATA.exists():
        return None
    with TEST_DATA.open(encoding="utf-8") as f:
        cases = json.load(f)
    return next((c for c in cases if c.get("name") == case_name), None)


# ── Model object builders ─────────────────────────────────────────────────────

def _species(v: str | None):
    from src.db.models import Species
    try:
        return Species(str(v).strip().lower()) if v else Species.OTHER
    except ValueError:
        return Species.OTHER


def _gender(v: str | None):
    from src.db.models import Gender
    try:
        return Gender(str(v).strip().lower()) if v else Gender.UNKNOWN
    except ValueError:
        return Gender.UNKNOWN


def _neutered(v: str | None):
    from src.db.models import NeuteredStatus
    aliases = {
        "neutered": NeuteredStatus.YES, "spayed": NeuteredStatus.YES,
        "intact": NeuteredStatus.NO, "entire": NeuteredStatus.NO,
    }
    if not v:
        return NeuteredStatus.UNKNOWN
    return aliases.get(str(v).strip().lower(), NeuteredStatus.UNKNOWN)


def _build_objects(case: dict[str, Any]):
    from src.db.models import (
        MemorySource, MemoryTerm, MemoryType,
        Pet, PetMemory, SubscriptionTier, User,
    )
    user_id = uuid.uuid4()
    pet_id = uuid.uuid4()
    pp = case.get("pet_profile") or {}

    user = User(
        id=user_id,
        telegram_id=f"trace-{user_id.hex[:8]}",
        display_name=case.get("user_display_name", "Trace User"),
        subscription_tier=SubscriptionTier.PLUS,
    )
    pet = Pet(
        id=pet_id, user_id=user_id,
        name=pp.get("name", "Pet"),
        species=_species(pp.get("species")),
        breed=pp.get("breed"),
        age_in_months=pp.get("age_in_months"),
        gender=_gender(pp.get("gender")),
        neutered_status=_neutered(pp.get("neutered_status")),
        weight_latest=pp.get("weight_latest"),
    )
    memories = []
    for m in (case.get("memories") or []):
        if "memory_type" not in m:
            continue
        memories.append(PetMemory(
            id=uuid.uuid4(), pet_id=pet_id,
            memory_type=MemoryType(m["memory_type"]),
            memory_term=MemoryTerm(m["memory_term"]),
            field=m.get("field", ""),
            value=m.get("value", ""),
            confidence_score=m.get("confidence_score", 0.9),
            source=MemorySource.AI_EXTRACTED,
            source_message_id=None,
            is_active=True,
        ))
    return user, pet, memories


# ── Core async trace runner ────────────────────────────────────────────────────

async def run_trace(case_name: str, model: str | None = None) -> TraceResult:
    """
    Run one regression case through the full orchestrator and return
    a structured per-turn trace.

    All DB calls are mocked — only the LLM is called live.
    """
    import sys
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from src.db.models import MemoryTerm, MessageType
    from src.llm.orchestrator import generate_response
    from src.triage.rules_engine import classify_by_rules

    case = _load_raw_case(case_name)
    if case is None:
        raise ValueError(f"Case '{case_name}' not found in {TEST_DATA.name}")

    resolved_model = model or "gemini-2.5-flash"
    if model:
        from src.config import settings
        settings.main_model = model
        settings.chat_model = model
        settings.fallback_model = model

    user, pet, memories = _build_objects(case)
    recent_turns: list[dict[str, str]] = list(case.get("recent_turns") or [])
    long_term  = [m for m in memories if m.memory_term == MemoryTerm.LONG]
    mid_term   = [m for m in memories if m.memory_term == MemoryTerm.MID]
    short_term = [m for m in memories if m.memory_term == MemoryTerm.SHORT]

    fake_session_id  = uuid.uuid4()
    fake_dialogue_id = uuid.uuid4()
    fake_message_id  = uuid.uuid4()

    pp = case.get("pet_profile") or {}
    pet_summary = (
        f"{pp.get('name','?')} | {pp.get('species','?')} | "
        f"{pp.get('gender','?')} | {pp.get('age_in_months','?')}mo | "
        f"{pp.get('weight_latest','?')}kg"
    )

    async def _fake_load_pet_context(*a: Any, **kw: Any) -> dict[str, Any]:
        return {
            "pet": pet,
            "long_term_memories":  long_term,
            "mid_term_memories":   mid_term,
            "short_term_memories": short_term,
            "recent_turns":        recent_turns,
            "daily_summary":       None,
            "weekly_summary":      None,
            "pending_confirmations": [],
        }

    async def _fake_load_related_memories(*a: Any, **kw: Any):
        return short_term

    async def _fake_store_triage_record(*a: Any, **kw: Any) -> None:
        return None

    turn_traces: list[TurnTrace] = []

    with (
        patch("src.llm.orchestrator.load_pet_context",       _fake_load_pet_context),
        patch("src.llm.orchestrator.load_related_memories",  _fake_load_related_memories),
        patch("src.llm.orchestrator._store_triage_record",   _fake_store_triage_record),
    ):
        for idx, user_text in enumerate(case.get("user_turns") or [], start=1):
            rule_result = classify_by_rules(pet, user_text)
            tt = TurnTrace(
                turn_num=idx,
                user_text=user_text,
                rule_classification=rule_result.classification.value,
                rule_score=rule_result.score,
                rule_confidence=rule_result.confidence,
                rule_matched=list(rule_result.matched_rules or []),
            )

            try:
                result = await generate_response(
                    user=user,
                    pet=pet,
                    dialogue_id=str(fake_dialogue_id),
                    user_message=user_text,
                    message_type=MessageType.TEXT,
                    session={
                        "user_id": str(user.id),
                        "active_pet_id": str(pet.id),
                        "session_id": str(fake_session_id),
                        "dialogue_id": str(fake_dialogue_id),
                    },
                    raw_message_id=str(fake_message_id),
                )
                tr = result.triage_result or {}
                tt.llm_level = tr.get("llm")
                tt.final_level = tr.get("final")
                tt.overridden = bool(tr.get("overridden"))
                tt.override_direction = tr.get("override_direction", "")
                tt.safety_banner = (
                    tr.get("rule") == "RED" and tr.get("llm") != "RED"
                )
                tt.response_preview = (result.response_text or "")[:200].replace("\n", " ")
                response_text = result.response_text or ""
            except Exception as exc:
                tt.error = str(exc)
                response_text = ""

            turn_traces.append(tt)
            recent_turns.append({"role": "user",      "content": user_text})
            recent_turns.append({"role": "assistant", "content": response_text})

    return TraceResult(
        case_name=case_name,
        pet_summary=pet_summary,
        scenario=case.get("scenario", ""),
        model=resolved_model,
        turns=turn_traces,
    )


def run_trace_sync(case_name: str, model: str | None = None) -> TraceResult:
    """
    Thread-safe sync wrapper around run_trace().
    Safe to call from Streamlit (which may have its own event loop).
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, run_trace(case_name, model)).result()
