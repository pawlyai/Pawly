"""
System prompt builder.

Prompt sections are loaded from Langfuse Prompt Management when available,
with prompts_config.yaml as the fallback.

Langfuse prompt names (create these in the Langfuse UI under "Prompts"):
    pawly-identity           - who Pawly is + persona + tone
    pawly-conversation-rules - info gathering, triage flow, follow-up rules
    pawly-hard-rules         - non-negotiable safety + behaviour rules
    pawly-medical-format     - assessment format for health queries

If a prompt doesn't exist in Langfuse yet, the YAML value is used instead.
Set PROMPT_HOT_RELOAD=true to re-check Langfuse on every request (dev only).

The build_system_prompt() function only assembles sections - do not touch it
unless you need to add a new conditional section.
"""

import os
import pathlib
from typing import Optional

import yaml

from src.db.models import Pet, SubscriptionTier, User
from src.utils.logger import get_logger

logger = get_logger(__name__)

# -- Langfuse prompt names ----------------------------------------------------

_LF_PROMPT_NAMES = {
    "identity": "pawly-identity",
    "conversation_rules": "pawly-conversation-rules",
    "hard_rules": "pawly-hard-rules",
    "medical_format": "pawly-medical-format",
}

_lf_client = None
try:
    from langfuse import Langfuse
    _lf_client = Langfuse()
except Exception:
    pass

# -- Load prompt sections from YAML (fallback) --------------------------------

_CONFIG_FILE = pathlib.Path(__file__).parent / "prompts_config.yaml"
_CACHE: dict = {"mtime": None, "sections": None}


def _load_yaml_sections() -> dict:
    with _CONFIG_FILE.open("r", encoding="utf-8") as _f:
        cfg: dict = yaml.safe_load(_f)
    return {
        "identity": cfg["identity"].rstrip("\n"),
        "conversation_rules": cfg["conversation_rules"].rstrip("\n"),
        "hard_rules": cfg["hard_rules"].rstrip("\n"),
        "medical_format": cfg["medical_format"].rstrip("\n"),
    }


def _load_from_langfuse(yaml_sections: dict) -> dict:
    """Fetch each section from Langfuse, falling back to YAML per-section."""
    if _lf_client is None:
        return yaml_sections
    sections = {}
    for key, name in _LF_PROMPT_NAMES.items():
        try:
            prompt = _lf_client.get_prompt(name, cache_ttl_seconds=300)
            sections[key] = prompt.compile().rstrip("\n")
        except Exception:
            sections[key] = yaml_sections[key]
    return sections


def _load_sections() -> dict:
    """
    Load prompt sections from Langfuse (with per-section YAML fallback).

    If PROMPT_HOT_RELOAD=true, bypass cache on every call.
    """
    hot_reload = os.getenv("PROMPT_HOT_RELOAD", "").lower() in {"1", "true", "yes"}
    mtime = _CONFIG_FILE.stat().st_mtime

    if not hot_reload and _CACHE["sections"] is not None:
        return _CACHE["sections"]

    if hot_reload and _CACHE["sections"] is not None and _CACHE["mtime"] == mtime and _lf_client is None:
        return _CACHE["sections"]

    yaml_sections = _load_yaml_sections()
    sections = _load_from_langfuse(yaml_sections)

    _CACHE["mtime"] = mtime
    _CACHE["sections"] = sections
    return sections


def reload_prompt_sections() -> dict:
    """Force reload of prompt sections (used by /reload_prompt)."""
    _CACHE["mtime"] = None
    _CACHE["sections"] = None
    return _load_sections()


# -- Assembler - no prompt text below this line -------------------------------


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
    sections = _load_sections()
    parts: list[str] = [
        sections["identity"],
        "",
        sections["conversation_rules"],
        "",
        sections["hard_rules"],
        "",
        sections["medical_format"],
    ]

    # Section 5 - Pet profile
    if pet:
        age_str = _format_age(pet.age_in_months)
        gender_str = pet.gender.value if pet.gender else "unknown"
        neutered_str = pet.neutered_status.value if pet.neutered_status else "unknown"
        pet_section = (
            f"Current pet: {pet.name}, {pet.species.value}"
            f" ({pet.breed or 'unknown breed'})"
            f", {age_str}"
            f", {gender_str}"
            f", neutered: {neutered_str}"
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

    # Section 6 - Memory context
    if memory_context:
        parts += ["", "Known context about this pet:", memory_context]

    # Section 7 - Pending confirmation
    if pending_confirmation:
        parts += [
            "",
            "Pending confirmation (weave naturally into conversation, max 1 per turn):",
            pending_confirmation,
        ]

    # Section 8 - New user onboarding nudge
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
