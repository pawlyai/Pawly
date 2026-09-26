"""Unit tests for the pending_clarify state machine in orchestrator.py.

Tests operate directly on the session dict and the validate_and_fix output,
mirroring what _generate_chat_actions_classic() does without the async LLM call.
"""

import pytest

from src.llm.chat_actions import validate_and_fix


# ── helpers ───────────────────────────────────────────────────────────────────

def _block(type_: str, text: str = "x") -> dict:
    return {"type": type_, "text": text}


def _simulate_turn(
    blocks,
    session: dict,
    safety: str = "green",
    max_rounds: int = 2,
) -> tuple[list[dict], list[str]]:
    """
    Run validate_and_fix then apply the clarify state-machine logic that lives
    in _generate_chat_actions_classic(), returning (final_blocks, violations).
    """
    result = validate_and_fix(
        blocks=list(blocks),
        record_actions=[],
        nav_actions=[],
        safety_level=safety,
    )

    _pending_clarify: dict | None = session.get("pending_clarify")
    has_clarify = any(b.get("type") == "clarify" for b in result.blocks)

    if has_clarify:
        _max = max_rounds if _pending_clarify is None else _pending_clarify.get("max_rounds", max_rounds)
        _used = 1 if _pending_clarify is None else _pending_clarify.get("rounds_used", 0) + 1
        if _used >= _max:
            result.blocks = [
                {**b, "type": "answer"} if b.get("type") == "clarify" else b
                for b in result.blocks
            ]
            result.violations.append("clarify_collapsed_max_rounds_exceeded")
            result.was_fixed = True
            session.pop("pending_clarify", None)
        else:
            clarify_text = next(b["text"] for b in result.blocks if b.get("type") == "clarify")
            session["pending_clarify"] = {
                "question": clarify_text,
                "max_rounds": _max,
                "rounds_used": _used,
            }
    else:
        session.pop("pending_clarify", None)

    return result.blocks, result.violations


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestClarifyStateFirstTurn:
    def test_first_clarify_sets_session(self):
        session: dict = {}
        blocks, violations = _simulate_turn(
            [_block("clarify", "Which leg is limping?")],
            session,
        )
        assert blocks[0]["type"] == "clarify"
        assert session["pending_clarify"]["question"] == "Which leg is limping?"
        assert session["pending_clarify"]["rounds_used"] == 1
        assert "clarify_collapsed_max_rounds_exceeded" not in violations

    def test_answer_on_first_turn_no_session_state(self):
        session: dict = {}
        blocks, _ = _simulate_turn([_block("answer", "Milo looks fine.")], session)
        assert blocks[0]["type"] == "answer"
        assert "pending_clarify" not in session


class TestClarifyStateSecondTurn:
    def test_second_clarify_within_limit_updates_session(self):
        session: dict = {
            "pending_clarify": {"question": "Q1", "max_rounds": 3, "rounds_used": 1}
        }
        blocks, violations = _simulate_turn(
            [_block("clarify", "Q2?")],
            session,
            max_rounds=3,
        )
        assert blocks[0]["type"] == "clarify"
        assert session["pending_clarify"]["rounds_used"] == 2
        assert "clarify_collapsed_max_rounds_exceeded" not in violations

    def test_answer_after_clarify_clears_session(self):
        session: dict = {
            "pending_clarify": {"question": "Which leg?", "max_rounds": 2, "rounds_used": 1}
        }
        blocks, _ = _simulate_turn([_block("answer", "Sounds like a sprain.")], session)
        assert blocks[0]["type"] == "answer"
        assert "pending_clarify" not in session


class TestClarifyMaxRoundsCollapse:
    def test_collapse_on_max_rounds(self):
        session: dict = {
            "pending_clarify": {"question": "Q1", "max_rounds": 2, "rounds_used": 1}
        }
        blocks, violations = _simulate_turn(
            [_block("clarify", "Q2 again?")],
            session,
        )
        # clarify block must be converted to answer
        assert all(b["type"] == "answer" for b in blocks if b.get("type") in ("clarify", "answer"))
        assert "clarify_collapsed_max_rounds_exceeded" in violations
        assert "pending_clarify" not in session

    def test_collapse_preserves_text(self):
        session: dict = {
            "pending_clarify": {"question": "Q", "max_rounds": 2, "rounds_used": 1}
        }
        blocks, _ = _simulate_turn(
            [_block("clarify", "Still unsure, which leg?")],
            session,
        )
        answer_blocks = [b for b in blocks if b["type"] == "answer"]
        assert answer_blocks[0]["text"] == "Still unsure, which leg?"

    def test_no_collapse_on_first_clarify_max_rounds_2(self):
        session: dict = {}
        blocks, violations = _simulate_turn(
            [_block("clarify", "First Q?")],
            session,
        )
        assert blocks[0]["type"] == "clarify"
        assert "clarify_collapsed_max_rounds_exceeded" not in violations
        assert session["pending_clarify"]["rounds_used"] == 1
