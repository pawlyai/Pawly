"""
Blackbox quality tests for the proactive message generation module.

Each test case:
  1. Calls the real generation function (live LLM, needs GOOGLE_API_KEY or configured model)
  2. Judges the output with deepeval GEval using the case-specific criteria

Run with:
    pytest tests/blackbox_proactive/ -v

Skip conditions:
  - deepeval not installed
  - No eval LLM configured (PAWLY_EVAL_LLM / DEEPEVAL_MODEL)
  - No generation LLM configured (GOOGLE_API_KEY)

Mark with @pytest.mark.skip or set PAWLY_PROACTIVE_BLACKBOX_SKIP=1 to skip all.
"""

import os

import pytest


def _skip_if_no_generation_key():
    key = os.environ.get("GOOGLE_API_KEY", "")
    if not key or key.startswith("test"):
        pytest.skip("No real GOOGLE_API_KEY — skipping live generation test")


async def _generate(case: dict) -> str:
    """Dispatch to the correct generation function based on case type."""
    t = case["type"]
    inp = case["input"]

    if t == "triage_followup":
        from src.jobs.followup import _generate_message
        return await _generate_message(
            pet_name=inp["pet_name"],
            pet_species=inp["pet_species"],
            triage_level=inp["triage_level"],
            symptom_tags=inp["symptom_tags"],
            stage=inp["stage"],
        )

    if t == "episode_checkin":
        from src.jobs.episode_checkin import _generate_episode_checkin
        return await _generate_episode_checkin(
            pet_name=inp["pet_name"],
            pet_species=inp["pet_species"],
            symptom_type=inp["symptom_type"],
            severity=inp["severity"],
            days_ongoing=inp["days_ongoing"],
            interventions=inp.get("interventions"),
        )

    if t == "reengagement":
        # Reengagement now uses a hardcoded message — no LLM call.
        pet_name = inp["pet_name"]
        species = inp.get("species", "pet").lower()
        return (
            f"Hey! It's been a couple of days — how is {pet_name} doing? 🐾\n"
            f"Feel free to share any updates or questions about your {species}!"
        )

    if t == "daily_summary_push":
        from src.proactive.summary_pusher import _generate_push_message
        return await _generate_push_message(
            pet_name=inp["pet_name"],
            species=inp["species"],
            unresolved=inp.get("unresolved", []),
            follow_up_reason=inp.get("follow_up_reason", ""),
        )

    raise ValueError(f"Unknown case type: {t}")


async def test_proactive_message_quality(
    proactive_case: dict, deepeval_model, proactive_run_collector: list
) -> None:
    """
    Generate a proactive message for the given case and evaluate it with GEval.
    Results are collected in proactive_run_collector; a report JSON is written
    to tests/blackbox_multiturn/results/ at session teardown so it appears in
    the 1_Reports.py panel alongside multiturn reports.
    """
    pytest.importorskip("deepeval")
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase
    from deepeval.test_case import SingleTurnParams

    _skip_if_no_generation_key()

    generated_text = await _generate(proactive_case)

    print(f"\n[{proactive_case['id']}] Generated: {generated_text!r}")
    assert generated_text, f"Generation returned empty string for case {proactive_case['id']}"

    metric = GEval(
        name="ProactiveMessageQuality",
        criteria=proactive_case["criteria"],
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
        model=deepeval_model,
        threshold=proactive_case.get("threshold", 0.7),
        async_mode=False,
        verbose_mode=True,
    )

    metric.measure(LLMTestCase(
        input=f"Generate proactive message for: {proactive_case['name']}",
        actual_output=generated_text,
    ))

    print(f"Score: {metric.score:.2f} | Reason: {metric.reason}")
    proactive_run_collector.append({
        "case": proactive_case,
        "score": metric.score,
        "reason": metric.reason or "",
        "passed": metric.is_successful(),
        "generated": generated_text,
    })
    assert metric.is_successful(), (
        f"[{proactive_case['id']}] Quality score {metric.score:.2f} < threshold "
        f"{proactive_case['threshold']} — Reason: {metric.reason}\n"
        f"Generated: {generated_text!r}"
    )
