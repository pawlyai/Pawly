"""Unit tests for scripts/analyze_root_causes.py.

Cover the pure-Python helpers (JSON extractor, taxonomy validator, target
selector) so changes to the script's parsing logic don't silently regress
when we tune the prompt or rerun the classifier on historical reports.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# scripts/ isn't a package; load the module by path so the tests don't
# depend on PYTHONPATH gymnastics.
_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "analyze_root_causes.py"
_spec = importlib.util.spec_from_file_location("analyze_root_causes", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
analyze = importlib.util.module_from_spec(_spec)
sys.modules["analyze_root_causes"] = analyze
_spec.loader.exec_module(analyze)


# ── JSON extractor ───────────────────────────────────────────────────────────


def test_extract_plain_json() -> None:
    obj = analyze._extract_json_object('{"category": "missing_disclaimer", "explanation": "ok"}')
    assert obj == {"category": "missing_disclaimer", "explanation": "ok"}


def test_extract_fenced_json() -> None:
    obj = analyze._extract_json_object(
        'Here is the analysis:\n```json\n'
        '{"category": "missing_l3_naming", "suggested_fix": "x"}\n'
        '```\n'
    )
    assert obj["category"] == "missing_l3_naming"


def test_extract_prose_wrapped_json() -> None:
    obj = analyze._extract_json_object(
        'Sure: {"category": "over_explained_refusal", "explanation": "y"} done.'
    )
    assert obj["category"] == "over_explained_refusal"


def test_extract_no_json_returns_empty() -> None:
    assert analyze._extract_json_object("Sorry, I cannot classify this.") == {}


def test_extract_empty_returns_empty() -> None:
    assert analyze._extract_json_object("") == {}
    assert analyze._extract_json_object("   \n  ") == {}


def test_balanced_object_handles_braces_in_strings() -> None:
    text = '{"explanation": "Use {brand} or similar product."}'
    obj = analyze._extract_json_object(text)
    assert obj["explanation"] == "Use {brand} or similar product."


# ── Category validator ──────────────────────────────────────────────────────


def test_valid_category_passes_through() -> None:
    for cat, _desc in analyze.ROOT_CAUSE_TAXONOMY:
        assert analyze._coerce_category(cat) == cat


def test_unknown_category_coerces_to_other() -> None:
    assert analyze._coerce_category("totally_invented_category") == "other"
    assert analyze._coerce_category(None) == "other"
    assert analyze._coerce_category(123) == "other"
    assert analyze._coerce_category("") == "other"


# ── Truncation ───────────────────────────────────────────────────────────────


def test_truncate_respects_limit() -> None:
    assert len(analyze._truncate("a" * 500, 220)) == 220


def test_truncate_handles_non_strings() -> None:
    assert analyze._truncate(None, 100) == ""
    assert analyze._truncate(42, 100) == ""


def test_truncate_strips_whitespace() -> None:
    assert analyze._truncate("  hello world  ", 100) == "hello world"


# ── Target selection ────────────────────────────────────────────────────────


def _case(status: str, score: float, threshold: float, root_cause: dict | None = None) -> dict:
    c: dict = {"name": "x", "status": status, "score": score, "threshold": threshold}
    if root_cause is not None:
        c["root_cause"] = root_cause
    return c


def test_selects_below_threshold_cases() -> None:
    cases = [
        _case("passed_threshold", 0.95, 0.7),
        _case("below_threshold", 0.5, 0.7),
        _case("below_threshold", 0.0, 0.92),
        _case("passed_threshold", 1.0, 0.7),
    ]
    selected = analyze._select_target_cases(cases, include_borderline=False, skip_existing=True)
    assert selected == [1, 2]


def test_borderline_mode_selects_close_passes() -> None:
    cases = [
        _case("passed_threshold", 0.92, 0.92),  # exactly threshold, Δ=0
        _case("passed_threshold", 0.85, 0.92),  # Δ=0.07, within 0.10
        _case("passed_threshold", 0.70, 0.92),  # Δ=0.22, too far
        _case("below_threshold", 0.5, 0.7),
    ]
    selected = analyze._select_target_cases(cases, include_borderline=True, skip_existing=True)
    assert selected == [0, 1, 3]


def test_skip_existing_skips_already_classified() -> None:
    cases = [
        _case("below_threshold", 0.5, 0.7, root_cause={"category": "missing_disclaimer"}),
        _case("below_threshold", 0.3, 0.7),
    ]
    selected = analyze._select_target_cases(cases, include_borderline=False, skip_existing=True)
    assert selected == [1]


def test_skip_existing_false_includes_all() -> None:
    cases = [
        _case("below_threshold", 0.5, 0.7, root_cause={"category": "missing_disclaimer"}),
        _case("below_threshold", 0.3, 0.7),
    ]
    selected = analyze._select_target_cases(cases, include_borderline=False, skip_existing=False)
    assert selected == [0, 1]
