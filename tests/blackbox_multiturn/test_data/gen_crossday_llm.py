"""
LLM-generated cross-day multi-turn test cases.

Calls the configured LLM (default: settings.main_model) to generate 12 diverse
cross-day scenarios, one topic at a time, then writes:
    tests/blackbox_multiturn/test_data/multiturn_crossday_llm_cases.json

Usage:
    # From repo root:
    GOOGLE_API_KEY=... python tests/blackbox_multiturn/test_data/gen_crossday_llm.py

    # Override model:
    GOOGLE_API_KEY=... PAWLY_MODEL=gemini-2.0-flash python ...

Run the generated cases:
    pytest tests/blackbox_multiturn/test_crossday_multiturn.py \\
        --crossday-topic=multiturn_crossday_llm --model=gemini-2.0-flash
"""
import asyncio
import json
import os
import pathlib
import re
import sys
import time

# Make src/ importable when running from any directory.
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-bot-token")
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")

OUT = pathlib.Path(__file__).parent / "multiturn_crossday_llm_cases.json"

# ──────────────────────────────────────────────────────────────────────────────
# Schema description sent to the LLM on every call
# ──────────────────────────────────────────────────────────────────────────────

SCHEMA = """
Cross-day test case JSON schema (output ONLY this JSON object, nothing else):
{
  "name": "unique_snake_case_id_cross_day",
  "scenario": "2-3 sentences covering the full multi-day situation",
  "expected_outcome": "What Pawly should do on Day 2 (or Day 3) to prove it remembers Day 1",
  "chatbot_role": "Pawly is a pet care assistant providing continuity-aware follow-up for ...",
  "criteria": "Judge must check that on Day 2 the bot: (a) ... (b) ... (c) ... (d) ...",
  "threshold": 0.85,
  "pet_profile": {
    "name": "PetName",
    "species": "dog" or "cat",
    "breed": "exact breed name",
    "age_in_months": <integer>,
    "gender": "male" or "female",
    "neutered_status": "yes" or "no",
    "weight_latest": <float, kg>
  },
  "days": [
    {
      "label": "Day 1 — Brief description of what happened",
      "user_turns": ["message 1", "message 2", "message 3"],
      "run_extraction": true,
      "run_daily_summary": true
    },
    {
      "label": "Day 2 — Brief description of follow-up",
      "user_turns": ["follow-up 1", "follow-up 2", "follow-up 3"],
      "run_extraction": false,
      "run_daily_summary": false
    }
  ]
}
"""

# ──────────────────────────────────────────────────────────────────────────────
# Worked example (included in every prompt as a format anchor)
# ──────────────────────────────────────────────────────────────────────────────

EXAMPLE = {
    "name": "mochi_vomiting_cross_day",
    "scenario": (
        "Mochi vomited twice and became lethargic on Day 1. The owner reported no blood in "
        "the vomit and that it looked like undigested food. On Day 2 the owner returns to ask "
        "how Mochi should be feeling and whether yesterday's episode is still cause for concern, "
        "given that Mochi ate a little this morning."
    ),
    "expected_outcome": (
        "On Day 2 the bot proactively references the vomiting episode from Day 1, asks whether "
        "vomiting has continued overnight, and gives recovery-aware advice that builds on the "
        "prior assessment — acknowledging the small meal as a positive sign without re-asking "
        "basic symptom questions already covered on Day 1."
    ),
    "chatbot_role": (
        "Pawly is a pet care assistant providing continuity-aware follow-up for a cat that had "
        "a vomiting and lethargy episode the previous day."
    ),
    "criteria": (
        "Judge must check that on Day 2 the bot: "
        "(a) references the vomiting episode from Day 1 without being prompted to do so; "
        "(b) asks about symptom progression — specifically whether vomiting continued after "
        "Day 1's conversation; "
        "(c) does NOT re-ask basic symptom questions already answered on Day 1 (was there blood, "
        "what did vomit look like, is she lethargic); "
        "(d) gives recovery-aware advice that explicitly acknowledges yesterday's assessment and "
        "frames the small meal as a positive indicator relative to the prior episode."
    ),
    "threshold": 0.85,
    "pet_profile": {
        "name": "Mochi", "species": "cat", "breed": "Domestic Shorthair",
        "age_in_months": 24, "gender": "female", "neutered_status": "yes",
        "weight_latest": 3.6,
    },
    "days": [
        {
            "label": "Day 1 — Vomiting and lethargy episode",
            "user_turns": [
                "Mochi threw up twice this morning, what should I do?",
                "She's been lethargic since and won't eat her food",
                "No blood in the vomit, it looked like undigested food",
            ],
            "run_extraction": True,
            "run_daily_summary": True,
        },
        {
            "label": "Day 2 — Follow-up after overnight rest",
            "user_turns": [
                "How is Mochi supposed to be feeling today after yesterday?",
                "She ate a little bit this morning, is that a good sign?",
                "Should I still worry about the vomiting from yesterday?",
            ],
            "run_extraction": False,
            "run_daily_summary": False,
        },
    ],
}

