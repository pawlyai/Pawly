"""
Memory context formatter.

build_context_block() converts loaded memory rows into two strings:
    memory_context      — injected into the system prompt as "Known context"
    pending_confirmation — the top pending change, phrased for natural weaving

Keeps total context under ~1500 tokens by skipping empty sections.
"""

from typing import Any, Optional

from src.db.models import (
    DailySummary,
    MemoryType,
    PendingMemoryChange,
    PetMemory,
    Pet,
)


def build_context_block(
    pet: Pet,
    long_term: list[PetMemory],
    mid_term: list[PetMemory],
    short_term: list[PetMemory],
    recent_turns: list[dict],
    daily_summary: Optional[DailySummary],
    pending: list[PendingMemoryChange],
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

    # ── Current status: short-term snapshots (appetite, energy, mood…) ───────
    status_items = _filter(
        short_term + _filter(mid_term, {MemoryType.PATTERN}),
        {MemoryType.SNAPSHOT, MemoryType.PATTERN},
    )
    if status_items:
        sections.append("Current status: " + _join_items(status_items))

    # ── Active episodes: ongoing symptoms ─────────────────────────────────────
    episode_items = _filter(mid_term, {MemoryType.EPISODE})
    if episode_items:
        sections.append("Active episodes: " + _join_items(episode_items))

    # ── Recent daily summary ──────────────────────────────────────────────────
    if daily_summary:
        core = daily_summary.summary.get("highlights") or daily_summary.summary.get("core_issues")
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
    parts = []
    for m in memories:
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

    # Take the most recent pending item
    item = pending[0]
    proposed = _fmt(item.proposed_value)

    if item.conflict_with_id:
        # There's a conflict with an existing memory value
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
