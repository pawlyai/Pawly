"""
Read-only memory loader.

The orchestrator calls these functions to assemble context for each LLM turn.
Nothing here writes to the database.

Public API:
    load_pet_context(pet_id, user_id, tier)  -> dict (full context bundle)
    load_related_memories(pet_id, message)   -> list[PetMemory]  (topic-matched)
    get_active_pet(user_id)                  -> Pet | None

Private helpers (prefixed _):
    _load_memories           — filtered PetMemory rows
    _load_recent_turns       — last N message pairs for the pet's latest dialogue
    _load_latest_summary     — most recent DailySummary or WeeklySummary
    _load_pending_confirmations — unconfirmed changes, critical fields first
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session_factory
from src.db.models import (
    DailySummary,
    Dialogue,
    MemoryTerm,
    MemoryType,
    Message,
    MessageRole,
    PendingMemoryChange,
    PendingStatus,
    Pet,
    PetMemory,
    SubscriptionTier,
    WeeklySummary,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── Tier config ───────────────────────────────────────────────────────────────

# Fields that must be confirmed by the user before storing
_CRITICAL_FIELDS = [
    "breed", "birth_date", "gender", "neutered_status",
    "chronic_conditions", "allergy_list", "medication_history",
]

# Map from topic keywords → related memory fields to surface
_TOPIC_MAP: dict[tuple[str, ...], list[str]] = {
    # ── Diet / nutrition / weight ─────────────────────────────────────────────
    ("weight", "diet", "food", "eating", "appetite", "feed", "nutrition",
     "kibble", "wet food", "raw food", "treat", "overweight", "underweight"): [
        "exercise_habit", "feeding_method", "meal_frequency", "meal_amount",
        "recent_diet_change", "chronic_conditions", "food_allergy",
    ],
    # ── Behaviour / emotion ───────────────────────────────────────────────────
    ("emotion", "behavior", "behaviour", "anxiety", "stress", "aggression",
     "hiding", "scared", "growl", "bark", "biting", "destructive",
     "separation", "training", "toilet", "litter box"): [
        "home_environment", "household_members", "has_children",
        "has_other_pets", "stress_sources", "pet_human_preferences",
    ],
    # ── GI / digestive ────────────────────────────────────────────────────────
    ("vomit", "diarrhea", "stomach", "bowel", "poop", "stool", "nausea",
     "constipat", "bloat", "gas", "indigestion", "regurgitat"): [
        "recent_diet_change", "recent_food_brand", "chronic_conditions",
        "food_allergy", "is_stomach_sensitive", "medication_history",
    ],
    # ── Skin / coat / allergy ─────────────────────────────────────────────────
    ("skin", "allergy", "itch", "scratch", "rash", "hair loss", "bald",
     "fur", "coat", "dandruff", "fleas", "tick", "hotspot", "hive",
     "swollen", "lump", "bump"): [
        "allergy_list", "home_environment", "seasonal_issues",
        "food_allergy", "vaccination_status",
    ],
    # ── Respiratory ───────────────────────────────────────────────────────────
    ("breath", "cough", "sneeze", "nose", "respiratory", "wheeze",
     "pant", "gasp", "nasal", "discharge", "runny"): [
        "vaccination_status", "home_environment", "chronic_conditions",
        "has_other_pets",
    ],
    # ── Urinary / kidney ─────────────────────────────────────────────────────
    ("urin", "pee", "kidney", "bladder", "litter", "strain", "blood in urine",
     "frequent urination", "accident", "incontinence"): [
        "water_intake_habit", "chronic_conditions", "medication_history",
        "neutered_status",
    ],
    # ── Eyes / ears ───────────────────────────────────────────────────────────
    ("eye", "vision", "squint", "discharge", "tear", "ear", "hearing",
     "head shake", "scratch ear", "smell from ear"): [
        "allergy_list", "chronic_conditions", "vaccination_status",
    ],
    # ── Joints / mobility / pain ──────────────────────────────────────────────
    ("limp", "joint", "arthritis", "hip", "knee", "mobility", "stiff",
     "pain", "hurt", "sore", "injury", "wound", "cut", "bite wound",
     "lameness", "can't walk", "falling"): [
        "chronic_conditions", "medication_history", "exercise_habit",
        "weight_latest", "breed",
    ],
    # ── Heart / circulation / energy ─────────────────────────────────────────
    ("heart", "letharg", "tired", "fatigue", "energy", "weak", "collapse",
     "faint", "pale gum", "blue gum", "rapid breathing", "exercise intolerance"): [
        "chronic_conditions", "medication_history", "vaccination_status",
        "exercise_habit",
    ],
    # ── Dental / oral ─────────────────────────────────────────────────────────
    ("teeth", "dental", "gum", "tartar", "drool", "bad breath", "mouth",
     "tooth", "chew", "jaw", "oral"): [
        "chronic_conditions", "feeding_method",
    ],
    # ── Neurological ─────────────────────────────────────────────────────────
    ("seizure", "tremor", "twitch", "balance", "coordination", "head tilt",
     "wobble", "disoriented", "circle", "paralysis"): [
        "chronic_conditions", "medication_history", "vaccination_status",
    ],
    # ── Reproduction / hormones ───────────────────────────────────────────────
    ("heat", "season", "pregnancy", "pregnant", "whelp", "kitten", "puppy",
     "neuter", "spay", "castrate", "hormone", "discharge"): [
        "neutered_status", "chronic_conditions", "vaccination_status",
    ],
    # ── Medication / treatment ────────────────────────────────────────────────
    ("medication", "medicine", "drug", "antibiotic", "steroid", "dose",
     "tablet", "pill", "injection", "side effect", "treatment", "vet visit",
     "prescription", "supplement"): [
        "medication_history", "chronic_conditions", "allergy_list",
        "vaccination_status",
    ],
}

# Map DB MessageRole → Gemini API role string
_ROLE_MAP: dict[str, str] = {"user": "user", "bot": "assistant"}

# ── Turn context token budgets per subscription tier ─────────────────────────
# Token budget for recent_turns injected into the messages array.
# At ~100 tokens/turn average: FREE ≈ 3 turns, PLUS ≈ 10 turns, PRO ≈ 16 turns.
# Adaptive: a turn with a long medical-advice reply consumes more tokens and
# naturally leaves less room for older turns without a hard count cap.
_TURN_TOKEN_BUDGETS: dict[SubscriptionTier, int] = {
    SubscriptionTier.NEW_FREE: 400,
    SubscriptionTier.OLD_FREE: 400,
    SubscriptionTier.PLUS:    1200,
    SubscriptionTier.PRO:     1800,
}

# Fetch this many messages from DB before trimming to the token budget.
# Large enough to cover the worst-case PRO budget even with short messages.
_DB_FETCH_MAX = 40


# ── Public API ────────────────────────────────────────────────────────────────


async def load_pet_context(
    pet_id: str,
    user_id: str,
    tier: SubscriptionTier,
) -> dict:
    """
    Load the full memory context bundle for one conversation turn.

    Memory depth and turn history scale with subscription tier:
        NEW_FREE / OLD_FREE — profile memories + short-term + 3 turns
        PLUS                — all long/mid/short + 5 turns
        PRO                 — all long/mid/short (higher limits) + 5 turns

    Returns:
        {
            "pet":                   Pet | None,
            "long_term_memories":    list[PetMemory],
            "mid_term_memories":     list[PetMemory],
            "short_term_memories":   list[PetMemory],
            "recent_turns":          list[{"role": str, "content": str}],
            "daily_summary":         DailySummary | None,
            "weekly_summary":        WeeklySummary | None,
            "pending_confirmations": list[PendingMemoryChange],
        }
    """
    factory = get_session_factory()
    async with factory() as db:
        pet = await db.get(Pet, uuid.UUID(pet_id))

        if tier in (SubscriptionTier.NEW_FREE, SubscriptionTier.OLD_FREE):
            long_term = await _load_memories(
                db, pet_id, MemoryTerm.LONG,
                types=[MemoryType.PROFILE], limit=10,
            )
            mid_term: list[PetMemory] = []
            short_term = await _load_memories(db, pet_id, MemoryTerm.SHORT, limit=10)

        elif tier == SubscriptionTier.PLUS:
            long_term = await _load_memories(db, pet_id, MemoryTerm.LONG, limit=20)
            mid_term = await _load_memories(db, pet_id, MemoryTerm.MID, limit=15)
            short_term = await _load_memories(db, pet_id, MemoryTerm.SHORT, limit=10)

        else:  # PRO
            long_term = await _load_memories(db, pet_id, MemoryTerm.LONG, limit=30)
            mid_term = await _load_memories(db, pet_id, MemoryTerm.MID, limit=20)
            short_term = await _load_memories(db, pet_id, MemoryTerm.SHORT, limit=15)

        turn_budget = _TURN_TOKEN_BUDGETS.get(tier, 1200)
        recent_turns = await _load_recent_turns(db, pet_id, user_id, token_budget=turn_budget)
        daily_summary = await _load_latest_summary(db, pet_id, "daily")
        weekly_summary = await _load_latest_summary(db, pet_id, "weekly")
        pending = await _load_pending_confirmations(db, pet_id, limit=3)

    return {
        "pet": pet,
        "long_term_memories": long_term,
        "mid_term_memories": mid_term,
        "short_term_memories": short_term,
        "recent_turns": recent_turns,
        "daily_summary": daily_summary,
        "weekly_summary": weekly_summary,
        "pending_confirmations": pending,
    }


async def load_related_memories(pet_id: str, user_message: str) -> list[PetMemory]:
    """
    Return active memories whose fields are topically related to *user_message*.

    Uses a TOPIC_MAP: message keywords → specific memory field names.
    Returns up to 10 rows, deduplicated, ordered most-recent first.
    """
    message_lower = user_message.lower()
    related_fields: set[str] = set()
    for keywords, fields in _TOPIC_MAP.items():
        if any(kw in message_lower for kw in keywords):
            related_fields.update(fields)

    if not related_fields:
        return []

    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(PetMemory)
            .where(
                PetMemory.pet_id == uuid.UUID(pet_id),
                PetMemory.field.in_(related_fields),
                PetMemory.is_active.is_(True),
            )
            .order_by(PetMemory.created_at.desc())
            .limit(10)
        )
        return list(result.scalars().all())


async def get_active_pet(user_id: str) -> Optional[Pet]:
    """
    Return the user's active pet.

    - 0 pets  → None
    - 1 pet   → return it directly
    - 2+ pets → find the one used most recently in a Dialogue
    """
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(Pet).where(
                Pet.user_id == uuid.UUID(user_id),
                Pet.is_active.is_(True),
            )
        )
        pets = list(result.scalars().all())

    if not pets:
        return None
    if len(pets) == 1:
        return pets[0]

    # Multiple pets: find the one referenced in the most recent Dialogue
    pet_id_strs = [str(p.id) for p in pets]
    factory = get_session_factory()
    async with factory() as db:
        latest = await db.execute(
            select(Dialogue.pet_id)
            .where(Dialogue.pet_id.in_(pet_id_strs))
            .order_by(Dialogue.created_at.desc())
            .limit(1)
        )
        latest_pet_id = latest.scalar_one_or_none()

    if latest_pet_id:
        return next((p for p in pets if str(p.id) == latest_pet_id), pets[0])
    return pets[0]


# ── Session-scoped helper (for use inside an existing db session) ─────────────


async def load_memory_field(
    db: AsyncSession,
    pet_id: uuid.UUID,
    field: str,
) -> Optional[PetMemory]:
    """Return the single active PetMemory for *pet_id* + *field*, or None."""
    result = await db.execute(
        select(PetMemory)
        .where(
            PetMemory.pet_id == pet_id,
            PetMemory.field == field,
            PetMemory.is_active.is_(True),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


# ── Private helpers ───────────────────────────────────────────────────────────


async def _load_memories(
    db: AsyncSession,
    pet_id: str,
    term: MemoryTerm,
    types: Optional[list[MemoryType]] = None,
    limit: int = 20,
) -> list[PetMemory]:
    """
    Return active, non-expired memories for *pet_id* filtered by term (and
    optionally by type). Results are ordered most-recent first.
    """
    stmt = (
        select(PetMemory)
        .where(
            PetMemory.pet_id == uuid.UUID(pet_id),
            PetMemory.memory_term == term,
            PetMemory.is_active.is_(True),
            or_(
                PetMemory.expires_at.is_(None),
                PetMemory.expires_at > func.now(),
            ),
        )
    )
    if types:
        stmt = stmt.where(PetMemory.memory_type.in_(types))

    stmt = stmt.order_by(PetMemory.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _fit_turns_to_budget(turns: list[dict], budget_tokens: int) -> list[dict]:
    """Return the most recent turns that fit within *budget_tokens*.

    Estimates 1 token per 4 characters (standard heuristic). Always keeps
    the most recent turn. Drops the oldest turns first when over budget.
    """
    if not turns:
        return []
    kept: list[dict] = []
    used = 0
    for turn in reversed(turns):
        tokens = max(1, len(turn.get("content", "")) // 4)
        if used + tokens > budget_tokens and kept:
            break
        kept.append(turn)
        used += tokens
    return list(reversed(kept))


async def _load_recent_turns(
    db: AsyncSession,
    pet_id: str,
    user_id: str,
    token_budget: int = 1200,
) -> list[dict]:
    """
    Load recent user/assistant turn pairs from the pet's most recent Dialogue,
    trimmed to fit within *token_budget* (estimated tokens).

    Fetches up to _DB_FETCH_MAX messages from the DB then selects the largest
    recent window that fits the budget — so long medical-advice turns naturally
    crowd out older context without a hard count cap.
    """
    dial_result = await db.execute(
        select(Dialogue.id)
        .where(Dialogue.pet_id == pet_id)
        .order_by(Dialogue.created_at.desc())
        .limit(1)
    )
    dialogue_id = dial_result.scalar_one_or_none()
    if not dialogue_id:
        return []

    msg_result = await db.execute(
        select(Message)
        .where(Message.dialogue_id == dialogue_id)
        .order_by(Message.created_at.desc())
        .limit(_DB_FETCH_MAX)
    )
    messages = list(reversed(msg_result.scalars().all()))

    turns = [
        {
            "role": _ROLE_MAP.get(m.role.value, m.role.value),
            "content": m.content,
        }
        for m in messages
    ]
    return _fit_turns_to_budget(turns, token_budget)


async def _load_latest_summary(
    db: AsyncSession,
    pet_id: str,
    period: str,
) -> Optional[DailySummary | WeeklySummary]:
    """
    Return the most recent DailySummary (period='daily') or
    WeeklySummary (period='weekly') for *pet_id*. Returns None if absent.
    """
    if period == "daily":
        result = await db.execute(
            select(DailySummary)
            .where(DailySummary.pet_id == pet_id)
            .order_by(DailySummary.date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    # weekly
    result = await db.execute(
        select(WeeklySummary)
        .where(WeeklySummary.pet_id == pet_id)
        .order_by(WeeklySummary.week_start.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _load_pending_confirmations(
    db: AsyncSession,
    pet_id: str,
    limit: int = 3,
) -> list[PendingMemoryChange]:
    """
    Return unconfirmed pending memory changes for *pet_id*, prioritising
    critical fields (breed, birth_date, chronic conditions, etc.) then recency.
    Expired items are excluded.
    """
    result = await db.execute(
        select(PendingMemoryChange)
        .where(
            PendingMemoryChange.pet_id == pet_id,
            PendingMemoryChange.validation_status == PendingStatus.NEEDS_CONFIRMATION,
            PendingMemoryChange.expires_at > func.now(),
        )
        .order_by(PendingMemoryChange.created_at.desc())
        .limit(limit * 4)  # fetch extra so we can re-sort in Python
    )
    all_pending = list(result.scalars().all())

    # Sort: critical fields first, then by recency
    def _sort_key(p: PendingMemoryChange) -> tuple[int, datetime]:
        priority = 0 if p.field in _CRITICAL_FIELDS else 1
        return (priority, p.created_at)

    all_pending.sort(key=_sort_key)
    return all_pending[:limit]
