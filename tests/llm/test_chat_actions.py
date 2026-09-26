"""Unit tests for src/llm/chat_actions.py — validate_and_fix()."""

import pytest

from src.llm.chat_actions import validate_and_fix


# ── helpers ───────────────────────────────────────────────────────────────────

def _block(type_: str, text: str = "x") -> dict:
    return {"type": type_, "text": text}


def _action(action_id: str, **payload) -> dict:
    return {"action_id": action_id, **({"payload": payload} if payload else {})}


def _run(blocks=None, records=None, nav=None, safety="green"):
    return validate_and_fix(
        blocks=list(blocks or []),
        record_actions=list(records or []),
        nav_actions=list(nav or []),
        safety_level=safety,
    )


# ── §1 whitelist: forbidden actions ──────────────────────────────────────────

class TestForbiddenActions:
    def test_open_photo_check_stripped_from_nav(self):
        r = _run(
            blocks=[_block("answer")],
            nav=[_action("open_photo_check"), _action("open_page")],
        )
        ids = [a["action_id"] for a in r.nav_actions]
        assert "open_photo_check" not in ids
        assert "open_page" in ids
        assert r.was_fixed
        assert any("forbidden_action_stripped" in v for v in r.violations)

    def test_modify_programme_stripped_from_nav(self):
        r = _run(nav=[_action("modify_programme")])
        assert r.nav_actions == []
        assert r.was_fixed

    def test_clean_output_untouched(self):
        r = _run(
            blocks=[_block("answer")],
            nav=[_action("open_page")],
        )
        assert not r.was_fixed
        assert r.violations == []


# ── §3 rule 5: educate.redflag suppresses educate.daily ──────────────────────

class TestRedflagSuppressesDaily:
    def test_daily_removed_when_redflag_present(self):
        r = _run(blocks=[
            _block("educate.redflag"),
            _block("educate.daily"),
        ])
        types = [b["type"] for b in r.blocks]
        assert "educate.daily" not in types
        assert "educate.redflag" in types
        assert r.was_fixed
        assert "educate.daily_suppressed_by_redflag" in r.violations

    def test_daily_kept_when_no_redflag(self):
        r = _run(blocks=[_block("answer"), _block("educate.daily")])
        types = [b["type"] for b in r.blocks]
        assert "educate.daily" in types
        assert not r.was_fixed


# ── §3 rule 3: max 1 answer/clarify, max 1 educate per turn ──────────────────

class TestBlockCounts:
    def test_duplicate_answers_reduced_to_one(self):
        r = _run(blocks=[_block("answer", "a1"), _block("answer", "a2")])
        answer_blocks = [b for b in r.blocks if b["type"] == "answer"]
        assert len(answer_blocks) == 1
        assert answer_blocks[0]["text"] == "a1"  # first one kept
        assert r.was_fixed

    def test_duplicate_educates_reduced_to_one(self):
        r = _run(blocks=[
            _block("answer"),
            _block("educate.daily", "e1"),
            _block("educate.daily", "e2"),
        ])
        educate_blocks = [b for b in r.blocks if b["type"].startswith("educate.")]
        assert len(educate_blocks) == 1
        assert educate_blocks[0]["text"] == "e1"
        assert r.was_fixed

    def test_answer_and_clarify_count_together(self):
        r = _run(blocks=[_block("answer"), _block("clarify")])
        kept = [b for b in r.blocks if b["type"] in ("answer", "clarify")]
        assert len(kept) == 1
        assert r.was_fixed


# ── §3 rule 1/2: block ordering ──────────────────────────────────────────────

class TestBlockOrdering:
    def test_educate_before_answer_is_reordered(self):
        r = _run(blocks=[_block("educate.daily"), _block("answer")])
        types = [b["type"] for b in r.blocks]
        assert types.index("answer") < types.index("educate.daily")
        assert r.was_fixed
        assert "block_order_corrected" in r.violations

    def test_correct_order_unchanged(self):
        r = _run(blocks=[_block("answer"), _block("educate.daily")])
        types = [b["type"] for b in r.blocks]
        assert types == ["answer", "educate.daily"]
        assert not r.was_fixed

    def test_clarify_then_educate_is_valid(self):
        r = _run(blocks=[_block("clarify"), _block("educate.daily")])
        assert not r.was_fixed


# ── Safety injection: red → nearest_clinics + vet_summary ────────────────────

class TestSafetyInjection:
    def test_both_injected_when_absent_on_red(self):
        r = _run(safety="red")
        ids = [a["action_id"] for a in r.nav_actions]
        assert "nearest_clinics" in ids
        assert "vet_summary" in ids
        assert r.was_fixed
        assert "safety_injected:nearest_clinics" in r.violations
        assert "safety_injected:vet_summary" in r.violations

    def test_no_duplicate_when_llm_already_included(self):
        r = _run(
            nav=[_action("nearest_clinics"), _action("vet_summary")],
            safety="red",
        )
        ids = [a["action_id"] for a in r.nav_actions]
        assert ids.count("nearest_clinics") == 1
        assert ids.count("vet_summary") == 1
        # was_fixed stays False — LLM got it right
        assert not r.was_fixed

    def test_partial_dedup_one_missing(self):
        r = _run(nav=[_action("vet_summary")], safety="red")
        ids = [a["action_id"] for a in r.nav_actions]
        assert ids.count("nearest_clinics") == 1
        assert ids.count("vet_summary") == 1

    def test_safety_actions_prepended_first(self):
        r = _run(nav=[_action("open_page")], safety="red")
        ids = [a["action_id"] for a in r.nav_actions]
        assert ids[0] in ("vet_summary", "nearest_clinics")
        assert "open_page" in ids

    def test_no_injection_on_orange(self):
        r = _run(safety="orange")
        ids = [a["action_id"] for a in r.nav_actions]
        assert "nearest_clinics" not in ids
        assert "vet_summary" not in ids

    def test_no_injection_on_green(self):
        r = _run(safety="green")
        assert r.nav_actions == []


# ── Interaction: red + forbidden ─────────────────────────────────────────────

class TestCombined:
    def test_red_strips_forbidden_then_injects_safety(self):
        r = _run(
            blocks=[_block("educate.redflag"), _block("educate.daily")],
            nav=[_action("open_photo_check")],
            safety="red",
        )
        types = [b["type"] for b in r.blocks]
        ids = [a["action_id"] for a in r.nav_actions]
        assert "educate.daily" not in types
        assert "open_photo_check" not in ids
        assert "nearest_clinics" in ids
        assert "vet_summary" in ids

    def test_fully_valid_turn_no_changes(self):
        r = _run(
            blocks=[_block("answer"), _block("educate.daily")],
            records=[{"action_id": "record.log_symptom", "requires_confirm": False}],
            nav=[_action("open_page")],
            safety="green",
        )
        assert not r.was_fixed
        assert r.violations == []
