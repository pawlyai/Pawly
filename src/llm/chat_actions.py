"""
Chat-actions orchestration layer for the 聊天办事 feature.

Defines:
  CHAT_ACTION_SCHEMA     — JSON schema for structured LLM output
  validate_and_fix()     — enforce hard composition rules (§3 §4 §5)

Rules enforced (non-exhaustive; see Sheets 校验点列):
  §3 rule 1/2  Block ordering: answer/clarify → educate → (record handled separately)
  §3 rule 5    educate.redflag suppresses educate.daily in the same turn
  §3 rule 3    Max 1 answer, max 1 educate per turn
  §4           Safety scenes suppress conversion (Free user check is caller's responsibility)
  §5           Whitelist: open_photo_check / modify_programme are hard-forbidden
  Safety inj.  safety_level=red → deterministic nearest_clinics + vet_summary injection
               (mirrors prepend_safety_banner; never relies on LLM output for safety-critical nav)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── Allowed type / action id sets ────────────────────────────────────────────

DISPLAY_BLOCK_TYPES: frozenset[str] = frozenset({
    "answer",
    "clarify",
    "educate.daily",
    "educate.redflag",
})

RECORD_ACTION_IDS: frozenset[str] = frozenset({
    "record.log_symptom",
    "record.episode_followup",
    "record.observation",
    "record.update_profile",
    "record.allergy_add",
})

NAV_ACTION_IDS: frozenset[str] = frozenset({
    "open_page",
    "open_programme",
    "add_reminder",
    "nearest_clinics",
    "vet_summary",
})

# Hard-forbidden regardless of context (§1 whitelist, §2 plan-modification gate)
FORBIDDEN_ACTION_IDS: frozenset[str] = frozenset({
    "open_photo_check",   # not this phase
    "modify_programme",   # chat cannot modify plans; plan page handles it
})

# Block ordering within a single turn (lower = earlier)
_BLOCK_ORDER: dict[str, int] = {
    "answer":          0,
    "clarify":         0,  # replaces answer when gathering info
    "educate.daily":   1,
    "educate.redflag": 1,
}


# ── Structured output schema ──────────────────────────────────────────────────

CHAT_ACTION_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "blocks": {
            "type": "ARRAY",
            "description": (
                "Ordered display blocks rendered in chat. "
                "Max 1 answer/clarify and 1 educate.* per turn. "
                "Ordering must be: answer/clarify → educate.* ."
            ),
            "items": {
                "type": "OBJECT",
                "properties": {
                    "type": {
                        "type": "STRING",
                        "enum": sorted(DISPLAY_BLOCK_TYPES),
                    },
                    "text": {
                        "type": "STRING",
                        "description": "User-facing text for this block.",
                    },
                    "grounded_by": {
                        "type": "STRING",
                        "description": "KB source id (§5 grounding gate). Required for answer blocks.",
                    },
                    "asset_id": {
                        "type": "STRING",
                        "description": "kb_img:// URI for educate.* blocks.",
                    },
                },
                "required": ["type", "text"],
            },
        },
        "record_actions": {
            "type": "ARRAY",
            "description": "State-mutating writes executed after display blocks.",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "action_id": {
                        "type": "STRING",
                        "enum": sorted(RECORD_ACTION_IDS),
                    },
                    "payload": {
                        "type": "OBJECT",
                        "description": "Action-specific fields (e.g. severity, life_stage).",
                    },
                    "requires_confirm": {
                        "type": "BOOLEAN",
                        "description": "If true, user must tap Save before write is committed.",
                    },
                    "show_receipt": {
                        "type": "BOOLEAN",
                        "description": "Show in-chat receipt card after successful write.",
                    },
                    "undoable_ttl_sec": {
                        "type": "INTEGER",
                        "description": "Seconds the user can undo this write (0 = not undoable).",
                    },
                },
                "required": ["action_id"],
            },
        },
        "nav_actions": {
            "type": "ARRAY",
            "description": "Navigation / external-service calls appended after record actions.",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "action_id": {
                        "type": "STRING",
                        "enum": sorted(NAV_ACTION_IDS),
                    },
                    "payload": {
                        "type": "OBJECT",
                        "description": "Action-specific params (e.g. target, urgency, limit).",
                    },
                },
                "required": ["action_id"],
            },
        },
        "intent": {
            "type": "STRING",
            "enum": [
                "symptom_report", "allergy_add", "weight_concern",
                "breed_query", "programme_request", "followup",
                "question", "general",
            ],
        },
        "safety_level": {
            "type": "STRING",
            "enum": ["green", "orange", "red"],
            "description": "green=routine, orange=concerning, red=emergency. Never downgrade.",
        },
    },
    "required": ["blocks", "intent", "safety_level"],
}


# Plain-language version for providers that only support json_object mode.
CHAT_ACTION_SCHEMA_INSTRUCTION = (
    "\n\nRespond with a single JSON object containing:\n"
    '  "blocks": array of {type, text, grounded_by?, asset_id?} — '
    'type ∈ ["answer","clarify","educate.daily","educate.redflag"]; '
    "max 1 answer/clarify and 1 educate per turn; order: answer/clarify first.\n"
    '  "record_actions": array of {action_id, payload?, requires_confirm?, show_receipt?, undoable_ttl_sec?} — '
    'action_id ∈ ["record.log_symptom","record.episode_followup","record.observation",'
    '"record.update_profile","record.allergy_add"].\n'
    '  "nav_actions": array of {action_id, payload?} — '
    'action_id ∈ ["open_page","open_programme","add_reminder","nearest_clinics","vet_summary"].\n'
    '  "intent": one of ["symptom_report","allergy_add","weight_concern","breed_query",'
    '"programme_request","followup","question","general"].\n'
    '  "safety_level": "green" | "orange" | "red". Never downgrade a red flag.\n'
    "Output JSON only — no markdown fences."
)


# ── Validation result ─────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    blocks: list[dict]
    record_actions: list[dict]
    nav_actions: list[dict]
    violations: list[str] = field(default_factory=list)
    was_fixed: bool = False


# ── Validator ─────────────────────────────────────────────────────────────────

def validate_and_fix(
    blocks: list[dict],
    record_actions: list[dict],
    nav_actions: list[dict],
    safety_level: str,
) -> ValidationResult:
    """
    Enforce hard composition rules and return a sanitised ValidationResult.

    All fixable violations are auto-corrected; the ``violations`` list records
    every rule that fired so callers can log them for offline review.
    """
    violations: list[str] = []
    was_fixed = False

    # ── 1. Strip hard-forbidden actions ──────────────────────────────────────
    bad_nav = [a for a in nav_actions if a.get("action_id") in FORBIDDEN_ACTION_IDS]
    if bad_nav:
        violations.append(f"forbidden_action_stripped:{[a['action_id'] for a in bad_nav]}")
        nav_actions = [a for a in nav_actions if a.get("action_id") not in FORBIDDEN_ACTION_IDS]
        was_fixed = True

    bad_rec = [a for a in record_actions if a.get("action_id") in FORBIDDEN_ACTION_IDS]
    if bad_rec:
        violations.append(f"forbidden_record_stripped:{[a['action_id'] for a in bad_rec]}")
        record_actions = [a for a in record_actions if a.get("action_id") not in FORBIDDEN_ACTION_IDS]
        was_fixed = True

    # ── 2. educate.redflag suppresses educate.daily (§3 rule 5) ──────────────
    has_redflag = any(b.get("type") == "educate.redflag" for b in blocks)
    if has_redflag:
        daily = [b for b in blocks if b.get("type") == "educate.daily"]
        if daily:
            violations.append("educate.daily_suppressed_by_redflag")
            blocks = [b for b in blocks if b.get("type") != "educate.daily"]
            was_fixed = True

    # ── 3. Max 1 answer/clarify, max 1 educate.* per turn (§3 rule 3) ────────
    answer_blocks = [b for b in blocks if b.get("type") in ("answer", "clarify")]
    if len(answer_blocks) > 1:
        violations.append(f"too_many_answer_clarify_blocks:{len(answer_blocks)}")
        kept = answer_blocks[0]
        blocks = [b for b in blocks if b.get("type") not in ("answer", "clarify")]
        blocks.insert(0, kept)
        was_fixed = True

    educate_blocks = [b for b in blocks if b.get("type", "").startswith("educate.")]
    if len(educate_blocks) > 1:
        violations.append(f"too_many_educate_blocks:{len(educate_blocks)}")
        kept = educate_blocks[0]
        blocks = [b for b in blocks if not b.get("type", "").startswith("educate.")]
        # Re-insert after any answer/clarify block
        insert_at = next(
            (i + 1 for i, b in enumerate(blocks) if b.get("type") in ("answer", "clarify")),
            len(blocks),
        )
        blocks.insert(insert_at, kept)
        was_fixed = True

    # ── 4. Enforce block ordering: answer/clarify → educate.* (§3 rule 1/2) ──
    ordered = sorted(blocks, key=lambda b: _BLOCK_ORDER.get(b.get("type", ""), 99))
    if ordered != blocks:
        violations.append("block_order_corrected")
        blocks = ordered
        was_fixed = True

    # ── 5. Safety injection: red → deterministic nearest_clinics + vet_summary ─
    # Mirrors prepend_safety_banner — safety-critical nav must never depend on
    # the LLM choosing to include it. Deduplicates if LLM already added them.
    if safety_level == "red":
        existing_ids = {a.get("action_id") for a in nav_actions}
        prepend: list[dict] = []
        if "vet_summary" not in existing_ids:
            prepend.append({"action_id": "vet_summary"})
            violations.append("safety_injected:vet_summary")
            was_fixed = True
        if "nearest_clinics" not in existing_ids:
            prepend.append({
                "action_id": "nearest_clinics",
                "payload": {"urgency": "now", "limit": 3},
            })
            violations.append("safety_injected:nearest_clinics")
            was_fixed = True
        nav_actions = prepend + nav_actions

    return ValidationResult(
        blocks=blocks,
        record_actions=record_actions,
        nav_actions=nav_actions,
        violations=violations,
        was_fixed=was_fixed,
    )
