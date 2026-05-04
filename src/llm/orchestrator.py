"""
LLM orchestration layer.

Public API consumed by bot handlers:
    generate_opening(user, pet, is_new_user, marketing_context) -> OrchestratorResult
    generate_response(user, pet, dialogue_id, user_message, ...)  -> OrchestratorResult

When USE_LANGGRAPH=true, generate_response() delegates to the LangGraph
pipeline (src/llm/graph/). Otherwise, it uses the classic sequential path.

generate_opening() always uses the classic path (no triage needed).
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select

from src.config import settings
from src.db.engine import get_session_factory
from src.db.models import (
    Dialogue,
    MessageType,
    Pet,
    RiskLevel,
    Sentiment,
    SubscriptionTier,
    TriageLevel,
    TriageRecord,
    User,
)
from src.llm.client import get_gemini_client
from src.llm.prompts.context import build_context_block
from src.llm.prompts.formatters import apply_response_format
from src.llm.prompts.system import build_system_prompt
from src.memory.reader import load_pet_context, load_related_memories
from src.observability.tracing import observe_span, update_span, update_trace
from src.triage.red_gate import should_fast_escape, verify_red
from src.triage.rules_engine import (
    classify_by_rules,
    compare_and_resolve,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Lazy-built graph to avoid circular import (graph.nodes imports from this module)
_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        from src.llm.graph import build_graph
        _graph = build_graph()
    return _graph


# ── Result type ───────────────────────────────────────────────────────────────


@dataclass
class OrchestratorResult:
    """Returned by both generate_response() and generate_opening()."""

    response_text: str
    triage_result: Optional[dict] = None       # {"rule", "llm", "final", "overridden", "matched_patterns", ...}
    intent: Optional[str] = None
    symptom_tags: list[str] = field(default_factory=list)
    risk_level: Optional[RiskLevel] = None
    sentiment_user: Optional[Sentiment] = None
    input_tokens: int = 0
    output_tokens: int = 0
    # True when this turn is a clarification question — caller skips the
    # RED visual chrome, the proactive follow-up scheduler, and the
    # TriageRecord write because the triage isn't finalised yet.
    is_clarification: bool = False


# ── Public entry points ───────────────────────────────────────────────────────


async def generate_opening(
    user: User,
    pet: Optional[Pet],
    is_new_user: bool,
    marketing_context: Optional[dict[str, str]],
    memory_context: str = "",
    proactive_context: Optional[dict] = None,
) -> OrchestratorResult:
    """
    Generate the /start greeting. Three cases:

    1. Pure new user (no pet) — warm onboarding explaining Pawly + prompt to create profile.
    2. Returning user after proactive follow-up — pick up naturally from the check-in.
    3. Returning user normal /start — personalised greeting using pet memory.
    """
    system = build_system_prompt(
        user=user,
        pet=pet,
        is_new_user=is_new_user,
        marketing_context=marketing_context,
        memory_context=memory_context,
    )

    # ── Case 1: pure new user ─────────────────────────────────────────────────
    if is_new_user or pet is None:
        parts = [
            "A brand new user has just opened Pawly for the first time. "
            "Write a warm, inviting 2–3 sentence intro as Pawly. "
            "Explain you're an AI pet care companion who helps with health questions, "
            "behavior, nutrition, and daily care. "
            "Tell them the first step is creating their pet's profile by tapping the button below. "
            "Be genuine — don't sound like marketing copy.",
        ]
        if marketing_context:
            th = marketing_context.get("theme", "")
            if th:
                parts.append(f"Their interest area is '{th}' — weave that in naturally.")

    # ── Case 2: returning user coming back after a proactive follow-up ────────
    elif proactive_context:
        pet_name = proactive_context.get("pet_name", pet.name)
        triage = proactive_context.get("triage_level", "").upper()
        symptoms = proactive_context.get("symptom_tags", [])
        sent_text = proactive_context.get("message_text", "")
        symptom_str = ", ".join(symptoms) if symptoms else "the health concern"
        urgency = "urgent situation" if triage == "RED" else "health concern"
        parts = [
            f"You recently sent this follow-up to the owner of {pet_name}: \"{sent_text}\"",
            f"They've now opened the chat. Warmly ask how {pet_name} is doing "
            f"with the {urgency} ({symptom_str}). "
            f"1–2 sentences only — don't repeat medical advice.",
        ]

    # ── Case 3: returning user normal /start ──────────────────────────────────
    else:
        pet_name = pet.name
        species = pet.species.value
        parts = [
            f"Welcome back the owner of {pet_name} the {species}. "
            f"Be warm and personal — always use {pet_name}'s name. "
            f"If there's memory context, reference something specific: "
            f"a recent symptom, an ongoing concern, or a positive development. "
            f"1–2 sentences. Don't just say 'welcome back' generically.",
        ]
        if marketing_context:
            ch = marketing_context.get("channel", "")
            if ch:
                parts.append(f"The user came from the '{ch}' channel.")

    user_prompt = " ".join(parts)

    client = get_gemini_client()
    try:
        raw = await client.chat(
            system_prompt=system,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=256,
            temperature=0.8,
        )
        text = raw["text"]
        in_tok = raw["input_tokens"]
        out_tok = raw["output_tokens"]
    except Exception as exc:
        logger.error("generate_opening failed", error=str(exc))
        if is_new_user or pet is None:
            text = (
                "Hi! I'm Pawly, your AI pet care companion — here to help with "
                "your pet's health, behavior, and daily care. "
                "Tap the button below to create your pet's profile and get started! 🐾"
            )
        else:
            text = f"Hey, great to see you! How is {pet.name} doing today?"
        in_tok = out_tok = 0

    return OrchestratorResult(
        response_text=text,
        input_tokens=in_tok,
        output_tokens=out_tok,
    )


async def generate_response(
    user: User,
    pet: Optional[Pet],
    dialogue_id: str,
    user_message: str,
    message_type: MessageType = MessageType.TEXT,
    session: Optional[dict[str, Any]] = None,
    raw_message_id: Optional[str] = None,
) -> OrchestratorResult:
    """
    Generate a response to a user message.

    When USE_LANGGRAPH=true, delegates to the LangGraph pipeline.
    Otherwise, uses the classic sequential orchestration path.
    """
    if settings.use_langgraph:
        return await _generate_response_graph(
            user, pet, dialogue_id, user_message, message_type, session,
        )
    return await _generate_response_classic(
        user, pet, dialogue_id, user_message, message_type, session, raw_message_id,
    )


# ── LangGraph path (USE_LANGGRAPH=true) ──────────────────────────────────────


async def _generate_response_graph(
    user: User,
    pet: Optional[Pet],
    dialogue_id: str,
    user_message: str,
    message_type: MessageType,
    session: Optional[dict[str, Any]],
) -> OrchestratorResult:
    """Delegate to the LangGraph pipeline with structured LLM output."""
    initial_state = {
        "user": user,
        "pet": pet,
        "user_message": user_message,
        "message_type": message_type,
        "session": session or {},
        "dialogue_id": dialogue_id,
    }

    try:
        final_state = await _get_graph().ainvoke(initial_state)
    except Exception as exc:
        logger.error("graph pipeline failed", error=str(exc))
        return OrchestratorResult(
            response_text="I'm having trouble connecting right now. Please try again in a moment.",
        )

    triage_result = {
        "rule": final_state.get("rule_triage", TriageLevel.GREEN).value,
        "llm": final_state["llm_triage"].value if final_state.get("llm_triage") else None,
        "final": final_state.get("final_triage", TriageLevel.GREEN).value,
        "overridden": final_state.get("triage_overridden", False),
        "override_direction": final_state.get("override_direction", ""),
        "matched_patterns": final_state.get("matched_patterns", []),
        "confidence": 0.95 if final_state.get("matched_patterns") else 0.5,
    }

    return OrchestratorResult(
        response_text=final_state.get("response_text", ""),
        triage_result=triage_result,
        intent=final_state.get("intent"),
        symptom_tags=final_state.get("symptom_tags", []),
        risk_level=final_state.get("risk_level"),
        sentiment_user=final_state.get("sentiment"),
        input_tokens=final_state.get("input_tokens", 0),
        output_tokens=final_state.get("output_tokens", 0),
    )


# ── Classic path (USE_LANGGRAPH=false, default) ──────────────────────────────


@observe_span(name="classic-orchestrator")
async def _generate_response_classic(
    user: User,
    pet: Optional[Pet],
    dialogue_id: str,
    user_message: str,
    message_type: MessageType = MessageType.TEXT,
    session: Optional[dict[str, Any]] = None,
    raw_message_id: Optional[str] = None,
) -> OrchestratorResult:
    """
    Classic sequential orchestration with the v2 confidence loop:

        1. Load pet context + memory
        2. Call chat_structured → response_text + triage_level + confidence
           + clarification_question + intent + sentiment + symptom_tags
        3. Run rules engine; resolve final triage (max severity)
        4. Branch on the resolved triage:
             a. Fast-escape (rules matched a critical RED pattern) →
                return as-is, RED is final, skip the gate.
             b. Final = RED, gate enabled, no fast-escape → run red_gate.
                If gate confirms → use its response_text + citation.
                If gate downgrades → return its clarification_question
                as a clarification turn.
             c. Confidence below threshold + round budget remaining →
                return clarification_question as a clarification turn.
             d. Otherwise finalise with the structured response_text.
        5. Persist clarification round/state on the Dialogue row.
        6. Apply visual chrome only on finalised turns.
    """
    tier = _tier(user)
    pet_id_str = str(pet.id) if pet else None
    is_health = looks_like_health_query(user_message)

    update_trace(
        user_id=str(user.id),
        session_id=dialogue_id,
        tags=[tier.value, "classic-path"],
        metadata={
            "pet_id": pet_id_str,
            "pet_name": pet.name if pet else None,
            "subscription_tier": tier.value,
        },
    )
    update_span(
        input={"user_message": user_message},
        metadata={
            "message_type": message_type.value,
            "is_health_query": is_health,
        },
    )

    # ── 1. LOAD CONTEXT ───────────────────────────────────────────────────────
    ctx: dict = {}
    if pet:
        try:
            ctx = await load_pet_context(
                pet_id=pet_id_str,  # type: ignore[arg-type]
                user_id=str(user.id),
                tier=tier,
            )
        except Exception as exc:
            logger.warning("load_pet_context failed", error=str(exc))

        if is_health:
            try:
                related = await load_related_memories(pet_id_str, user_message)  # type: ignore[arg-type]
                existing_ids = {m.id for m in ctx.get("short_term_memories", [])}
                ctx.setdefault("short_term_memories", []).extend(
                    m for m in related if m.id not in existing_ids
                )
            except Exception as exc:
                logger.warning("load_related_memories failed", error=str(exc))

    long_term = ctx.get("long_term_memories", [])
    mid_term = ctx.get("mid_term_memories", [])
    short_term = ctx.get("short_term_memories", [])
    recent_turns: list[dict] = ctx.get("recent_turns", [])
    daily_summary = ctx.get("daily_summary")
    pending = ctx.get("pending_confirmations", [])

    # Existing clarification round count for this dialogue
    prior_round = await _load_clarification_round(dialogue_id)

    # ── 2. BUILD SYSTEM PROMPT ────────────────────────────────────────────────
    memory_context, pending_confirmation = build_context_block(
        pet=pet,  # type: ignore[arg-type]
        long_term=long_term,
        mid_term=mid_term,
        short_term=short_term,
        recent_turns=recent_turns,
        daily_summary=daily_summary,
        pending=pending,
    )

    system = build_system_prompt(
        user=user,
        pet=pet,
        tier=tier,
        memory_context=memory_context,
        pending_confirmation=pending_confirmation,
        marketing_context=(session or {}).get("marketing_context"),
    )

    # ── 3. BUILD MESSAGES ARRAY ───────────────────────────────────────────────
    messages = recent_turns + [{"role": "user", "content": user_message}]

    # ── 4. CALL GEMINI (structured) ───────────────────────────────────────────
    client = get_gemini_client()
    in_tok = out_tok = 0
    try:
        raw = await client.chat_structured(system_prompt=system, messages=messages)
        response_text = (raw.get("response_text") or "").strip()
        confidence = float(raw.get("confidence") or 0.0)
        clarification_question = (raw.get("clarification_question") or "").strip()
        missing_info = list(raw.get("missing_info") or [])
        llm_triage_str = raw.get("triage_level")
        llm_triage = (
            TriageLevel(llm_triage_str.lower()) if isinstance(llm_triage_str, str) else None
        )
        intent = raw.get("intent") or detect_intent(user_message)
        sentiment_str = raw.get("sentiment")
        sentiment = (
            Sentiment(sentiment_str.lower()) if isinstance(sentiment_str, str) else detect_sentiment(user_message)
        )
        symptom_tags = list(raw.get("symptom_tags") or [])
        in_tok = int(raw.get("input_tokens") or 0)
        out_tok = int(raw.get("output_tokens") or 0)
    except Exception as exc:
        logger.error("structured llm call failed", error=str(exc))
        response_text = (
            "I'm having trouble connecting right now. Please try again in a moment."
        )
        confidence = 0.0
        clarification_question = ""
        missing_info = []
        llm_triage = None
        intent = detect_intent(user_message)
        sentiment = detect_sentiment(user_message)
        symptom_tags = []

    # ── 5. POST-PROCESS TRIAGE ────────────────────────────────────────────────
    rule_result = classify_by_rules(pet, user_message)
    resolved = compare_and_resolve(llm_triage, rule_result.classification)

    # Merge symptom keywords from rule engine
    symptom_tags = sorted({*symptom_tags, *extract_symptom_keywords(user_message, rule_result.matched_patterns)})

    fast_escape = should_fast_escape(rule_result.matched_rules)

    is_clarification = False
    citation = ""
    matched_scenario = ""
    gate_ran = False
    final_triage = resolved.final_classification

    # ── 5a. RED branch: fast-escape vs Red gate vs gate-clarify ───────────────
    if final_triage == TriageLevel.RED and not fast_escape and settings.red_gate_enabled:
        gate_ran = True
        gate = await verify_red(
            pet=pet,
            user_message=user_message,
            recent_turns=recent_turns,
            memory_context=memory_context,
            matched_rules=rule_result.matched_rules,
        )
        in_tok += gate.input_tokens
        out_tok += gate.output_tokens
        citation = gate.citation
        matched_scenario = gate.matched_scenario

        if gate.confirmed_red:
            # Replace LLM body with the gate's grounded response
            if gate.response_text:
                response_text = gate.response_text
            # final_triage stays RED
        elif gate.clarification_question and prior_round < settings.clarification_max_rounds:
            # Gate asked for one more piece of info before committing to RED.
            # Treat as a clarification turn at the next-lower (Orange) tier so
            # we don't slap RED chrome onto a question.
            response_text = gate.clarification_question
            final_triage = TriageLevel.ORANGE
            is_clarification = True
        else:
            # Gate said not RED but we've exhausted the round budget — fall
            # back to the LLM's structured response_text at Orange.
            final_triage = TriageLevel.ORANGE
            if gate.response_text:
                response_text = gate.response_text

    # ── 5b. Non-RED clarification: confidence-driven loop ─────────────────────
    elif (
        not is_clarification
        and clarification_question
        and confidence < settings.clarification_threshold
        and prior_round < settings.clarification_max_rounds
        and not fast_escape
    ):
        response_text = clarification_question
        is_clarification = True

    # ── 5c. Persist clarification state on the Dialogue ───────────────────────
    new_round = (prior_round + 1) if is_clarification else 0
    new_state = _build_clarification_state(
        prior_round=prior_round,
        is_clarification=is_clarification,
        question=clarification_question if is_clarification else "",
        missing_info=missing_info,
        triage=final_triage,
        confidence=confidence,
    )
    try:
        await _save_clarification_state(dialogue_id, new_round, new_state)
    except Exception as exc:
        logger.warning("save_clarification_state failed", error=str(exc))

    # ── 6. Apply visual chrome — finalised turns only ─────────────────────────
    if not is_clarification:
        response_text = apply_response_format(response_text, final_triage)
        if citation and final_triage == TriageLevel.RED:
            # Append the source name on confirmed-RED turns. We add it after
            # the formatter so it sits below the closing footer.
            response_text = f"{response_text}\n\n<i>Reference: {citation}</i>"

    triage_result = {
        "rule": rule_result.classification.value,
        "llm": llm_triage.value if llm_triage else None,
        "final": final_triage.value,
        "overridden": resolved.overridden,
        "override_direction": resolved.override_direction,
        "matched_patterns": rule_result.matched_rules,
        "confidence": confidence,
        "is_clarification": is_clarification,
        "clarification_round": new_round,
        "missing_info": missing_info,
        "fast_escape": fast_escape,
        "red_gate_ran": gate_ran,
        "matched_scenario": matched_scenario,
        "citation": citation,
    }

    risk_level = map_triage_to_risk(final_triage)

    # Persist TriageRecord only on finalised non-GREEN outcomes — clarification
    # turns aren't a final classification.
    if (
        pet
        and not is_clarification
        and (is_health or final_triage != TriageLevel.GREEN)
    ):
        try:
            await _store_triage_record(
                pet_id=pet.id,
                message_id=raw_message_id,
                triage=triage_result,
                user_message=user_message,
            )
        except Exception as exc:
            logger.warning("store_triage_record failed", error=str(exc))

    update_span(
        output={"response_text": response_text},
        metadata={
            "triage_final": triage_result["final"],
            "triage_overridden": triage_result["overridden"],
            "is_clarification": is_clarification,
            "clarification_round": new_round,
            "confidence": confidence,
            "fast_escape": fast_escape,
            "red_gate_ran": gate_ran,
            "intent": intent,
            "symptom_tags": symptom_tags,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
        },
    )

    return OrchestratorResult(
        response_text=response_text,
        triage_result=triage_result,
        intent=intent,
        symptom_tags=symptom_tags,
        risk_level=risk_level,
        sentiment_user=sentiment,
        input_tokens=in_tok,
        output_tokens=out_tok,
        is_clarification=is_clarification,
    )


# ── Helper functions (kept for backward compat + generate_opening) ───────────


def looks_like_health_query(text: str) -> bool:
    """Return True if the message appears to be a health / symptom concern."""
    health_words = (
        "sick", "vomit", "diarrhea", "blood", "limp", "pain", "hurt",
        "fever", "sneeze", "cough", "lethargic", "not eating", "not drinking",
        "swollen", "wound", "scratch", "discharge", "seizure", "collapse",
        "breathing", "unconscious", "bleed",
    )
    lower = text.lower()
    return any(w in lower for w in health_words)


def detect_intent(text: str) -> Optional[str]:
    """Classify user message into a coarse intent bucket."""
    lower = text.lower()
    if any(w in lower for w in ("vomit", "blood", "limp", "sick", "hurt", "pain",
                                 "sneez", "cough", "fever", "letharg", "bleed",
                                 "seizu", "collaps", "unconscious")):
        return "symptom_report"
    if any(w in lower for w in ("eat", "food", "drink", "diet", "treat", "fed",
                                 "nutrition", "kibble", "wet food")):
        return "nutrition"
    if any(w in lower for w in ("walk", "exercise", "run", "play", "active", "energy")):
        return "exercise"
    if any(w in lower for w in ("groom", "bath", "brush", "nail", "fur", "coat", "shed")):
        return "grooming"
    if any(w in lower for w in ("what", "how", "why", "when", "can", "should", "?")):
        return "question"
    return None


def detect_sentiment(text: str) -> Optional[Sentiment]:
    """Infer owner's emotional state from message text."""
    lower = text.lower()
    panic_words = (
        "emergency", "dying", "dead", "help!", "please help", "oh no",
        "scared", "terrified", "panicking", "rushed",
    )
    anxious_words = (
        "worried", "concern", "not sure", "should i", "is this normal",
        "anxious", "nervous", "stressed", "afraid",
    )
    if any(w in lower for w in panic_words):
        return Sentiment.PANIC
    if any(w in lower for w in anxious_words):
        return Sentiment.ANXIOUS
    return Sentiment.CALM


