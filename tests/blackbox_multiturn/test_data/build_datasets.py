"""
Build canonical test_data/*_cases.json files from gen_*.py outputs.

Each gen_*.py writes <topic>.json. Cases come in two shapes:

  (a) Already-structured memories: gen_p0_dangerous, gen_p0_compliance,
      gen_p0_injection, gen_p1_edge, gen_p1_emotional. Their mem() helper
      already returns {memory_type, memory_term, field, value, ...} dicts.

  (b) Turn-shaped memories: gen_longitudinal, gen_p0_outofscope,
      gen_p1_general. Their mem() helper returns {role, content} — these
      are raw past-session chat turns, the same shape that
      src.memory.extractor consumes in production after a session ends.

For (b) cases, this script invokes src.memory.extractor.extract_memories()
over the turns to produce real PetMemory records — matching exactly what
production's extraction pipeline would have written to PetMemory rows
between sessions. The result is then assigned to the case's `memories`
field. (a) cases pass through unchanged.

Output:
  <topic>.json          — gen output (raw)
  <topic>_cases.json    — post-extraction, the file the test loader reads
  <topic combined>_cases.json — concatenation of all topics

Run from anywhere:
  python3 tests/blackbox_multiturn/test_data/build_datasets.py

Requirements:
  - An API key for the model in settings.extraction_model
    (GOOGLE_API_KEY for gemini-*, DEEPSEEK_API_KEY for deepseek-*, etc.)
  - Network access from the host running the script.

Reproducibility:
  Extraction is LLM-driven and stochastic. The extractor sets temperature=0.2
  which is fairly stable but not deterministic. Re-running this script may
  produce slightly different memory entries (different field naming choices
  by the LLM). Commit the produced _cases.json files alongside any prompt or
  generator change so reviewers see the resulting data, not just the source.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import re
import runpy
import sys
import uuid

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent.parent.parent  # project root

# Required env defaults so `from src.config import settings` works; the
# extraction step needs a real API key for the configured model, but the
# other vars are only consumed by db / bot init paths that we don't touch.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-bot-token")
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")

sys.path.insert(0, str(ROOT))

from src.config import settings  # noqa: E402
from src.db.models import (  # noqa: E402
    Gender,
    NeuteredStatus,
    Pet,
    Species,
)
from src.memory.extractor import MemoryProposal, extract_memories  # noqa: E402

GENERATORS: list[tuple[str, str]] = [
    ("gen_longitudinal.py", "multiturn_pawly_regression_test_longitudinal"),
    ("gen_p0_compliance.py", "multiturn_pawly_regression_test_p0_compliance"),
    ("gen_p0_dangerous.py", "multiturn_pawly_regression_test_p0_dangerous"),
    ("gen_p0_injection.py", "multiturn_pawly_regression_test_p0_injection"),
    ("gen_p0_outofscope.py", "multiturn_pawly_regression_test_p0_outofscope"),
    ("gen_p1_edge.py", "multiturn_pawly_regression_test_p1_edge"),
    ("gen_p1_emotional.py", "multiturn_pawly_regression_test_p1_emotional"),
    ("gen_p1_general.py", "multiturn_pawly_regression_test_p1_general"),
]
ALL_TOPIC = "multiturn_pawly_regression_test_all_223"


# ── Shape detection ──────────────────────────────────────────────────────────


def _is_turn_shaped(memories: list[dict]) -> bool:
    """True if memories are chat-turn dicts ({role, content}) that need to
    be passed through the extractor; False if already structured PetMemory
    records (have a 'memory_type' key)."""
    if not memories:
        return False
    first = memories[0]
    return isinstance(first, dict) and "role" in first and "memory_type" not in first


# ── pet_profile schema bridging ──────────────────────────────────────────────
#
# Some gen scripts use 'age' (string "3 years") / 'weight' (string "5.2 kg") /
# 'sex' (string "female spayed"), and others use production names
# 'age_in_months' (int) / 'weight_latest' (float) / 'gender' / 'neutered_status'.
# The extractor wants a Pet ORM object; build one tolerantly.


def _parse_age_months(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).lower()
    years = months = 0
    m = re.search(r"(\d+)\s*y", s)
    if m:
        years = int(m.group(1))
    m = re.search(r"(\d+)\s*m", s)
    if m:
        months = int(m.group(1))
    if years or months:
        return years * 12 + months
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def _parse_weight_kg(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"(\d+(?:\.\d+)?)", str(value))
    return float(m.group(1)) if m else None


def _parse_gender_and_neutered(sex_str: str) -> tuple[Gender, NeuteredStatus]:
    s = (sex_str or "").lower()
    gender = Gender.UNKNOWN
    if "female" in s or "girl" in s:
        gender = Gender.FEMALE
    elif "male" in s or "boy" in s:
        gender = Gender.MALE

    neutered = NeuteredStatus.UNKNOWN
    if "spayed" in s or "neutered" in s or "fixed" in s or "desexed" in s:
        neutered = NeuteredStatus.YES
    elif "intact" in s or "entire" in s:
        neutered = NeuteredStatus.NO

    return gender, neutered


def _build_pet_for_extraction(pet_profile: dict) -> Pet:
    """Map a generator's pet_profile dict to a Pet ORM object the extractor
    can read. Pet is not persisted; just used for prompt context."""
    pet_profile = pet_profile or {}
    species_str = pet_profile.get("species", "dog")

    age_in_months = pet_profile.get("age_in_months")
    if age_in_months is None:
        age_in_months = _parse_age_months(pet_profile.get("age"))

    weight = pet_profile.get("weight_latest")
    if weight is None:
        weight = _parse_weight_kg(pet_profile.get("weight"))

    gender_str = pet_profile.get("gender")
    neutered_str = pet_profile.get("neutered_status")
    if gender_str is not None:
        gender = Gender(gender_str)
    elif neutered_str is None:
        gender, _ = _parse_gender_and_neutered(pet_profile.get("sex", ""))
    else:
        gender = Gender.UNKNOWN

    if neutered_str is not None:
        neutered = NeuteredStatus(neutered_str)
    elif gender_str is None:
        _, neutered = _parse_gender_and_neutered(pet_profile.get("sex", ""))
    else:
        neutered = NeuteredStatus.UNKNOWN

    return Pet(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name=pet_profile.get("name", "Unnamed"),
        species=Species(species_str),
        breed=pet_profile.get("breed"),
        age_in_months=age_in_months,
        gender=gender,
        neutered_status=neutered,
        weight_latest=weight,
    )


# ── Extraction pipeline ──────────────────────────────────────────────────────


def _proposal_to_dict(p: MemoryProposal) -> dict:
    """Serialize a MemoryProposal to the JSON shape that
    conftest._build_pet_memory consumes."""
    return {
        "memory_type": p.memory_type.value,
        "memory_term": p.memory_term.value,
        "field": p.field,
        "value": p.value,
        "confidence_score": p.confidence,
        "source_quote": p.source_quote,
    }


async def _extract_case(case: dict, index: int, total: int) -> list[dict]:
    name = case.get("name", f"<case_{index}>")
    turns = case.get("memories", [])
    if not _is_turn_shaped(turns):
        return turns

    try:
        pet = _build_pet_for_extraction(case.get("pet_profile", {}))
    except Exception as exc:
        print(f"  [{index}/{total}] {name}: pet_profile build failed: {exc}", file=sys.stderr)
        return []

    try:
        proposals = await extract_memories(turns, pet, existing_memories=[])
    except Exception as exc:
        print(f"  [{index}/{total}] {name}: extractor raised: {exc}", file=sys.stderr)
        return []

    facts = [_proposal_to_dict(p) for p in proposals]
    print(f"  [{index}/{total}] {name}: {len(turns)} turns -> {len(facts)} facts")
    return facts


async def _extract_for_topic(cases: list[dict]) -> list[dict]:
    """Extract sequentially (rate-limit safe). The resilient client in
    src.llm.client already enforces a min interval between calls."""
    for i, case in enumerate(cases, start=1):
        memories = case.get("memories", [])
        if _is_turn_shaped(memories):
            case["memories"] = await _extract_case(case, i, len(cases))
    return cases


# ── Main pipeline ────────────────────────────────────────────────────────────


def _has_extraction_keys() -> bool:
    model = (settings.extraction_model or "").lower()
    if "gemini" in model:
        return bool(os.environ.get("GOOGLE_API_KEY", "").strip())
    if "deepseek" in model:
        return bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())
    if "claude" in model or "sonnet" in model or "haiku" in model:
        return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    if "gpt" in model or "openai" in model:
        return bool(os.environ.get("OPENAI_API_KEY", "").strip())
    # Unknown model — let it try and fail loudly.
    return True


def main() -> int:
    print(f"[build] working dir: {HERE}")
    print(f"[build] extraction model: {settings.extraction_model}")

    skip_extraction = os.environ.get("SKIP_EXTRACTION", "").strip() in ("1", "true", "yes")
    if not skip_extraction and not _has_extraction_keys():
        print(
            f"\nERROR: extraction step requires an API key for model "
            f"'{settings.extraction_model}'. Set the appropriate env var "
            f"(e.g. GOOGLE_API_KEY / DEEPSEEK_API_KEY / ANTHROPIC_API_KEY) "
            f"and re-run, or set SKIP_EXTRACTION=1 to leave turn-shaped "
            f"memories as-is (eval results will be invalid).",
            file=sys.stderr,
        )
        return 2

    combined: list[dict] = []

    for script, topic in GENERATORS:
        gen_path = HERE / script
        out_path = HERE / f"{topic}.json"
        cases_path = HERE / f"{topic}_cases.json"

        print(f"\n[build] running {script}")
        runpy.run_path(str(gen_path), run_name="__main__")

        if not out_path.exists():
            print(f"  ERROR: {out_path} not produced by {script}", file=sys.stderr)
            return 1

        cases = json.loads(out_path.read_text(encoding="utf-8"))

        if not skip_extraction and any(
            _is_turn_shaped(c.get("memories", [])) for c in cases
        ):
            print(f"  extracting memories for {sum(1 for c in cases if _is_turn_shaped(c.get('memories', [])))} cases (of {len(cases)} total)...")
            cases = asyncio.run(_extract_for_topic(cases))

        cases_path.write_text(
            json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"  wrote {cases_path.name}")
        combined.extend(cases)

    total = len(combined)
    print(f"\n[build] combined dataset: {total} cases")

    all_path = HERE / f"{ALL_TOPIC}.json"
    all_cases_path = HERE / f"{ALL_TOPIC}_cases.json"
    payload = json.dumps(combined, indent=2, ensure_ascii=False)
    all_path.write_text(payload, encoding="utf-8")
    all_cases_path.write_text(payload, encoding="utf-8")
    print(f"[build] wrote {all_path.name} and {all_cases_path.name}")

    if total != 223:
        print(f"  NOTE: total cases is {total}, not 223 — verify gen scripts are current")

    return 0


if __name__ == "__main__":
    sys.exit(main())
