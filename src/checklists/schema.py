"""
Pydantic schema for checklist YAML files.

Every YAML in src/checklists/data/ must validate against ChecklistSpec at
load time. Validation is the contract that lets the orchestrator trust the
data.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


SlotType = Literal["multiselect", "select", "text", "number", "boolean"]
TriageLevel = Literal["red", "orange", "green"]
UrgencyAction = Literal["immediate_emergency", "urgent_24h", "urgent_48h", "monitor"]
ApprovalStatus = Literal["draft", "vet_review", "approved", "deprecated"]


class TriggerSpec(BaseModel):
    keywords_en: list[str] = Field(default_factory=list)
    keywords_zh: list[str] = Field(default_factory=list)
    false_positive_phrases: list[str] = Field(default_factory=list)
    exclude_routes: list[str] = Field(default_factory=list)
    precedence_over: list[str] = Field(default_factory=list)


class SlotSpec(BaseModel):
    id: str
    purpose: str
    type: SlotType
    options: list[str] = Field(default_factory=list)
    question_en: str
    question_zh: str
    required: bool = True
    skip_if_in_memory: list[str] = Field(default_factory=list)


class ConditionalSlotSpec(SlotSpec):
    trigger_condition: str  # human-readable; evaluated via simple expression engine


class UrgencyTriggerSpec(BaseModel):
    id: str
    condition: str  # e.g. "M1 contains 'blood' OR M1 contains 'coffee_grounds'"
    action: UrgencyAction
    triage: TriageLevel
    rationale: str
    skip_remaining_clarification: bool = True


class HardLimitSpec(BaseModel):
    forbidden: list[str] = Field(default_factory=list)
    required: list[str] = Field(default_factory=list)


class AdviceTemplateSpec(BaseModel):
    signal_recap_en: str = ""
    signal_recap_zh: str = ""
    home_observation_en: str = ""
    home_observation_zh: str = ""
    return_for_vet_triggers_en: str = ""
    return_for_vet_triggers_zh: str = ""
    disclaimer_en: str = (
        "This isn't a diagnosis — if anything feels off, please reach out to your vet."
    )
    disclaimer_zh: str = (
        "这不是诊断,如果有任何疑虑请联系兽医。"
    )


class EscalationTemplateSpec(BaseModel):
    """Used when an urgency trigger fires — short-circuit response."""
    en: str
    zh: str


class ApprovalSpec(BaseModel):
    status: ApprovalStatus = "draft"
    approved_by: Optional[str] = None
    approved_date: Optional[str] = None
    license_number: Optional[str] = None
    notes: Optional[str] = None


class ChecklistSpec(BaseModel):
    checklist_id: str
    version: str = "0.1"
    title_en: str
    title_zh: str

    # Section 1 — applicable scope
    species: list[Literal["dog", "cat", "any"]] = Field(default_factory=lambda: ["any"])
    age_groups: list[Literal["any", "juvenile", "adult", "senior"]] = Field(
        default_factory=lambda: ["any"]
    )

    # Section 1 — trigger
    trigger: TriggerSpec

    # Section 2 — mandatory slots
    mandatory_slots: list[SlotSpec] = Field(default_factory=list)

    # Section 3 — conditional slots
    conditional_slots: list[ConditionalSlotSpec] = Field(default_factory=list)

    # Section 5 — urgency triggers
    urgency_triggers: list[UrgencyTriggerSpec] = Field(default_factory=list)

    # Section 7 — ask order: list of slot IDs in turn-priority order
    ask_order: list[str] = Field(default_factory=list)
    max_turns: int = 5

    # Section 9 — hard limits
    hard_limits: HardLimitSpec = Field(default_factory=HardLimitSpec)

    # Section 10 — advice template
    advice: AdviceTemplateSpec = Field(default_factory=AdviceTemplateSpec)

    # Section 5b — fired-trigger escalation message
    escalation_template: Optional[EscalationTemplateSpec] = None

    # Section 11 — approval audit trail
    approval: ApprovalSpec = Field(default_factory=ApprovalSpec)

    # Routing priority among co-triggered checklists. Higher wins.
    routing_priority: int = 50
