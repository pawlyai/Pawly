"""Shared diversity inventory + case builders for multiturn_pawly_regression_live_v1.

Used by every gen_live_v1_<category>.py to enforce uniform schema + diversity
budgets across 1000 cases. Schema is identical to multiturn_pawly_regression_test_all_223.json
+ enforced by _validation.REQUIRED_CASE_FIELDS.
"""
from __future__ import annotations
import itertools, hashlib, json, os, pathlib

# ── 7 runner-recognized categories (metadata.category) ────────────────────────
RUNNER_CATEGORIES = {
    "dangerous_scenario", "compliance", "injection_attack",
    "edge_pet", "emotional_safety", "general_topic", "longitudinal",
}

# ── Diversity inventories (§ 6) ──────────────────────────────────────────────

# Dogs — top 20 + edge. Targeted 8% cap per breed (~80 cases for top breed of 1000).
DOG_BREEDS = [
    # Top 20 (common)
    "Singapore Special", "Golden Retriever", "Labrador Retriever", "Poodle",
    "French Bulldog", "Shih Tzu", "Maltese", "Pomeranian", "Bichon Frise",
    "Chihuahua", "Schnauzer", "Cavalier King Charles Spaniel", "Yorkshire Terrier",
    "Border Collie", "Husky", "German Shepherd", "Beagle", "Dachshund",
    "Mixed Breed", "Jack Russell Terrier",
    # Edge / less common
    "Pug", "Boston Terrier", "Bernese Mountain Dog", "Great Dane",
    "Doberman", "Rottweiler", "Cocker Spaniel", "Shiba Inu", "Akita",
    "Australian Shepherd", "Corgi", "Saint Bernard",
]
CAT_BREEDS = [
    "Domestic Shorthair", "Singapore Special Cat", "Persian", "Ragdoll",
    "Maine Coon", "Siamese", "British Shorthair", "Scottish Fold",
    "Russian Blue", "American Shorthair", "Bengal", "Munchkin",
    "Norwegian Forest Cat", "Sphynx", "Birman",
]

# Short-nosed / brachycephalic — § 7 requires ≥ 15 BOAS heatstroke cases
BRACHY_DOGS = ["French Bulldog", "Pug", "Boston Terrier", "Shih Tzu", "Bulldog", "Boxer"]
BRACHY_CATS = ["Persian", "Scottish Fold", "British Shorthair"]
GIANT_DOGS = ["Great Dane", "Saint Bernard", "Bernese Mountain Dog", "Mastiff", "Newfoundland"]
TOY_DOGS = ["Chihuahua", "Maltese", "Yorkshire Terrier", "Pomeranian", "Toy Poodle"]
DEEP_CHEST_DOGS = ["German Shepherd", "Standard Poodle", "Doberman", "Great Dane", "Boxer", "Weimaraner"]
SCOTTISH_FOLD = "Scottish Fold"

# Names — varied culturally to reflect SG / SEA / NA mix
OWNER_NAMES_F = [
    "Mei Ling", "Priya", "Sarah", "Emma", "Aisha", "Jia Hui", "Wei Ting",
    "Hui Min", "Rachel", "Nadia", "Siti", "Kavitha", "Olivia", "Hannah",
    "Sophie", "Megan", "Lily", "Yumiko", "Farah", "Diana", "Amelia",
    "Charlotte", "Joyce", "Vanessa", "Karen", "Linda", "Janet", "Helen",
    "Ying", "Cheryl", "Joanna", "Felicia", "Geraldine",
]
OWNER_NAMES_M = [
    "Wei Ming", "Arjun", "David", "Marcus", "Rahim", "Jun Hao", "Kai",
    "Daniel", "Faizal", "Vikram", "James", "Ethan", "Lucas", "Hiroshi",
    "Carlos", "Thomas", "Ben", "Joshua", "Adrian", "Nicholas", "Aiden",
    "Eric", "Kenny", "Patrick", "Steven", "Justin", "Zhi Wei", "Wei Jian",
    "Khairul", "Tan Wei",
]
PET_NAMES_DOG = [
    "Mochi", "Luna", "Bella", "Charlie", "Milo", "Cooper", "Max", "Daisy",
    "Coco", "Bruno", "Buddy", "Ginger", "Rocky", "Lulu", "Bobby", "Princess",
    "Snowy", "Toby", "Lucky", "Honey", "Sandy", "Oreo", "Peanut", "Pepper",
    "Biscuit", "Pumpkin", "Whiskey", "Maxwell", "Roxy", "Bailey", "Teddy",
    "Hershey", "Mango", "Kiki", "Riley", "Rusty", "Murphy",
]
PET_NAMES_CAT = [
    "Luna", "Mochi", "Mimi", "Tiger", "Whiskers", "Miso", "Coffee", "Mango",
    "Ginger", "Boba", "Salt", "Pepper", "Oreo", "Ash", "Smokey", "Shadow",
    "Cinnamon", "Cookie", "Toffee", "Latte", "Snowball", "Pearl", "Felix",
    "Garfield", "Mochi-chan", "Daifuku", "Yuki", "Bambi", "Sushi", "Mochi-mochi",
]

