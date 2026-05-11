"""Unit tests for DeepSeek's chat_structured payload parser.

These cover the response shapes that DeepSeek has been observed to return
under `response_format=json_object`: well-formed JSON, markdown-fenced JSON,
JSON wrapped in prose, and pure prose with no JSON at all. The orchestrator
relies on `_parse_structured_payload` returning a usable shape for each so
chat_structured doesn't fail loudly and trigger the "I'm having trouble
connecting" fallback for inputs that the model actually answered.
"""

from __future__ import annotations

import pytest

from src.llm.providers_deepseek import (
    _first_balanced_object,
    _parse_structured_payload,
)


def test_well_formed_json_parses_directly() -> None:
    text = (
        '{"response_text": "Looks fine, monitor at home.", '
        '"triage_level": "GREEN", "intent": "general", '
        '"sentiment": "CALM", "symptom_tags": []}'
    )
    payload, status = _parse_structured_payload(text)
    assert status == "json"
    assert payload["response_text"] == "Looks fine, monitor at home."
    assert payload["triage_level"] == "GREEN"


def test_markdown_fenced_json_is_recovered() -> None:
    text = (
        "Here's the response in JSON:\n"
        "```json\n"
        '{"response_text": "Take Buddy to the vet.", "triage_level": "RED"}\n'
        "```\n"
        "Hope that helps!"
    )
    payload, status = _parse_structured_payload(text)
    assert status == "fenced"
    assert payload["response_text"] == "Take Buddy to the vet."
    assert payload["triage_level"] == "RED"


def test_prose_wrapped_balanced_object_is_recovered() -> None:
    text = (
        "Sure, here is the analysis: "
        '{"response_text": "Worth watching.", "triage_level": "ORANGE"} '
        "Let me know if you have questions."
    )
    payload, status = _parse_structured_payload(text)
    assert status == "balanced"
    assert payload["response_text"] == "Worth watching."


def test_pure_prose_falls_through_to_prose_fallback() -> None:
    text = "Sorry, I cannot help with that — please consult your vet."
    payload, status = _parse_structured_payload(text)
    assert status == "prose_fallback"
    assert payload == {}


def test_empty_text_is_empty_status() -> None:
    payload, status = _parse_structured_payload("")
    assert status == "empty"
    assert payload == {}


def test_whitespace_only_is_empty_status() -> None:
    payload, status = _parse_structured_payload("   \n  ")
    assert status == "empty"


def test_malformed_json_with_trailing_text_uses_balanced_extractor() -> None:
    # JSON parses but is followed by stray content; the raw `json.loads`
    # path would reject this, but the balanced extractor recovers.
    text = (
        '{"response_text": "It is not urgent.", "triage_level": "GREEN"}\n\n'
        "Hope you and Buddy feel better soon!"
    )
    payload, status = _parse_structured_payload(text)
    # Could be either "json" (some parsers tolerate trailing text — Python's
    # doesn't) or "balanced" — both indicate successful recovery.
    assert status in ("json", "balanced")
    assert "not urgent" in payload["response_text"]


def test_balanced_object_finder_handles_braces_in_strings() -> None:
    # The inner literal `{` inside a string should not confuse the parser.
    text = '{"response_text": "Try food {brand X} or similar.", "triage_level": "GREEN"}'
    balanced = _first_balanced_object(text)
    assert balanced == text


def test_balanced_object_finder_returns_none_when_no_object() -> None:
    assert _first_balanced_object("no json here at all") is None


def test_balanced_object_finder_returns_first_complete_object() -> None:
    # Two side-by-side objects — we want the first one.
    text = '{"a": 1} {"b": 2}'
    assert _first_balanced_object(text) == '{"a": 1}'


@pytest.mark.parametrize(
    "text,expected_status",
    [
        # The classic DeepSeek "Here's your JSON:" wrapper
        ('Here is the JSON: {"response_text": "ok", "triage_level": "GREEN"}', "balanced"),
        # Stray code fence with no language tag
        ('```\n{"response_text": "ok", "triage_level": "GREEN"}\n```', "fenced"),
        # JSON with a trailing comment line (illegal in strict JSON)
        # The balanced extractor should still find the {...} substring.
        ('{"response_text": "ok", "triage_level": "GREEN"}\n// note: monitor',
         "balanced"),
    ],
)
def test_various_deepseek_response_shapes(text: str, expected_status: str) -> None:
    payload, status = _parse_structured_payload(text)
    assert status == expected_status
    assert payload["response_text"] == "ok"
    assert payload["triage_level"] == "GREEN"
