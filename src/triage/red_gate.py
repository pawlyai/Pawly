"""
Red gate — prompt-grounded verification of a RED triage decision.

Before finalising a RED label, do a second LLM call instructing the model
to consult its training knowledge of authoritative veterinary sources
(Merck Vet Manual, AVMA / AAHA Guidelines, VECCS Protocols, ACVIM
Consensus Statements, ASPCA / Pet Poison Helpline) and either:

    - confirm RED with a citation and a final user-facing response, or
    - return ONE clarification question that distinguishes RED vs the
      next-lower tier.

Fast-escape: rule_engine matches that imply imminent danger (seizure,
collapse, suspected toxin, blocked male cat, severe bleeding, distended
abdomen, blue/pale gums) bypass the gate entirely. Adding another LLM
hop on those cases trades latency for the chance to flip a clearly-RED
case down — not worth it.

Public API:
    should_fast_escape(matched_rules)   -> bool
    verify_red(...)                      -> RedGateResult
"""

from dataclasses import dataclass
from typing import Any, Optional

from src.db.models import Pet
from src.llm.client import get_gemini_client
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Rule-engine match strings that should skip the gate.
# Anchor: TriageRuleResult.matched_rules entries from src/triage/rules_engine.py.
_FAST_ESCAPE_PATTERNS: frozenset[str] = frozenset({
    # Critical RED keywords (life-threatening, no upside in re-checking)
    "keyword_red:seizure",
    "keyword_red:convulsion",
    "keyword_red:fitting",
    "keyword_red:shaking_uncontrollably",
    "keyword_red:collapsed",
    "keyword_red:unconscious",
    "keyword_red:won't_wake",
    "keyword_red:wont_wake",
    "keyword_red:not_responding",
    "keyword_red:can't_breathe",
    "keyword_red:cant_breathe",
    "keyword_red:not_breathing",
    "keyword_red:gasping",
    "keyword_red:struggling_to_breathe",
    "keyword_red:blue_gums",
    "keyword_red:pale_gums",
    "keyword_red:white_gums",
    "keyword_red:heavy_bleeding",
    "keyword_red:won't_stop_bleeding",
    "keyword_red:wont_stop_bleeding",
    "keyword_red:ate_chocolate",
    "keyword_red:ate_xylitol",
    "keyword_red:ate_lily",
    "keyword_red:ate_antifreeze",
    "keyword_red:ate_grape",
    "keyword_red:ate_raisin",
    "keyword_red:ate_onion",
    "keyword_red:poisoned",
    "keyword_red:bloated_stomach",
    "keyword_red:distended_abdomen",
    "keyword_red:stomach_swelling",
    "keyword_red:paralyzed",
    "keyword_red:dragging_legs",
    "keyword_red:hind_legs_not_working",
    "keyword_red:eye_popping",
    "keyword_red:eye_out",
    "keyword_red:prolapse",
    "keyword_red:heatstroke",
    # Pet-specific combos (already vet-aware)
    "pet:male_cat_urinary_blockage",
    "pet:young_animal_anorexia",
    "combo:bloody_diarrhea_lethargy",
    "combo:breathing_plus_other",
})


def should_fast_escape(matched_rules: list[str]) -> bool:
    """True if any matched_rules entry is in the fast-escape set."""
    return any(rule in _FAST_ESCAPE_PATTERNS for rule in matched_rules)


_GATE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "matched_scenario": {
            "type": "STRING",
            "description": "Closest clinical scenario from authoritative sources, e.g. 'canine GDV', 'chocolate toxicity', 'feline urethral obstruction'.",
        },
        "red_flags_in_source": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Standard red-flag signs for matched_scenario from your training knowledge of authoritative sources.",
        },
        "red_flags_observed": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Subset of red_flags_in_source that the dialogue actually evidences.",
        },
        "confirmed_red": {
            "type": "BOOLEAN",
            "description": "True if observed red flags meet the standard for RED triage; false if more information is needed.",
        },
        "clarification_question": {
            "type": "STRING",
            "description": "ONE focused question that would distinguish RED from the next-lower tier (Orange). Empty when confirmed_red=true.",
        },
        "response_text": {
            "type": "STRING",
            "description": "Final user-facing response when confirmed_red=true. Plain text — visual chrome is added by the system. Empty when confirmed_red=false.",
        },
        "citation": {
            "type": "STRING",
            "description": "Source name only — e.g. 'Merck Vet Manual', 'ASPCA / Pet Poison Helpline', 'AVMA Guidelines'. Do NOT invent section numbers, paragraph IDs, or page references.",
        },
    },
    "required": [
        "matched_scenario", "red_flags_in_source", "red_flags_observed",
        "confirmed_red", "clarification_question", "response_text", "citation",
    ],
}


