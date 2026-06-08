"""
Expand the 12 cross-day cases to 200 by creating variations.

Reads multiturn_crossday_llm_cases.json and creates 200 variations
by modifying pet profiles and scenario details while keeping the
structure intact.
"""
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

IN_FILE = pathlib.Path(__file__).parent / "multiturn_crossday_llm_cases.json"
OUT_FILE = pathlib.Path(__file__).parent / "multiturn_crossday_llm_200cases.json"

DOG_NAMES = ["Max", "Bella", "Charlie", "Daisy", "Rocky", "Luna", "Buddy", "Lucy", "Cooper", "Molly",
             "Rex", "Sadie", "Duke", "Zoe", "Bailey", "Chloe", "Diesel", "Maggie", "Boss", "Sophie"]
CAT_NAMES = ["Mittens", "Whiskers", "Fluffy", "Shadow", "Tiger", "Simba", "Milo", "Nala", "Felix", "Lucy",
             "Leo", "Luna", "Smokey", "Ginger", "Oliver", "Oscar", "Jasper", "Lily", "Cleo", "Oreo"]
BREED_DOGS = ["Labrador", "Golden Retriever", "German Shepherd", "Bulldog", "Poodle",
              "Beagle", "Cocker Spaniel", "Husky", "Corgi", "Dachshund"]
BREED_CATS = ["Domestic Shorthair", "Persian", "Maine Coon", "Bengal", "Siamese",
              "British Shorthair", "Scottish Fold", "Ragdoll", "Tabby", "Calico"]

def expand_cases(base_cases: list[dict], target_count: int = 200) -> list[dict]:
    """Create variations of base cases to reach target count."""
    expanded = []
    case_idx = 0

    for i in range(target_count):
        base = base_cases[case_idx % len(base_cases)]
        case = json.loads(json.dumps(base))  # Deep copy

        # Vary the pet profile
        pet = case.get("pet_profile", {})
        species = pet.get("species", "dog")

        if species == "dog":
            pet["name"] = random.choice(DOG_NAMES)
            pet["breed"] = random.choice(BREED_DOGS)
        else:
            pet["name"] = random.choice(CAT_NAMES)
            pet["breed"] = random.choice(BREED_CATS)

        # Vary age slightly
        base_age = pet.get("age_in_months", 24)
        pet["age_in_months"] = base_age + random.randint(-6, 6)

        # Vary weight
        base_weight = pet.get("weight_latest", 4.0)
        pet["weight_latest"] = round(base_weight * (0.9 + random.random() * 0.2), 1)

        # Vary gender
        pet["gender"] = random.choice(["male", "female"])

        # Create unique case name
        base_name = case.get("name", f"case_{i}")
        case["name"] = f"{base_name}_var_{i:03d}"

        expanded.append(case)

        # Cycle through base cases
        if (i + 1) % len(base_cases) == 0:
            case_idx = 0
        else:
            case_idx += 1

    return expanded


if __name__ == "__main__":
    if not IN_FILE.exists():
        print(f"ERROR: {IN_FILE} not found")
        sys.exit(1)

    print(f"Reading {IN_FILE}...")
    base_cases = json.loads(IN_FILE.read_text(encoding="utf-8"))
    print(f"Loaded {len(base_cases)} base cases")

    print("Generating 200 variations...")
    expanded = expand_cases(base_cases, 200)

    print(f"Writing {len(expanded)} cases to {OUT_FILE}...")
    OUT_FILE.write_text(json.dumps(expanded, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[OK] Done. Generated {len(expanded)} test cases")
    print(f"Run with:")
    print(f"  pytest tests/blackbox_multiturn/test_crossday_multiturn.py \\")
    print(f"    --crossday-topic=multiturn_crossday_llm_200cases \\")
    print(f"    -n 8 --model=deepseek-v4-pro")
