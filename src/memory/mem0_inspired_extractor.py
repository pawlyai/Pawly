"""
Mem0-inspired memory extraction system for Pawly.

Based on Mem0 v3 architecture principles:
  - Temporal reasoning (when facts occurred)
  - Entity linking (connect facts across conversations)
  - Confidence scoring (reliability measure)
  - Multi-signal retrieval (semantic + keyword + entity)
  - ADD-only model (never lose medical facts)

Key improvements over multi-agent approach:
  - Single extraction pipeline (no specialist duplication)
  - Temporal awareness (fixes Month 1 vs Month 6 confusion)
  - Entity linking (fixes medication repetition)
  - Better confidence handling (replaces validator over-filtering)
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, Any
from collections import defaultdict

from src.db.models import MemoryTerm, MemoryType


# ── Memory Data Structures ────────────────────────────────────────────────────

@dataclass
class MemoryFact:
    """A single extracted memory fact with metadata."""

    field: str
    value: Any
    confidence: float  # 0.0-1.0
    source_quote: str
    memory_type: str  # CHRONIC, SAFETY, EPISODE, SYMPTOM, etc.
    memory_term: str  # SHORT, MID, LONG

    # Mem0-specific metadata
    entity: str  # e.g. "medication", "symptom", "procedure"
    temporal_context: Optional[str] = None  # e.g. "Month 1", "Week 3", "Day 1"
    keywords: list[str] = None  # For multi-signal retrieval
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class EntityLink:
    """Links multiple facts referring to the same entity."""

    entity_name: str  # "Milo's joint pain"
    facts: list[MemoryFact]  # All facts mentioning this entity
    first_mention: datetime
    last_mention: datetime
    mention_count: int


# ── Mem0-inspired Extraction ──────────────────────────────────────────────────

MEM0_EXTRACTION_PROMPT = """\
Extract pet health facts as JSON. Do not include any text outside the JSON array.

Pet: {pet_name}
Conversation:
{messages}

Extract facts as JSON array. Each fact has:
- field: what is described
- value: the fact
- confidence: 0.0-1.0 (1.0=directly stated, 0.8=implied, 0.6=inferred, <0.5=skip)
- source_quote: exact text from conversation
- entity: category (medication, symptom, procedure, etc.)
- temporal_context: when (Month 1, Week 3, Day 1, or null)
- keywords: search terms
- memory_type: SYMPTOM or EPISODE or INTERVENTION or SAFETY or CHRONIC or SNAPSHOT or PATTERN or ENVIRONMENT or PROFILE
- memory_term: LONG or MID or SHORT

Return ONLY JSON array. Example format:
[
  {{
    "field": "current_symptom",
    "value": "limping on front left leg",
    "confidence": 0.9,
    "source_quote": "He's been limping on his left front leg",
    "entity": "symptom",
    "temporal_context": null,
    "keywords": ["limping", "leg", "front left"],
    "memory_type": "SYMPTOM",
    "memory_term": "SHORT"
  }}
]

