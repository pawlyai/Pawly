"""
Merge / Veto Decision Layer.

Combines deterministic safety signals (crisis_gate, rules_engine, per-checklist
pre-fire U-triggers) with LLM-derived signals (scenario_scores,
urgency_soft_score) into a single routing decision.

Defense-in-depth principles:
    1. Deterministic veto wins. crisis_gate / rules_engine RED / pre-fire
       U-trigger all preempt LLM judgment.
    2. Scenarios are multi-label. Medical and emotional can co-exist.
    3. Asymmetric defaults. Ambiguity resolves toward more caution.
    4. High-priority sensitive checklists (OWNERMH, EUTHANASIA, ...) preempt
       generic emotional fallback even when emotional score is high — they
       carry domain-specific Section 9 hard limits that emotional doesn't.

Public API:
    decide(...) -> MergeDecision
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from src.checklists.loader import get as get_checklist
from src.checklists.router import PreFireResult
from src.db.models import TriageLevel
from src.triage.crisis_gate import CrisisResult
from src.triage.rules_engine import TriageRuleResult


Branch = Literal[
    "crisis",
    "abc_screen",
    "checklist",
    "checklist_prefire",     # checklist with U-trigger pre-fired → escalation immediately
    "emotional",
    "general",
]


@dataclass
class MergeDecision:
    branch: Branch
    triage_level: TriageLevel = TriageLevel.GREEN
    checklist_id: Optional[str] = None
    fired_trigger_id: Optional[str] = None
    rationale: list[str] = field(default_factory=list)

    rule_matched: list[str] = field(default_factory=list)
    scenario_scores: dict[str, float] = field(default_factory=dict)
    urgency_soft_score: float = 0.0
    apply_response_chrome: bool = True


# ── Thresholds ──────────────────────────────────────────────────────────────

CRISIS_LLM_THRESHOLD = 0.4
MEDICAL_THRESHOLD = 0.3
EMOTIONAL_THRESHOLD = 0.5
URGENCY_AMBIGUOUS_LOW = 0.3
URGENCY_AMBIGUOUS_HIGH = 0.7
ROUTING_CONFIDENCE_THRESHOLD = 0.30

# routing_priority at or above this counts as "sensitive checklist" — preempts
# both ABC and emotional fallback. OWNERMH=100, EUTHANASIA=90 qualify;
# VOMIT=50 does not.
SENSITIVE_PRIORITY_THRESHOLD = 80


def _is_sensitive(checklist_id: Optional[str]) -> bool:
    if not checklist_id:
        return False
    spec = get_checklist(checklist_id)
    if spec is None:
        return False
    return spec.routing_priority >= SENSITIVE_PRIORITY_THRESHOLD


def decide(
    crisis: CrisisResult,
    rule: TriageRuleResult,
    scenario_scores: dict[str, float],
    urgency_soft_score: float,
    router_checklist_id: Optional[str],
    router_confidence: float,
    pre_fire: Optional[PreFireResult] = None,
    pet_has_chronic_condition: bool = False,
    pet_is_juvenile: bool = False,
) -> MergeDecision:
    """Pick the response branch.

    Order of precedence (top wins):
        1. crisis_gate match               → crisis template (skip LLM)
        2. LLM scenario.crisis_human high  → crisis template
        3. rules_engine RED                → checklist (medical) + RED triage
        4. pre_fire U-trigger match        → checklist_prefire branch (deterministic
                                             escalation, skips ABC + slot filling)
        5. sensitive checklist routed      → checklist (preempts ABC + emotional;
                                             routing_priority ≥ 80)
        6. ambiguous urgency soft score    → ABC Quick Screen
        7. confident regular checklist     → checklist branch
        8. medical scenario without router → checklist branch (no specific id)
        9. emotional scenario              → emotional branch
       10. fallback                        → general branch
    """
    rationale: list[str] = []

    # ── 1. Hard crisis short-circuit ─────────────────────────────────────────
    if crisis.matched:
        return MergeDecision(
            branch="crisis",
            triage_level=TriageLevel.GREEN,
            rationale=[f"crisis_gate matched ({crisis.severity})"],
            scenario_scores=scenario_scores,
            urgency_soft_score=urgency_soft_score,
            apply_response_chrome=False,
        )

    # ── 2. LLM-flagged crisis ───────────────────────────────────────────────
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

    # ── 4. Pre-fire U-trigger ────────────────────────────────────────────────
    # Per-checklist deterministic escalation on natural-language paraphrases of
    # slot enum values (e.g. "vomited blood" → CL-VOMIT U1). Skips ABC and
    # slot filling — caller renders the matched trigger's escalation_template.
    if pre_fire is not None:
        rationale.append(
            f"pre_fire {pre_fire.checklist_id}/{pre_fire.trigger_id} on "
            f"'{pre_fire.matched_phrase}'"
        )
        return MergeDecision(
            branch="checklist_prefire",
            triage_level=TriageLevel.RED,
            checklist_id=pre_fire.checklist_id,
            fired_trigger_id=pre_fire.trigger_id,
            rationale=rationale,
            rule_matched=rule.matched_rules,
            scenario_scores=scenario_scores,
            urgency_soft_score=urgency_soft_score,
            apply_response_chrome=True,
        )

    # ── 5. Sensitive checklist preempts everything below ────────────────────
    # OWNERMH (100), EUTHANASIA (90), and any future P0 sensitive scenarios
    # carry domain-specific Section 9 hard limits — don't let emotional or
    # ABC steal them.
    if (
        router_checklist_id
        and router_confidence >= ROUTING_CONFIDENCE_THRESHOLD
        and _is_sensitive(router_checklist_id)
    ):
        rationale.append(
            f"sensitive checklist {router_checklist_id} (priority≥{SENSITIVE_PRIORITY_THRESHOLD}, "
            f"conf={router_confidence:.2f})"
        )
        return MergeDecision(
            branch="checklist",
            triage_level=rule.classification,
            checklist_id=router_checklist_id,
            rationale=rationale,
            rule_matched=rule.matched_rules,
            scenario_scores=scenario_scores,
            urgency_soft_score=urgency_soft_score,
            apply_response_chrome=False,        # sensitive scenarios manage their own UX
        )

    # ── 6. Ambiguous urgency → ABC Screen ────────────────────────────────────
    low = URGENCY_AMBIGUOUS_LOW
    if pet_has_chronic_condition:
        low -= 0.15
    if pet_is_juvenile:
        low -= 0.10
    low = max(low, 0.10)

    if urgency_soft_score >= low:
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

    # ── 7. Regular-priority checklist match ──────────────────────────────────
    if router_checklist_id and router_confidence >= ROUTING_CONFIDENCE_THRESHOLD:
        rationale.append(
            f"router={router_checklist_id} (conf={router_confidence:.2f})"
        )
        return MergeDecision(
            branch="checklist",
            triage_level=rule.classification,
            checklist_id=router_checklist_id,
            rationale=rationale,
            rule_matched=rule.matched_rules,
            scenario_scores=scenario_scores,
            urgency_soft_score=urgency_soft_score,
            apply_response_chrome=True,
        )

    # ── 8. Medical scenario score without specific router match ─────────────
    medical_score = scenario_scores.get("medical", 0.0)
    if medical_score >= MEDICAL_THRESHOLD:
        rationale.append(
            f"scenario.medical={medical_score:.2f}≥{MEDICAL_THRESHOLD} (no checklist)"
        )
        return MergeDecision(
            branch="checklist",
            triage_level=rule.classification,
            checklist_id=None,
            rationale=rationale,
            rule_matched=rule.matched_rules,
            scenario_scores=scenario_scores,
            urgency_soft_score=urgency_soft_score,
            apply_response_chrome=(rule.classification != TriageLevel.GREEN),
        )

    # ── 9. Emotional scenario ────────────────────────────────────────────────
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

    # ── 10. General fallback ─────────────────────────────────────────────────
    rationale.append("no triggers — general chat")
    return MergeDecision(
        branch="general",
        triage_level=TriageLevel.GREEN,
        rationale=rationale,
        scenario_scores=scenario_scores,
        urgency_soft_score=urgency_soft_score,
        apply_response_chrome=False,
    )
