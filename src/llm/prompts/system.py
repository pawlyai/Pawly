"""
System prompt builder.

ALL editable prompt text lives in prompts_config.yaml (same directory).
Edit that file to tune personality, rules, or medical format — no Python
changes required. The file is loaded once at import time; restart the
process to pick up changes.

Sections (keys in prompts_config.yaml):
    identity           — who Pawly is + two operating modes
    conversation_rules — opening, pet ID, info gathering, follow-up, closure
    hard_rules         — non-negotiable safety + behaviour rules
    medical_format     — internal assessment + response structure for health queries

The build_system_prompt() function only assembles sections — do not touch it
unless you need to add a new conditional section.
"""

import pathlib
from typing import Optional

import yaml

from src.db.models import Pet, SubscriptionTier, User

# ── Load prompt sections from YAML ────────────────────────────────────────────

_CONFIG_FILE = pathlib.Path(__file__).parent / "prompts_config.yaml"

with _CONFIG_FILE.open("r", encoding="utf-8") as _f:
    _cfg: dict = yaml.safe_load(_f)

# Module-level constants — importable by tests or admin tooling.
SECTION_IDENTITY: str = _cfg["identity"].rstrip("\n")
SECTION_CONVERSATION_RULES: str = _cfg["conversation_rules"].rstrip("\n")
SECTION_HARD_RULES: str = _cfg["hard_rules"].rstrip("\n")
SECTION_MEDICAL_FORMAT: str = _cfg["medical_format"].rstrip("\n")


# ── Assembler — no prompt text below this line ────────────────────────────────


def build_system_prompt(
    user: User,
    pet: Optional[Pet] = None,
    tier: SubscriptionTier = SubscriptionTier.NEW_FREE,
    is_new_user: bool = False,
    marketing_context: Optional[dict] = None,
    memory_context: str = "",
    pending_confirmation: str = "",
) -> str:
    """
    Assemble the full system prompt for a given turn.

    Sections 1-4 are always included. Sections 5-8 are conditional.
    """
    parts: list[str] = [
        SECTION_IDENTITY,
        "",
        SECTION_CONVERSATION_RULES,
        "",
        SECTION_HARD_RULES,
        "",
        SECTION_MEDICAL_FORMAT,
    ]

    # Section 5 — Pet profile
    if pet:
        age_str = _format_age(pet.age_in_months)
        pet_section = (
            f"Current pet: {pet.name}, {pet.species.value}"
            f" ({pet.breed or 'unknown breed'})"
            f", {age_str}"
            f", {pet.gender.value}"
            f", neutered: {pet.neutered_status.value}"
            f", weight: {pet.weight_latest or '?'} kg"
        )
        if pet.stage:
            pet_section += f", life stage: {pet.stage.value}"
        parts += ["", pet_section]
    else:
        parts += [
            "",
            "No pet profile registered yet. "
            "Naturally guide the user to share their pet's name, species, age, and breed "
            "within the first few messages. Be conversational, not a form.",
        ]

    # Section 6 — Memory context
    if memory_context:
        parts += ["", "Known context about this pet:", memory_context]

    # Section 7 — Pending confirmation
    if pending_confirmation:
        parts += [
            "",
            "Pending confirmation (weave naturally into conversation, max 1 per turn):",
            pending_confirmation,
        ]

    # Section 8 — New user onboarding nudge
    if is_new_user and pet is None:
        parts += [
            "",
            "This is a new user with no pet registered. "
            "Naturally guide them to share their pet's name, species, age, and breed "
            "within the first few messages. Be conversational, not a form.",
        ]

    # Marketing context hint
    if marketing_context:
        ch = marketing_context.get("channel", "")
        th = marketing_context.get("theme", "")
        hints: list[str] = []
        if ch:
            hints.append(f"channel={ch}")
        if th:
            hints.append(f"theme={th}")
        if hints:
            parts += ["", f"[User origin: {', '.join(hints)}]"]

    return "\n".join(parts)


def _format_age(age_in_months: Optional[int]) -> str:
    if not age_in_months:
        return "? months old"
    years, months = divmod(age_in_months, 12)
    if years and months:
        return f"{years}y {months}m old"
    if years:
        return f"{years} year{'s' if years > 1 else ''} old"
    return f"{months} month{'s' if months > 1 else ''} old"