# ──────────────────────────────────────────────────────────────────────────────
# Topic definitions — one LLM call per topic
# ──────────────────────────────────────────────────────────────────────────────

TOPICS = [
    {
        "id": "limping_recovery",
        "days": 2,
        "prompt": (
            "Dog suddenly starts limping on one rear leg after a morning walk. "
            "Owner sees no obvious wound. On Day 2 the limp has noticeably improved but "
            "the dog is still favouring that leg."
        ),
        "pet_type": "dog",
        "breed_hint": "French Bulldog, Corgi, or Jack Russell Terrier",
    },
    {
        "id": "post_spay_recovery",
        "days": 2,
        "prompt": (
            "Cat came home from spay surgery on Day 1 — still groggy, not eating. "
            "On Day 2 the owner notices the incision site looks slightly puffy and asks if it is normal."
        ),
        "pet_type": "cat",
        "breed_hint": "Domestic Shorthair, Bengal, or Ragdoll",
    },
    {
        "id": "skin_rash_treatment",
        "days": 2,
        "prompt": (
            "Dog has a red, itchy patch on its belly on Day 1. Vet prescribed an antihistamine "
            "and medicated shampoo. On Day 2 the rash is less red but the dog still scratches."
        ),
        "pet_type": "dog",
        "breed_hint": "Poodle, Maltese, or Shih Tzu",
    },
    {
        "id": "eye_discharge_monitoring",
        "days": 2,
        "prompt": (
            "Cat has yellowish eye discharge and is squinting on Day 1. "
            "Vet prescribed antibiotic eye drops. On Day 2 the discharge has reduced but "
            "the cat still seems uncomfortable."
        ),
        "pet_type": "cat",
        "breed_hint": "Persian, Scottish Fold, or British Shorthair",
    },
    {
        "id": "antibiotic_side_effect",
        "days": 2,
        "prompt": (
            "Dog started a 10-day course of amoxicillin for an ear infection on Day 1. "
            "On Day 2 the dog is off food and seems nauseous — owner wonders if it is the medication."
        ),
        "pet_type": "dog",
        "breed_hint": "Cocker Spaniel, Beagle, or Basset Hound",
    },
    {
        "id": "coughing_respiratory",
        "days": 2,
        "prompt": (
            "Cat has been coughing and sneezing repeatedly throughout Day 1 with no fever. "
            "On Day 2 the sneezing has halved in frequency but there is now nasal discharge."
        ),
        "pet_type": "cat",
        "breed_hint": "Siamese, Domestic Shorthair, or Maine Coon",
    },
    {
        "id": "appetite_loss_weight",
        "days": 2,
        "prompt": (
            "Dog has barely eaten for 2 days and the owner notices visible rib definition on Day 1. "
            "Owner switched to a high-palatability wet food. On Day 2 the dog ate half the portion."
        ),
        "pet_type": "dog",
        "breed_hint": "Border Collie, Australian Shepherd, or Labrador",
    },
    {
        "id": "stress_new_environment",
        "days": 2,
        "prompt": (
            "Owner moved to a new apartment and their cat has been hiding under the bed all Day 1, "
            "refusing food and hissing when approached. On Day 2 the cat has come out briefly "
            "but is still very subdued."
        ),
        "pet_type": "cat",
        "breed_hint": "Ragdoll, Russian Blue, or Birman",
    },
    {
        "id": "urinary_straining",
        "days": 2,
        "prompt": (
            "Dog strains to urinate and only passes small amounts on Day 1. Vet prescribed "
            "anti-spasmodic medication. On Day 2 urination is easier but still more frequent than normal."
        ),
        "pet_type": "dog",
        "breed_hint": "Dalmatian, Miniature Schnauzer, or Yorkshire Terrier",
    },
    {
        "id": "bite_wound_healing",
        "days": 2,
        "prompt": (
            "Cat got a bite wound from a neighbourhood cat on Day 1 — small but deep. "
            "Owner cleaned it with saline. On Day 2 the wound has a small amount of dried discharge "
            "and the cat is licking it more."
        ),
        "pet_type": "cat",
        "breed_hint": "Domestic Shorthair, Tabby, or Siamese",
    },
    {
        "id": "ear_infection_drops",
        "days": 2,
        "prompt": (
            "Dog with a confirmed ear infection starts prescribed ear drops on Day 1 — still "
            "shaking its head and scratching the ear. On Day 2 head shaking is less intense "
            "but owner notices a faint smell from the ear."
        ),
        "pet_type": "dog",
        "breed_hint": "Golden Retriever, Cavalier King Charles Spaniel, or Poodle",
    },
    {
        "id": "three_day_worsening_then_recovery",
        "days": 3,
        "prompt": (
            "Dog seems off on Day 1 (lethargy, skipped dinner). Worsens on Day 2 — vomited once, "
            "still not eating. Starts recovering on Day 3 — ate breakfast, more alert. "
            "IMPORTANT: This is a 3-day case. "
            "Day 1: run_extraction=true, run_daily_summary=true. "
            "Day 2: run_extraction=true, run_daily_summary=true. "
            "Day 3: run_extraction=false, run_daily_summary=false. "
            "The criteria must check Day 3 behaviour: bot must reference BOTH Day 1 and Day 2 events."
        ),
        "pet_type": "dog",
        "breed_hint": "Labrador Retriever, Golden Retriever, or Husky",
    },
]

