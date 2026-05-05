"""
Merge / Veto Decision Layer.

Combines deterministic safety signals (crisis_gate, rules_engine, per-checklist
U-triggers) with LLM-derived signals (scenario_scores, urgency_soft_score)
into a single routing decision.

Defense-in-depth principles:
    1. Deterministic veto wins. If crisis_gate or rules_engine RED fires,
       LLM judgment cannot override.
    2. Scenarios are multi-label. Medical and emotional can co-exist; each
       drives independent UX adjustments.
    3. Asymmetric defaults. Ambiguity resolves toward MORE caution
       (more likely to escalate / ABC-screen / route to medical).

Public API:
    decide(...) -> MergeDecision
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from src.db.models import TriageLevel
from src.triage.crisis_gate import CrisisResult
from src.triage.rules_engine import TriageRuleResult


Branch = Literal[
    "crisis",            # Self-harm: short-circuit to crisis template
    "abc_screen",        # Soft urgency: ask 3 vital-sign questions first
    "checklist",         # Confident medical: route to specific checklist
    "emotional",         # Emotional support (grief, anxiety): no medical chrome
    "general",           # Casual / educational: free LLM chat
]


@dataclass
class MergeDecision:
    branch: Branch
    triage_level: TriageLevel = TriageLevel.GREEN
    checklist_id: Optional[str] = None
    rationale: list[str] = field(default_factory=list)

    # Pass-through context for downstream processing
    rule_matched: list[str] = field(default_factory=list)
    scenario_scores: dict[str, float] = field(default_factory=dict)
    urgency_soft_score: float = 0.0
    apply_response_chrome: bool = True


# ── Thresholds (tunable; do NOT tune against light-30) ──────────────────────

CRISIS_LLM_THRESHOLD = 0.4       # scenario_scores.crisis_human ≥ this → crisis
MEDICAL_THRESHOLD = 0.3          # scenario_scores.medical ≥ this → checklist routing
EMOTIONAL_THRESHOLD = 0.5        # scenario_scores.emotional ≥ this → soften UX
URGENCY_AMBIGUOUS_LOW = 0.3      # below: skip ABC
URGENCY_AMBIGUOUS_HIGH = 0.7     # above: trigger ABC
ROUTING_CONFIDENCE_THRESHOLD = 0.30  # checklist router min confidence


def decide(
    crisis: CrisisResult,
    rule: TriageRuleResult,
    scenario_scores: dict[str, float],
    urgency_soft_score: float,
    router_checklist_id: Optional[str],
    router_confidence: float,
    pet_has_chronic_condition: bool = False,
    pet_is_juvenile: bool = False,
) -> MergeDecision:
    """Pick the response branch.

    Order of precedence (top wins):
        1. crisis_gate match               → crisis template, skip LLM
        2. crisis scenario score high       → crisis template, skip LLM
        3. rules_engine RED                 → checklist (medical) + RED triage
        4. ambiguous urgency (soft score)   → ABC Screen
        5. router has confident checklist   → checklist branch
        6. emotional scenario score high    → emotional branch
        7. low medical score & no triggers  → general branch
    """
    rationale: list[str] = []

    # ── 1. Hard crisis short-circuit ─────────────────────────────────────────
    if crisis.matched:
        return MergeDecision(
            branch="crisis",
            triage_level=TriageLevel.GREEN,    # crisis isn't medical RED
            rationale=[f"crisis_gate matched ({crisis.severity})"],
            scenario_scores=scenario_scores,
            urgency_soft_score=urgency_soft_score,
            apply_response_chrome=False,
        )

    # ── 2. LLM-flagged crisis (subtle suicidality the keyword bank missed) ──
    if scenario_scores.get("crisis_human", 0.0) >= CRISIS_LLM_THRESHOLD:
        rationale.append(
            f"scenario.crisis_human={scenario_scores['crisis_human']:.2f}≥{CRISIS_LLM_THRESHOLD}"
        )
        return MergeDecision(
            branch="crisis",
            triage_level=TriageLevel.GREEN,
            rationale=rationale,
            scenario_scores=scenario_scores,
            urgency_soft_score=urgency_soft_score,
            apply_response_chrome=False,
        )

    # ── 3. Deterministic medical RED veto ────────────────────────────────────
    if rule.classification == TriageLevel.RED:
        rationale.append(f"rules_engine RED ({','.join(rule.matched_rules)})")
        return MergeDecision(
            branch="checklist",
            triage_level=TriageLevel.RED,
            checklist_id=router_checklist_id,
            rationale=rationale,
            rule_matched=rule.matched_rules,
            scenario_scores=scenario_scores,
            urgency_soft_score=urgency_soft_score,
            apply_response_chrome=True,
        )

    # ── 4. Ambiguous urgency → ABC Screen ────────────────────────────────────
    # Threshold lowered for vulnerable pets (asymmetric cost).
    low = URGENCY_AMBIGUOUS_LOW
    if pet_has_chronic_condition:
        low -= 0.15
    if pet_is_juvenile:
        low -= 0.10
    low = max(low, 0.10)

    if URGENCY_AMBIGUOUS_LOW > 0 and urgency_soft_score >= low:
        rationale.append(
            f"urgency_soft={urgency_soft_score:.2f}≥{low:.2f} → ABC screen"
        )
        return MergeDecision(
            branch="abc_screen",
            triage_level=rule.classification,
            rationale=rationale,
            rule_matched=rule.matched_rules,
            scenario_scores=scenario_scores,
            urgency_soft_score=urgency_soft_score,
            apply_response_chrome=False,
        )

    # ── 5. Confident medical routing ─────────────────────────────────────────
    medical_score = scenario_scores.get("medical", 0.0)
    if router_checklist_id and router_confidence >= ROUTING_CONFIDENCE_THRESHOLD:
        rationale.append(
            f"router={router_checklist_id} (conf={router_confidence:.2f})"
        )
        triage = (
            rule.classification
            if rule.classification != TriageLevel.GREEN
            else TriageLevel.GREEN
        )
        return MergeDecision(
            branch="checklist",
            triage_level=triage,
            checklist_id=router_checklist_id,
            rationale=rationale,
            rule_matched=rule.matched_rules,
            scenario_scores=scenario_scores,
            urgency_soft_score=urgency_soft_score,
            apply_response_chrome=True,
        )

    # ── 5b. Medical score implies medical even without router match ─────────
    # Default to general medical chat (no specific checklist) — solves the
    # "scenario classifier said medical but no checklist matched keywords" case.
    if medical_score >= MEDICAL_THRESHOLD:
        rationale.append(
            f"scenario.medical={medical_score:.2f}≥{MEDICAL_THRESHOLD} (no checklist match)"
        )
        return MergeDecision(
            branch="checklist",
            triage_level=rule.classification,    # ORANGE if ORANGE keyword hit
            checklist_id=None,                   # generic medical path
            rationale=rationale,
            rule_matched=rule.matched_rules,
            scenario_scores=scenario_scores,
            urgency_soft_score=urgency_soft_score,
            apply_response_chrome=(rule.classification != TriageLevel.GREEN),
        )

    # ── 6. Emotional scenario ─────────────────────────────────────────────────
    if scenario_scores.get("emotional", 0.0) >= EMOTIONAL_THRESHOLD:
        rationale.append(
            f"scenario.emotional={scenario_scores['emotional']:.2f}≥{EMOTIONAL_THRESHOLD}"
        )
        return MergeDecision(
            branch="emotional",
            triage_level=TriageLevel.GREEN,
            rationale=rationale,
            scenario_scores=scenario_scores,
            urgency_soft_score=urgency_soft_score,
            apply_response_chrome=False,
        )

    # ── 7. General fallback ───────────────────────────────────────────────────
    rationale.append("no triggers — general chat")
    return MergeDecision(
        branch="general",
        triage_level=TriageLevel.GREEN,
        rationale=rationale,
        scenario_scores=scenario_scores,
        urgency_soft_score=urgency_soft_score,
        apply_response_chrome=False,
    )
