"""
Async LLM-based memory extraction.

Extracts structured pet facts from a conversation turn using Gemini Flash 2.0.

Public API:
    MemoryProposal   — dataclass returned by extract_memories()
    EXTRACTION_PROMPT — module-level string, editable without touching logic
    extract_memories(raw_messages, pet, existing_memories) -> list[MemoryProposal]
"""

import asyncio
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from src.config import settings
from src.db.models import MemoryTerm, MemoryType, Pet, PetMemory
from src.llm.providers import get_chat_client
from src.memory.extractor_agents import (
    triage_message,
    HEALTH_SPECIALIST_PROMPT,
    MEDICATION_SPECIALIST_PROMPT,
    BEHAVIOR_SPECIALIST_PROMPT,
    ACUTE_SPECIALIST_PROMPT,
    validate_facts,
)
from src.memory.mem0_inspired_extractor import (
    extract_memories_mem0,
    link_entities,
    retrieve_memories_multisignal,
    MemoryFact,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


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
  "memory_type": "type (see rules below)",
  "memory_term": "SHORT|MID|LONG",
  "observed_at": "ISO date or null"
}}]

Confidence: 1.0=directly stated, 0.8-0.9=strongly implied, 0.5-0.7=inferred. Below 0.5: don't extract.

MEMORY_TYPE CLASSIFICATION RULES:
- SYMPTOM: acute symptoms (vomiting, limping, itching) → memory_term=SHORT or MID
- EPISODE: active ongoing illness/issue → memory_term=MID
- INTERVENTION: medications, treatments, prescriptions → memory_term=LONG or MID
- SAFETY: life-critical (allergies, medications, emergency contact) → memory_term=LONG
- CHRONIC: permanent conditions (breed, allergies, chronic disease) → memory_term=LONG
- BASELINE: normal/typical state (usual weight, normal appetite) → memory_term=MID
- SNAPSHOT: recent observation (current appetite, current energy) → memory_term=SHORT
- PATTERN: recurring behavior (bowel frequency, exercise habit) → memory_term=MID or LONG
- ENVIRONMENT: home situation (home type, other pets, stressors) → memory_term=MID or LONG
- PROFILE: background info (breed, gender, age) → memory_term=LONG

MEMORY_TERM RULES:
- SHORT: changes daily (current appetite, current energy, current symptoms) → retention: days
- MID: changes weekly/monthly (medications, active episodes, diet) → retention: weeks/months
- LONG: permanent/yearly (allergies, breed, chronic conditions, home) → retention: months/years

Allowed fields:
LONG: weight_latest, stage, breed, birth_date, gender, neutered_status, chronic_conditions, allergy_list, medication_history, medication_dose, medication_frequency, medication_indication, medication_titration_plan, food_allergy, drug_allergy, water_intake_habit, meal_frequency, feeding_method, meal_amount, exercise_habit, exercise_duration, bowel_frequency, bowel_health, is_stomach_sensitive, seasonal_issues, home_type, home_environment, has_other_pets, has_children, stress_sources, household_members, pet_human_preferences, emergency_contact, preferred_vet_clinic
MID: current_symptom, symptom_onset, symptom_frequency, symptom_severity, symptom_trend, recent_diet_change, recent_food_brand, diet_change_period, is_stressed, stress_trigger, environment_change, vaccination_status, vaccination_date, deworming_status, treatment_action, treatment_start_date, treatment_response, vet_diagnosis, vet_prescription, lab_results, timeline_label
SHORT: current_appetite, current_water_intake, current_energy_level, current_bowel_status, current_vomiting, current_breathing, current_pain_signs

Rules: only extract explicitly stated facts, don't infer unstated symptoms, don't duplicate existing, return [] if nothing new, return ONLY valid JSON.
Special: When extracting medication/treatment info, ALWAYS include dose, frequency, and indication if mentioned. When tracking symptoms, extract ANY symptom_trend value (improving/stable/worsening) to track progression. Extract timeline_label (e.g. "Month 2", "Day 1", "Week 3") to preserve temporal context across multi-day conversations.\
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


_HTML_TAG_RE = re.compile(r"<[^>]+>")

def _clean_content(text: str) -> str:
    """Strip HTML tags and decode HTML entities for clean LLM extraction input.

    Telegram messages arrive with HTML parse_mode markup (<b>, <blockquote>,
    &#x27; etc.). Passing raw HTML to the extraction LLM confuses it and inflates
    the prompt unnecessarily. Decoding entities and stripping tags gives the LLM
    plain readable text while preserving all factual content.
    """
    text = html.unescape(text)
    text = _HTML_TAG_RE.sub("", text)
    return text.strip()