# ──────────────────────────────────────────────────────────────────────────────
# JSON extraction helpers
# ──────────────────────────────────────────────────────────────────────────────

def _extract_json_object(text: str) -> str:
    """Extract the first balanced JSON object from arbitrary LLM text."""
    text = text.strip()

    # Strip markdown fences if present.
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()

    # Find the first '{' and walk to the matching '}'.
    start = text.find("{")
    if start == -1:
        return text

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return text[start:]


# ──────────────────────────────────────────────────────────────────────────────
# Schema validation
# ──────────────────────────────────────────────────────────────────────────────

def _validate(case: dict, topic_id: str) -> list[str]:
    """Return a list of error strings (empty = valid)."""
    errors: list[str] = []

    for f in ("name", "scenario", "expected_outcome", "chatbot_role", "criteria", "threshold", "pet_profile", "days"):
        if f not in case:
            errors.append(f"missing top-level field: {f}")

    pet = case.get("pet_profile") or {}
    for f in ("name", "species", "breed", "age_in_months", "gender", "neutered_status"):
        if f not in pet:
            errors.append(f"pet_profile missing: {f}")

    if pet.get("species") not in ("dog", "cat"):
        errors.append(f"pet_profile.species must be 'dog' or 'cat', got: {pet.get('species')!r}")
    if pet.get("gender") not in ("male", "female"):
        errors.append(f"pet_profile.gender must be 'male' or 'female', got: {pet.get('gender')!r}")

    days = case.get("days") or []
    if not isinstance(days, list) or len(days) < 2:
        errors.append("days must be a list with at least 2 entries")
    else:
        for i, d in enumerate(days):
            turns = d.get("user_turns") or []
            if not isinstance(turns, list) or len(turns) < 2:
                errors.append(f"days[{i}].user_turns must have at least 2 strings")
            if "run_extraction" not in d:
                errors.append(f"days[{i}] missing run_extraction")
            if "run_daily_summary" not in d:
                errors.append(f"days[{i}] missing run_daily_summary")

    return errors


def _normalise(case: dict) -> dict:
    """Coerce numeric fields, inject fixed metadata."""
    pet = case.get("pet_profile") or {}
    try:
        pet["age_in_months"] = int(pet["age_in_months"])
    except (KeyError, TypeError, ValueError):
        pass
    try:
        pet["weight_latest"] = float(pet.get("weight_latest", 4.0))
    except (TypeError, ValueError):
        pet["weight_latest"] = 4.0

    try:
        case["threshold"] = float(case.get("threshold", 0.85))
    except (TypeError, ValueError):
        case["threshold"] = 0.85

    # Ensure boolean types for run_* flags.
    for d in case.get("days") or []:
        for flag in ("run_extraction", "run_daily_summary"):
            v = d.get(flag)
            if isinstance(v, str):
                d[flag] = v.lower() in ("true", "1", "yes")

    # Always inject the correct metadata.
    case["metadata"] = {
        "category": "cross_day",
        "layer": "handler_blackbox_multiturn",
        "priority": "P1",
        "multiturn": True,
    }
    return case