_GATE_SYSTEM_PROMPT = """You are a veterinary triage validator. Your only job is to verify whether a RED (emergency) triage decision is justified before it reaches the user.

Use your training knowledge of these authoritative sources:
- Merck Veterinary Manual (merckvetmanual.com) — clinical conditions
- AVMA / AAHA Guidelines — practice and care standards
- VECCS Protocols — emergency and critical-care consensus
- ACVIM Consensus Statements — internal medicine specialty consensus
- ASPCA / Pet Poison Helpline — toxin tables and management

Pet context is load-bearing. The same symptom can be RED for one pet and
Orange for another — read the Pet block and Known context carefully:
- Diabetic cat vomiting → RED (DKA risk); healthy adult cat vomiting once → Orange.
- Senior dog with known cardiac disease + cough → RED; young dog with kennel cough → Orange.
- Puppy / kitten + not eating > 24h → RED (hypoglycaemia / dehydration risk); adult skipping a meal → Green.
- Pet on NSAIDs + lethargy or black stool → RED (GI bleed risk).
- Brachycephalic breed (Bulldog, Pug, Persian) + heavy panting → escalate threshold; same in Border Collie may not.
- Male cat + any urinary signs → RED (urethral obstruction risk).
Always factor age, breed, gender / neuter status, life stage, weight,
chronic conditions and current medications from the supplied context
into the threshold for confirming RED.

Procedure (run silently, output the JSON schema only):
1. Identify the closest clinical scenario from the dialogue.
2. List the standard red flags for that scenario from the sources above.
3. Identify which of those red flags the dialogue actually evidences,
   adjusted by the pet's profile (age / breed / chronic conditions / meds).
4. If observed red flags meet the source standard for emergency action,
   set confirmed_red=true and write the user-facing response_text:
     - urgent and clear, action-oriented
     - tell the owner to seek vet care now
     - do NOT suggest home remedies
     - plain text only — the system adds visual chrome
5. Otherwise set confirmed_red=false and write ONE clarification_question
   that would directly distinguish RED from Orange. Be specific and easy
   to answer. Leave response_text empty when confirmed_red=false.

Citation rules:
- Name the source only ("Merck Vet Manual", "ASPCA", "AVMA Guidelines").
- Do NOT invent section numbers, paragraph IDs, page references, or
  guideline version numbers. Fabricated citations are unacceptable.

Bias: when in doubt, prefer asking clarification over confirming.
Confirming RED is the most consequential decision; do not confirm
without observed evidence."""


@dataclass
class RedGateResult:
    confirmed_red: bool
    response_text: str
    clarification_question: str
    citation: str
    matched_scenario: str
    red_flags_observed: list[str]
    input_tokens: int
    output_tokens: int


async def verify_red(
    pet: Optional[Pet],
    user_message: str,
    recent_turns: list[dict],
    memory_context: str,
    matched_rules: list[str],
) -> RedGateResult:
    """
    Run the RED verification gate. The caller MUST invoke
    `should_fast_escape(matched_rules)` first and skip this function
    when it returns True — those cases need immediate action, not
    another LLM hop.
    """
    pet_block = ""
    if pet is not None:
        pet_block = (
            f"Pet: name={pet.name}"
            f", species={pet.species.value}"
            f", breed={pet.breed or 'unknown'}"
            f", age_months={pet.age_in_months or 'unknown'}"
            f", gender={pet.gender.value}"
            f", neutered={pet.neutered_status.value}"
            f", weight_kg={pet.weight_latest if pet.weight_latest is not None else 'unknown'}"
            f", stage={pet.stage.value if pet.stage else 'unknown'}"
        )

    rules_block = ""
    if matched_rules:
        rules_block = "Rule-engine matched patterns: " + ", ".join(matched_rules)

    history = "\n".join(
        f"{turn.get('role', 'user')}: {turn.get('content', '')}"
        for turn in recent_turns
    )

    user_payload = "\n\n".join(
        part for part in (
            pet_block,
            f"Known context:\n{memory_context}" if memory_context else "",
            f"Recent dialogue:\n{history}" if history else "",
            f"Latest user message:\n{user_message}",
            rules_block,
        ) if part
    )

    client = get_gemini_client()
    try:
        result = await client.chat_with_schema(
            system_prompt=_GATE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_payload}],
            response_schema=_GATE_SCHEMA,
            max_tokens=1024,
            temperature=0.2,
        )
    except Exception as exc:
        logger.error("red_gate verification failed", error=str(exc))
        # Fail safe: confirm RED rather than risk dropping a real emergency.
        return RedGateResult(
            confirmed_red=True,
            response_text="",
            clarification_question="",
            citation="",
            matched_scenario="(gate failed)",
            red_flags_observed=[],
            input_tokens=0,
            output_tokens=0,
        )

    return RedGateResult(
        confirmed_red=bool(result.get("confirmed_red", False)),
        response_text=str(result.get("response_text", "")).strip(),
        clarification_question=str(result.get("clarification_question", "")).strip(),
        citation=str(result.get("citation", "")).strip(),
        matched_scenario=str(result.get("matched_scenario", "")).strip(),
        red_flags_observed=list(result.get("red_flags_observed", [])),
        input_tokens=int(result.get("input_tokens", 0) or 0),
        output_tokens=int(result.get("output_tokens", 0) or 0),
    )
