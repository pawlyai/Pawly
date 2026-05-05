"""
Unit tests for the DeepSeek V4 v0 system prompt builder.

Verifies:
- All 9 XML-tagged sections + 3 memory tags appear in build_system_prompt output
- Empty <retrieved_followups> / <special_scenarios> are dropped, memory tags stay
- Memory tag fallback strings are used when slots are empty
- Token budget guard truncates <memory_recent_episodes> oldest-first when over hard cap
- Even one memory entry that overflows budget falls back to "(history truncated)"
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from src.db.models import Gender, NeuteredStatus, Species, SubscriptionTier
from src.llm.prompts import system as prompt_system
from src.llm.prompts.system import (
    HARD_TOKEN_BUDGET,
    MEMORY_HISTORY_TRUNCATED,
    MEMORY_NO_PROFILE,
    MEMORY_NO_RECENT_EPISODES,
    SECTION_KEYS,
    _truncate_recent_episodes,
    build_system_prompt,
    estimate_tokens,
)


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        telegram_id="test_001",
        display_name="Owner",
        subscription_tier=SubscriptionTier.NEW_FREE,
        locale="en",
    )


def _pet() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="Biscuit",
        species=Species.DOG,
        breed="Golden Retriever",
        age_in_months=96,
        gender=Gender.MALE,
        neutered_status=NeuteredStatus.YES,
        weight_latest=32.0,
        stage=None,
    )


@pytest.fixture(autouse=True)
def _clear_section_cache():
    """Each test loads fresh sections from YAML — no Langfuse, no cross-test leakage."""
    prompt_system._CACHE["mtime"] = None
    prompt_system._CACHE["sections"] = None
    yield
    prompt_system._CACHE["mtime"] = None
    prompt_system._CACHE["sections"] = None


def test_build_system_prompt_emits_all_nine_xml_sections() -> None:
    """The 9 v0 XML tags must appear in the assembled prompt (snapshot guard)."""
    prompt = build_system_prompt(user=_user(), pet=_pet())

    for key in SECTION_KEYS:
        assert f"<{key}>" in prompt, f"missing opening tag <{key}>"
        assert f"</{key}>" in prompt, f"missing closing tag </{key}>"


def test_build_system_prompt_always_emits_three_memory_tags() -> None:
    """Memory tags are emitted on every turn — empty or not — for positional stability."""
    prompt_with_pet = build_system_prompt(user=_user(), pet=_pet())
    prompt_without_pet = build_system_prompt(user=_user(), pet=None)

    for prompt in (prompt_with_pet, prompt_without_pet):
        assert "<memory_pet_profile>" in prompt
        assert "<memory_owner_profile>" in prompt
        assert "<memory_recent_episodes>" in prompt


def test_memory_pet_profile_uses_fallback_when_no_pet() -> None:
    prompt = build_system_prompt(user=_user(), pet=None)
    # The (no profile) fallback must appear inside the pet profile tag.
    assert (
        f"<memory_pet_profile>\n{MEMORY_NO_PROFILE}\n</memory_pet_profile>" in prompt
    )


def test_memory_pet_profile_populated_from_pet_record() -> None:
    pet = _pet()
    prompt = build_system_prompt(user=_user(), pet=pet)
    assert "Name: Biscuit" in prompt
    assert "Species: dog" in prompt
    assert "Weight: 32.0 kg" in prompt


def test_memory_owner_profile_uses_fallback_in_pr2() -> None:
    """PR 6 will populate this slot; PR 2 just leaves the fallback string."""
    prompt = build_system_prompt(user=_user(), pet=_pet())
    assert (
        f"<memory_owner_profile>\n{MEMORY_NO_PROFILE}\n</memory_owner_profile>"
        in prompt
    )


def test_memory_recent_episodes_falls_back_when_empty() -> None:
    prompt = build_system_prompt(user=_user(), pet=_pet(), memory_context="")
    assert (
        f"<memory_recent_episodes>\n{MEMORY_NO_RECENT_EPISODES}\n</memory_recent_episodes>"
        in prompt
    )


def test_memory_recent_episodes_uses_supplied_memory_context() -> None:
    ctx = "Active episodes: vomiting since yesterday"
    prompt = build_system_prompt(user=_user(), pet=_pet(), memory_context=ctx)
    assert ctx in prompt


def test_kb_slots_are_dropped_entirely_when_empty() -> None:
    """Per v0 spec: when KB slots are empty, the whole tag is removed (not left empty).

    Closing tags are checked because the pet_health_consultation prompt body
    contains a reference to ``<retrieved_followups>`` in prose; the closing
    form ``</retrieved_followups>`` only appears when the slot is emitted.
    """
    prompt = build_system_prompt(user=_user(), pet=_pet())
    assert "</retrieved_followups>" not in prompt
    assert "</special_scenarios>" not in prompt


def test_kb_slots_are_emitted_when_populated() -> None:
    prompt = build_system_prompt(
        user=_user(),
        pet=_pet(),
        retrieved_followups="**Vomiting:** What does it look like?",
        special_scenarios='<rule id="medication_dosage">MUST NOT give specific mg/kg.</rule>',
    )
    assert "</retrieved_followups>" in prompt
    assert "**Vomiting:**" in prompt
    assert "</special_scenarios>" in prompt
    assert 'rule id="medication_dosage"' in prompt


def test_role_section_includes_cross_language_directive() -> None:
    """v0 appends the OWNER_PROFILE.language fallback line to <role>."""
    prompt = build_system_prompt(user=_user(), pet=_pet())
    assert (
        "Respond in the language indicated by OWNER_PROFILE.language" in prompt
    )


def test_role_cross_language_line_is_inside_role_tag() -> None:
    prompt = build_system_prompt(user=_user(), pet=_pet())
    role_open = prompt.index("<role>")
    role_close = prompt.index("</role>")
    inside = prompt[role_open:role_close]
    assert "Respond in the language indicated by OWNER_PROFILE.language" in inside


# ── Token budget tests ─────────────────────────────────────────────────────────


def test_truncate_recent_episodes_drops_oldest_first() -> None:
    """Lines are newest-first; oldest line goes first under budget pressure."""
    episodes = "\n".join(
        [
            "1. 2026-05-01 - Newest entry",
            "2. 2026-04-22 - Second entry",
            "3. 2026-04-10 - Third entry",
            "4. 2026-04-01 - Oldest entry",
        ]
    )
    # Allow only enough budget for ~2 entries.
    headroom = estimate_tokens("1. 2026-05-01 - Newest entry\n2. 2026-04-22 - Second entry") + 1
    truncated = _truncate_recent_episodes(episodes, headroom)
    assert "Newest entry" in truncated, "must always keep the newest entry"
    assert "Oldest entry" not in truncated, "oldest line must be dropped first"


def test_truncate_recent_episodes_keeps_at_least_newest() -> None:
    """Even if very tight, the newest line stays unless it alone overflows."""
    episodes = "\n".join(
        [
            "1. Newest short",
            "2. Older line we should drop first",
            "3. Even older line",
        ]
    )
    headroom = estimate_tokens("1. Newest short") + 2
    truncated = _truncate_recent_episodes(episodes, headroom)
    assert truncated == "1. Newest short"


def test_truncate_recent_episodes_history_truncated_when_one_entry_overflows() -> None:
    """When even the newest single entry doesn't fit, fall back to (history truncated)."""
    huge_entry = "X" * 40_000  # ≈ 10_000 tokens at 4 chars/token
    truncated = _truncate_recent_episodes(huge_entry, headroom_tokens=10)
    assert truncated == MEMORY_HISTORY_TRUNCATED


def test_token_budget_triggers_truncation_in_build_system_prompt() -> None:
    """build_system_prompt actually invokes the truncation path when over the hard cap."""
    # Build a memory blob big enough to push the prompt over the hard cap.
    # HARD_TOKEN_BUDGET = 6000, baseline prompt ~ 1k-2k tokens. 5000 lines × ~10 tokens
    # ≈ 50k tokens of episodes — guaranteed to trigger truncation, with the newest
    # line preserved.
    episodes = "\n".join(
        f"{i}. 2026-05-{(i % 28) + 1:02d} - episode entry padding text"
        for i in range(1, 5001)
    )
    prompt = build_system_prompt(
        user=_user(),
        pet=_pet(),
        memory_context=episodes,
    )

    # The total prompt must be under (or near) the hard cap after truncation.
    assert estimate_tokens(prompt) <= HARD_TOKEN_BUDGET + estimate_tokens(
        "(history truncated)"
    )
    # Either the newest entry survives (if any single entry fits) or the
    # (history truncated) fallback was used.
    assert (
        "1. 2026-05-02 - episode entry padding text" in prompt
        or MEMORY_HISTORY_TRUNCATED in prompt
    )
