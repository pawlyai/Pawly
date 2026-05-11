"""
Async LLM-based memory extraction.

Extracts structured pet facts from a conversation turn using Gemini Flash 2.0.

Public API:
    MemoryProposal   — dataclass returned by extract_memories()
    EXTRACTION_PROMPT — module-level string, editable without touching logic
    extract_memories(raw_messages, pet, existing_memories) -> list[MemoryProposal]
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from src.config import settings
from src.db.models import MemoryTerm, MemoryType, Pet, PetMemory
from src.llm.providers import get_chat_client
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Reasoning-style models (DeepSeek V4, Claude with extended thinking, etc.)
# emit chain-of-thought before the actual answer. Strip these wrappers before
# attempting JSON parse.
_THINK_TAG_RE = re.compile(r"<think(?:ing)?>.*?</think(?:ing)?>", re.DOTALL | re.IGNORECASE)
_REASONING_BLOCK_RE = re.compile(r"<reasoning>.*?</reasoning>", re.DOTALL | re.IGNORECASE)


# ── Result type ───────────────────────────────────────────────────────────────


@dataclass
class MemoryProposal:
    """A single extracted fact, ready for validation."""

    field: str
    value: Any
    confidence: float
    source_quote: str
    memory_type: MemoryType
    memory_term: MemoryTerm
    observed_at: Optional[datetime] = None


# ══════════════════════════════════════════════════════════════════════════════
# EDITABLE EXTRACTION PROMPT
# Edit the string below. Do not touch extract_memories() unless you need to
# change parsing logic.
# ══════════════════════════════════════════════════════════════════════════════

EXTRACTION_PROMPT = """\
You are a veterinary data extraction system.
Given a conversation, extract NEW factual information about the pet.

Current pet: {pet_name} ({species}, {breed}, {age_months} months, {gender}, neutered: {neutered}, weight: {weight}kg)

Already known (DO NOT re-extract):
{existing_facts}

Conversation:
{messages}

Extract NEW facts as JSON array:
[{{
  "field": "allowed field name",
  "value": "extracted value",
  "confidence": 0.0-1.0,
  "source_quote": "exact supporting text",
  "memory_type": "PROFILE|CHRONIC|BASELINE|PATTERN|ENVIRONMENT|SAFETY|SNAPSHOT|SYMPTOM|EPISODE|INTERVENTION|FOLLOWUP",
  "memory_term": "SHORT|MID|LONG",
  "observed_at": "ISO date or null"
}}]

Confidence: 1.0=directly stated, 0.8-0.9=strongly implied, 0.5-0.7=inferred. Below 0.5: don't extract.

Allowed fields:
LONG: weight_latest, stage, breed, birth_date, gender, neutered_status, chronic_conditions, allergy_list, medication_history, food_allergy, drug_allergy, water_intake_habit, meal_frequency, feeding_method, meal_amount, exercise_habit, exercise_duration, bowel_frequency, bowel_health, is_stomach_sensitive, seasonal_issues, home_type, home_environment, has_other_pets, has_children, stress_sources, household_members, pet_human_preferences, emergency_contact, preferred_vet_clinic
MID: current_symptom, symptom_onset, symptom_frequency, symptom_severity, recent_diet_change, recent_food_brand, diet_change_period, is_stressed, stress_trigger, environment_change, vaccination_status, vaccination_date, deworming_status, treatment_action, vet_diagnosis, vet_prescription, lab_results
SHORT: current_appetite, current_water_intake, current_energy_level, current_bowel_status, current_vomiting, current_breathing, current_pain_signs

