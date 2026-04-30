"""
LLM-based agent memory extraction.

Extracts structured interaction preferences and relationship facts from a
conversation turn. These facts describe how the AI agent should communicate
with this specific user — not facts about the pet's health.

Public API:
    AgentMemoryProposal     — dataclass returned by extract_agent_memories()
    AGENT_EXTRACTION_PROMPT — module-level string, editable without touching logic
    extract_agent_memories(raw_messages, user_id, existing_memories)
        -> list[AgentMemoryProposal]
"""

import json
from dataclasses import dataclass
from typing import Any

from src.db.models import AgentMemory, AgentMemoryCategory, AgentMemoryScope
from src.llm.client import get_gemini_client
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ── Result type ───────────────────────────────────────────────────────────────


@dataclass
class AgentMemoryProposal:
    """A single extracted agent-level insight, ready for committing."""

    field: str
    value: Any
    confidence: float
    source_quote: str
    category: AgentMemoryCategory
    scope: AgentMemoryScope


# ══════════════════════════════════════════════════════════════════════════════
# EDITABLE EXTRACTION PROMPT
# Edit this string to change what agent-level facts are extracted.
# Do not touch extract_agent_memories() unless you need to change parsing logic.
# ══════════════════════════════════════════════════════════════════════════════

AGENT_EXTRACTION_PROMPT = """\
You are an interaction-pattern analyser for a pet care AI assistant.
Given a conversation between a user and the assistant, extract NEW facts about
how the user prefers to interact — communication style, emotional state, and
relationship patterns. Do NOT extract facts about the pet's health.

Already known about this user's preferences (DO NOT re-extract):
{existing_facts}

Conversation:
{messages}

Extract NEW interaction facts as a JSON array:
[{{
  "field": "allowed field name",
  "value": "extracted value (string, number, or list)",
  "confidence": 0.0-1.0,
  "source_quote": "exact supporting text from the conversation",
  "category": "preference|communication|pattern|relationship|goal",
  "scope": "short|long"
}}]

Confidence: 1.0=directly stated, 0.8-0.9=strongly implied, 0.5-0.7=inferred.
Do not extract anything below 0.5 confidence.

Allowed fields and their expected scope:
LONG fields (permanent, no expiry):
  response_verbosity   — user preferred response length: "brief" | "detailed" | "mixed"
  technical_level      — how technical responses should be: "layperson" | "intermediate" | "expert"
  preferred_language   — primary language for responses (e.g. "en", "zh", "ja")
  emoji_preference     — whether user likes emoji in messages: "yes" | "no" | "neutral"
  communication_tone   — desired conversational tone: "formal" | "casual" | "warm"
  sensitivity_topics   — list of topics the user is emotionally sensitive about
  care_motivation      — what drives this user's engagement (e.g. "first-time owner", "anxious parent")
  trust_signals        — what builds trust with this user (e.g. "scientific citations", "step-by-step guidance")

SHORT fields (ephemeral, 7-day TTL):
  session_concern_level    — urgency/worry level right now: "low" | "medium" | "high"
  session_emotional_state  — detected emotional state: "calm" | "anxious" | "frustrated" | "relieved"
  active_followup_topic    — health topic the user is actively tracking (e.g. "vomiting episode")
  recent_interaction_quality — how the last interaction felt: "positive" | "neutral" | "negative"

Rules:
- Only extract what is explicitly stated or strongly implied by the user's own words
- Do not infer personality traits from a single short message
- Prefer not to extract over guessing
- Return [] if nothing new is clearly evidenced
- Return ONLY valid JSON\
"""


# ── Allowed fields ────────────────────────────────────────────────────────────

ALLOWED_AGENT_FIELDS: dict[str, AgentMemoryScope] = {
    # LONG
    "response_verbosity":        AgentMemoryScope.LONG,
    "technical_level":           AgentMemoryScope.LONG,
    "preferred_language":        AgentMemoryScope.LONG,
    "emoji_preference":          AgentMemoryScope.LONG,
    "communication_tone":        AgentMemoryScope.LONG,
    "sensitivity_topics":        AgentMemoryScope.LONG,
    "care_motivation":           AgentMemoryScope.LONG,
    "trust_signals":             AgentMemoryScope.LONG,
    # SHORT
    "session_concern_level":         AgentMemoryScope.SHORT,
    "session_emotional_state":       AgentMemoryScope.SHORT,
    "active_followup_topic":         AgentMemoryScope.SHORT,
    "recent_interaction_quality":    AgentMemoryScope.SHORT,
}


# ── Internal helpers ──────────────────────────────────────────────────────────


def _format_existing(memories: list[AgentMemory]) -> str:
    if not memories:
        return "(none)"
    lines = []
    for m in memories:
        v = m.value.get("v", m.value) if isinstance(m.value, dict) else m.value
        lines.append(f"  {m.field}: {v}")
    return "\n".join(lines)


def _format_messages(raw_messages: list[dict]) -> str:
    lines = []
    for msg in raw_messages:
        role = "User" if msg.get("role") == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```", 2)
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


# ── Public API ────────────────────────────────────────────────────────────────


async def extract_agent_memories(
    raw_messages: list[dict],
    user_id: str,
    existing_memories: list[AgentMemory],
) -> list[AgentMemoryProposal]:
    """
    Extract new agent-level interaction facts from a conversation turn.

    Args:
        raw_messages:      [{"role": "user"|"assistant", "content": str}]
        user_id:           user identifier (for logging)
        existing_memories: active AgentMemory rows for this user (avoids re-extraction)

    Returns:
        list[AgentMemoryProposal] — confidence >= 0.5 only, unknown fields skipped
    """
    filled_prompt = AGENT_EXTRACTION_PROMPT.format(
        existing_facts=_format_existing(existing_memories),
        messages=_format_messages(raw_messages),
    )

    client = get_gemini_client()
    try:
        raw = await client.extract(
            system_prompt=filled_prompt,
            messages=[{"role": "user", "content": "Extract interaction facts from the conversation above."}],
        )
        data = json.loads(_strip_fences(raw["text"]))
        if not isinstance(data, list):
            return []
    except Exception as exc:
        logger.error("extract_agent_memories failed", error=str(exc), user_id=user_id)
        return []

    proposals: list[AgentMemoryProposal] = []
    for item in data:
        try:
            confidence = float(item.get("confidence", 0))
            if confidence < 0.5:
                continue

            field = str(item["field"]).strip()
            if field not in ALLOWED_AGENT_FIELDS:
                logger.warning("skipping unknown agent memory field", field=field, user_id=user_id)
                continue

            proposals.append(
                AgentMemoryProposal(
                    field=field,
                    value=item["value"],
                    confidence=confidence,
                    source_quote=str(item.get("source_quote", "")),
                    category=AgentMemoryCategory(item.get("category", "preference").lower()),
                    scope=AgentMemoryScope(item.get("scope", "short").lower()),
                )
            )
        except Exception as exc:
            logger.warning("skipping malformed agent extraction item", error=str(exc), item=item)

    return proposals