def extract_symptom_keywords(
    text: str,
    matched_patterns: list[str],
) -> list[str]:
    """
    Combine rule-engine matched patterns with simple keyword extraction.

    Returns a deduplicated list of symptom strings.
    """
    keywords: set[str] = set(matched_patterns)
    symptom_words = (
        "vomiting", "diarrhea", "lethargy", "limping", "sneezing", "coughing",
        "bleeding", "seizure", "fever", "swelling", "discharge", "pain",
        "scratching", "itching", "weight loss", "not eating", "not drinking",
    )
    lower = text.lower()
    for word in symptom_words:
        if word in lower:
            keywords.add(word)
    return sorted(keywords)


def _tier(user: User) -> SubscriptionTier:
    """Return the user's subscription tier, defaulting to NEW_FREE."""
    return getattr(user, "subscription_tier", SubscriptionTier.NEW_FREE)


def map_triage_to_risk(level: TriageLevel) -> Optional[RiskLevel]:
    """Convert resolved TriageLevel to RiskLevel for DB storage."""
    mapping = {
        TriageLevel.RED: RiskLevel.HIGH,
        TriageLevel.ORANGE: RiskLevel.MED,
        TriageLevel.GREEN: RiskLevel.LOW,
    }
    return mapping.get(level)


async def generate_followup_message(
    pet_name: str,
    pet_species: str,
    triage_level: str,
    symptom_tags: list[str],
) -> str:
    """Generate a short proactive check-in for a RED/ORANGE triage conversation."""
    hours = 2 if triage_level.lower() == "red" else 4
    urgency = "urgent" if triage_level.lower() == "red" else "concerning"
    symptoms_str = ", ".join(symptom_tags) if symptom_tags else "health concerns"

    prompt = (
        f"You are following up {hours} hours after advising the owner of {pet_name} "
        f"({pet_species}) about {symptoms_str}, which you classified as {urgency}. "
        f"Write ONE warm, caring message (1-2 sentences) asking how {pet_name} is doing. "
        f"Do not repeat medical advice. Be genuine and natural, not formulaic. "
        f"{'No emoji — the situation was serious.' if triage_level.lower() == 'red' else 'One emoji is fine.'}"
    )

    client = get_gemini_client()
    raw = await client.chat(
        system_prompt=(
            "You are Pawly, an AI pet care assistant. "
            "Output only the follow-up message text — no preamble, no quotes."
        ),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=120,
        temperature=0.7,
    )
    return raw["text"].strip()