Rules: only extract explicitly stated facts, don't infer unstated symptoms, don't duplicate existing, return [] if nothing new, return ONLY valid JSON.\
"""


# ── Internal helpers ──────────────────────────────────────────────────────────


def _format_existing(memories: list[PetMemory]) -> str:
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
    """Remove markdown code fences if the model wrapped its JSON."""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```", 2)
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


def _strip_reasoning_tags(text: str) -> str:
    """Strip <think>...</think> / <reasoning>...</reasoning> blocks that
    reasoning-style models (DeepSeek V4, Claude extended thinking) emit
    before the actual answer. Also handles dangling <think> with no closing
    tag (when max_tokens cuts off mid-thinking)."""
    text = _THINK_TAG_RE.sub("", text)
    text = _REASONING_BLOCK_RE.sub("", text)
    # Dangling open tag (cut off mid-stream) — drop everything before it
    # since the actual answer never arrived.
    for open_tag in ("<think>", "<thinking>", "<reasoning>"):
        idx = text.lower().find(open_tag)
        if idx != -1:
            # If there's no matching close tag, anything after the open is
            # just truncated thinking — discard.
            close_tag = open_tag.replace("<", "</")
            if close_tag.lower() not in text.lower():
                text = text[:idx]
    return text.strip()


def _extract_json_array(text: str) -> Optional[str]:
    """Find the first balanced JSON array [...] in text. Used as a fallback
    when the response has prose mixed in around the JSON."""
    start = text.find("[")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse_extraction_response(raw_text: str) -> Optional[list]:
    """Robust extraction-response parser. Tries multiple strategies in order.
    Returns parsed list on success, None on hard failure."""
    if not raw_text or not raw_text.strip():
        return None

    cleaned = _strip_reasoning_tags(raw_text)
    cleaned = _strip_fences(cleaned)

    if not cleaned:
        return None

    # Strategy 1: direct parse
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, list) else None
    except json.JSONDecodeError:
        pass

    # Strategy 2: pull out first balanced [...] array
    array_str = _extract_json_array(cleaned)
    if array_str is None:
        return None
    try:
        data = json.loads(array_str)
        return data if isinstance(data, list) else None
    except json.JSONDecodeError:
        return None


# ── Public API ────────────────────────────────────────────────────────────────


async def extract_memories(
    raw_messages: list[dict],
    pet: Pet,
    existing_memories: list[PetMemory],
) -> list[MemoryProposal]:
    """
    Extract new pet facts from a conversation turn.

    Args:
        raw_messages:      [{"role": "user"|"assistant", "content": str}]
        pet:               Pet ORM object for context
        existing_memories: active PetMemory rows (injected as "already known")

    Returns:
        list[MemoryProposal] — confidence >= 0.5 only, malformed items skipped
    """
    filled_prompt = EXTRACTION_PROMPT.format(
        pet_name=pet.name,
        species=pet.species.value,
        breed=pet.breed or "unknown",
        age_months=pet.age_in_months or "?",
        gender=pet.gender.value,
        neutered=pet.neutered_status.value,
        weight=pet.weight_latest or "?",
        existing_facts=_format_existing(existing_memories),
        messages=_format_messages(raw_messages),
    )

    extraction_model = settings.extraction_model
    client = get_chat_client(extraction_model)

    # max_tokens budget: reasoning-style models (V4) spend tokens on chain-of-
    # thought before producing JSON. 2048 was empirically too tight for
    # longitudinal cases — observed empty responses from deepseek-v4-flash.
    # 8192 gives ample headroom; non-reasoning models stop early anyway so the
    # cost increase is negligible in practice.
    primary_max_tokens = 8192
    retry_max_tokens = 12000

    last_raw_text = ""
    data: Optional[list] = None

    try:
        raw = await client.chat(
            system_prompt=filled_prompt,
            messages=[{"role": "user", "content": "Extract facts from the conversation above."}],
            model=extraction_model,
            max_tokens=primary_max_tokens,
            temperature=0.2,
        )
        last_raw_text = raw.get("text", "")
        data = _parse_extraction_response(last_raw_text)
    except Exception as exc:
        logger.error(
            "extract_memories primary call failed",
            error=str(exc),
            pet_id=str(pet.id),
        )

    # Retry once with explicit "output ONLY JSON, no reasoning" instruction
    # and larger token budget. Reasoning models that exceeded the primary
    # budget will usually succeed here.
    if data is None:
        retry_messages = [
            {
                "role": "user",
                "content": (
                    "Extract facts from the conversation above. "
                    "OUTPUT ONLY THE JSON ARRAY. "
                    "Do not emit any reasoning, thinking, or prose — "
                    "start your response with '[' and end with ']'. "
                    "If there are no new facts, output exactly: []"
                ),
            }
        ]
        try:
            raw = await client.chat(
                system_prompt=filled_prompt,
                messages=retry_messages,
                model=extraction_model,
                max_tokens=retry_max_tokens,
                temperature=0.0,
            )
            last_raw_text = raw.get("text", "")
            data = _parse_extraction_response(last_raw_text)
        except Exception as exc:
            logger.error(
                "extract_memories retry call failed",
                error=str(exc),
                pet_id=str(pet.id),
            )

    if data is None:
        # Log a head/tail snippet of the raw response so future failures
        # are diagnosable from logs alone — no need to bisect with print().
        head = repr(last_raw_text[:200]) if last_raw_text else "<empty>"
        tail = repr(last_raw_text[-200:]) if len(last_raw_text) > 200 else ""
        logger.error(
            "extract_memories failed to parse JSON after retry",
            pet_id=str(pet.id),
            raw_len=len(last_raw_text),
            raw_head=head,
            raw_tail=tail,
        )
        return []

    proposals: list[MemoryProposal] = []
    for item in data:
        try:
            confidence = float(item.get("confidence", 0))
            if confidence < 0.5:
                continue

            observed_at: Optional[datetime] = None
            raw_date = item.get("observed_at")
            if raw_date:
                try:
                    observed_at = datetime.fromisoformat(str(raw_date))
                except ValueError:
                    pass

            proposals.append(
                MemoryProposal(
                    field=str(item["field"]).strip(),
                    value=item["value"],
                    confidence=confidence,
                    source_quote=str(item.get("source_quote", "")),
                    memory_type=MemoryType(item.get("memory_type", "snapshot").lower()),
                    memory_term=MemoryTerm(item.get("memory_term", "short").lower()),
                    observed_at=observed_at,
                )
            )
        except Exception as exc:
            logger.warning("skipping malformed extraction item", error=str(exc), item=item)

    return proposals

