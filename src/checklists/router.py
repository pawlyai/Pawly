"""
Checklist Router — pick the best checklist (or none) for a user message.

Two responsibilities:
    1. route() — pick the best checklist via keyword (proximity-aware) match
    2. pre_fire_scan() — check if any U-trigger's pre_fire_keywords match the
       raw user message; if so, fire that trigger directly (skip ABC, skip
       slot filling)

Multi-word EN keyword matching uses token-proximity instead of substring
containment, so "put down" matches "put my old dog down" (gap=3).

V1 (TODO): replace keyword scoring with embedding similarity once we have a
phrase bank covering each checklist's natural-language trigger surface.

Public API:
    route(user_message, intent_hint=None, scenario_scores=None) -> RouterResult
    pre_fire_scan(user_message) -> Optional[PreFireResult]
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from src.checklists.loader import all_approved, all_loaded
from src.checklists.schema import ChecklistSpec, UrgencyTriggerSpec
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RouterResult:
    checklist_id: Optional[str]
    confidence: float                      # [0, 1]
    candidates: list[tuple[str, float]]    # (id, score) for all matched candidates


@dataclass
class PreFireResult:
    checklist_id: str
    trigger_id: str
    matched_phrase: str


# Score thresholds
_MIN_CONFIDENCE = 0.30
_MIN_KEYWORD_HITS = 1
_MAX_TOKEN_GAP = 3                          # words allowed between multi-word keyword tokens


# ── Tokenization & matching helpers ─────────────────────────────────────────

_WORD_RE = re.compile(r"[a-z0-9']+")


def _tokenize_en(text: str) -> list[str]:
    """Lowercase + word-level tokenization (strips punctuation)."""
    return _WORD_RE.findall(text.lower())


def _proximity_match(tokens: list[str], keyword: str, max_gap: int = _MAX_TOKEN_GAP) -> bool:
    """Match an EN keyword against tokenized text with proximity tolerance.

    Single-word keywords use plain containment (covers stems too).
    Multi-word keywords match when tokens appear in order with at most
    max_gap intervening words between consecutive matches.

    Examples (max_gap=3):
        "put down" matches "put my old dog down"           ✓ (gap=3)
        "ate chocolate" matches "ate some dark chocolate"   ✓ (gap=2)
        "won't eat" matches "won't even eat"                ✓ (gap=1)
        "blood urine" does NOT match "blood transfusion to urinary tract"  ✗
    """
    keyword_tokens = keyword.lower().split()
    if not keyword_tokens:
        return False

    if len(keyword_tokens) == 1:
        # Single token: stem-friendly containment ("vomit" matches "vomiting")
        kw = keyword_tokens[0]
        return any(kw == t or t.startswith(kw) for t in tokens)

    n = len(tokens)
    m = len(keyword_tokens)

    for i in range(n):
        if not _token_matches(tokens[i], keyword_tokens[0]):
            continue
        last = i
        ok = True
        for k in range(1, m):
            found = False
            search_end = min(last + 2 + max_gap, n)
            for j in range(last + 1, search_end):
                if _token_matches(tokens[j], keyword_tokens[k]):
                    last = j
                    found = True
                    break
            if not found:
                ok = False
                break
        if ok:
            return True
    return False


def _token_matches(text_token: str, kw_token: str) -> bool:
    """Token-level match: equal, or text token starts with kw token (stem)."""
    if text_token == kw_token:
        return True
    # Stem-tolerance: only when keyword token is reasonably long, to avoid
    # "i" matching "is" / "in" / etc.
    if len(kw_token) >= 4 and text_token.startswith(kw_token):
        return True
    return False


def _zh_match(text: str, keyword: str) -> bool:
    """Chinese keyword: substring containment (no whitespace tokenization)."""
    return keyword in text


# ── Pre-routing U-trigger scan ──────────────────────────────────────────────


def pre_fire_scan(
    user_message: str,
    use_unapproved: bool = False,
) -> Optional[PreFireResult]:
    """Scan user message against ALL loaded checklists' U-trigger pre_fire_keywords.

    Returns the FIRST checklist+trigger combo that matches, ordered by
    routing_priority desc. Caller should treat this as an immediate
    escalation signal (skip ABC, skip slot filling, render the trigger's
    escalation template).

    The pre-fire keywords are vet-curated natural-language paraphrases of
    the slot enum values referenced by U-trigger conditions, allowing
    deterministic emergency detection on the user's first message before
    any slot has been formally collected.
    """
    if not user_message:
        return None

    pool = all_loaded() if use_unapproved else all_approved()
    if not pool:
        return None

    # Sort by priority desc so high-priority checklists pre-fire first
    pool = sorted(pool, key=lambda s: s.routing_priority, reverse=True)

    tokens = _tokenize_en(user_message)
    text_lower = user_message.lower()

    for spec in pool:
        for trigger in spec.urgency_triggers:
            for phrase in trigger.pre_fire_keywords_en:
                if _proximity_match(tokens, phrase):
                    logger.info(
                        "pre_fire_scan matched",
                        checklist=spec.checklist_id,
                        trigger=trigger.id,
                        phrase=phrase,
                    )
                    return PreFireResult(
                        checklist_id=spec.checklist_id,
                        trigger_id=trigger.id,
                        matched_phrase=phrase,
                    )
            for phrase in trigger.pre_fire_keywords_zh:
                if _zh_match(user_message, phrase):
                    logger.info(
                        "pre_fire_scan matched (zh)",
                        checklist=spec.checklist_id,
                        trigger=trigger.id,
                        phrase=phrase,
                    )
                    return PreFireResult(
                        checklist_id=spec.checklist_id,
                        trigger_id=trigger.id,
                        matched_phrase=phrase,
                    )
    return None


# ── Routing ──────────────────────────────────────────────────────────────────


def _keyword_score(text: str, spec: ChecklistSpec) -> tuple[float, int]:
    """Return (score, hit_count) for a single checklist."""
    tokens = _tokenize_en(text)
    hits = 0

    for kw in spec.trigger.keywords_en:
        if _proximity_match(tokens, kw):
            hits += 1
    for kw in spec.trigger.keywords_zh:
        if _zh_match(text, kw):
            hits += 1

    if hits == 0:
        return 0.0, 0

    # False-positive filter: any FP phrase match → suppress this candidate
    text_lower = text.lower()
    for fp in spec.trigger.false_positive_phrases:
        if re.search(fp, text_lower, flags=re.IGNORECASE):
            return 0.0, 0

    score = min(0.4 + 0.15 * (hits - 1), 0.85)
    return score, hits


def _apply_precedence(
    ranked: list[tuple[ChecklistSpec, float, int]],
) -> list[tuple[ChecklistSpec, float, int]]:
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

    ranked = _apply_precedence(ranked)

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