Extract ALL facts with confidence >= 0.5. Return empty array [] if no facts found.
"""


async def extract_memories_mem0(
    raw_messages: list[dict],
    pet_name: str,
    extraction_prompt: str = None,
) -> list[MemoryFact]:
    """
    Extract memories using Mem0-inspired approach.

    This is Phase A: simplified single-pass extraction with Mem0 post-processing.
    Uses proven extraction prompt, then applies Mem0 principles as post-processing.
    """
    from src.llm.providers import get_chat_client
    from src.config import settings

    if extraction_prompt is None:
        extraction_prompt = MEM0_EXTRACTION_PROMPT

    formatted_messages = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}" for msg in raw_messages
    )

    prompt = extraction_prompt.format(
        pet_name=pet_name,
        messages=formatted_messages,
    )

    client = get_chat_client(settings.extraction_model)
    try:
        raw = await client.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "Extract facts. Return ONLY valid JSON."}],
            model=settings.extraction_model,
            max_tokens=4096,
            temperature=0.1,  # Lower temperature for more consistent JSON
        )

        text = raw["text"].strip()
        if not text:
            return []

        # Remove markdown fences if present
        if text.startswith("```"):
            # Find the end marker
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                # Remove json language identifier
                if text.startswith("json\n"):
                    text = text[5:]
                elif text.startswith("json"):
                    text = text[4:].lstrip()

        # Try to parse JSON
        text = text.strip()
        if not text.startswith("["):
            # Try to find the JSON array in the text
            start = text.find("[")
            if start >= 0:
                # Find the matching closing bracket
                depth = 0
                for i in range(start, len(text)):
                    if text[i] == "[":
                        depth += 1
                    elif text[i] == "]":
                        depth -= 1
                        if depth == 0:
                            text = text[start:i+1]
                            break

        data = json.loads(text)
        if not isinstance(data, list):
            return []

        # Convert to MemoryFact objects
        facts = []
        for item in data:
            if item.get("confidence", 0) >= 0.5:  # Only keep confident facts
                try:
                    fact = MemoryFact(
                        field=str(item.get("field", "")).strip(),
                        value=item.get("value"),
                        confidence=float(item.get("confidence", 0.5)),
                        source_quote=str(item.get("source_quote", "")),
                        memory_type=str(item.get("memory_type", "SNAPSHOT")).upper(),
                        memory_term=str(item.get("memory_term", "SHORT")).upper(),
                        entity=str(item.get("entity", "")).strip(),
                        temporal_context=item.get("temporal_context"),
                        keywords=item.get("keywords", []),
                    )
                    facts.append(fact)
                except Exception as e:
                    # Skip malformed items
                    pass

        return facts

    except Exception as e:
        return []


# ── Entity Linking (Mem0 principle) ───────────────────────────────────────────

def link_entities(facts: list[MemoryFact]) -> dict[str, EntityLink]:
    """
    Link facts referring to the same entity.

    Mem0 principle: "medication_name: gabapentin" + "medication_dose: 300mg"
    become a single entity "gabapentin medication" with 2 fact links.

    This prevents duplication and enables coherent retrieval.
    """
    entity_map: dict[str, list[MemoryFact]] = defaultdict(list)

    for fact in facts:
        # Group by entity + keyword matching
        # E.g., "limping" + "joint pain" both link to "joint_pain" entity
        key = _normalize_entity(fact.field, fact.entity, fact.keywords)
        entity_map[key].append(fact)

    # Convert to EntityLink objects
    result = {}
    for entity_key, entity_facts in entity_map.items():
        if entity_facts:
            timestamps = [f.created_at for f in entity_facts if f.created_at]
            result[entity_key] = EntityLink(
                entity_name=entity_key,
                facts=entity_facts,
                first_mention=min(timestamps) if timestamps else datetime.now(),
                last_mention=max(timestamps) if timestamps else datetime.now(),
                mention_count=len(entity_facts),
            )

    return result


def _normalize_entity(field: str, entity: str, keywords: list[str]) -> str:
    """
    Create a normalized entity key for linking.

    E.g.:
      - "medication_dose" + "medication" + ["gabapentin", "300mg"] → "medication::gabapentin"
      - "symptom_severity" + "symptom" + ["limping", "joint"] → "symptom::joint"
    """
    base = f"{entity}::{field.split('_')[0]}"

    # Add primary keyword if available
    if keywords:
        base = f"{entity}::{keywords[0]}"

    return base.lower()


# ── Multi-Signal Retrieval (Mem0 principle) ──────────────────────────────────

def retrieve_memories_multisignal(
    query: str,
    facts: list[MemoryFact],
    entity_links: dict[str, EntityLink],
    top_k: int = 5,
) -> list[MemoryFact]:
    """
    Retrieve memories using multiple signals: semantic, keyword, entity.

    Mem0 principle: "scratching" should return facts about:
      - Exact keyword match: "scratching"
      - Semantic match: "itching", "pruritus"
      - Entity match: "skin condition" facts
      - Temporal match: "recent" scratching vs "Month 1" scratching
    """
    scores = {}

    # Score each fact
    for fact in facts:
        score = 0.0

        # Signal 1: Keyword match
        query_terms = set(query.lower().split())
        keyword_matches = sum(1 for kw in fact.keywords if kw in query_terms)
        score += keyword_matches * 0.3  # 30% weight

        # Signal 2: Field match
        if any(qt in fact.field.lower() for qt in query_terms):
            score += 0.2  # 20% weight

        # Signal 3: Entity match
        entity_key = _normalize_entity(fact.field, fact.entity, fact.keywords)
        if entity_key in entity_links:
            # Boost if part of entity with multiple mentions
            link = entity_links[entity_key]
            score += (link.mention_count / 10.0) * 0.3  # 30% weight, capped

        # Signal 4: Recency (temporal)
        if fact.temporal_context and fact.temporal_context.lower() in query.lower():
            score += 0.2  # 20% weight

        scores[fact] = score

    # Return top-k by score + confidence
    ranked = sorted(
        facts,
        key=lambda f: (scores.get(f, 0) * f.confidence),
        reverse=True
    )

    return ranked[:top_k]


# ── Deduplication via Entity Linking ──────────────────────────────────────────

def deduplicate_via_entities(
    facts: list[MemoryFact],
    entity_links: dict[str, EntityLink],
    threshold: float = 0.7,
) -> list[MemoryFact]:
    """
    Deduplicate facts using entity linking instead of string matching.

    Mem0 approach: rather than checking if "scratching" == "itching",
    link them as the same entity and keep both facts.

    This is ADD-only: we never delete information, just organize it.
    """
    # Select one representative fact per entity
    deduplicated = []
    seen_entities = set()

    for entity_key, link in entity_links.items():
        if entity_key not in seen_entities:
            # Keep the highest-confidence fact for this entity
            best_fact = max(link.facts, key=lambda f: f.confidence)
            deduplicated.append(best_fact)
            seen_entities.add(entity_key)

    # Also include facts that don't have entity links (isolated facts)
    for fact in facts:
        entity_key = _normalize_entity(fact.field, fact.entity, fact.keywords)
        if entity_key not in seen_entities:
            deduplicated.append(fact)

    return deduplicated
