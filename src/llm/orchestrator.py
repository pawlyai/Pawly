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

from src.config import settings
from src.db.models import (
    MessageType,
    Pet,
    RiskLevel,
    Sentiment,
    SubscriptionTier,
    TriageLevel,
    TriageRecord,
    User,
)
from src.llm.prompts.context import build_context_block
from src.llm.prompts.formatters import apply_response_format, prepend_safety_banner
from src.llm.prompts.system import build_system_prompt
from src.llm.providers import get_chat_client
from src.llm.retrievers import (
    build_retrieval_context,
    format_followups,
    format_special_rules,
    match_followups,
    match_red_flags,
)
from src.memory.reader import load_pet_context, load_related_memories
from src.observability.tracing import observe_span, update_span, update_trace
from src.triage.rules_engine import (
    audit_log_triage_divergence,
    classify_by_rules,
    compare_and_resolve,
    detect_triage_from_response,
    get_red_floor,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _active_chat_model() -> str:
    """Resolve the model to send chat traffic to.

    ``settings.chat_model`` opts production into a non-Gemini provider
    (e.g. ``deepseek-v4``). When unset, fall back to ``main_model`` so
    behaviour is identical to the previous Gemini-only path.
    """
    return settings.chat_model or settings.main_model


# Mirror of src/llm/graph/nodes.py::_parse_triage_level so both paths
# normalise the LLM's structured triage_level string the same way.
_STRUCTURED_TRIAGE_MAP = {
    "RED": TriageLevel.RED,
    "ORANGE": TriageLevel.ORANGE,
    "GREEN": TriageLevel.GREEN,
}

# DeepSeek sometimes emits a punctuation-only stub ("...", "…") when it is
# conflicted about a compliance boundary. Any response this short is not
# useful; treat it as a generation failure so we can retry on the plain path.
_STUB_RESPONSES: frozenset[str] = frozenset({"...", "…", ".", "..", "?", "!", ","})
_STUB_MIN_LEN = 5


def _parse_structured_triage(raw: Any) -> Optional[TriageLevel]:
    if not isinstance(raw, str) or not raw.strip():
        return None
    return _STRUCTURED_TRIAGE_MAP.get(raw.strip().upper())

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
    triage_result: Optional[dict] = None       # {"rule", "llm", "final", "overridden", "matched_patterns"}
    intent: Optional[str] = None
    symptom_tags: list[str] = field(default_factory=list)
    risk_level: Optional[RiskLevel] = None
    sentiment_user: Optional[Sentiment] = None
    input_tokens: int = 0
    output_tokens: int = 0


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

    chat_model = _active_chat_model()
    client = get_chat_client(chat_model)
    try:
        raw = await client.chat(
            system_prompt=system,
            messages=[{"role": "user", "content": user_prompt}],
            model=chat_model,
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
    """Original sequential orchestration — proven stable path."""
    tier = _tier(user)
    pet_id_str = str(pet.id) if pet else None
    is_health = looks_like_health_query(user_message)

    # user_id/session_id/tags belong on the trace in v2 SDK
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

    retrieval_ctx = build_retrieval_context(recent_turns, user_message)
    followups = match_followups(retrieval_ctx)
    red_flags = match_red_flags(retrieval_ctx)

    system = build_system_prompt(
        user=user,
        pet=pet,
        tier=tier,
        memory_context=memory_context,
        pending_confirmation=pending_confirmation,
        marketing_context=(session or {}).get("marketing_context"),
        retrieved_followups=format_followups(followups),
        special_scenarios=format_special_rules(red_flags),
    )

    # ── 3. BUILD MESSAGES ARRAY ───────────────────────────────────────────────
    messages = recent_turns + [{"role": "user", "content": user_message}]

    # ── 4. CALL CHAT MODEL ────────────────────────────────────────────────────
    # Try chat_structured first so the LLM can emit an authoritative
    # triage_level alongside the response text. If that path fails (DeepSeek
    # in particular sometimes returns malformed JSON when constrained to a
    # response_format=json_object schema, see providers_deepseek.py:117 — a
    # raw json.loads with no exception handling) we degrade gracefully to
    # plain chat() and rely on the rule engine alone for triage. Same
    # fallback message of last resort if both paths fail.
    chat_model = _active_chat_model()
    client = get_chat_client(chat_model)
    structured_triage: Optional[TriageLevel] = None
    response_text = ""
    in_tok = 0
    out_tok = 0

    try:
        raw = await client.chat_structured(
            system_prompt=system, messages=messages, model=chat_model
        )
        response_text = (raw.get("response_text") or "").strip()
        in_tok = raw.get("input_tokens", 0)
        out_tok = raw.get("output_tokens", 0)
        structured_triage = _parse_structured_triage(raw.get("triage_level"))
        if not response_text or response_text in _STUB_RESPONSES or len(response_text) < _STUB_MIN_LEN:
            # JSON parsed but response_text was empty or a punctuation stub
            # ("...") — model put everything in metadata or hit a compliance
            # conflict. Fall through to the plain chat() retry below.
            raise ValueError(f"chat_structured returned degenerate response_text: {response_text!r}")
    except Exception as exc:
        logger.warning(
            "chat_structured failed - falling back to plain chat",
            error=str(exc),
            chat_model=chat_model,
        )
        try:
            raw = await client.chat(
                system_prompt=system, messages=messages, model=chat_model
            )
            response_text = raw.get("text", "")
            if not response_text or response_text.strip() in _STUB_RESPONSES or len(response_text.strip()) < _STUB_MIN_LEN:
                raise ValueError(f"plain chat also returned degenerate response: {response_text!r}")
            response_text = response_text.strip()
            in_tok = raw.get("input_tokens", 0)
            out_tok = raw.get("output_tokens", 0)
            # No structured signal available on the fallback path; the
            # resolver will rely on rule_classification alone (which is the
            # safety floor anyway).
            structured_triage = None
        except Exception as exc2:
            logger.error("plain chat fallback also failed", error=str(exc2))
            response_text = (
                "I'm having trouble connecting right now. Please try again in a moment."
            )
            in_tok = 0
            out_tok = 0

    # ── 5. POST-PROCESS TRIAGE ────────────────────────────────────────────────
    # Carry forward a conversation-level RED state via the rule engine: if a
    # recent assistant turn flagged 🔴 Urgent and the user hasn't signalled
    # resolution, classify_by_rules floors this turn's result to RED. The LLM
    # path is unchanged — banner persistence is purely a rule_engine concern.
    context_floor = get_red_floor(recent_turns)
    rule_result = classify_by_rules(pet, user_message, context_floor=context_floor)
    # llm_triage is now sourced from the LLM's own structured output
    # (triage_level field in the JSON response). detect_triage_from_response
    # is still called below for telemetry — its substring scan can disagree
    # with the structured signal, which is a useful diagnostic — but it
    # never influences the resolved classification or the override decision.
    llm_triage = structured_triage
    response_keyword_triage = detect_triage_from_response(response_text)
    resolved = compare_and_resolve(llm_triage, rule_result.classification)

    # Safety-banner override (replaces the v1 LLM re-call path).
    #
    # When the rule engine — scanning the user's message — escalates to RED
    # but the LLM under-triaged, we prepend a deterministic safety banner to
    # the LLM's existing response instead of regenerating with a CRITICAL
    # OVERRIDE system prompt. Three reasons:
    #
    #   1. The LLM's contextual reasoning (pet name, individual details,
    #      tailored care advice) is preserved verbatim — re-generation would
    #      throw all of that away.
    #   2. A second LLM call doubles the cost and latency of the override
    #      path; the banner is constructed in Python from `matched_rules`.
    #   3. The banner is deterministic — it always names the exact triggers
    #      that fired, so users see a specific reason ("suspected toxin
    #      ingestion") rather than a generic "this is urgent" rewrite.
    rule_red_with_llm_under = (
        rule_result.classification == TriageLevel.RED
        and llm_triage != TriageLevel.RED
    )
    if rule_red_with_llm_under:
        response_text = prepend_safety_banner(response_text, rule_result.matched_rules)
        logger.warning(
            "triage RED safety banner prepended",
            pet_id=pet_id_str,
            rule=rule_result.classification.value,
            llm=llm_triage.value if llm_triage else None,
            matched=rule_result.matched_rules,
        )

    # Emit a structured log line whenever the three triage sources diverge.
    # This is the productive use of the deprecated `detect_triage_from_response`
    # audit signal — surface offline review opportunities without letting
    # them drive any user-visible behaviour.
    audit_log_triage_divergence(
        pet_id=pet_id_str,
        structured_triage=structured_triage,
        rule_classification=rule_result.classification,
        response_keyword_triage=response_keyword_triage,
        matched_rules=rule_result.matched_rules,
        logger_=logger,
    )

    # Visual format uses the resolved classification (stricter of rule + LLM
    # structured). The old comment about response-keyword leakage no longer
    # applies: compare_and_resolve only takes llm_triage (structured JSON field)
    # and rule_result; detect_triage_from_response is audit-only and never
    # reaches resolved.final_classification.
    effective_triage = resolved.final_classification
    response_text = apply_response_format(response_text, effective_triage)

    triage_result = {
        "rule": rule_result.classification.value,
        # LLM's own triage from structured output — authoritative LLM signal.
        "llm": llm_triage.value if llm_triage else None,
        # Audit-only: substring-scan of the LLM's reply. Useful for spotting
        # cases where the LLM's wording disagreed with its structured triage
        # (or the rule engine), but not part of the decision graph.
        "llm_response_keywords": (
            response_keyword_triage.value if response_keyword_triage else None
        ),
        "final": effective_triage.value,
        "overridden": resolved.overridden,
        "override_direction": resolved.override_direction,
        "matched_patterns": rule_result.matched_rules,
        "confidence": rule_result.confidence,
        "score": getattr(rule_result, "score", 0.0),
    }

    risk_level = map_triage_to_risk(effective_triage)

    # Persist triage record for non-GREEN outcomes (or health queries)
    if pet and (is_health or effective_triage != TriageLevel.GREEN):
        try:
            await _store_triage_record(
                pet_id=pet.id,
                message_id=raw_message_id,
                triage=triage_result,
                user_message=user_message,
            )
        except Exception as exc:
            logger.warning("store_triage_record failed", error=str(exc))

    # ── 6. DETECT INTENT + SENTIMENT + SYMPTOMS ───────────────────────────────
    intent = detect_intent(user_message)
    sentiment = detect_sentiment(user_message)
    symptom_tags = extract_symptom_keywords(user_message, rule_result.matched_patterns)

    update_span(
        output={"response_text": response_text},
        metadata={
            "triage_final": triage_result["final"],
            "triage_overridden": triage_result["overridden"],
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

    chat_model = _active_chat_model()
    client = get_chat_client(chat_model)
    raw = await client.chat(
        system_prompt=(
            "You are Pawly, an AI pet care assistant. "
            "Output only the follow-up message text — no preamble, no quotes."
        ),
        messages=[{"role": "user", "content": prompt}],
        model=chat_model,
        max_tokens=120,
        temperature=0.7,
    )
    return raw["text"].strip()


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
