"""
Checklist Router — pick the best checklist (or none) for a user message.

V0 strategy:
    1. Keyword-bag match across loaded checklists → candidate set with scores
    2. Apply false-positive filter (drop candidates whose FP phrases match)
    3. Apply LLM-provided scenario hints (intent / scenario_scores) when available
    4. Apply precedence_over rules to break ties
    5. Return top candidate above threshold, else None (route to general chat)

V1 (TODO): replace keyword scoring with embedding similarity once we have a
phrase bank covering each checklist's natural-language trigger surface.

Public API:
    route(user_message, intent_hint=None, scenario_scores=None) -> RouterResult
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from src.checklists.loader import all_approved, all_loaded
from src.checklists.schema import ChecklistSpec
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RouterResult:
    checklist_id: Optional[str]
    confidence: float                      # [0, 1]
    candidates: list[tuple[str, float]]    # (id, score) for all matched candidates


# Score thresholds
_MIN_CONFIDENCE = 0.30      # below this, return no checklist (general path)
_MIN_KEYWORD_HITS = 1       # must have at least N keyword matches


def _keyword_score(text: str, spec: ChecklistSpec) -> tuple[float, int]:
    """Return (score, hit_count) for a single checklist."""
    lowered = text.lower()
    hits = 0

    for kw in spec.trigger.keywords_en:
        if kw.lower() in lowered:
            hits += 1
    for kw in spec.trigger.keywords_zh:
        if kw in text:                      # don't lower — Chinese
            hits += 1

    if hits == 0:
        return 0.0, 0

    # False-positive filter: any FP phrase match → suppress this candidate
    for fp in spec.trigger.false_positive_phrases:
        if re.search(fp, lowered, flags=re.IGNORECASE):
            return 0.0, 0

    # Diminishing returns: 1 hit = 0.4, 2 = 0.6, 3 = 0.7, 4+ = 0.8
    score = min(0.4 + 0.15 * (hits - 1), 0.85)
    return score, hits


def _apply_precedence(
    ranked: list[tuple[ChecklistSpec, float, int]],
) -> list[tuple[ChecklistSpec, float, int]]:
    """If checklist A.precedence_over contains B, drop B from candidates."""
    ids_present = {spec.checklist_id for spec, _, _ in ranked}
    suppressed: set[str] = set()

    for spec, _, _ in ranked:
        for lower_id in spec.trigger.precedence_over:
            if lower_id in ids_present:
                suppressed.add(lower_id)

    return [(s, sc, h) for s, sc, h in ranked if s.checklist_id not in suppressed]


def route(
    user_message: str,
    intent_hint: Optional[str] = None,
    scenario_scores: Optional[dict[str, float]] = None,
    use_unapproved: bool = False,
) -> RouterResult:
    """Pick best matching checklist (or None for general path).

    Args:
        user_message: raw user text
        intent_hint: optional LLM-provided intent label (boosts matching)
        scenario_scores: optional LLM-provided multi-label scenario scores
        use_unapproved: include checklists not yet vet-signed (dev only)
    """
    pool = all_loaded() if use_unapproved else all_approved()
    if not pool:
        return RouterResult(checklist_id=None, confidence=0.0, candidates=[])

    ranked: list[tuple[ChecklistSpec, float, int]] = []
    for spec in pool:
        score, hits = _keyword_score(user_message, spec)
        if hits >= _MIN_KEYWORD_HITS:
            ranked.append((spec, score, hits))

    if not ranked:
        return RouterResult(checklist_id=None, confidence=0.0, candidates=[])

    # Apply precedence_over to drop dominated candidates
    ranked = _apply_precedence(ranked)

    # Sort by (score desc, routing_priority desc, hits desc)
    ranked.sort(key=lambda t: (t[1], t[0].routing_priority, t[2]), reverse=True)

    top_spec, top_score, _ = ranked[0]
    candidates = [(spec.checklist_id, score) for spec, score, _ in ranked]

    if top_score < _MIN_CONFIDENCE:
        return RouterResult(checklist_id=None, confidence=top_score, candidates=candidates)

    return RouterResult(
        checklist_id=top_spec.checklist_id,
        confidence=top_score,
        candidates=candidates,
    )
