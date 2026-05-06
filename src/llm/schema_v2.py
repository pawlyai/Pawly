"""
LLM Response Schema v2 — multi-label scenario + soft urgency + structured signals.

Replaces (in v2 path) the original RESPONSE_SCHEMA in client.py. Key
differences from v1:
    - scenario_scores: multi-label probabilities (medical/emotional/crisis_human/
      general_chat/out_of_scope), not a single triage_level
    - urgency_soft_score: 0-1 estimate of how "soft-urgent" the message reads,
      independent of explicit medical keywords
    - human_distress_signals: structured enum list for the merge layer to
      cross-check against crisis_gate
    - pet_signals_present: boolean for routing fallback heuristics
    - response_text: still the user-facing reply, but with explicit guard
      against dumping JSON or schema fields

Public API:
    RESPONSE_SCHEMA_V2: dict ready for Gemini structured output config
"""

from __future__ import annotations

from typing import Any


RESPONSE_SCHEMA_V2: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        # ── User-facing reply ────────────────────────────────────────────────
        "response_text": {
            "type": "STRING",
            "description": (
                "The user-facing reply, written as if it will be shown directly. "
                "Plain text only. Do NOT include JSON, schema field names, or "
                "internal classifier labels in this field. If the scenario is "
                "emotional or crisis, write the empathetic human response here — "
                "do NOT redirect to pet care."
            ),
        },

        # ── Scenario scores (multi-label) ────────────────────────────────────
        "scenario_scores": {
            "type": "OBJECT",
            "properties": {
                "medical": {
                    "type": "NUMBER",
                    "description": "0.0-1.0. Probability the user is reporting a pet health/symptom concern.",
                },
                "emotional": {
                    "type": "NUMBER",
                    "description": "0.0-1.0. Probability user is processing grief/stress/anxiety about pet or self.",
                },
                "crisis_human": {
                    "type": "NUMBER",
                    "description": "0.0-1.0. Probability user is showing signs of self-harm or suicidal ideation.",
                },
                "general_chat": {
                    "type": "NUMBER",
                    "description": "0.0-1.0. Casual pet chat, photo sharing, naming.",
                },
                "out_of_scope": {
                    "type": "NUMBER",
                    "description": "0.0-1.0. Non-pet topic the assistant should redirect.",
                },
            },
            "required": [
                "medical", "emotional", "crisis_human", "general_chat", "out_of_scope",
            ],
        },

        # ── Soft urgency ─────────────────────────────────────────────────────
        "urgency_soft_score": {
            "type": "NUMBER",
            "description": (
                "0.0-1.0. How urgent does the message FEEL even without explicit "
                "emergency keywords? Used to decide whether to ask vital-sign "
                "questions (Airway/Breathing/Circulation). Examples: "
                "'something is wrong with him' = ~0.5; 'he just collapsed' = "
                "~0.95; 'what should I feed my puppy' = ~0.05."
            ),
        },

        # ── Triage (only meaningful when scenario_scores.medical is high) ───
        "triage_level": {
            "type": "STRING",
            "enum": ["RED", "ORANGE", "GREEN", "NA"],
            "description": "RED/ORANGE/GREEN if scenario is medical; NA otherwise.",
        },
        "missing_info": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "What additional info would raise diagnostic confidence. Empty when non-medical.",
        },

        # ── Distress signal extraction (for crisis cross-check) ─────────────
        "human_distress_signals": {
            "type": "ARRAY",
            "items": {
                "type": "STRING",
                "enum": [
                    "grief",
                    "anxiety_panic",
                    "burnout_caregiver",
                    "hopelessness",
                    "suicidal_ideation_implicit",
                    "suicidal_ideation_explicit",
                    "self_harm_intent",
                    "isolation",
                    "none",
                ],
            },
        },
        "pet_signals_present": {
            "type": "BOOLEAN",
            "description": "True if message references a pet, symptom, behavior, or pet-related context.",
        },
        "symptom_tags": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Pet symptoms explicitly mentioned (lower-snake-case).",
        },

        # ── Existing meta fields (sentiment / intent) ────────────────────────
        "intent": {
            "type": "STRING",
            "enum": [
                "symptom_report", "nutrition", "exercise", "grooming",
                "behavior", "question", "emotional_support", "crisis",
                "general", "out_of_scope",
            ],
        },
        "sentiment": {
            "type": "STRING",
            "enum": [
                "calm", "concerned", "worried", "distressed",
                "grieving", "angry", "neutral",
            ],
        },
    },
    "required": [
        "response_text",
        "scenario_scores",
        "urgency_soft_score",
        "triage_level",
        "pet_signals_present",
        "human_distress_signals",
        "intent",
        "sentiment",
    ],
}


# ── Defaults for fallback when LLM call fails ───────────────────────────────

DEFAULT_RESPONSE_V2: dict[str, Any] = {
    "response_text": "I'm having trouble processing that right now. Could you tell me a bit more, or try again in a moment?",
    "scenario_scores": {
        "medical": 0.0, "emotional": 0.0, "crisis_human": 0.0,
        "general_chat": 0.5, "out_of_scope": 0.0,
    },
    "urgency_soft_score": 0.0,
    "triage_level": "GREEN",
    "missing_info": [],
    "human_distress_signals": ["none"],
    "pet_signals_present": False,
    "symptom_tags": [],
    "intent": "general",
    "sentiment": "neutral",
}