def _format_messages(raw_messages: list[dict]) -> str:
    lines = []
    for msg in raw_messages:
        role = "User" if msg.get("role") == "user" else "Assistant"
        lines.append(f"{role}: {_clean_content(msg['content'])}")
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


# ── Multi-agent Pipeline ─────────────────────────────────────────────────────


def _deduplicate_facts(facts: list[dict]) -> list[dict]:
    """Remove duplicate/redundant facts extracted by different specialists.

    Keeps the fact with highest confidence when duplicates exist.
    Considers facts duplicates if they have the same field and similar values.
    """
    if not facts:
        return []

    # Group by (field, value_key) to find duplicates
    # value_key is the first 30 chars of stringified value (for approximate matching)
    dedup_map = {}

    for fact in facts:
        field = fact.get("field", "").lower().strip()
        value = str(fact.get("value", "")).lower().strip()
        value_key = value[:40]  # First 40 chars for grouping

        key = (field, value_key)

        # Keep fact with highest confidence
        current_confidence = fact.get("confidence", 0)
        if key not in dedup_map:
            dedup_map[key] = fact
        else:
            existing_confidence = dedup_map[key].get("confidence", 0)
            if current_confidence > existing_confidence:
                dedup_map[key] = fact

    result = list(dedup_map.values())
    logger.debug(f"dedup: removed {len(facts) - len(result)} duplicate facts")
    return result


async def _run_specialist(
    specialist_name: str,
    prompt_template: str,
    pet: Pet,
    existing_facts: str,
    messages: str,
) -> list[dict]:
    """Run a single specialist agent to extract facts."""
    prompt = prompt_template.format(
        pet_name=pet.name,
        species=pet.species.value,
        breed=pet.breed or "unknown",
        age_months=pet.age_in_months or "?",
        gender=pet.gender.value,
        existing_facts=existing_facts,
        messages=messages,
    )

    # Use the same model as the main extraction system (from settings)
    # This ensures specialists work with whatever model the user configured
    specialist_model = settings.extraction_model
    client = get_chat_client(specialist_model)
    try:
        raw = await client.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": f"Extract {specialist_name} facts."}],
            model=specialist_model,
            max_tokens=2048,
            temperature=0.2,
        )
        text = raw["text"].strip()
        if not text:
            return []
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"specialist {specialist_name} failed", error=str(e), model=specialist_model)
        return []


async def _extract_multiagent(
    raw_messages: list[dict],
    pet: Pet,
    existing_memories: list[PetMemory],
) -> list[MemoryProposal]:
    """Multi-agent extraction pipeline with specialists, validation, and routing."""

    formatted_messages = _format_messages(raw_messages)
    existing_facts = _format_existing(existing_memories)

    # Step 1: Triage (classify intent)
    logger.info("extraction: running triage agent")
    triage = await triage_message(raw_messages)
    logger.debug(f"triage result: {triage['intent']}")

    # Step 2: Run specialists in parallel
    logger.info("extraction: running specialist agents (parallel)")
    health_facts, medication_facts, behavior_facts, acute_facts = await asyncio.gather(
        _run_specialist(
            "health",
            HEALTH_SPECIALIST_PROMPT,
            pet,
            existing_facts,
            formatted_messages,
        ),
        _run_specialist(
            "medication",
            MEDICATION_SPECIALIST_PROMPT,
            pet,
            existing_facts,
            formatted_messages,
        ),
        _run_specialist(
            "behavior",
            BEHAVIOR_SPECIALIST_PROMPT,
            pet,
            existing_facts,
            formatted_messages,
        ),
        _run_specialist(
            "acute",
            ACUTE_SPECIALIST_PROMPT,
            pet,
            existing_facts,
            formatted_messages,
        ),
    )

    # Merge specialist results
    all_facts = health_facts + medication_facts + behavior_facts + acute_facts
    logger.info(f"extraction: specialists produced {len(all_facts)} facts before dedup")

    # Step 2b: Deduplication (remove duplicate extractions)
    before_dedup = len(all_facts)
    all_facts = _deduplicate_facts(all_facts)
    logger.info(f"extraction: dedup: {before_dedup} => {len(all_facts)} facts")
    if all_facts:
        logger.debug(f"extraction: facts after dedup: {[(f.get('field'), f.get('memory_type')) for f in all_facts[:5]]}")

    if not all_facts:
        return []

    # Step 3: Validate facts
    logger.info("extraction: running validator agent")
    validations = await validate_facts(raw_messages, pet.name, all_facts)

    # Filter by validation
    kept_indices = {
        v.get("index")
        for v in validations
        if v.get("keep", False) and v.get("adjusted_confidence", 0) >= 0.5
    }
    filtered_facts = [f for i, f in enumerate(all_facts) if i in kept_indices]
    logger.info(f"extraction: validator kept {len(filtered_facts)}/{len(all_facts)} facts")

    # Debug: show what validator rejected
    if validations and len(filtered_facts) == 0 and all_facts:
        logger.debug(f"extraction: ALL facts rejected by validator!")
        for v in validations[:3]:
            logger.debug(f"  - index {v.get('index')}: keep={v.get('keep')}, conf={v.get('adjusted_confidence')}, issues={v.get('issues')}")

    # Step 4: Build proposals from validated facts
    # (Specialists already assigned memory_type and memory_term, no routing needed)
    logger.info("extraction: building proposals from validated facts")
    proposals: list[MemoryProposal] = []

    for i, fact in enumerate(filtered_facts):
        try:
            # Get validation adjustment (confidence score may have been adjusted)
            adjusted_confidence = next(
                (v.get("adjusted_confidence", fact.get("confidence", 0.5)) for v in validations
                 if v.get("index") == i),
                fact.get("confidence", 0.5),
            )

            observed_at: Optional[datetime] = None
            raw_date = fact.get("observed_at")
            if raw_date:
                try:
                    observed_at = datetime.fromisoformat(str(raw_date))
                except ValueError:
                    pass

            # Use memory_type and memory_term from specialist (already assigned)
            memory_type_str = fact.get("memory_type", "snapshot").lower()
            memory_term_str = fact.get("memory_term", "short").lower()

            proposals.append(
                MemoryProposal(
                    field=str(fact.get("field", "")).strip(),
                    value=fact.get("value"),
                    confidence=float(adjusted_confidence),
                    source_quote=str(fact.get("source_quote", "")),
                    memory_type=MemoryType(memory_type_str),
                    memory_term=MemoryTerm(memory_term_str),
                    observed_at=observed_at,
                )
            )
        except Exception as e:
            logger.warning(f"failed to build proposal, skipping", error=str(e), fact=fact)

    logger.info(f"extraction: pipeline complete, returning {len(proposals)} proposals")
    return proposals