# ──────────────────────────────────────────────────────────────────────────────
# Single-case generation
# ──────────────────────────────────────────────────────────────────────────────

_SYSTEM = (
    "You are a test-case designer for a pet care chatbot called Pawly. "
    "Your output must be a single valid JSON object with no markdown, no commentary, "
    "no text before or after the JSON."
)


async def _generate_case(client, model: str, topic: dict, max_attempts: int = 3) -> dict | None:
    example_json = json.dumps(EXAMPLE, indent=2, ensure_ascii=False)

    days_note = ""
    if topic["days"] == 3:
        days_note = (
            "\nThis case spans THREE days. "
            "Day 1 and Day 2 both set run_extraction=true and run_daily_summary=true. "
            "Day 3 sets run_extraction=false and run_daily_summary=false."
        )

    prompt = f"""Generate ONE cross-day multi-turn test case for the Pawly pet care chatbot.

SCENARIO TO GENERATE:
{topic['prompt']}
Pet type: {topic['pet_type']} ({topic['breed_hint']})
Case name must contain: {topic['id']}
{days_note}

SCHEMA (follow exactly):
{SCHEMA}

EXAMPLE CASE (format reference — do NOT copy content):
{example_json}

IMPORTANT RULES:
1. Day 2+ user messages must NOT re-explain what already happened on Day 1.
   The owner assumes Pawly remembers. E.g. Day 2: "Is she better today?" not "My cat vomited yesterday..."
2. criteria must list exactly 4 checkable cross-day continuity conditions as (a)(b)(c)(d).
3. Use a Singapore-based owner first name and realistic Singapore pet context.
4. Each day should have 3-4 user_turns, each 1-2 sentences long.
5. name must end with _cross_day.

Output ONLY the JSON object.
"""

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            await asyncio.sleep(6 * attempt)
        try:
            result = await client.chat(
                system_prompt=_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=4096,
                model=model,
            )
            raw = result.get("text", "")
            extracted = _extract_json_object(raw)
            case = json.loads(extracted)
            case = _normalise(case)
            errors = _validate(case, topic["id"])
            if errors:
                print(f"    attempt {attempt}: validation errors — {errors}")
                # Feed back the errors on the next attempt.
                prompt += f"\n\nYour previous attempt had these schema errors:\n" + "\n".join(f"- {e}" for e in errors) + "\nFix them and try again."
                last_error = ValueError(str(errors))
                continue
            return case
        except Exception as exc:
            last_error = exc
            print(f"    attempt {attempt}: {type(exc).__name__}: {exc}")

    print(f"  FAILED after {max_attempts} attempts: {last_error}")
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    from src.config import settings
    from src.llm.providers import get_chat_client

    model = os.environ.get("PAWLY_MODEL") or settings.main_model or "gemini-2.0-flash"
    print(f"Generator model: {model}")
    print(f"Output: {OUT}\n")

    client = get_chat_client(model)

    cases: list[dict] = []
    seen_names: set[str] = set()

    for i, topic in enumerate(TOPICS):
        print(f"[{i + 1}/{len(TOPICS)}] {topic['id']} ({topic['days']}-day case)...")
        case = await _generate_case(client, model, topic)

        if case is None:
            print(f"  SKIPPED\n")
            continue

        # Deduplicate names.
        base = case.get("name") or f"{topic['id']}_cross_day"
        name = base
        n = 2
        while name in seen_names:
            name = f"{base}_{n}"
            n += 1
        case["name"] = name
        seen_names.add(name)

        cases.append(case)
        print(f"  OK {name} ({len(case['days'])} days, threshold={case['threshold']})\n")

        # Polite rate-limit gap between calls.
        if i < len(TOPICS) - 1:
            await asyncio.sleep(4)

    print(f"Generated {len(cases)}/{len(TOPICS)} cases")

    if not cases:
        print("No cases generated — check your API key and model settings.")
        sys.exit(1)

    OUT.write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Written to {OUT}")
    print(f"\nRun with:")
    print(f"  pytest tests/blackbox_multiturn/test_crossday_multiturn.py \\")
    print(f"    --crossday-topic=multiturn_crossday_llm --model={model}")


if __name__ == "__main__":
    asyncio.run(main())
