"""
System prompt builder.

Prompt sections are loaded from Langfuse Prompt Management when available,
with prompts_config.yaml as the fallback.

Langfuse prompt names match the YAML keys 1:1 with a ``pawly_`` prefix
(see :data:`_LF_PROMPT_NAMES`). When a prompt doesn't exist in Langfuse yet,
the YAML value is used. Set ``PROMPT_HOT_RELOAD=true`` to re-check Langfuse
on every request (dev only).

The build_system_prompt() function only assembles the 9 XML-tagged sections
and the memory / KB injection slots — do not put prompt text here.
"""

import os
import pathlib
from datetime import datetime, timezone
from typing import Optional

import yaml

from src.db.models import Pet, SubscriptionTier, User
from src.utils.logger import get_logger

logger = get_logger(__name__)

# -- Section keys (canonical order in the assembled prompt) -------------------

SECTION_KEYS: tuple[str, ...] = (
    "role",
    "persona",
    "response_format",
    "continuity_rules",
    "pet_health_consultation",
    "pet_behavior_consultation",
    "followup_reminder_support",
    "knowledge_safety",
    "final_reminders",
)

# Langfuse prompt names match YAML keys 1:1 with the pawly_ prefix.
_LF_PROMPT_NAMES: dict[str, str] = {key: f"pawly_{key}" for key in SECTION_KEYS}

# -- Token budget guardrails (DeepSeek V4 v0 spec) ----------------------------

WARN_TOKEN_BUDGET = 4000
HARD_TOKEN_BUDGET = 6000

# -- Memory tag fallback strings ---------------------------------------------

MEMORY_NO_PROFILE = "(no profile)"
MEMORY_NO_RECENT_EPISODES = "(no recent episodes)"
MEMORY_HISTORY_TRUNCATED = "(history truncated)"

# -- Langfuse client (lazy, optional) -----------------------------------------

_lf_client = None
try:
    from langfuse import Langfuse
    _lf_client = Langfuse()
except Exception:
    pass

# -- Load prompt sections from YAML (fallback) --------------------------------

_CONFIG_FILE = pathlib.Path(__file__).parent / "prompts_config.yaml"
_CACHE: dict = {"mtime": None, "sections": None}


def _load_yaml_sections() -> dict[str, str]:
    with _CONFIG_FILE.open("r", encoding="utf-8") as f:
        cfg: dict = yaml.safe_load(f)
    sections: dict[str, str] = {}
    for key in SECTION_KEYS:
        value = cfg.get(key)
        if value is None:
            raise RuntimeError(
                f"prompts_config.yaml is missing required section: {key}"
            )
        sections[key] = str(value).rstrip("\n")
    return sections


def _load_from_langfuse(yaml_sections: dict[str, str]) -> dict[str, str]:
    """Fetch each section from Langfuse, falling back to YAML per-section."""
    if _lf_client is None:
        return yaml_sections
    sections: dict[str, str] = {}
    for key in SECTION_KEYS:
        try:
            prompt = _lf_client.get_prompt(_LF_PROMPT_NAMES[key], cache_ttl_seconds=300)
            sections[key] = prompt.compile().rstrip("\n")
        except Exception:
            sections[key] = yaml_sections[key]
    return sections


def _load_sections() -> dict[str, str]:
    """Load prompt sections from Langfuse (with per-section YAML fallback)."""
    hot_reload = os.getenv("PROMPT_HOT_RELOAD", "").lower() in {"1", "true", "yes"}
    mtime = _CONFIG_FILE.stat().st_mtime

    if not hot_reload and _CACHE["sections"] is not None:
        return _CACHE["sections"]

    if (
        hot_reload
        and _CACHE["sections"] is not None
        and _CACHE["mtime"] == mtime
        and _lf_client is None
    ):
        return _CACHE["sections"]

    yaml_sections = _load_yaml_sections()
    sections = _load_from_langfuse(yaml_sections)

    _CACHE["mtime"] = mtime
    _CACHE["sections"] = sections
    return sections