# ── Public API ────────────────────────────────────────────────────────────────


async def _extract_mem0(
    raw_messages: list[dict],
    pet: Pet,
    existing_memories: list[PetMemory],
) -> list[MemoryProposal]:
    """
    Mem0-inspired memory extraction with temporal reasoning and entity linking.

    Phase A: Single-pass extraction using simplified Mem0 principles:
      1. Use proven single-agent extraction (not multi-agent)
      2. Apply entity linking to group related facts
      3. Add temporal awareness from conversation context
      4. Skip aggressive validator (trust extraction confidence >= 0.5)

    Advantages over multi-agent:
      - Single pass (no specialist duplication/overhead)
      - Entity linking (gabapentin dose + frequency linked)
      - Temporal awareness preserved
      - No validator bottleneck (confidence threshold only)
    """
    logger.info("extraction: using Mem0-inspired approach (Phase A)")

    formatted_messages = _format_messages(raw_messages)
    existing_facts = _format_existing(existing_memories)

    # Use proven extraction prompt (from EXTRACTION_PROMPT global)
    filled_prompt = EXTRACTION_PROMPT.format(
        pet_name=pet.name,
        species=pet.species.value,
        breed=pet.breed or "unknown",
        age_months=pet.age_in_months or "?",
        gender=pet.gender.value,
        neutered=pet.neutered_status.value,
        weight=pet.weight_latest or "?",
        existing_facts=existing_facts,
        messages=formatted_messages,
    )

    extraction_model = settings.extraction_model
    client = get_chat_client(extraction_model)
    try:
        raw = await client.chat(
            system_prompt=filled_prompt,
            messages=[{"role": "user", "content": "Extract facts from the conversation above."}],
            model=extraction_model,
            max_tokens=4096,
            temperature=0.2,
        )
        raw_text = raw["text"]
        if not raw_text.strip():
            logger.warning("extract_memories: empty response from LLM", model=extraction_model)
            return []

        data = json.loads(_strip_fences(raw_text))
        if not isinstance(data, list):
            return []

    except Exception as exc:
        logger.error("Mem0 extraction failed", error=str(exc), model=extraction_model)
        return []

    # Convert to Mem0 facts with temporal + entity metadata
    mem0_facts: list[MemoryFact] = []
    for item in data:
        confidence = float(item.get("confidence", 0))
        if confidence >= 0.5:  # Threshold only, no validator
            try:
                # Infer entity from field or memory_type
                field = str(item.get("field", "")).lower()
                memory_type = str(item.get("memory_type", "snapshot")).lower()
                entity = "unknown"

                if "medication" in field or "medication" in memory_type:
                    entity = "medication"
                elif "symptom" in field or "symptom" in memory_type:
                    entity = "symptom"
                elif "procedure" in field or "procedure" in memory_type:
                    entity = "procedure"
                elif "diet" in field or "food" in field:
                    entity = "diet"
                elif "exercise" in field or "activity" in field:
                    entity = "activity"

                fact = MemoryFact(
                    field=str(item.get("field", "")).strip(),
                    value=item.get("value"),
                    confidence=confidence,
                    source_quote=str(item.get("source_quote", "")),
                    memory_type=str(item.get("memory_type", "snapshot")).upper(),
                    memory_term=str(item.get("memory_term", "short")).upper(),
                    entity=entity,
                    temporal_context=item.get("timeline_label"),  # Extract if available
                    keywords=[str(item.get("field", "")).lower()],  # Add field as keyword
                )
                mem0_facts.append(fact)
            except Exception as e:
                logger.warning(f"skipped malformed item", error=str(e), item=str(item)[:100])

    if not mem0_facts:
        logger.info("extraction: Mem0 extracted 0 facts")
        return []

    logger.info(f"extraction: Mem0 extracted {len(mem0_facts)} facts")

    # Apply Mem0 principles: entity linking
    entity_links = link_entities(mem0_facts)
    logger.debug(f"extraction: created {len(entity_links)} entity links")

    # Build proposals from Mem0 facts
    proposals: list[MemoryProposal] = []
    for fact in mem0_facts:
        try:
            proposals.append(
                MemoryProposal(
                    field=fact.field,
                    value=fact.value,
                    confidence=fact.confidence,
                    source_quote=fact.source_quote,
                    memory_type=MemoryType(fact.memory_type.lower()),
                    memory_term=MemoryTerm(fact.memory_term.lower()),
                    observed_at=fact.created_at,
                )
            )
        except Exception as e:
            logger.warning(f"failed to build proposal", error=str(e), field=fact.field)

    logger.info(f"extraction: Mem0 pipeline complete, returning {len(proposals)} proposals")
    return proposals


