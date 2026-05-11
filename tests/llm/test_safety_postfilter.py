"""Unit tests for safety_postfilter — no LLM calls, pure regex."""

from src.db.models import TriageLevel
from src.llm.safety_postfilter import apply_safety_postfilter


def test_non_red_passes_through():
    text = "Try giving 50mg of benadryl — totally fine, no induce vomiting"
    out, actions = apply_safety_postfilter(text, TriageLevel.GREEN)
    assert out == text
    assert actions == []
    out, actions = apply_safety_postfilter(text, TriageLevel.ORANGE)
    assert out == text
    assert actions == []


def test_red_with_proper_urgency_unchanged():
    text = (
        "🔴 Urgent. This looks like a possible toxin exposure. "
        "Go to the nearest emergency vet immediately and bring the packaging."
    )
    out, actions = apply_safety_postfilter(text, TriageLevel.RED)
    assert out == text
    assert actions == []


def test_red_missing_urgency_gets_closer():
    text = "🔴 Urgent. This could be serious. Please see a vet soon."
    out, actions = apply_safety_postfilter(text, TriageLevel.RED)
    assert "every minute counts" in out
    assert "appended_urgency_closer" in actions


def test_red_with_dose_stripped():
    text = (
        "🔴 Urgent. Go to the vet immediately. In the meantime, "
        "you can try giving 25mg of benadryl per 10kg of body weight."
    )
    out, actions = apply_safety_postfilter(text, TriageLevel.RED)
    assert "25mg" not in out or "[home-treatment guidance removed" in out
    assert any(a.startswith("forbidden:") for a in actions)


def test_red_induce_vomiting_stripped():
    text = (
        "🔴 Urgent. Suspected toxin. Go to the vet right away. "
        "If you cannot reach a vet, induce vomiting with hydrogen peroxide."
    )
    out, actions = apply_safety_postfilter(text, TriageLevel.RED)
    assert "induce vomiting" not in out.lower()
    assert any(a.startswith("forbidden:") for a in actions)


def test_red_benadryl_advice_stripped():
    text = (
        "🔴 Urgent. Allergic reaction. Call your emergency vet now. "
        "You can also administer benadryl while heading there."
    )
    out, actions = apply_safety_postfilter(text, TriageLevel.RED)
    assert "administer benadryl" not in out.lower()
    assert any(a.startswith("forbidden:") for a in actions)


def test_red_urgency_recognition_variants():
    variants = [
        "Go to the ER now.",
        "Call your vet immediately.",
        "Do not delay — this needs attention now.",
        "Right away — head to the emergency hospital.",
        "Within 30 min, get her to the vet.",
        "Every minute matters here.",
    ]
    for v in variants:
        out, actions = apply_safety_postfilter(v, TriageLevel.RED)
        assert "appended_urgency_closer" not in actions, f"falsely flagged: {v}"
