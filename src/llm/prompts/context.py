"""
Memory context formatter.

build_context_block() converts loaded memory rows into two strings:
    memory_context      — injected into the system prompt as "Known context"
    pending_confirmation — the top pending change, phrased for natural weaving

Memories within each section are sorted by a priority score
(confidence × recency_decay × type_weight) so the most reliable,
recent, and critical facts always surface first and are dropped last
when the token budget is tight.
"""

import math
from datetime import datetime, timezone
from typing import Any, Optional

from src.db.models import (
    DailySummary,
    MemoryType,
    PendingMemoryChange,
    PetMemory,
    Pet,
    WeeklySummary,
)

# ── Memory priority weights ───────────────────────────────────────────────────
# Higher weight = injected earlier, dropped last when token budget is tight.

_TYPE_WEIGHT: dict[MemoryType, float] = {
    MemoryType.CHRONIC:     1.0,   # chronic disease, known allergies
    MemoryType.SAFETY:      1.0,   # drug interactions, toxin flags
    MemoryType.EPISODE:     0.9,   # active/recent health episode
    MemoryType.SYMPTOM:     0.8,   # reported symptoms
    MemoryType.BASELINE:    0.6,   # weight, diet, exercise baselines
    MemoryType.SNAPSHOT:    0.5,   # point-in-time observation
    MemoryType.PATTERN:     0.5,   # recurring behaviour patterns
    MemoryType.ENVIRONMENT: 0.4,   # home setup, stressors
    MemoryType.PROFILE:     0.3,   # breed, age (already in pet profile)
}

# Memories older than this contribute ~50% of their peak score.
_RECENCY_HALF_LIFE_DAYS = 30.0


def _memory_score(m: PetMemory) -> float:
    """score = confidence × recency_decay × type_weight.

    Used to order memories so critical/confident/recent facts come first
    and are the last to be dropped if the token budget is exceeded.
    """
    type_w = _TYPE_WEIGHT.get(m.memory_type, 0.5)
    confidence = m.confidence_score if m.confidence_score is not None else 0.5

    if m.created_at:
        now = datetime.now(timezone.utc)
        created = m.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        days_ago = max(0.0, (now - created).total_seconds() / 86400)
        recency = math.exp(-days_ago / _RECENCY_HALF_LIFE_DAYS)
    else:
        recency = 0.5

    return confidence * recency * type_w


def build_context_block(
    pet: Pet,
    long_term: list[PetMemory],
    mid_term: list[PetMemory],
    short_term: list[PetMemory],
    recent_turns: list[dict],
    daily_summary: Optional[DailySummary],
    pending: list[PendingMemoryChange],
    weekly_summary: Optional[WeeklySummary] = None,
) -> tuple[str, str]:
    """
    Returns (memory_context, pending_confirmation).

    memory_context      — formatted multi-section string for system prompt injection
    pending_confirmation — single sentence describing the top unconfirmed change
    """
    sections: list[str] = []

    # ── Health history: chronic conditions, allergies, safety flags ───────────
    health_items = _filter(long_term, {MemoryType.CHRONIC, MemoryType.SAFETY})
    if health_items:
        sections.append("Health history: " + _join_items(health_items))

    # ── Baselines: weight, diet, exercise, bowel habits ───────────────────────
    baseline_items = _filter(long_term, {MemoryType.BASELINE})
    if baseline_items:
        sections.append("Baselines: " + _join_items(baseline_items))

    # ── Environment: home type, other pets, children, stressors ──────────────
    env_items = _filter(long_term, {MemoryType.ENVIRONMENT})
    if env_items:
        sections.append("Environment: " + _join_items(env_items))

    # ── Current status: short-term snapshots and acute symptoms ──────────────
    status_items = _filter(
        short_term + _filter(mid_term, {MemoryType.PATTERN, MemoryType.SYMPTOM}),
        {MemoryType.SNAPSHOT, MemoryType.PATTERN, MemoryType.SYMPTOM},
    )
    if status_items:
        sections.append("Current status: " + _join_items(status_items))

    # ── Active episodes: ongoing symptoms ─────────────────────────────────────
    episode_items = _filter(mid_term, {MemoryType.EPISODE})
    if episode_items:
        sections.append("Active episodes: " + _join_items(episode_items))

    # ── Weekly pattern (injected before daily so daily is the freshest) ───────
    if weekly_summary:
        highlights = (
            weekly_summary.summary.get("highlights")
            or weekly_summary.summary.get("core_issues")
        )
        if highlights:
            if isinstance(highlights, list):
                highlights = "; ".join(str(x) for x in highlights)
            sections.append(f"Weekly pattern: {highlights}")

    # ── Recent daily summary ──────────────────────────────────────────────────
    if daily_summary:
        core = (
            daily_summary.summary.get("highlights")
            or daily_summary.summary.get("core_issues")
        )
        if core:
            if isinstance(core, list):
                core = "; ".join(str(x) for x in core)
            sections.append(f"Recent summary: {core}")

    memory_context = "\n".join(sections)

    # ── Pending confirmation (top 1 item) ─────────────────────────────────────
    pending_confirmation = _format_pending(pending)

    return memory_context, pending_confirmation


# ── Internal helpers ──────────────────────────────────────────────────────────


def _filter(
    memories: list[PetMemory],
    types: set[MemoryType],
) -> list[PetMemory]:
    return [m for m in memories if m.memory_type in types]


def _join_items(memories: list[PetMemory]) -> str:
    # Sort by priority score: critical/confident/recent memories come first.
    sorted_mems = sorted(memories, key=_memory_score, reverse=True)
    parts = []
    for m in sorted_mems:
        value = _fmt(m.value)
        parts.append(f"{m.field}={value}")
    return ", ".join(parts)


def _fmt(value: Any) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{k}:{v}" for k, v in value.items())
    if isinstance(value, list):
        return "/".join(str(v) for v in value)
    return str(value)


def _format_pending(pending: list[PendingMemoryChange]) -> str:
    if not pending:
        return ""

    item = pending[0]
    proposed = _fmt(item.proposed_value)

    if item.conflict_with_id:
        return (
            f'User previously mentioned "{item.source_quote}". '
            f"This suggests {item.field} = {proposed}, "
            f"but a different value is already stored. "
            f"Ask which is correct."
        )

    return (
        f'User previously mentioned "{item.source_quote}". '
        f"This suggests {item.field} = {proposed}. "
        f"Confirm naturally in conversation."
    )