async def _load_clarification_round(dialogue_id: Optional[str]) -> int:
    """Look up the dialogue's current clarification_round (0 if missing)."""
    if not dialogue_id:
        return 0
    try:
        dialogue_uuid = uuid.UUID(dialogue_id)
    except (ValueError, TypeError):
        return 0
    factory = get_session_factory()
    async with factory() as db:
        row = await db.execute(
            select(Dialogue.clarification_round).where(Dialogue.id == dialogue_uuid)
        )
        value = row.scalar_one_or_none()
    return int(value) if value is not None else 0


async def _save_clarification_state(
    dialogue_id: Optional[str],
    new_round: int,
    new_state: dict,
) -> None:
    """Persist the new round count + state JSON onto the Dialogue row."""
    if not dialogue_id:
        return
    try:
        dialogue_uuid = uuid.UUID(dialogue_id)
    except (ValueError, TypeError):
        return
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(Dialogue).where(Dialogue.id == dialogue_uuid)
        )
        dialogue = result.scalar_one_or_none()
        if dialogue is None:
            return
        dialogue.clarification_round = new_round
        dialogue.clarification_state = new_state
        await db.commit()


def _build_clarification_state(
    prior_round: int,
    is_clarification: bool,
    question: str,
    missing_info: list[str],
    triage: TriageLevel,
    confidence: float,
) -> dict:
    """Compose the JSONB blob written to Dialogue.clarification_state."""
    return {
        "prior_round": prior_round,
        "is_clarification": is_clarification,
        "last_question": question,
        "last_missing_info": missing_info,
        "last_triage": triage.value,
        "last_confidence": round(float(confidence), 3),
    }


async def _store_triage_record(
    pet_id: uuid.UUID,
    message_id: Optional[str],
    triage: dict,
    user_message: str,
) -> None:
    """Persist a TriageRecord to the database (fire-and-forget, errors are logged)."""
    from src.db.engine import get_session_factory

    final_str = triage.get("final", "green")
    rule_str = triage.get("rule", "green")
    llm_str = triage.get("llm")

    final_level = TriageLevel(final_str) if final_str else TriageLevel.GREEN
    rule_level = TriageLevel(rule_str) if rule_str else TriageLevel.GREEN
    llm_level = TriageLevel(llm_str) if llm_str else TriageLevel.GREEN

    record = TriageRecord(
        pet_id=str(pet_id),
        message_id=message_id or str(uuid.uuid4()),
        llm_classification=llm_level,
        rule_classification=rule_level,
        final_classification=final_level,
        symptoms={
            "matched": triage.get("matched_patterns", []),
            "text_excerpt": user_message[:500],
        },
    )

    factory = get_session_factory()
    async with factory() as db:
        db.add(record)
        await db.commit()
