"""
Validation rules for proposed memory changes.

validate_proposal() takes a MemoryProposal and the pet's existing memories and
returns a ValidationResult. It never writes to the database.

Decision tree:
  1. Schema: field must be in ALLOWED_FIELDS
  2. Freshness: reject if same field was written < 1 hour ago
  3. Dedup: reject if same field + same normalised value is already active
  4. Critical fields → always NEEDS_CONFIRMATION
  5. Confidence thresholds per memory_term (LONG ≥ 0.85, MID ≥ 0.75, SHORT ≥ 0.60)
  6. Conflict (same field, different value):
       confidence ≥ 0.90 → AUTO_APPROVED (override)
       confidence ≥ min_threshold → NEEDS_CONFIRMATION
       otherwise → REJECTED

TTL: SHORT=7d, MID=180d, LONG=permanent (None)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.db.models import MemoryTerm, PendingStatus, Pet, PetMemory
from src.memory.extractor import MemoryProposal

# ── Configuration ─────────────────────────────────────────────────────────────

CRITICAL_FIELDS: frozenset[str] = frozenset([
    "breed", "birth_date", "gender", "neutered_status",
    "chronic_conditions", "allergy_list", "medication_history",
])

# All fields the extractor is allowed to produce, mapped to their expected term.
ALLOWED_FIELDS: dict[str, MemoryTerm] = {
    # ── LONG ─────────────────────────────────────────────────────────────────
    "weight_latest":          MemoryTerm.LONG,
    "stage":                  MemoryTerm.LONG,
    "breed":                  MemoryTerm.LONG,
    "birth_date":             MemoryTerm.LONG,
    "gender":                 MemoryTerm.LONG,
    "neutered_status":        MemoryTerm.LONG,
    "chronic_conditions":     MemoryTerm.LONG,
    "allergy_list":           MemoryTerm.LONG,
    "medication_history":     MemoryTerm.LONG,
    "food_allergy":           MemoryTerm.LONG,
    "drug_allergy":           MemoryTerm.LONG,
    "water_intake_habit":     MemoryTerm.LONG,
    "meal_frequency":         MemoryTerm.LONG,
    "feeding_method":         MemoryTerm.LONG,
    "meal_amount":            MemoryTerm.LONG,
    "exercise_habit":         MemoryTerm.LONG,
    "exercise_duration":      MemoryTerm.LONG,
    "bowel_frequency":        MemoryTerm.LONG,
    "bowel_health":           MemoryTerm.LONG,
    "is_stomach_sensitive":   MemoryTerm.LONG,
    "seasonal_issues":        MemoryTerm.LONG,
    "home_type":              MemoryTerm.LONG,
    "home_environment":       MemoryTerm.LONG,
    "has_other_pets":         MemoryTerm.LONG,
    "has_children":           MemoryTerm.LONG,
    "stress_sources":         MemoryTerm.LONG,
    "household_members":      MemoryTerm.LONG,
    "pet_human_preferences":  MemoryTerm.LONG,
    "emergency_contact":      MemoryTerm.LONG,
    "preferred_vet_clinic":   MemoryTerm.LONG,
    # ── MID ──────────────────────────────────────────────────────────────────
    "current_symptom":        MemoryTerm.MID,
    "symptom_onset":          MemoryTerm.MID,
    "symptom_frequency":      MemoryTerm.MID,
    "symptom_severity":       MemoryTerm.MID,
    "recent_diet_change":     MemoryTerm.MID,
    "recent_food_brand":      MemoryTerm.MID,
    "diet_change_period":     MemoryTerm.MID,
    "is_stressed":            MemoryTerm.MID,
    "stress_trigger":         MemoryTerm.MID,
    "environment_change":     MemoryTerm.MID,
    "vaccination_status":     MemoryTerm.MID,
    "vaccination_date":       MemoryTerm.MID,
    "deworming_status":       MemoryTerm.MID,
    "treatment_action":       MemoryTerm.MID,
    "vet_diagnosis":          MemoryTerm.MID,
    "vet_prescription":       MemoryTerm.MID,
    "lab_results":            MemoryTerm.MID,
    # ── SHORT ─────────────────────────────────────────────────────────────────
    "current_appetite":       MemoryTerm.SHORT,
    "current_water_intake":   MemoryTerm.SHORT,
    "current_energy_level":   MemoryTerm.SHORT,
    "current_bowel_status":   MemoryTerm.SHORT,
    "current_vomiting":       MemoryTerm.SHORT,
    "current_breathing":      MemoryTerm.SHORT,
    "current_pain_signs":     MemoryTerm.SHORT,
}

# TTL per memory term
_TTL: dict[MemoryTerm, Optional[timedelta]] = {
    MemoryTerm.SHORT: timedelta(days=7),
    MemoryTerm.MID:   timedelta(days=180),
    MemoryTerm.LONG:  None,
}

# Minimum confidence to auto-approve per memory term
_MIN_CONFIDENCE: dict[MemoryTerm, float] = {
    MemoryTerm.LONG:  0.85,
    MemoryTerm.MID:   0.75,
    MemoryTerm.SHORT: 0.60,
}

# How soon after a write to reject a duplicate extraction
_FRESHNESS_WINDOW = timedelta(hours=1)

# High-confidence threshold for overriding a conflicting existing value
_OVERRIDE_CONFIDENCE = 0.90


# ── Result type ───────────────────────────────────────────────────────────────


@dataclass
class ValidationResult:
    status: PendingStatus        # AUTO_APPROVED | NEEDS_CONFIRMATION | REJECTED
    reason: str
    conflict_with_id: Optional[str] = None
    expires_at: Optional[datetime] = None


# ── Public API ────────────────────────────────────────────────────────────────


def validate_proposal(
    proposal: MemoryProposal,
    existing: list[PetMemory],
    pet: Pet,
) -> ValidationResult:
    """
    Validate *proposal* against the pet's current memories.

    Args:
        proposal: extracted fact to evaluate
        existing: all active PetMemory rows for this pet (read-only)
        pet:      Pet ORM object (reserved for future breed-specific rules)

    Returns:
        ValidationResult with status, reason, optional conflict_with_id,
        and expires_at (for the PendingMemoryChange or new PetMemory row).
    """
    now = datetime.now(timezone.utc)

    # ── 1. Schema check ───────────────────────────────────────────────────────
    if proposal.field not in ALLOWED_FIELDS:
        return ValidationResult(
            status=PendingStatus.REJECTED,
            reason=f"unknown_field:{proposal.field}",
        )

    # Pre-compute useful record sets
    field_records = [m for m in existing if m.field == proposal.field]
    active_record = next((m for m in field_records if m.is_active), None)

    # ── 2. Freshness check ────────────────────────────────────────────────────
    if active_record:
        anchor = active_record.updated_at or active_record.created_at
        if anchor:
            ts = anchor if anchor.tzinfo else anchor.replace(tzinfo=timezone.utc)
            if (now - ts) < _FRESHNESS_WINDOW:
                return ValidationResult(status=PendingStatus.REJECTED, reason="too_recent")

    # ── 3. Dedup check ────────────────────────────────────────────────────────
    proposed_norm = _normalise(proposal.value)
    if active_record and active_record.value == proposed_norm:
        return ValidationResult(status=PendingStatus.REJECTED, reason="duplicate")

    # Compute expires_at for the new record / pending change
    ttl = _TTL.get(proposal.memory_term)
    expires_at = (now + ttl) if ttl else None
    # Critical + non-TTL fields still need a finite expiry on the pending row
    confirm_expires = expires_at or (now + timedelta(days=7))

    # ── 4. Critical fields → always require user confirmation ─────────────────
    if proposal.field in CRITICAL_FIELDS:
        return ValidationResult(
            status=PendingStatus.NEEDS_CONFIRMATION,
            reason="critical_field",
            conflict_with_id=str(active_record.id) if active_record else None,
            expires_at=confirm_expires,
        )

    min_conf = _MIN_CONFIDENCE.get(proposal.memory_term, 0.85)

    # ── 5 + 6. Confidence + conflict resolution ───────────────────────────────
    if active_record:
        # Conflict: active record exists with a different value
        if proposal.confidence >= _OVERRIDE_CONFIDENCE:
            return ValidationResult(
                status=PendingStatus.AUTO_APPROVED,
                reason="high_confidence_override",
                conflict_with_id=str(active_record.id),
                expires_at=expires_at,
            )
        if proposal.confidence >= min_conf:
            return ValidationResult(
                status=PendingStatus.NEEDS_CONFIRMATION,
                reason="conflict_needs_confirmation",
                conflict_with_id=str(active_record.id),
                expires_at=confirm_expires,
            )
        return ValidationResult(
            status=PendingStatus.REJECTED,
            reason=f"low_confidence:{proposal.confidence:.2f}<{min_conf}",
        )

    # New fact — no existing active record
    if proposal.confidence >= min_conf:
        return ValidationResult(
            status=PendingStatus.AUTO_APPROVED,
            reason="new_fact_auto_approved",
            expires_at=expires_at,
        )

    return ValidationResult(
        status=PendingStatus.REJECTED,
        reason=f"low_confidence:{proposal.confidence:.2f}<{min_conf}",
    )


# ── Internal ──────────────────────────────────────────────────────────────────


def _normalise(value: object) -> object:
    """Wrap scalar values the same way the committer will store them."""
    return value if isinstance(value, dict) else {"v": value}
