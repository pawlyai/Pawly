"""
Orchestrator v2 — defense-in-depth scenario routing with checklist-driven
clarification.

Pipeline (highest precedence first):

    1. crisis_gate (deterministic regex bank)        ──┐
    2. rules_engine RED keywords                      ─┼─ all run in parallel,
    3. LLM combined call (scenario_scores +           ─┘   results merged
       urgency_soft_score + response_text + ...)
    4. Soft urgency (Python keyword bank, complements
       LLM's urgency_soft_score)
                              │
                              ▼
                       merge.decide()
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
   Branch dispatch:                     ABC Quick Screen
     • crisis    → crisis template         (when urgency
     • checklist → slot filler              ambiguous)
     • emotional → soft LLM reply
     • general   → free LLM reply
              │
              ▼
        Section 9 hard limits + Section 10 advice template

Public API:
    generate_response_v2(...)  -> OrchestratorResultV2

Feature-flagged via settings.use_triage_v2 (default False — v1 path stays
intact until v2 is shadow-validated).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from src.checklists import loader as checklist_loader
from src.checklists import advice as checklist_advice
from src.checklists import router as checklist_router
from src.checklists import slot_filler
from src.config import settings
from src.db.models import (
    LifeStage,
    MessageType,
    Pet,
    RiskLevel,
    Sentiment,
    TriageLevel,
    User,
)
from src.llm.client import get_gemini_client
from src.llm.prompts.context import build_context_block
from src.llm.prompts.system import build_system_prompt
from src.llm.schema_v2 import DEFAULT_RESPONSE_V2, RESPONSE_SCHEMA_V2
from src.memory.reader import load_pet_context
from src.observability.tracing import update_span, update_trace
from src.triage import abc_screen, crisis_gate, soft_urgency
from src.triage.merge import MergeDecision, decide as merge_decide
from src.triage.rules_engine import classify_by_rules
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ── Result type ──────────────────────────────────────────────────────────────


@dataclass
class OrchestratorResultV2:
    response_text: str
    branch: str
    triage_level: TriageLevel = TriageLevel.GREEN
    checklist_id: Optional[str] = None
    rationale: list[str] = field(default_factory=list)
    intent: Optional[str] = None
    sentiment_user: Optional[Sentiment] = None
    symptom_tags: list[str] = field(default_factory=list)
    risk_level: Optional[RiskLevel] = None
    input_tokens: int = 0
    output_tokens: int = 0
    is_clarification: bool = False
    awaiting: Optional[str] = None              # "abc_screen" | "slot:<slot_id>" | None


# ── Pet vulnerability helpers ────────────────────────────────────────────────


def _pet_is_juvenile(pet: Optional[Pet]) -> bool:
    if pet is None:
        return False
    return getattr(pet, "stage", None) in (LifeStage.PUPPY, LifeStage.KITTEN)


def _pet_has_chronic_condition(pet: Optional[Pet], memory_context: str) -> bool:
    """Heuristic: scan memory_context for chronic condition markers.

    V0: keyword scan. V1: pull from PetMemory.long_term tags structurally.
    """
    if not memory_context:
        return False
    markers = (
        "diabetes", "cushing", "addison",
        "heart disease", "cardiomyopathy", "congestive heart",
        "epilepsy", "seizure history",
        "chronic kidney", "ckd",
        "ibd", "inflammatory bowel",
        "chronic pancreatitis",
        "糖尿病", "心脏病", "癫痫", "肾病", "慢性",
    )
    lowered = memory_context.lower()
    return any(m in lowered for m in markers)


# ── Locale detection ────────────────────────────────────────────────────────


def _detect_locale(text: str) -> str:
    """Crude language detection — Chinese chars present → zh, else en."""
    for ch in text:
        if "一" <= ch <= "鿿":
            return "zh"
    return "en"


# ── Main entry point ─────────────────────────────────────────────────────────


async def generate_response_v2(
    user: User,
    pet: Optional[Pet],
    dialogue_id: str,
    user_message: str,
    message_type: MessageType = MessageType.TEXT,
    session: Optional[dict[str, Any]] = None,
    raw_message_id: Optional[str] = None,
    dialogue_state: Optional[dict[str, Any]] = None,
) -> OrchestratorResultV2:
    """V2 orchestrator entry point.

    Args:
        dialogue_state: per-dialogue persisted state — used to resume
            mid-checklist or post-ABC. Schema:
                {
                    "awaiting": "abc_screen" | "slot:M3" | None,
                    "active_checklist": "CL-VOMIT-001" | None,
                    "collected": {"M1": "fresh_blood", ...},
                    "asked": ["M1", "M2"],
                    "rounds": 2,
                }
    """
    locale = _detect_locale(user_message)
    pet_id_str = str(pet.id) if pet else None

    update_trace(
        user_id=str(user.id),
        session_id=dialogue_id,
        tags=["v2-path", locale],
        metadata={"pet_id": pet_id_str},
    )
    update_span(input={"user_message": user_message})

    # ────────────────────────────────────────────────────────────────────────
    # FAST PATH — resume previously-paused conversation
    # ────────────────────────────────────────────────────────────────────────
    if dialogue_state and dialogue_state.get("awaiting") == "abc_screen":
        return _resume_abc(user_message, dialogue_state, locale)

    if dialogue_state and dialogue_state.get("awaiting", "").startswith("slot:"):
        return await _resume_slot_fill(
            user, pet, user_message, dialogue_state, locale,
        )

    # ────────────────────────────────────────────────────────────────────────
    # LAYER 1 (parallel) — gather all signals
    # ────────────────────────────────────────────────────────────────────────

    # 1a. Crisis gate — deterministic, highest priority
    crisis = crisis_gate.detect_crisis(user_message)

    # 1b. Rules engine — deterministic medical RED/ORANGE keywords
    rule_result = classify_by_rules(pet, user_message)

    # 1c. Load pet context (for memory-aware threshold + system prompt)
    ctx: dict = {}
    if pet:
        try:
            ctx = await load_pet_context(
                pet_id=pet_id_str,
                user_id=str(user.id),
                tier=session.get("tier") if session else None,
            )
        except Exception as exc:
            logger.warning("load_pet_context failed", error=str(exc))

    long_term = ctx.get("long_term_memories", [])
    mid_term = ctx.get("mid_term_memories", [])
    short_term = ctx.get("short_term_memories", [])
    recent_turns: list[dict] = ctx.get("recent_turns", [])
    daily_summary = ctx.get("daily_summary")
    pending = ctx.get("pending_confirmations", [])

    memory_context, pending_confirmation = build_context_block(
        pet=pet,
        long_term=long_term,
        mid_term=mid_term,
        short_term=short_term,
        recent_turns=recent_turns,
        daily_summary=daily_summary,
        pending=pending,
    )

    # 1d. Soft urgency (Python keyword scan)
    urgency_python = soft_urgency.soft_urgency_score(user_message)

    # 1e. LLM combined call — scenario scores + soft urgency + response_text
    llm_signals = await _call_llm_v2(
        user, pet, user_message, recent_turns, memory_context, pending_confirmation,
    )

    # Combine Python and LLM urgency scores — take max for safety
    urgency_score = max(urgency_python, llm_signals.get("urgency_soft_score", 0.0))

    # 1f. Checklist routing + pre-fire U-trigger scan
    intent_hint = llm_signals.get("intent")
    scenario_scores = llm_signals.get("scenario_scores", {})

    # In dev / shadow mode, allow unapproved checklists for plumbing testing.
    use_unapproved = bool(getattr(settings, "use_unapproved_checklists", False))

    # Pre-fire scan: if any checklist's U-trigger has a natural-language
    # phrase that matches the raw user message, escalate immediately.
    pre_fire = checklist_router.pre_fire_scan(
        user_message=user_message,
        use_unapproved=use_unapproved,
    )

    router_result = checklist_router.route(
        user_message=user_message,
        intent_hint=intent_hint,
        scenario_scores=scenario_scores,
        use_unapproved=use_unapproved,
    )

    # ────────────────────────────────────────────────────────────────────────
    # MERGE / VETO LAYER — pick branch
    # ────────────────────────────────────────────────────────────────────────
    decision = merge_decide(
        crisis=crisis,
        rule=rule_result,
        scenario_scores=scenario_scores,
        urgency_soft_score=urgency_score,
        router_checklist_id=router_result.checklist_id,
        router_confidence=router_result.confidence,
        pre_fire=pre_fire,
        pet_has_chronic_condition=_pet_has_chronic_condition(pet, memory_context),
        pet_is_juvenile=_pet_is_juvenile(pet),
    )

    logger.info(
        "merge decision",
        branch=decision.branch,
        checklist=decision.checklist_id,
        triage=decision.triage_level.value if decision.triage_level else None,
        rationale=decision.rationale,
    )

    # ────────────────────────────────────────────────────────────────────────
    # BRANCH DISPATCH
    # ────────────────────────────────────────────────────────────────────────
    if decision.branch == "crisis":
        return _branch_crisis(decision, crisis, locale, llm_signals)

    if decision.branch == "abc_screen":
        return _branch_abc_screen(decision, locale, llm_signals)

    if decision.branch == "checklist_prefire":
        return _branch_checklist_prefire(decision, locale, llm_signals)

    if decision.branch == "checklist":
        return await _branch_checklist(
            decision, user, pet, user_message, locale, llm_signals,
        )

    if decision.branch == "emotional":
        return _branch_emotional(decision, llm_signals)

    # general fallback
    return _branch_general(decision, llm_signals)


# ── LLM call (v2 schema) ─────────────────────────────────────────────────────


async def _call_llm_v2(
    user: User,
    pet: Optional[Pet],
    user_message: str,
    recent_turns: list[dict],
    memory_context: str,
    pending_confirmation: str,
) -> dict[str, Any]:
    tier = getattr(user, "subscription_tier", None)

    system = build_system_prompt(
        user=user,
        pet=pet,
        tier=tier,
        memory_context=memory_context,
        pending_confirmation=pending_confirmation,
    )
    # Append v2-specific instructions reinforcing the schema requirements.
    system += (
        "\n\n# Output Format (v2)\n"
        "You MUST return JSON conforming to the response schema. The "
        "response_text field is what the user sees — write it as natural prose. "
        "Do NOT include JSON, schema field names, or classifier labels in "
        "response_text. If the message is emotional or crisis, write the "
        "empathetic response in response_text — do not redirect to pet care."
    )

    messages = recent_turns + [{"role": "user", "content": user_message}]

    client = get_gemini_client()
    try:
        raw = await client.chat_structured_v2(
            system_prompt=system,
            messages=messages,
            response_schema=RESPONSE_SCHEMA_V2,
        )
    except Exception as exc:
        logger.error("v2 structured call failed", error=str(exc))
        raw = dict(DEFAULT_RESPONSE_V2)
        raw["input_tokens"] = 0
        raw["output_tokens"] = 0
        return raw

    # Defensive: ensure required fields exist
    for key, default in DEFAULT_RESPONSE_V2.items():
        raw.setdefault(key, default)
    return raw


# ── Branch implementations ──────────────────────────────────────────────────


def _branch_crisis(
    decision: MergeDecision,
    crisis_result,
    locale: str,
    llm_signals: dict,
) -> OrchestratorResultV2:
    severity = crisis_result.severity if crisis_result.matched else "critical"
    reply = crisis_gate.crisis_reply(severity, locale=locale)
    return OrchestratorResultV2(
        response_text=reply,
        branch="crisis",
        triage_level=TriageLevel.GREEN,
        rationale=decision.rationale,
        intent="crisis",
        sentiment_user=Sentiment.DISTRESSED if hasattr(Sentiment, "DISTRESSED") else None,
        input_tokens=int(llm_signals.get("input_tokens", 0)),
        output_tokens=int(llm_signals.get("output_tokens", 0)),
        is_clarification=False,
    )


def _branch_abc_screen(
    decision: MergeDecision,
    locale: str,
    llm_signals: dict,
) -> OrchestratorResultV2:
    question = abc_screen.abc_question(locale=locale)
    return OrchestratorResultV2(
        response_text=question,
        branch="abc_screen",
        triage_level=decision.triage_level,
        rationale=decision.rationale,
        is_clarification=True,
        awaiting="abc_screen",
        intent="symptom_report",
        input_tokens=int(llm_signals.get("input_tokens", 0)),
        output_tokens=int(llm_signals.get("output_tokens", 0)),
    )


def _branch_checklist_prefire(
    decision: MergeDecision,
    locale: str,
    llm_signals: dict,
) -> OrchestratorResultV2:
    """A pre-fire U-trigger fired on the user's first message.

    Render the matched trigger's escalation_template directly. Skip ABC and
    slot filling — the U-trigger's purpose is exactly this kind of
    deterministic immediate escalation.
    """
    spec = checklist_loader.get(decision.checklist_id)
    if spec is None:
        # Fallback to generic escalation if spec is missing
        from src.checklists.advice import render_escalation as _generic
        return OrchestratorResultV2(
            response_text=(
                "🚨 What you're describing needs an emergency vet now. "
                "Please go straight to the ER."
            ),
            branch="checklist",
            triage_level=TriageLevel.RED,
            rationale=decision.rationale,
            input_tokens=int(llm_signals.get("input_tokens", 0)),
            output_tokens=int(llm_signals.get("output_tokens", 0)),
        )

    return OrchestratorResultV2(
        response_text=checklist_advice.render_escalation(spec, locale=locale),
        branch="checklist",
        triage_level=TriageLevel.RED,
        checklist_id=decision.checklist_id,
        rationale=decision.rationale,
        input_tokens=int(llm_signals.get("input_tokens", 0)),
        output_tokens=int(llm_signals.get("output_tokens", 0)),
        is_clarification=False,
    )


async def _branch_checklist(
    decision: MergeDecision,
    user: User,
    pet: Optional[Pet],
    user_message: str,
    locale: str,
    llm_signals: dict,
) -> OrchestratorResultV2:
    checklist_id = decision.checklist_id
    if not checklist_id:
        # No specific checklist matched but merge layer wants medical path —
        # fall back to LLM response_text with appropriate triage chrome.
        return _branch_general(decision, llm_signals)

    spec = checklist_loader.get(checklist_id)
    if spec is None:
        logger.warning("checklist spec missing", checklist_id=checklist_id)
        return _branch_general(decision, llm_signals)

    # First turn in this checklist — collected slots empty.
    # Real implementation extracts initial slots from user_message via LLM
    # (see TODO below). V0 starts empty and asks first slot.
    collected: dict[str, Any] = {}
    asked: list[str] = []
    rounds = 0

    # TODO: extract initial slot values from user's first message using LLM.
    # E.g. "my dog vomited 3 times today, has yellow bile" should auto-fill
    # M1 (yellow_bile) and M2 (1_to_3_per_day). Skipped for V0 to keep this
    # commit reviewable.

    action = slot_filler.next_action(
        spec=spec,
        collected=collected,
        asked=asked,
        rounds=rounds,
        locale=locale,
    )

    if action.kind == "urgency_fire":
        reply = checklist_advice.render_escalation(spec, locale=locale)
        return OrchestratorResultV2(
            response_text=reply,
            branch="checklist",
            triage_level=TriageLevel.RED,
            checklist_id=checklist_id,
            rationale=decision.rationale + [
                f"checklist U-trigger fired: {action.fired_trigger.id}"
            ],
            input_tokens=int(llm_signals.get("input_tokens", 0)),
            output_tokens=int(llm_signals.get("output_tokens", 0)),
            is_clarification=False,
        )

    if action.kind == "ready_for_advice":
        reply = checklist_advice.render_advice(spec, collected, locale=locale)
        return OrchestratorResultV2(
            response_text=reply,
            branch="checklist",
            triage_level=decision.triage_level,
            checklist_id=checklist_id,
            rationale=decision.rationale,
            input_tokens=int(llm_signals.get("input_tokens", 0)),
            output_tokens=int(llm_signals.get("output_tokens", 0)),
        )

    # Default: ask the next slot
    return OrchestratorResultV2(
        response_text=action.next_question or "",
        branch="checklist",
        triage_level=decision.triage_level,
        checklist_id=checklist_id,
        rationale=decision.rationale,
        is_clarification=True,
        awaiting=f"slot:{action.next_slot_id}",
        input_tokens=int(llm_signals.get("input_tokens", 0)),
        output_tokens=int(llm_signals.get("output_tokens", 0)),
    )


def _branch_emotional(
    decision: MergeDecision,
    llm_signals: dict,
) -> OrchestratorResultV2:
    """Emotional support — use LLM's response_text directly, NO medical chrome."""
    return OrchestratorResultV2(
        response_text=llm_signals.get("response_text", "").strip(),
        branch="emotional",
        triage_level=TriageLevel.GREEN,
        rationale=decision.rationale,
        intent=llm_signals.get("intent"),
        symptom_tags=list(llm_signals.get("symptom_tags") or []),
        input_tokens=int(llm_signals.get("input_tokens", 0)),
        output_tokens=int(llm_signals.get("output_tokens", 0)),
        is_clarification=False,
    )


