"""
Unit tests for src/llm/retrievers.py — PR 3 (symptom followup KB) + PR 4 (special rules).
"""

from __future__ import annotations

import pytest

import src.llm.retrievers as _ret_module
from src.llm.retrievers import (
    format_followups,
    format_special_rules,
    match_followups,
    match_red_flags,
)


@pytest.fixture(autouse=True)
def _clear_retriever_cache():
    """Reload YAML data on each test to prevent cross-test state leakage."""
    _ret_module._followups_loaded = None
    _ret_module._special_rules_loaded = None
    yield
    _ret_module._followups_loaded = None
    _ret_module._special_rules_loaded = None


# ── PR 3: match_followups ──────────────────────────────────────────────────────

def test_match_followups_cn_vomiting():
    """Chinese vomiting message hits the vomiting entry."""
    results = match_followups("我家狗一直在吐")
    ids = [f.id for f in results]
    assert "vomiting" in ids


def test_match_followups_cn_respiratory():
    """Chinese respiratory message hits the respiratory entry."""
    results = match_followups("猫呼吸急促")
    ids = [f.id for f in results]
    assert "respiratory" in ids


def test_match_followups_no_match():
    """Customer service query produces no hits."""
    results = match_followups("我想咨询客服")
    assert results == []


def test_match_followups_en_vomiting():
    """English vomiting message hits the vomiting entry."""
    results = match_followups("my dog has been vomiting since this morning")
    ids = [f.id for f in results]
    assert "vomiting" in ids


def test_match_followups_en_no_match():
    """Greeting produces no hits."""
    results = match_followups("hello how are you")
    assert results == []


def test_match_followups_top_k():
    """top_k limits the number of results."""
    results = match_followups("vomiting and diarrhea and bleeding", top_k=2)
    assert len(results) <= 2


def test_match_followups_result_has_questions():
    """Matched entry carries question list."""
    results = match_followups("my dog is vomiting")
    assert results
    assert len(results[0].questions) > 0


# ── PR 4: match_red_flags ──────────────────────────────────────────────────────

def test_match_red_flags_medication_dosage():
    """Dosage question triggers medication_dosage rule."""
    results = match_red_flags("how many ml of metacam for my 5kg dog?")
    ids = [r.id for r in results]
    assert "medication_dosage" in ids


def test_match_red_flags_toxin_ingestion():
    """Xylitol ingestion hits toxin_ingestion via rules_engine keywords."""
    results = match_red_flags("my dog ate xylitol gum")
    ids = [r.id for r in results]
    assert "toxin_ingestion" in ids


def test_match_red_flags_owner_mental_health_cn():
    """Chinese suicide signal hits owner_mental_health rule."""
    results = match_red_flags("我想死了")
    ids = [r.id for r in results]
    assert "owner_mental_health" in ids


def test_match_red_flags_no_match():
    """Off-topic query produces no hits."""
    results = match_red_flags("how's the weather")
    assert results == []


def test_match_red_flags_euthanasia_en():
    """Euthanasia keyword hits euthanasia rule."""
    results = match_red_flags("should I euthanize my dog?")
    ids = [r.id for r in results]
    assert "euthanasia" in ids


def test_match_red_flags_toxin_cn():
    """Chinese 误食 triggers toxin_ingestion."""
    results = match_red_flags("我家猫误食了百合花")
    ids = [r.id for r in results]
    assert "toxin_ingestion" in ids


def test_match_red_flags_multiple_hits():
    """Message with both dosage and toxin keywords triggers both rules."""
    results = match_red_flags("my dog ate xylitol and I want to know the dosage of the antidote")
    ids = [r.id for r in results]
    assert "toxin_ingestion" in ids
    assert "medication_dosage" in ids


def test_match_red_flags_toxin_uses_rules_engine_keywords():
    """toxin_ingestion triggers_en come from rules_engine, not redeclared in YAML."""
    from src.triage.rules_engine import TOXIN_TRIGGER_KEYWORDS
    rules = _ret_module._get_special_rules()
    toxin_rule = next(r for r in rules if r.id == "toxin_ingestion")
    assert set(toxin_rule.triggers_en) == set(TOXIN_TRIGGER_KEYWORDS)


# ── Format functions ───────────────────────────────────────────────────────────

def test_format_followups_empty():
    assert format_followups([]) == ""


def test_format_followups_contains_questions():
    results = match_followups("my dog is vomiting")
    text = format_followups(results)
    assert "vomiting" in text.lower()
    assert "?" in text


def test_format_followups_contains_escalation_hint():
    results = match_followups("my dog is vomiting")
    text = format_followups(results)
    assert "ER" in text or "vet" in text.lower()


def test_format_special_rules_empty():
    assert format_special_rules([]) == ""


def test_format_special_rules_wraps_in_rule_tag():
    results = match_red_flags("how many ml of metacam?")
    text = format_special_rules(results)
    assert 'rule id="medication_dosage"' in text
    assert "</rule>" in text


def test_format_special_rules_only_matched_entries():
    """Only the matched rule is in the output — not all 4."""
    results = match_red_flags("what is the dosage of metacam?")
    text = format_special_rules(results)
    assert 'rule id="medication_dosage"' in text
    assert 'rule id="euthanasia"' not in text
    assert 'rule id="toxin_ingestion"' not in text
    assert 'rule id="owner_mental_health"' not in text