async def extract_memories(
    raw_messages: list[dict],
    pet: Pet,
    existing_memories: list[PetMemory],
) -> list[MemoryProposal]:
    """
    Extract new pet facts from a conversation turn.

    Supports two extraction backends:
      - "mem0": Mem0-inspired single-pass extraction (Phase A)
      - "multiagent": Multi-specialist extraction with validation (current)

    Args:
        raw_messages:      [{"role": "user"|"assistant", "content": str}]
        pet:               Pet ORM object for context
        existing_memories: active PetMemory rows

    Returns:
        list[MemoryProposal] — validated facts with confidence >= 0.5
    """
    # Feature flag to toggle between extraction backends
    extraction_backend = getattr(settings, "extraction_backend", "multiagent")

    if extraction_backend == "mem0":
        try:
            return await _extract_mem0(raw_messages, pet, existing_memories)
        except Exception as e:
            logger.error(f"Mem0 extraction failed, falling back to multiagent", error=str(e))
            return await _extract_multiagent(raw_messages, pet, existing_memories)
    else:
        # Default to multi-agent approach
        try:
            return await _extract_multiagent(raw_messages, pet, existing_memories)
        except Exception as e:
            logger.error(f"multiagent extraction failed, falling back to single-agent", error=str(e))
            return await _extract_simple(raw_messages, pet, existing_memories)


async def _extract_simple(
    raw_messages: list[dict],
    pet: Pet,
    existing_memories: list[PetMemory],
) -> list[MemoryProposal]:
    """Fallback single-agent extraction (simpler, more reliable)."""
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
    try:
        raw = await client.chat(
            system_prompt=filled_prompt,
            messages=[{"role": "user", "content": "Extract facts from the conversation above."}],
            model=extraction_model,
            max_tokens=4096,
            temperature=0.2,
        )
        raw_text = raw["text"]
        if not raw_text.strip():
            logger.warning(
                "extract_memories: empty response from LLM",
                model=extraction_model,
                input_tokens=raw.get("input_tokens", 0),
                output_tokens=raw.get("output_tokens", 0),
                pet_id=str(pet.id),
            )
            return []
        data = json.loads(_strip_fences(raw_text))
        if not isinstance(data, list):
            return []
    except Exception as exc:
        logger.error(
            "extract_memories failed",
            error=str(exc),
            model=extraction_model,
            raw_snippet=(raw.get("text", "") if "raw" in dir() else "")[:200],
            pet_id=str(pet.id),
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