def _branch_general(
    decision: MergeDecision,
    llm_signals: dict,
) -> OrchestratorResultV2:
    """General chat / fallback — use LLM's response_text directly."""
    return OrchestratorResultV2(
        response_text=llm_signals.get("response_text", "").strip(),
        branch="general",
        triage_level=decision.triage_level,
        rationale=decision.rationale,
        intent=llm_signals.get("intent"),
        symptom_tags=list(llm_signals.get("symptom_tags") or []),
        input_tokens=int(llm_signals.get("input_tokens", 0)),
        output_tokens=int(llm_signals.get("output_tokens", 0)),
        is_clarification=False,
    )


# ── Resume handlers (mid-conversation continuation) ─────────────────────────


def _resume_abc(
    user_message: str,
    dialogue_state: dict[str, Any],
    locale: str,
) -> OrchestratorResultV2:
    """User just answered the ABC Screen — parse and decide next step."""
    abc_result = abc_screen.parse_abc_answer(user_message, locale=locale)

    if abc_result.escalate:
        # Any abnormal or ambiguous answer → escalate
        return OrchestratorResultV2(
            response_text=abc_screen.abc_escalation_reply(locale=locale),
            branch="abc_screen",
            triage_level=TriageLevel.RED,
            rationale=[f"ABC abnormal: {abc_result.overall}"],
            is_clarification=False,
            awaiting=None,
        )

    # All-normal ABC: clear pause, return to general chat (the original concern
    # was soft urgency, now ruled out as non-emergent).
    relief_en = (
        "Good — those are the most important basics, and they all sound okay. "
        "Tell me a bit more about what you're noticing, and we'll figure out the next step together."
    )
    relief_zh = (
        "好的 —— 这 3 个基础体征都正常,说明不是立刻危及生命的情况。"
        "再多告诉我一点你观察到的情况,我们一起判断下一步。"
    )
    return OrchestratorResultV2(
        response_text=relief_zh if locale.startswith("zh") else relief_en,
        branch="general",
        triage_level=TriageLevel.GREEN,
        rationale=["ABC all_normal"],
        is_clarification=True,
        awaiting=None,
    )