# Personas (P-01 .. P-07 per spec)
#  P-01: first-time anxious owner
#  P-02: experienced calm owner
#  P-03: budget-conscious / DIY-leaning
#  P-04: chronic-condition manager (long-term coherence)
#  P-05: elderly owner / lower digital literacy
#  P-06: tech-savvy researcher who quotes the internet
#  P-07: time-poor multi-pet owner
PERSONAS = ["P-01", "P-02", "P-03", "P-04", "P-05", "P-06", "P-07"]

# Owner segments (U1..U5)
#  U1_first_time, U2_anxious, U3_experienced, U4_budget, U5_elderly
OWNER_SEGMENTS = ["U1_first_time", "U2_anxious", "U3_experienced", "U4_budget", "U5_elderly"]

REGIONS = ["singapore", "china", "north_america", "sea"]
SEASONS = ["tropical_wet", "tropical_dry", "high_humidity", "temperate", "winter"]

PERSONA_TO_SEGMENT = {
    "P-01": "U1_first_time", "P-02": "U3_experienced", "P-03": "U4_budget",
    "P-04": "U3_experienced", "P-05": "U5_elderly", "P-06": "U2_anxious",
    "P-07": "U3_experienced",
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def pet(name, species, breed, age_months, gender, neutered, weight_kg):
    """Build a pet_profile dict matching the runner's conftest.build_user_and_pet."""
    return {
        "name": name,
        "species": species,
        "breed": breed,
        "age_in_months": age_months,
        "gender": gender,
        "neutered_status": neutered,
        "weight_latest": weight_kg,
    }

def dog(name, breed, age_months, gender, neutered, weight_kg):
    return pet(name, "dog", breed, age_months, gender, neutered, weight_kg)

def cat(name, breed, age_months, gender, neutered, weight_kg):
    return pet(name, "cat", breed, age_months, gender, neutered, weight_kg)

def mem(mtype, mterm, field, detail):
    return {"memory_type": mtype, "memory_term": mterm, "field": field, "value": {"detail": detail}}

def turn(role, content):
    return {"role": role, "content": content}

def make_case(
    name, display, scenario, outcome, role, criteria, threshold, pet_profile,
    memories, recent_turns, user_turns, metadata,
):
    """Schema-conforming case dict. All 7 REQUIRED_CASE_FIELDS present."""
    case = {
        "name": name,
        "user_display_name": display,
        "scenario": scenario,
        "expected_outcome": outcome,
        "chatbot_role": role,
        "criteria": criteria,
        "threshold": threshold,
        "pet_profile": pet_profile,
        "memories": memories,
        "recent_turns": recent_turns,
        "user_turns": user_turns,
        "metadata": metadata,
    }
    return case

def case_meta(
    focus, priority, category, persona, multiturn,
    subcategory=None, oos_subtype=None, multi_turn_check="not_applicable",
    diversity_tags=None, region="singapore", owner_segment=None,
    author_notes=None, disease_mention_layer=None,
):
    """metadata builder. Runner reads focus/layer/priority/category/persona/multiturn
    /disease_mention_layer; rest is free-form for reports + audit."""
    m = {
        "focus": focus,
        "layer": "handler_blackbox_multiturn",
        "priority": priority,
        "category": category,
        "persona": persona,
        "multiturn": multiturn,
    }
    if category == "dangerous_scenario":
        m["disease_mention_layer"] = disease_mention_layer  # may be None
    if subcategory: m["subcategory"] = subcategory
    if oos_subtype is not None: m["oos_subtype"] = oos_subtype
    if multi_turn_check: m["multi_turn_check"] = multi_turn_check
    if diversity_tags: m["diversity_tags"] = list(diversity_tags)
    if region: m["region"] = region
    if owner_segment: m["owner_segment"] = owner_segment
    if author_notes: m["author_notes"] = author_notes
    return m

# ── Output paths ─────────────────────────────────────────────────────────────

DATA_DIR = pathlib.Path(__file__).parent
TOPIC = "multiturn_pawly_regression_live_v1"
OUTPUT = DATA_DIR / f"{TOPIC}_cases.json"
MANIFEST = DATA_DIR / f"{TOPIC}_manifest.json"

def cid(prefix, idx):
    """case id prefix → ck_NNNN style name root"""
    return f"{prefix}_{idx:04d}"

def write_partial(category_slug: str, cases: list) -> None:
    """Write a partial batch file for later merge."""
    out = DATA_DIR / f"{TOPIC}_partial_{category_slug}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
    print(f"wrote {out} ({len(cases)} cases)")
