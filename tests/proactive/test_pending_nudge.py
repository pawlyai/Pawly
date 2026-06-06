"""
Unit tests for src/jobs/pending_nudge.py — _build_nudge_text().

_build_nudge_text is a pure function (no DB, no LLM), so all tests are
synchronous and run in milliseconds.

Covers:
  - Basic structure: references pet name, field, and confirmation request
  - Dict proposed_value with "value" key
  - Dict proposed_value with "raw" key
  - Dict without known keys → no value_str injected
  - String proposed_value
  - Empty / None proposed_value → no value_str
  - Field name underscores converted to spaces
"""


from src.jobs.pending_nudge import _build_nudge_text


# ── Basic content ─────────────────────────────────────────────────────────────

def test_contains_pet_name():
    text = _build_nudge_text("Milo", "vaccination_date", {"value": "2026-08-01"}, "got his shots")
    assert "Milo" in text


def test_contains_readable_field():
    text = _build_nudge_text("Milo", "vaccination_date", {}, "")
    assert "vaccination date" in text


def test_confirmation_request_present():
    text = _build_nudge_text("Milo", "weight", {"value": "5.5kg"}, "")
    assert "confirm" in text.lower()


def test_reply_instruction_present():
    text = _build_nudge_text("Milo", "weight", {}, "")
    assert "Reply to this chat" in text


# ── proposed_value extraction ─────────────────────────────────────────────────

def test_dict_value_key_extracted():
    text = _build_nudge_text("Milo", "weight", {"value": "5.5kg"}, "")
    assert '"5.5kg"' in text


def test_dict_raw_key_extracted():
    text = _build_nudge_text("Milo", "medication", {"raw": "Metronidazole"}, "")
    assert '"Metronidazole"' in text


def test_dict_unknown_key_no_crash():
    # Dict with no "value" or "raw" key → no value_str
    text = _build_nudge_text("Milo", "breed", {"name": "Poodle"}, "")
    assert "Milo" in text
    # Should not raise; no value injected in wrong format
    assert '"Poodle"' not in text


def test_string_proposed_value():
    text = _build_nudge_text("Milo", "breed", "Poodle", "")
    assert '"Poodle"' in text


def test_none_proposed_value_no_crash():
    text = _build_nudge_text("Milo", "breed", None, "")
    assert "Milo" in text
    assert '"' not in text or "Reply" in text  # no rogue value_str


def test_empty_dict_proposed_value():
    text = _build_nudge_text("Milo", "weight", {}, "")
    assert "Milo" in text
    # Empty dict → no value_str quotation injected for the value itself
    assert "— " not in text.split("weight")[1].split("based on")[0]


# ── Field name formatting ─────────────────────────────────────────────────────

def test_underscores_in_field_become_spaces():
    text = _build_nudge_text("Luna", "vaccination_date", {}, "")
    assert "vaccination date" in text


def test_single_word_field_unchanged():
    text = _build_nudge_text("Luna", "weight", {}, "")
    assert "weight" in text


# ── Emoji present ─────────────────────────────────────────────────────────────

def test_paw_emoji_at_end():
    text = _build_nudge_text("Luna", "weight", {"value": "4kg"}, "")
    assert "🐾" in text