def reload_prompt_sections() -> dict[str, str]:
    """Force reload of prompt sections (used by /reload_prompt)."""
    _CACHE["mtime"] = None
    _CACHE["sections"] = None
    return _load_sections()


# -- Token budget helpers -----------------------------------------------------


def estimate_tokens(text: str) -> int:
    """Rough token estimate (4 chars ≈ 1 token, OpenAI's standard heuristic)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def _truncate_recent_episodes(episodes_text: str, headroom_tokens: int) -> str:
    """Trim ``<memory_recent_episodes>`` content to fit *headroom_tokens*.

    Drops the oldest entries first (assumed last lines), keeps at least the
    newest entry. If even one entry overflows the headroom, returns the
    ``(history truncated)`` fallback.
    """
    if estimate_tokens(episodes_text) <= headroom_tokens:
        return episodes_text

    # Each non-empty line is treated as one entry; entries assumed newest-first.
    lines = [line for line in episodes_text.splitlines() if line.strip()]
    if not lines:
        return MEMORY_NO_RECENT_EPISODES

    while len(lines) > 1:
        lines.pop()  # drop oldest
        candidate = "\n".join(lines)
        if estimate_tokens(candidate) <= headroom_tokens:
            return candidate

    # Only the newest entry remains. If it still overflows, history truncated.
    if estimate_tokens(lines[0]) <= headroom_tokens:
        return lines[0]
    return MEMORY_HISTORY_TRUNCATED


# -- Section formatters -------------------------------------------------------


def _format_pet_profile(pet: Optional[Pet]) -> str:
    if pet is None:
        return MEMORY_NO_PROFILE

    lines: list[str] = []
    lines.append(f"Name: {pet.name}")
    species = pet.species.value if pet.species else "unknown"
    breed = pet.breed or "unknown breed"
    lines.append(f"Species: {species} ({breed})")
    if pet.gender:
        lines.append(f"Sex: {pet.gender.value}")
    if pet.neutered_status:
        lines.append(f"Neutered: {pet.neutered_status.value}")
    age_str = _format_age(pet.age_in_months)
    if age_str:
        lines.append(f"Age: {age_str}")
    if pet.weight_latest:
        lines.append(f"Weight: {pet.weight_latest} kg")
    if getattr(pet, "stage", None):
        lines.append(f"Life stage: {pet.stage.value}")
    return "\n".join(lines)


def _xml(tag: str, body: str) -> str:
    return f"<{tag}>\n{body}\n</{tag}>"


# -- Public API ---------------------------------------------------------------


def build_system_prompt(
    user: User,
    pet: Optional[Pet] = None,
    tier: SubscriptionTier = SubscriptionTier.NEW_FREE,
    is_new_user: bool = False,
    marketing_context: Optional[dict] = None,
    memory_context: str = "",
    pending_confirmation: str = "",
    retrieved_followups: str = "",
    special_scenarios: str = "",
) -> str:
    """Assemble the full DeepSeek V4 v0 system prompt for a given turn.

    9 XML-tagged sections come from ``_load_sections()``. Memory tags are
    always emitted (placeholders filled with v0 fallback strings when empty)
    so the model sees stable structure across turns. Empty
    ``<retrieved_followups>`` and ``<special_scenarios>`` tags are dropped
    entirely — those KB slots are populated by later PRs.
    """
    sections = _load_sections()

    pet_profile_text = _format_pet_profile(pet)
    owner_profile_text = MEMORY_NO_PROFILE  # PR 6 will populate this slot.
    recent_episodes_text = (
        memory_context.strip() if memory_context.strip() else MEMORY_NO_RECENT_EPISODES
    )

    parts: list[str] = [
        _xml("role", sections["role"]),
        _xml("persona", sections["persona"]),
        _xml("response_format", sections["response_format"]),
        _xml("memory_pet_profile", pet_profile_text),
        _xml("memory_owner_profile", owner_profile_text),
        _xml("memory_recent_episodes", recent_episodes_text),
        _xml("continuity_rules", sections["continuity_rules"]),
        _xml("pet_health_consultation", sections["pet_health_consultation"]),
    ]

    # KB-driven slots: drop the entire tag when empty (per v0 spec).
    if retrieved_followups.strip():
        parts.append(_xml("retrieved_followups", retrieved_followups.strip()))
    if special_scenarios.strip():
        parts.append(_xml("special_scenarios", special_scenarios.strip()))

    parts += [
        _xml("pet_behavior_consultation", sections["pet_behavior_consultation"]),
        _xml("followup_reminder_support", sections["followup_reminder_support"]),
        _xml("knowledge_safety", sections["knowledge_safety"]),
        _xml("final_reminders", sections["final_reminders"]),
    ]

    # Operational footer (kept outside the XML body): pending confirmation +
    # reminder protocol + new-user nudge + marketing hint. These are
    # turn-level state, not prompt config — still attached so the orchestrator
    # doesn't need to know about token contracts.
    if pending_confirmation:
        parts.append(
            "Pending confirmation (weave naturally into conversation, max 1 per turn):\n"
            f"{pending_confirmation}"
        )

    if is_new_user and pet is None:
        parts.append(
            "This is a new user with no pet registered. "
            "Naturally guide them to share their pet's name, species, age, and breed "
            "within the first few messages. Be conversational, not a form."
        )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parts.append(
        f"Today's date (UTC): {today}.\n"
        "Reminder rule: when the user mentions a specific future action (vaccine, vet "
        "appointment, medication, deworming, grooming), append EXACTLY ONE line at the "
        "very end of your response in this format — nothing after it: "
        "[SET_REMINDER: <brief action> | <YYYY-MM-DD>]. "
        "Only emit this when there is a clear scheduled date or timeframe. Omit entirely otherwise."
    )

    if marketing_context:
        ch = marketing_context.get("channel", "")
        th = marketing_context.get("theme", "")
        hints: list[str] = []
        if ch:
            hints.append(f"channel={ch}")
        if th:
            hints.append(f"theme={th}")
        if hints:
            parts.append(f"[User origin: {', '.join(hints)}]")

    prompt = "\n\n".join(parts)

    # ── Token budget guard (warn at WARN, hard cap at HARD) ──────────────────
    total = estimate_tokens(prompt)
    if total > WARN_TOKEN_BUDGET:
        logger.warning(
            "system prompt exceeds warn budget",
            estimated_tokens=total,
            warn=WARN_TOKEN_BUDGET,
            hard=HARD_TOKEN_BUDGET,
        )
    if total > HARD_TOKEN_BUDGET:
        # Truncate <memory_recent_episodes> from the oldest first, keeping at
        # least the newest entry. If even one entry overflows, replace the
        # whole tag content with the (history truncated) fallback.
        non_episode = total - estimate_tokens(recent_episodes_text)
        headroom = max(1, HARD_TOKEN_BUDGET - non_episode)
        truncated_episodes = _truncate_recent_episodes(recent_episodes_text, headroom)
        if truncated_episodes != recent_episodes_text:
            logger.warning(
                "memory_recent_episodes truncated to fit token budget",
                before_tokens=estimate_tokens(recent_episodes_text),
                after_tokens=estimate_tokens(truncated_episodes),
            )
            prompt = prompt.replace(
                _xml("memory_recent_episodes", recent_episodes_text),
                _xml("memory_recent_episodes", truncated_episodes),
                1,
            )

    return prompt


def _format_age(age_in_months: Optional[int]) -> Optional[str]:
    if not age_in_months:
        return None
    years, months = divmod(age_in_months, 12)
    if years and months:
        return f"{years}y {months}m old"
    if years:
        return f"{years} year{'s' if years > 1 else ''} old"
    return f"{months} month{'s' if months > 1 else ''} old"