async def _resume_slot_fill(
    user: User,
    pet: Optional[Pet],
    user_message: str,
    dialogue_state: dict[str, Any],
    locale: str,
) -> OrchestratorResultV2:
    """User just answered a slot question — record value and ask next.

    V0: stores raw user text under the awaited slot ID. V1 should call a small
    LLM extraction to convert text to typed slot values matching the schema's
    options. That extraction is deliberately deferred to keep this commit
    reviewable — current behavior treats answers as text strings.
    """
    awaited = dialogue_state["awaiting"]
    slot_id = awaited.split(":", 1)[1]
    checklist_id = dialogue_state.get("active_checklist")
    if not checklist_id:
        return OrchestratorResultV2(
            response_text=user_message,
            branch="general",
            triage_level=TriageLevel.GREEN,
            rationale=["slot resume but no active_checklist"],
        )

    spec = checklist_loader.get(checklist_id)
    if spec is None:
        return OrchestratorResultV2(
            response_text="Sorry, I lost track of the conversation. Could you tell me what's going on again?",
            branch="general",
            triage_level=TriageLevel.GREEN,
            rationale=["checklist spec missing on resume"],
        )

    collected = dict(dialogue_state.get("collected") or {})
    asked = list(dialogue_state.get("asked") or [])
    rounds = int(dialogue_state.get("rounds") or 0) + 1

    # V0: store user's raw text. V1 will parse into typed slot value.
    collected[slot_id] = user_message.strip()
    if slot_id not in asked:
        asked.append(slot_id)

    action = slot_filler.next_action(
        spec=spec,
        collected=collected,
        asked=asked,
        rounds=rounds,
        locale=locale,
    )

    if action.kind == "urgency_fire":
        return OrchestratorResultV2(
            response_text=checklist_advice.render_escalation(spec, locale=locale),
            branch="checklist",
            triage_level=TriageLevel.RED,
            checklist_id=checklist_id,
            rationale=[f"U-trigger fired: {action.fired_trigger.id}"],
            is_clarification=False,
            awaiting=None,
        )

    if action.kind in ("ready_for_advice", "max_turns_reached"):
        return OrchestratorResultV2(
            response_text=checklist_advice.render_advice(spec, collected, locale=locale),
            branch="checklist",
            triage_level=TriageLevel.GREEN,
            checklist_id=checklist_id,
            rationale=[f"slot fill complete ({action.kind})"],
            is_clarification=False,
            awaiting=None,
        )

    return OrchestratorResultV2(
        response_text=action.next_question or "",
        branch="checklist",
        triage_level=TriageLevel.GREEN,
        checklist_id=checklist_id,
        rationale=["next slot"],
        is_clarification=True,
        awaiting=f"slot:{action.next_slot_id}",
    )
