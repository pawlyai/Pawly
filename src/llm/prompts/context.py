"""
Memory context formatter.

build_context_block() converts loaded memory rows into two strings:
    memory_context      — injected into the system prompt as "Known context"
    pending_confirmation — the top pending change, phrased for natural weaving

Sections are ordered by clinical/contextual priority so that when the
max_memory_tokens budget is reached, the least important sections are
dropped first:

  1. Health history  (CHRONIC + SAFETY)  — always keep; life-critical
  2. Active episodes (ongoing illness)   — most relevant to current turn
  3. Current status  (recent symptoms)   — current visit context
  4. Baselines       (weight/diet)       — useful background
  5. Environment     (home/stressors)    — lowest-priority structural info
  6. Weekly pattern  (summary)           — can be inferred from above
  7. Recent summary  (daily)             — most redundant with recent_turns

Within each section, items are sorted by:
    score = confidence × recency_decay × type_weight
so the most reliable, recent, and critical facts come first.
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

_TYPE_WEIGHT: dict[MemoryType, float] = {
    MemoryType.CHRONIC:      1.0,
    MemoryType.SAFETY:       1.0,
    MemoryType.INTERVENTION: 0.95,
    MemoryType.EPISODE:      0.9,
    MemoryType.SYMPTOM:      0.8,
    MemoryType.BASELINE:     0.6,
    MemoryType.SNAPSHOT:     0.5,
    MemoryType.PATTERN:      0.5,
    MemoryType.ENVIRONMENT:  0.4,
    MemoryType.PROFILE:      0.3,
}

_RECENCY_HALF_LIFE_DAYS = 30.0

# Default proactive token cap for the assembled memory context block.
# The system.py hard cap (6 000 tokens) acts as a safety net; this budget
# ensures memory rarely needs reactive truncation and reserves headroom for
# KB slots and recent turns.
_DEFAULT_MAX_MEMORY_TOKENS = 1000


def _memory_score(m: PetMemory) -> float:
    """score = confidence × recency_decay × type_weight."""
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
    max_memory_tokens: int = _DEFAULT_MAX_MEMORY_TOKENS,
    session_bridge: Optional[dict] = None,  # P0: Cross-day continuity
) -> tuple[str, str]:
    """
    Returns (memory_context, pending_confirmation).

    memory_context      — formatted multi-section string for system prompt injection
    pending_confirmation — single sentence describing the top unconfirmed change

    P0 Enhancement: Session Bridge
    - If session_bridge provided (new session), inject previous day's summary first
    - Dramatically improves cross-day continuity
    """

    # ── Build ordered section list ────────────────────────────────────────────
    # Sections are appended in priority order (highest first) so that when
    # max_memory_tokens is exceeded, sections.pop() removes the least important.

    sections: list[str] = []

    # P0: Session bridge (highest priority for new sessions)
    if session_bridge and session_bridge.get("context_hint"):
        sections.append(f"Continuity from previous session: {session_bridge['context_hint']}")

    # 1. Health history: chronic conditions, allergies, safety flags
    health_items = _filter(long_term, {MemoryType.CHRONIC, MemoryType.SAFETY})
    if health_items:
        sections.append("Health history: " + _join_items(health_items))

    # 2. Active episodes: ongoing health episodes (highest clinical relevance)
    episode_items = _filter(mid_term, {MemoryType.EPISODE})
    if episode_items:
        sections.append("Active episodes: " + _join_items(episode_items))

    # 3. Current status: recent snapshots + acute symptoms
    status_items = _filter(
        short_term + _filter(mid_term, {MemoryType.PATTERN, MemoryType.SYMPTOM}),
        {MemoryType.SNAPSHOT, MemoryType.PATTERN, MemoryType.SYMPTOM},
    )
    if status_items:
        sections.append("Current status: " + _join_items(status_items))

    # 4. Baselines: weight, diet, exercise, bowel habits
    baseline_items = _filter(long_term, {MemoryType.BASELINE})
    if baseline_items:
        sections.append("Baselines: " + _join_items(baseline_items))

    # 5. Environment: home type, other pets, children, stressors
    env_items = _filter(long_term, {MemoryType.ENVIRONMENT})
    if env_items:
        sections.append("Environment: " + _join_items(env_items))

    # 6. Weekly pattern summary (lower priority — partially redundant with above)
    if weekly_summary:
        highlights = (
            weekly_summary.summary.get("highlights")
            or weekly_summary.summary.get("core_issues")
        )
        if highlights:
            if isinstance(highlights, list):
                highlights = "; ".join(str(x) for x in highlights)
            sections.append(f"Weekly pattern: {highlights}")

    # 7. Recent daily summary (lowest priority — most redundant with recent_turns)
    if daily_summary:
        core = (
            daily_summary.summary.get("highlights")
            or daily_summary.summary.get("core_issues")
        )
        if core:
            if isinstance(core, list):
                core = "; ".join(str(x) for x in core)
            sections.append(f"Recent summary: {core}")

    # ── Proactive token-budget trimming ───────────────────────────────────────
    # Drop least-important sections (from the end) until within max_memory_tokens.
    # Health history is always kept (sections[0]); we never drop below 1 section.
    memory_context = "\n".join(sections)
    while len(sections) > 1 and _estimate_tokens(memory_context) > max_memory_tokens:
        sections.pop()
        memory_context = "\n".join(sections)

    # ── Pending confirmation (top 1 item) ─────────────────────────────────────
    pending_confirmation = _format_pending(pending)

    return memory_context, pending_confirmation


# ── Internal helpers ──────────────────────────────────────────────────────────


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _filter(
    memories: list[PetMemory],
    types: set[MemoryType],
) -> list[PetMemory]:
    return [m for m in memories if m.memory_type in types]


def _join_items(memories: list[PetMemory]) -> str:
    """Format memories as readable context string.

    Mem0 improvement: Include temporal_context to clarify when facts occurred.
    Example: "symptom_severity=moderate limping (Month 2)" vs just "moderate limping"
    helps LLM distinguish temporal trajectory.
    """
    sorted_mems = sorted(memories, key=_memory_score, reverse=True)
    parts = []
    for m in sorted_mems:
        value = _fmt(m.value)
        # Add temporal context if available (Mem0 feature for cross-day continuity)
        if m.temporal_context:
            parts.append(f"{m.field}={value} ({m.temporal_context})")
        else:
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
