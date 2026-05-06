"""
Slot-Filling Engine — drives the checklist-bound clarification loop.

State per dialogue:
    collected: dict[slot_id, value]    # what the user has answered so far
    asked: list[slot_id]               # what's been asked already (don't repeat)
    rounds: int                        # turns spent in this checklist

Each turn:
    1. Inspect already-collected slots (skip mandatory slots already answered)
    2. Pick next slot per Section 7 ask_order
    3. Format the question for the user's locale
    4. Return question OR fire urgency trigger OR exit to advice

The LLM is consulted in two narrow places:
    - Slot extraction: parse user text into structured slot values (cheap)
    - Per-turn judgment: did the user just give multiple slot values at once?

Public API:
    next_action(spec, collected, asked, user_text, locale) -> SlotAction
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

from src.checklists.schema import ChecklistSpec, SlotSpec, UrgencyTriggerSpec


ActionKind = Literal["ask", "urgency_fire", "ready_for_advice", "max_turns_reached"]


@dataclass
class SlotAction:
    kind: ActionKind
    next_question: Optional[str] = None
    next_slot_id: Optional[str] = None
    fired_trigger: Optional[UrgencyTriggerSpec] = None
    collected: dict[str, Any] = None
    rounds: int = 0


def _question_for(spec_slot: SlotSpec, locale: str) -> str:
    return spec_slot.question_zh if locale.lower().startswith("zh") else spec_slot.question_en


def _evaluate_condition(condition: str, collected: dict[str, Any]) -> bool:
    """Evaluate a checklist-condition string.

    V0: extremely simple expression engine. Supports patterns like:
        "M1 contains 'blood'"
        "M2 > 5"
        "M3 == 'pale'"
        "M1 contains 'blood' OR M1 contains 'coffee'"

    For anything beyond AND/OR + contains/==/<> />/<, return False (safe default).

    V1 (TODO): proper expression parser (e.g. Lark-based) once condition
    library grows.
    """
    expr = condition.strip()

    # OR clauses
    if " OR " in expr:
        parts = expr.split(" OR ")
        return any(_evaluate_condition(p.strip(), collected) for p in parts)
    if " AND " in expr:
        parts = expr.split(" AND ")
        return all(_evaluate_condition(p.strip(), collected) for p in parts)

    # contains
    if " contains " in expr:
        slot_id, _, needle = expr.partition(" contains ")
        slot_id = slot_id.strip()
        needle = needle.strip().strip("'\"")
        value = collected.get(slot_id)
        if isinstance(value, list):
            return any(needle.lower() in str(v).lower() for v in value)
        if isinstance(value, str):
            return needle.lower() in value.lower()
        return False

    # equality
    if "==" in expr:
        slot_id, _, val = expr.partition("==")
        slot_id = slot_id.strip()
        val = val.strip().strip("'\"")
        return str(collected.get(slot_id, "")).lower() == val.lower()

    # numeric comparison
    for op in (">=", "<=", ">", "<"):
        if op in expr:
            slot_id, _, val = expr.partition(op)
            try:
                left = float(collected.get(slot_id.strip(), 0))
                right = float(val.strip())
                return {
                    ">=": left >= right,
                    "<=": left <= right,
                    ">": left > right,
                    "<": left < right,
                }[op]
            except (ValueError, TypeError):
                return False

    return False


def _check_urgency_triggers(
    spec: ChecklistSpec,
    collected: dict[str, Any],
) -> Optional[UrgencyTriggerSpec]:
    """Return the first urgency trigger that fires, or None."""
    for trigger in spec.urgency_triggers:
        if _evaluate_condition(trigger.condition, collected):
            return trigger
    return None


def _all_required_filled(spec: ChecklistSpec, collected: dict[str, Any]) -> bool:
    for slot in spec.mandatory_slots:
        if slot.required and slot.id not in collected:
            return False
    return True


def _next_slot_to_ask(
    spec: ChecklistSpec,
    collected: dict[str, Any],
    asked: list[str],
) -> Optional[SlotSpec]:
    # First pass: ask order respected
    for slot_id in spec.ask_order:
        if slot_id in collected:
            continue
        slot = next(
            (s for s in spec.mandatory_slots if s.id == slot_id),
            None,
        )
        if slot is not None and slot.required:
            return slot

    # Fallback: any remaining mandatory slot not yet collected
    for slot in spec.mandatory_slots:
        if slot.required and slot.id not in collected:
            return slot

    # Mandatory all done — check conditional slots whose triggers fire
    for cond_slot in spec.conditional_slots:
        if cond_slot.id in collected or cond_slot.id in asked:
            continue
        if _evaluate_condition(cond_slot.trigger_condition, collected):
            return cond_slot

    return None


def next_action(
    spec: ChecklistSpec,
    collected: dict[str, Any],
    asked: list[str],
    rounds: int,
    locale: str = "en",
) -> SlotAction:
    """Determine what to do next given current slot state."""

    # 1. Always check urgency triggers first — collected values may have
    #    crossed a threshold that fires immediate escalation.
    fired = _check_urgency_triggers(spec, collected)
    if fired is not None:
        return SlotAction(
            kind="urgency_fire",
            fired_trigger=fired,
            collected=collected,
            rounds=rounds,
        )

    # 2. All mandatory slots filled → ready for advice
    if _all_required_filled(spec, collected):
        # Check for outstanding conditional slots
        next_slot = _next_slot_to_ask(spec, collected, asked)
        if next_slot is None:
            return SlotAction(
                kind="ready_for_advice",
                collected=collected,
                rounds=rounds,
            )

    # 3. Max turns reached → exit even if slots remain
    if rounds >= spec.max_turns:
        return SlotAction(
            kind="max_turns_reached",
            collected=collected,
            rounds=rounds,
        )

    # 4. Ask the next slot
    next_slot = _next_slot_to_ask(spec, collected, asked)
    if next_slot is None:
        return SlotAction(
            kind="ready_for_advice",
            collected=collected,
            rounds=rounds,
        )

    return SlotAction(
        kind="ask",
        next_question=_question_for(next_slot, locale),
        next_slot_id=next_slot.id,
        collected=collected,
        rounds=rounds,
    )
