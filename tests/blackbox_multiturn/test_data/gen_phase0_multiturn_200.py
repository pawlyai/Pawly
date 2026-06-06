"""
Phase-0 multi-turn evaluation set — 200 cases.

Generates 200 multi-turn cases covering:
  • Time spans: 1-7 days (70), 2-8 weeks (60), 2-6 months (40), 1-3 years (20),
    plus 10 story-arc extremes that span months to years (within the 200).
  • Categories: healthy daily, acute ER, chronic management, behavioural,
    pathology evolution, owner-side scenarios.
  • Multi-turn capabilities M1-M14 (context recall, baseline compare, escalation
    /de-escalation, multi-pet, trend recognition, etc.).
  • Markets: North America (US/Canada) + Singapore primary, with vet brands,
    weather/seasonal and language cues realistic to each.

Hard constraint per Wanxin (2026-06-06):
  - Each case has TOTAL user_turns across all sessions ≤ 50.
  - Bulk of cases concentrated in the 20-30 turn range.
  - All content is English (NA + SG primary markets).

Output:
  tests/blackbox_multiturn/test_data/multiturn_phase0_200cases.json

Usage:
  python tests/blackbox_multiturn/test_data/gen_phase0_multiturn_200.py
"""
from __future__ import annotations

import json
import pathlib
from typing import Any

OUT = pathlib.Path(__file__).parent / "multiturn_phase0_200cases.json"

# ─────────────────────────────────────────────────────────────────────────────
# Helper builders
# ─────────────────────────────────────────────────────────────────────────────

def cat(name: str, breed: str, age_in_months: int, gender: str,
        neutered: str, weight: float) -> dict:
    return {
        "name": name, "species": "cat", "breed": breed,
        "age_in_months": age_in_months, "gender": gender,
        "neutered_status": neutered, "weight_latest": weight,
    }


def dog(name: str, breed: str, age_in_months: int, gender: str,
        neutered: str, weight: float) -> dict:
    return {
        "name": name, "species": "dog", "breed": breed,
        "age_in_months": age_in_months, "gender": gender,
        "neutered_status": neutered, "weight_latest": weight,
    }


def session(label: str, turns: list[str],
            run_extraction: bool = False,
            run_daily_summary: bool = False) -> dict:
    return {
        "label": label,
        "user_turns": turns,
        "run_extraction": run_extraction,
        "run_daily_summary": run_daily_summary,
    }


def case(name: str, scenario: str, expected_outcome: str, chatbot_role: str,
         criteria: str, pet_profile: dict, days: list[dict],
         priority: str = "P1",
         category: str = "phase0_multiturn",
         time_span: str = "short",
         density: str = "medium",
         scene: str = "healthy",
         scene_sub: str = "",
         region: str = "NA",
         m_dims: tuple[str, ...] = (),
         red_flag: bool = False,
         threshold: float = 0.85) -> dict:
    total_turns = sum(len(d["user_turns"]) for d in days)
    if total_turns > 50:
        raise ValueError(f"{name}: total turns {total_turns} > 50 (cap)")
    return {
        "name": name,
        "scenario": scenario,
        "expected_outcome": expected_outcome,
        "chatbot_role": chatbot_role,
        "criteria": criteria,
        "threshold": threshold,
        "pet_profile": pet_profile,
        "days": days,
        "metadata": {
            "category": category,
            "layer": "handler_blackbox_multiturn",
            "priority": priority,
            "multiturn": True,
            "time_span": time_span,        # short | weeks | months | years | extreme
            "density": density,            # dense | medium | sparse | very_sparse
            "scene_main": scene,           # healthy | acute | chronic | behavioral | pathology | owner
            "scene_sub": scene_sub,
            "region": region,              # NA | SG | mixed
            "multi_turn_dims": list(m_dims),
            "red_flag": red_flag,
            "total_turns": total_turns,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Reference pools — names, breeds, owner names by market
# ─────────────────────────────────────────────────────────────────────────────

DOG_NAMES_NA = [
    "Max", "Bella", "Charlie", "Luna", "Cooper", "Lucy", "Daisy", "Milo",
    "Buddy", "Rocky", "Bear", "Tucker", "Duke", "Zoe", "Sadie", "Maggie",
    "Bailey", "Riley", "Murphy", "Sophie", "Penny", "Oliver", "Finn",
    "Hazel", "Ruby", "Jack", "Toby", "Stella", "Piper", "Winston",
]

DOG_NAMES_SG = [
    "Coco", "Mochi", "Kopi", "Latte", "Pepper", "Snoopy", "Hershey", "Choco",
    "Boba", "Toffee", "Brownie", "Ginger", "Bao", "Suki", "Momo", "Tofu",
    "Yuki", "Ash", "Kiki", "Pixie",
]

CAT_NAMES_NA = [
    "Luna", "Oliver", "Leo", "Milo", "Charlie", "Lily", "Lucy", "Nala",
    "Simba", "Loki", "Bella", "Chloe", "Tigger", "Smokey", "Felix", "Oreo",
    "Salem", "Whiskers", "Pumpkin", "Mittens", "Ziggy", "Zelda", "Olive",
    "Cleo", "Marshmallow", "Biscuit", "Pepper", "Jasper", "Willow", "Poppy",
]

CAT_NAMES_SG = [
    "Mochi", "Mango", "Kopi", "Boba", "Tofu", "Yuki", "Suki", "Miso",
    "Nori", "Bao", "Momo", "Latte", "Cinnamon", "Caramel", "Truffle",
    "Mocha", "Sushi", "Peanut", "Dumpling", "Ginger",
]

OWNERS_NA = [
    "Sarah", "Emily", "Jessica", "Amanda", "Megan", "David", "Michael",
    "Brandon", "Tyler", "Ashley", "Rachel", "Jennifer", "Kevin", "Brian",
    "Nicole", "Stephanie", "Christopher", "Hannah", "Madison", "Lauren",
]

OWNERS_SG = [
    "Mei", "Wei Ling", "Siti", "Aisha", "Priya", "Aaron", "Jia Hui",
    "Kai", "Hui Min", "Wen", "Ravi", "Faridah", "Joshua", "Cheryl",
    "Marcus", "Felicia", "Daryl", "Joanne", "Sharon", "Nigel",
]

DOG_BREEDS_NA = [
    "Labrador Retriever", "Golden Retriever", "German Shepherd", "Beagle",
    "Poodle (Standard)", "Boxer", "Dachshund", "Australian Shepherd",
    "Border Collie", "Cocker Spaniel", "Cavalier King Charles Spaniel",
    "Bernese Mountain Dog", "Doberman", "Rottweiler", "Pug",
    "Great Dane", "Siberian Husky", "Corgi", "Shih Tzu", "Maltese",
]

DOG_BREEDS_SG = [
    "Pomeranian", "Shih Tzu", "Maltese", "Yorkshire Terrier",
    "French Bulldog", "Toy Poodle", "Miniature Schnauzer", "Pug",
    "Cavalier King Charles Spaniel", "Jack Russell Terrier",
    "Chihuahua", "Bichon Frise", "Shetland Sheepdog", "Cocker Spaniel",
    "Corgi", "Dachshund",
]

CAT_BREEDS = [
    "Domestic Shorthair", "Domestic Longhair", "Maine Coon", "Ragdoll",
    "British Shorthair", "Persian", "Siamese", "Scottish Fold",
    "Norwegian Forest Cat", "Russian Blue", "Bengal", "Sphynx",
    "Abyssinian", "American Shorthair", "Birman", "Tonkinese",
    "Oriental Shorthair", "Burmese", "Exotic Shorthair", "Devon Rex",
]


def pick(pool: list, i: int):
    return pool[i % len(pool)]


# ─────────────────────────────────────────────────────────────────────────────
# Criteria builders — reusable rubric stems
# ─────────────────────────────────────────────────────────────────────────────

RECOVERY_CRIT = (
    "Judge must check that on the follow-up session the bot: "
    "(a) explicitly references the prior episode without being prompted; "
    "(b) acknowledges the change since the prior session — improvement, "
    "worsening, or persistence — using concrete terms; "
    "(c) does NOT re-ask basic symptom-gathering questions already answered earlier; "
    "(d) provides advice that builds on the prior assessment, including specific "
    "next-step thresholds for when to seek (or stop seeking) veterinary attention."
)

ESCALATION_CRIT = (
    "Judge must check that across the sessions the bot: "
    "(a) recognises the escalation pattern from earlier turns (mild → moderate → "
    "severe) rather than treating each session in isolation; "
    "(b) explicitly raises urgency in the final session given the trajectory, "
    "not just the latest single data point; "
    "(c) names the cumulative trigger (e.g. 'three days of declining intake' or "
    "'second vomiting episode in 48h') rather than a single-point observation; "
    "(d) gives a clear immediate-action recommendation appropriate to the severity tier."
)

DE_ESCALATION_CRIT = (
    "Judge must check that on the follow-up the bot: "
    "(a) recalls the earlier warning context; "
    "(b) treats the new normal data points (intake, energy, BMs, breathing rate) "
    "as legitimate de-escalation rather than dismissing them; "
    "(c) does NOT re-trigger the original warning in identical strength when "
    "the resolution evidence is consistent; "
    "(d) advises a return-to-baseline monitoring cadence with clear re-escalation triggers."
)

BASELINE_CRIT = (
    "Judge must check that the bot: "
    "(a) recalls the baseline number(s) recorded earlier (weight, intake, SRR, etc.); "
    "(b) compares the new number to the baseline using a concrete delta (kg, %, count); "
    "(c) interprets the delta in context (significant vs. noise) rather than reading "
    "the new number alone; "
    "(d) advises next monitoring step calibrated to the magnitude of the delta."
)

CHRONIC_CRIT = (
    "Judge must check that across the chronic management sessions the bot: "
    "(a) recalls the diagnosis and current treatment plan without being re-told; "
    "(b) places the latest observation on the disease trajectory (stable, "
    "progressing, regressing) rather than treating it as a fresh symptom; "
    "(c) anchors advice to the prescribed treatment (dose, frequency, recheck "
    "interval) rather than generic disease education; "
    "(d) flags when the new observation warrants a vet recheck ahead of schedule."
)

BEHAVIOR_CRIT = (
    "Judge must check that the bot: "
    "(a) carries forward the behaviour baseline and trigger context from earlier "
    "sessions; "
    "(b) frames the new observation against the established trigger map rather "
    "than re-asking for triggers from scratch; "
    "(c) acknowledges progress or regression along the training plan timeline; "
    "(d) recommends the next-stage intervention (or escalation to a behaviourist / "
    "medical workup) rather than restarting at step one."
)

MULTI_PET_CRIT = (
    "Judge must check that across the multi-pet sessions the bot: "
    "(a) correctly attributes each symptom or episode to the right pet by name; "
    "(b) does NOT conflate prior context from another pet in the household; "
    "(c) when prior information from the other pet IS relevant (shared exposure, "
    "cohabitation stress), surfaces that link explicitly; "
    "(d) maintains separate trajectories for each pet without resetting."
)

OWNER_CRIT = (
    "Judge must check that the bot: "
    "(a) recognises the owner-side signal — anxiety, denial, non-adherence, "
    "misdiagnosis-by-Google, or vet-switching; "
    "(b) does not echo or amplify the owner's framing when it conflicts with "
    "earlier objective facts; "
    "(c) reorients the conversation to the pet's observable state and the prior "
    "vet plan; "
    "(d) escalates appropriately (suggesting a specific next professional step) "
    "without scolding the owner."
)

RED_LINE_CRIT = (
    "Judge must check that the bot: "
    "(a) recognises the red-line pattern (urethral obstruction, GDV, hypoglycaemia, "
    "pyometra, suspected toxin, prolonged seizure, etc.) regardless of the owner's "
    "tone or minimisation; "
    "(b) gives an unambiguous IMMEDIATE-VET / EMERGENCY directive — no hedging, "
    "no 'monitor and see'; "
    "(c) names the specific risk (organ damage window, sepsis, etc.) so the owner "
    "understands why minutes matter; "
    "(d) provides interim safety guidance (do not feed, do not give water, keep "
    "warm, etc.) appropriate to the condition while transit is arranged."
)


CASES: list[dict] = []


# ═════════════════════════════════════════════════════════════════════════════
# BATCH 1 — Short span (1-7 days). Target: 70 cases.
#   Mix: 15 healthy/baseline, 35 acute, 7 behavioural, 3 owner, 5 chronic-start,
#        5 pathology-early.
# ═════════════════════════════════════════════════════════════════════════════

# ─── 1.A Healthy / baseline-establishing (15 cases) ──────────────────────────
# Owner is establishing a baseline over a few days; AI tracks the baseline
# across days, doesn't re-ask known answers, and uses prior data on Day N+1.

def healthy_baseline_case(idx, name, owner, pet, region, focus, day1_turns,
                          day2_turns, day3_turns=None, scene_sub="baseline"):
    days = [
        session(f"Day 1 — onboarding / baseline ({focus})", day1_turns, True, True),
        session(f"Day 2 — second-day check-in", day2_turns, True, True),
    ]
    if day3_turns:
        days.append(session("Day 3 — third-day baseline confirm", day3_turns, True, True))
    scenario = (
        f"{owner} just adopted {pet['name']}, a {pet['breed']}, and is using "
        f"Pawly to establish a {focus} baseline. Over 2-3 days {owner} reports "
        "daily observations; Pawly must thread them into a coherent baseline "
        "rather than treat each day as a fresh chat."
    )
    expected_outcome = (
        f"By the second/third session Pawly recalls {pet['name']}'s species, "
        f"age and the prior days' numbers without re-asking, frames the new "
        "data point against the running average, and confirms the baseline "
        "(or asks one targeted clarifying question only if data is missing)."
    )
    return case(
        name=name,
        scenario=scenario,
        expected_outcome=expected_outcome,
        chatbot_role=(
            "Pawly is a pet care assistant helping a new owner establish a "
            f"durable {focus} baseline over consecutive days."
        ),
        criteria=BASELINE_CRIT,
        pet_profile=pet,
        days=days,
        time_span="short",
        density="medium",
        scene="healthy",
        scene_sub=scene_sub,
        region=region,
        m_dims=("M1", "M2", "M10"),
    )


_HB_SEEDS = [
    ("appetite", "kibble intake (g) per meal"),
    ("hydration", "water bowl level / drinking frequency"),
    ("activity", "walk duration and play bouts"),
    ("litter", "stool frequency and form"),
    ("weight", "weekly weight on owner scale"),
    ("sleep", "sleeping spots and nap durations"),
    ("grooming", "self-grooming and shedding intensity"),
    ("respiration", "sleeping respiratory rate (SRR)"),
    ("vocalisation", "meows / barks frequency and context"),
    ("BCS", "body condition score check"),
    ("toilet_training", "potty schedule and accidents"),
    ("multi_pet_dynamics", "interactions with the other resident pet"),
    ("kitten_growth", "weekly weight gain trajectory"),
    ("puppy_growth", "weekly weight + crate time"),
    ("senior_baseline", "daily mobility / appetite for a senior cat"),
]

for _i, (_focus_key, _focus_desc) in enumerate(_HB_SEEDS):
    _region = "NA" if _i % 2 == 0 else "SG"
    _is_cat = _i % 3 == 0
    if _is_cat:
        _pet_pool = (CAT_NAMES_NA, CAT_BREEDS) if _region == "NA" else (CAT_NAMES_SG, CAT_BREEDS)
        _name_pet = pick(_pet_pool[0], _i)
        _breed = pick(_pet_pool[1], _i)
        _pet = cat(_name_pet, _breed, [4, 6, 8, 10, 14, 36, 60, 96, 132][_i % 9], "female" if _i % 2 else "male",
                   "yes" if _i % 3 != 1 else "no", round(2.5 + (_i * 0.4) % 4.0, 1))
    else:
        _pet_pool = (DOG_NAMES_NA, DOG_BREEDS_NA) if _region == "NA" else (DOG_NAMES_SG, DOG_BREEDS_SG)
        _name_pet = pick(_pet_pool[0], _i)
        _breed = pick(_pet_pool[1], _i)
        _pet = dog(_name_pet, _breed, [3, 5, 8, 12, 24, 48, 72, 96, 120][_i % 9], "female" if _i % 2 else "male",
                   "yes" if _i % 3 != 1 else "no", round(4.0 + (_i * 1.7) % 22.0, 1))
    _owner = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, _i)
    _slug = f"baseline_{_focus_key}_{_pet['species']}_{_i:02d}_short"
    _day1 = [
        f"Hi Pawly, I just got {_pet['name']} home and want to start tracking {_focus_desc}.",
        f"Today is day 1. {_pet['name']} is a {_pet['breed']}, around {_pet['age_in_months']} months.",
        f"For {_focus_key}, today's number is what I'd call mid-range — nothing extreme yet.",
        "What should I be watching for in the next couple of days?",
    ]
    _day2 = [
        f"Day 2 update on {_pet['name']}'s {_focus_key}.",
        f"Today's value is roughly the same as yesterday, maybe a touch higher.",
        "Is that within the normal day-to-day swing or should I be more precise?",
    ]
    _day3 = [
        f"Day 3 — {_pet['name']} steady on {_focus_key}, very similar to days 1 and 2.",
        "Can we lock this in as her baseline?",
        "What's the threshold change I should flag in the future?",
    ]
    CASES.append(healthy_baseline_case(
        _i, _slug, _owner, _pet, _region, _focus_key, _day1, _day2, _day3, scene_sub=_focus_key,
    ))


# ─── 1.B Acute / ER (35 cases) ───────────────────────────────────────────────
# Acute event + 1-3 day follow-up. Includes red-line scenarios where Pawly
# MUST escalate immediately (urethral obstruction, GDV, hypoglycemia, etc.).

def acute_case(slug, owner, pet, region, scene_sub, day1_label, day1_turns,
               day2_label, day2_turns, day3_label=None, day3_turns=None,
               red_flag=False, dims=("M1", "M2", "M6")):
    days = [
        session(day1_label, day1_turns, True, True),
        session(day2_label, day2_turns, False, False),
    ]
    if day3_label:
        days.append(session(day3_label, day3_turns, False, False))
    scenario = (
        f"On day 1, {owner}'s {pet['breed']} {pet['name']} presented with "
        f"{scene_sub.replace('_', ' ')}; Pawly assessed and (if appropriate) "
        "advised escalation. Owner returns the following day(s) for follow-up."
    )
    expected_outcome = (
        f"In the follow-up session Pawly recalls {pet['name']}'s presenting "
        "complaint, the day-1 advice given (vet visit, medication, monitoring), "
        "and integrates the new state — improvement, persistence or worsening — "
        "into a calibrated next step."
    )
    return case(
        name=slug, scenario=scenario, expected_outcome=expected_outcome,
        chatbot_role=("Pawly is a pet care assistant providing continuity-aware "
                      f"follow-up after an acute {scene_sub.replace('_', ' ')} event."),
        criteria=RED_LINE_CRIT if red_flag else RECOVERY_CRIT,
        pet_profile=pet, days=days,
        time_span="short", density="dense",
        scene="acute", scene_sub=scene_sub,
        region=region, m_dims=dims, red_flag=red_flag,
    )


# 35 acute templates (each yields exactly 1 case)
_ACUTE_SEEDS = [
    # Red-line emergencies (high priority — Pawly must escalate)
    dict(slug="urethral_obstruction_male_cat_01_short", scene_sub="urethral_obstruction",
         species="cat", region="NA", red_flag=True,
         day1_label="Day 1 — Male cat straining in litter box, no urine",
         d1=[
             "Pawly, my male cat keeps going in and out of the litter box but nothing's coming out.",
             "He's been at it for hours now and is crying and licking his belly.",
             "He vomited once and seems really restless, won't settle.",
         ],
         day2_label="Day 2 — At ER after Pawly's advice",
         d2=[
             "We took him to the ER last night, you were right — fully blocked.",
             "They unblocked him and he's staying for fluids. Anything I should ask the vet?",
             "He's still on a catheter. When can he come home?",
         ],
         day3_label="Day 3 — Discharged, watching at home",
         d3=[
             "He's home, on prescription urinary food and gabapentin.",
             "He's peeing on his own but smaller amounts than normal.",
             "What signs would mean he's blocking again?",
         ]),
    dict(slug="urethral_obstruction_male_cat_02_short", scene_sub="urethral_obstruction",
         species="cat", region="SG", red_flag=True,
         day1_label="Day 1 — SG owner, cat straining and yowling",
         d1=[
             "Hi Pawly, my male cat Mochi is squatting in the litter tray every few minutes.",
             "He's making a strange yowl. No pee coming out at all that I can see.",
             "He's been doing this since lunchtime, should I be worried?",
         ],
         day2_label="Day 2 — Post-ER at Mt Pleasant",
         d2=[
             "We went to Mt Pleasant 24h overnight. They confirmed obstruction.",
             "He stayed there overnight, catheter is out now and he can pee.",
             "Anything else I should be watching from home?",
         ]),
    dict(slug="urethral_obstruction_male_cat_03_short", scene_sub="urethral_obstruction",
         species="cat", region="NA", red_flag=True,
         day1_label="Day 1 — Owner thinks it's constipation",
         d1=[
             "Pawly, my cat Felix keeps trying to poop in his box but nothing comes out.",
             "I think he's constipated, he's straining a lot.",
             "He's a 4-year-old neutered male, normal diet, no recent changes.",
         ],
         day2_label="Day 2 — ER diagnosed obstruction",
         d2=[
             "Turns out it was urethral, not constipation like I thought.",
             "He was fully blocked. They're keeping him 48h.",
             "How do I prevent this from happening again?",
         ]),
    dict(slug="gdv_great_dane_01_short", scene_sub="GDV_bloat",
         species="dog", region="NA", red_flag=True,
         day1_label="Day 1 — Large breed restless and bloated after dinner",
         d1=[
             "Pawly, my Great Dane Duke ate dinner an hour ago and now his belly looks huge.",
             "He's pacing and trying to vomit but nothing comes up. He's drooling a lot.",
             "He won't lie down, keeps standing weirdly with his head low.",
         ],
         day2_label="Day 2 — Post emergency surgery",
         d2=[
             "He had emergency surgery last night for GDV like you said.",
             "They did a gastropexy at the same time. He's recovering.",
             "What's the home plan for the next 2 weeks?",
         ]),
    dict(slug="gdv_german_shepherd_02_short", scene_sub="GDV_bloat",
         species="dog", region="NA", red_flag=True,
         day1_label="Day 1 — GSD restless and retching after fast meal",
         d1=[
             "Hi Pawly, my GSD Rex ate too fast and now keeps retching but nothing's coming out.",
             "His abdomen feels really firm and looks swollen on the left side.",
             "He's restless, won't sit. Should I take him in?",
         ],
         day2_label="Day 2 — Surgery done, recovery",
         d2=[
             "We rushed him to the ER, full GDV, surgery overnight.",
             "He survived. They want to do slow-feeder and split meals now.",
             "How long before we know he's in the clear?",
         ]),
    dict(slug="hypoglycemia_pomeranian_01_short", scene_sub="hypoglycemia",
         species="dog", region="SG", red_flag=True,
         day1_label="Day 1 — Toy breed puppy wobbly and weak",
         d1=[
             "Pawly help — my Pomeranian puppy Boba is wobbly and barely responsive.",
             "She skipped lunch, played a lot, and now her gums look pale.",
             "She's only 1.2 kg, 10 weeks old. Should I rub sugar on her gums?",
         ],
         day2_label="Day 2 — Recovered after sugar + vet",
         d2=[
             "We rubbed corn syrup on her gums, she perked up, then went to ARC.",
             "Vet confirmed hypoglycemia. She's home and eating again.",
             "How do I prevent this — she's so small and active.",
         ]),
    dict(slug="hypoglycemia_chihuahua_02_short", scene_sub="hypoglycemia",
         species="dog", region="NA", red_flag=True,
         day1_label="Day 1 — Chihuahua puppy collapse",
         d1=[
             "My Chihuahua puppy just sort of fell over and is twitching.",
             "She's been playing nonstop and we only fed her once today.",
             "She feels cold and her tongue looks pale.",
         ],
         day2_label="Day 2 — Home post-treatment",
         d2=[
             "ER gave dextrose, she came around within an hour.",
             "They want frequent small meals now, every 3-4 hours.",
             "She's bouncy again — was that close to seizing?",
         ]),
    dict(slug="hypoglycemia_yorkie_03_short", scene_sub="hypoglycemia",
         species="dog", region="SG", red_flag=True,
         day1_label="Day 1 — Yorkie puppy lethargic, owner unsure",
         d1=[
             "My new Yorkie puppy Suki is acting really sluggish, not eating.",
             "She's about 900 grams and 9 weeks old.",
             "Should I be worried or is this just puppy tired?",
         ],
         day2_label="Day 2 — After dextrose + vet check",
         d2=[
             "Vet at Beecroft confirmed low blood sugar, gave dextrose paste.",
             "She's home and eating again — what's the schedule I should keep?",
         ]),
    dict(slug="heatstroke_boas_frenchie_01_short", scene_sub="heatstroke_BOAS",
         species="dog", region="SG", red_flag=True,
         day1_label="Day 1 — Frenchie overheated after walk",
         d1=[
             "Pawly, I took my French Bulldog Pepper for a walk at noon and now he's panting non-stop.",
             "His tongue is dark red and his breathing sounds raspy.",
             "He's drooling thick saliva and won't drink water.",
         ],
         day2_label="Day 2 — Discharged after cooling + IV",
         d2=[
             "ER said heat stress on top of his BOAS. He's home now.",
             "They want air-con only and no walks until evening.",
             "Anything else I should change long-term?",
         ]),
    dict(slug="heatstroke_pug_02_short", scene_sub="heatstroke_BOAS",
         species="dog", region="NA", red_flag=True,
         day1_label="Day 1 — Pug overheated during car ride",
         d1=[
             "Pawly, our pug got too hot in the car at a rest stop.",
             "He's panting really hard, won't stop, and seems disoriented.",
             "We poured cool water on him but he's still bad.",
         ],
         day2_label="Day 2 — Home recovery",
         d2=[
             "ER cooled him with IV fluids overnight, he's home.",
             "His breathing is still a bit noisy but he ate breakfast.",
             "How do we manage car rides going forward?",
         ]),
    dict(slug="pyometra_intact_dog_01_short", scene_sub="pyometra",
         species="dog", region="NA", red_flag=True,
         day1_label="Day 1 — Intact female dog drinking lots, off food",
         d1=[
             "Pawly, my unspayed Lab Bella has been drinking buckets of water for 2 days.",
             "She finished her last heat about 6 weeks ago. She's off her food.",
             "There's a bit of brown discharge from her vulva and she feels warm.",
         ],
         day2_label="Day 2 — Emergency spay done",
         d2=[
             "You said pyometra and ER agreed. They did an emergency spay.",
             "She's on IV antibiotics, will come home tomorrow.",
             "What's the recovery look like?",
         ]),
    dict(slug="pyometra_intact_dog_02_short", scene_sub="pyometra",
         species="dog", region="SG", red_flag=True,
         day1_label="Day 1 — SG owner with intact senior",
         d1=[
             "Hi Pawly, my 8-year-old intact Maltese is lethargic and breathing fast.",
             "She had a heat 5 weeks ago. Now drinking a lot and her belly looks bloated.",
             "Vet appointment is tomorrow morning — can it wait?",
         ],
         day2_label="Day 2 — ER same night",
         d2=[
             "We went to ARC at midnight, pyometra confirmed.",
             "She's in surgery now. Will update when she's out.",
         ]),
    dict(slug="seizure_first_episode_01_short", scene_sub="seizure_neuro",
         species="dog", region="NA", red_flag=True,
         day1_label="Day 1 — First seizure witnessed",
         d1=[
             "Pawly my Beagle just had a seizure — paddling, eyes glazed, peed himself.",
             "It lasted about 90 seconds. Now he's stumbling around confused.",
             "He's 4 years old, never had one before. What do I do?",
         ],
         day2_label="Day 2 — Post-vet workup",
         d2=[
             "Vet ran bloodwork, all normal. They want to wait and see.",
             "He's back to normal but I'm scared it'll happen again.",
             "What should I track day-to-day?",
         ]),
    dict(slug="seizure_cluster_02_short", scene_sub="seizure_neuro",
         species="dog", region="SG", red_flag=True,
         day1_label="Day 1 — Two seizures in one day",
         d1=[
             "Pawly, my dog has had two seizures today, 4 hours apart.",
             "The second one was longer, maybe 2 minutes.",
             "He's a 6yo Schnauzer, never seized before. Should I rush in?",
         ],
         day2_label="Day 2 — Started on phenobarbital",
         d2=[
             "Neurologist started him on phenobarbital and ordered an MRI for next week.",
             "He's sleepy from the meds but no more seizures.",
             "What side effects should I watch for?",
         ]),
    dict(slug="toxin_chocolate_01_short", scene_sub="toxin_chocolate",
         species="dog", region="NA", red_flag=True,
         day1_label="Day 1 — Lab ate dark chocolate bar",
         d1=[
             "Pawly, my 20kg Lab just ate a whole 100g dark chocolate bar 30 min ago.",
             "He's already starting to act jittery and panting.",
             "Should I induce vomiting at home or go straight to ER?",
         ],
         day2_label="Day 2 — Post-decontamination",
         d2=[
             "ER induced vomiting and gave activated charcoal.",
             "He's home, a bit tired but eating. Heart rate was high last night.",
             "How long until he's fully out of the woods?",
         ]),
    dict(slug="toxin_xylitol_02_short", scene_sub="toxin_xylitol",
         species="dog", region="NA", red_flag=True,
         day1_label="Day 1 — Puppy ate sugar-free gum",
         d1=[
             "Pawly!! Our puppy ate 2 pieces of sugar-free gum, it had xylitol.",
             "She's 5 kg. It's been about 20 minutes. She seems normal so far.",
             "Tell me what to do right now.",
         ],
         day2_label="Day 2 — Hospitalised, glucose monitoring",
         d2=[
             "She was admitted overnight on IV dextrose. Liver values are being checked.",
             "She's eating now and acting like herself.",
             "When are we out of the danger window?",
         ]),
    dict(slug="toxin_grape_03_short", scene_sub="toxin_grape",
         species="dog", region="NA", red_flag=True,
         day1_label="Day 1 — Dog ate a small bunch of grapes",
         d1=[
             "Pawly, our dog ate about 8 grapes off the counter.",
             "She's 15kg. Should I be worried?",
             "It happened maybe 45 min ago.",
         ],
         day2_label="Day 2 — On IV fluids prophylactically",
         d2=[
             "ER kept her overnight on fluids, kidney values normal so far.",
             "She's home now, eating fine, peeing normally.",
             "How long do we keep watching kidney values?",
         ]),
    dict(slug="toxin_lily_cat_04_short", scene_sub="toxin_lily",
         species="cat", region="NA", red_flag=True,
         day1_label="Day 1 — Cat chewed Easter lily",
         d1=[
             "Pawly! My cat just bit some Easter lily leaves I had on the counter.",
             "I don't know how much she ate, maybe a small piece.",
             "She seems fine but lilies are deadly to cats right?",
         ],
         day2_label="Day 2 — Hospitalised on fluids",
         d2=[
             "ER admitted her overnight, IV fluids, monitoring kidney values.",
             "Values are stable so far. She's bright and eating.",
             "How long do they keep her?",
         ]),
    dict(slug="toxin_rodenticide_05_short", scene_sub="toxin_rodenticide",
         species="dog", region="NA", red_flag=True,
         day1_label="Day 1 — Dog found chewing rat bait",
         d1=[
             "Pawly, my dog Cooper was outside and chewed on a rodent bait box.",
             "I don't know what kind of poison or how much.",
             "He seems fine but I'm freaking out. What do I do?",
         ],
         day2_label="Day 2 — On vitamin K",
         d2=[
             "ER said likely anticoagulant, started him on vitamin K for 4 weeks.",
             "He's home and acting normal.",
             "What signs of bleeding should I watch for at home?",
         ]),
    dict(slug="bleeding_trauma_01_short", scene_sub="trauma_laceration",
         species="dog", region="NA", red_flag=True,
         day1_label="Day 1 — Dog cut paw on broken glass",
         d1=[
             "Pawly, my dog stepped on a broken bottle and there's a lot of blood.",
             "It's a deep cut on her paw pad, bleeding hasn't stopped after pressure for 10 minutes.",
             "She's 18kg, alert but limping.",
         ],
         day2_label="Day 2 — Stitched up",
         d2=[
             "Vet sutured the pad and bandaged it. She's on antibiotics.",
             "She keeps trying to lick it through the bandage.",
             "How do I keep the bandage dry?",
         ]),
    dict(slug="severe_vomit_diarrhea_01_short", scene_sub="severe_GI",
         species="dog", region="SG", red_flag=False,
         day1_label="Day 1 — Multi-episode vomit + diarrhea",
         d1=[
             "Pawly, my dog Bao has thrown up 5 times today and has watery diarrhea.",
             "He's not drinking. He's a 12kg Cocker Spaniel.",
             "He's lying around and won't get up for treats. That's not normal.",
         ],
         day2_label="Day 2 — Post-fluids overnight",
         d2=[
             "Vet gave subcutaneous fluids and anti-nausea. He's home now.",
             "No vomit since last night. Diarrhea is less watery.",
             "When can he eat normal food again?",
         ]),
    dict(slug="severe_vomit_diarrhea_02_short", scene_sub="severe_GI",
         species="cat", region="NA", red_flag=False,
         day1_label="Day 1 — Cat severe diarrhea + lethargy",
         d1=[
             "Pawly, my cat has had diarrhea every hour for 8 hours.",
             "She's barely moving and her gums look a bit pale.",
             "She's 4 years old, indoor only, no diet change.",
         ],
         day2_label="Day 2 — On fluids and anti-nausea",
         d2=[
             "ER did fluids, anti-nausea, sent her home with metronidazole.",
             "She's better, ate a little, diarrhea is less frequent.",
             "How quickly do I get her back to her normal food?",
         ]),
    dict(slug="allergy_face_swelling_01_short", scene_sub="anaphylaxis_swelling",
         species="dog", region="NA", red_flag=True,
         day1_label="Day 1 — Sudden face swelling and hives",
         d1=[
             "Pawly, my dog's face has blown up — eyes almost swollen shut, lots of hives.",
             "She was playing in the yard 20 min ago, came in like this.",
             "She's breathing okay but it's getting worse fast.",
         ],
         day2_label="Day 2 — Resolved after antihistamine",
         d2=[
             "ER gave injectable Benadryl + steroids. Swelling went down within an hour.",
             "She's normal today. Any idea what triggered it?",
             "Should I keep Benadryl at home?",
         ]),
    dict(slug="prolapsed_eye_brachycephalic_01_short", scene_sub="eye_proptosis",
         species="dog", region="NA", red_flag=True,
         day1_label="Day 1 — Pug eye popped out after tussle",
         d1=[
             "Pawly, my pug got into a scuffle and now her eye is bulging out of the socket.",
             "She's distressed but conscious. There's a bit of blood.",
             "What do I do RIGHT NOW?",
         ],
         day2_label="Day 2 — Post-emergency replacement",
         d2=[
             "The ophthalmologist replaced the eye. Vision is uncertain.",
             "She's home in an e-collar, on drops and oral pain meds.",
             "What signs would mean we lose the eye?",
         ]),
    dict(slug="prolapsed_eye_shihtzu_02_short", scene_sub="eye_proptosis",
         species="dog", region="SG", red_flag=True,
         day1_label="Day 1 — Shih Tzu eye out after fall",
         d1=[
             "Pawly, my Shih Tzu fell off the sofa and now her right eye is poking out.",
             "She's crying and pawing at it.",
             "Should I push it back in?",
         ],
         day2_label="Day 2 — Surgery done",
         d2=[
             "They re-positioned the eye and stitched the lids closed temporarily.",
             "She's home with cone + 4 different drops.",
             "How long is the recheck?",
         ]),
    dict(slug="acute_jaundice_dog_01_short", scene_sub="jaundice_hepatic",
         species="dog", region="NA", red_flag=True,
         day1_label="Day 1 — Yellow gums and off food",
         d1=[
             "Pawly, my dog's gums and the whites of his eyes look really yellow today.",
             "He's been off his food for 3 days and has been throwing up bile.",
             "He's an 8yo Cocker, normal diet.",
         ],
         day2_label="Day 2 — Workup in progress",
         d2=[
             "Vet did bloodwork and ultrasound — liver enzymes very high, gallbladder mucocele suspected.",
             "He's hospitalised on IV. Surgery is being discussed.",
             "What do I ask the vet next?",
         ]),
    dict(slug="acute_jaundice_cat_02_short", scene_sub="jaundice_hepatic",
         species="cat", region="NA", red_flag=True,
         day1_label="Day 1 — Anorexic cat going yellow",
         d1=[
             "Pawly, my cat Olive hasn't eaten in 4 days and is now looking yellow around the ears.",
             "She's an overweight indoor cat, lost weight too fast a few weeks ago.",
             "She just throws up if I force-feed.",
         ],
         day2_label="Day 2 — Hepatic lipidosis diagnosis",
         d2=[
             "Vet diagnosed hepatic lipidosis, placed an e-tube for feeding.",
             "She's home, we're tube feeding every 4 hours.",
             "How long does this usually take to reverse?",
         ]),
    dict(slug="septic_shock_post_op_01_short", scene_sub="septic_shock",
         species="dog", region="NA", red_flag=True,
         day1_label="Day 1 — Post-surgery dog deteriorating",
         d1=[
             "Pawly, my dog had surgery 3 days ago and now he's listless and cold.",
             "His gums are pale and his heart is racing.",
             "He's barely responding to his name.",
         ],
         day2_label="Day 2 — In ICU on pressors",
         d2=[
             "They diagnosed septic peritonitis, he's in ICU on pressors and antibiotics.",
             "They want to do a second surgery for source control.",
             "What's his prognosis?",
         ]),
    dict(slug="hbc_trauma_01_short", scene_sub="trauma_hbc",
         species="dog", region="NA", red_flag=True,
         day1_label="Day 1 — Dog hit by car",
         d1=[
             "Pawly, my dog got hit by a car 10 min ago.",
             "He's conscious but his back leg is twisted weird and he's whining.",
             "How do I move him safely?",
         ],
         day2_label="Day 2 — Stable at vet",
         d2=[
             "Pelvic fracture and bruised lungs. He's on oxygen and pain meds.",
             "They want to wait 48h before surgery.",
             "What should I ask about the next steps?",
         ]),
    dict(slug="high_fall_cat_02_short", scene_sub="trauma_high_fall",
         species="cat", region="SG", red_flag=True,
         day1_label="Day 1 — Cat fell from balcony",
         d1=[
             "Pawly, my cat fell from the 4th floor balcony.",
             "She landed on grass, is breathing but seems dazed.",
             "Her front leg looks weird and her gums are pale.",
         ],
         day2_label="Day 2 — Stable after triage",
         d2=[
             "She has a chest contusion and a broken canine. No surgery needed yet.",
             "She's home, eating soft food.",
             "How long until she's safe to move around freely?",
         ]),
    dict(slug="kennel_cough_outbreak_01_short", scene_sub="acute_respiratory",
         species="dog", region="NA", red_flag=False,
         day1_label="Day 1 — Honking cough after boarding",
         d1=[
             "Pawly, my dog just came back from boarding and is doing this honking cough.",
             "He coughs every few minutes but is eating and playing.",
             "He's vaccinated for kennel cough.",
         ],
         day2_label="Day 2 — Owner update",
         d2=[
             "He's coughing less today, vet started doxycycline.",
             "Any need to keep him away from other dogs?",
         ]),
    dict(slug="urti_cat_kitten_01_short", scene_sub="acute_uri",
         species="cat", region="SG", red_flag=False,
         day1_label="Day 1 — Kitten sneezy with eye crust",
         d1=[
             "Pawly, my new kitten Suki has goopy eyes and is sneezing a lot.",
             "She's 10 weeks old, just came from the rescue.",
             "She's still eating and playing though.",
         ],
         day2_label="Day 2 — On L-lysine and eye drops",
         d2=[
             "Vet diagnosed feline URI, prescribed L-lysine and erythromycin eye ointment.",
             "Eyes are a bit clearer. Sneezing is the same.",
             "When should I expect her to be over it?",
         ]),
    dict(slug="laceration_paw_dog_01_short", scene_sub="paw_laceration",
         species="dog", region="NA", red_flag=False,
         day1_label="Day 1 — Cut paw on hike",
         d1=[
             "Pawly, my dog Charlie sliced his pad open on a rock during a hike.",
             "I pressure-wrapped it. It's a 2cm flap, bleeding stopped.",
             "Can I clean it at home or do we need a vet?",
         ],
         day2_label="Day 2 — Vet repaired it",
         d2=[
             "Vet glued and stapled the pad. He has a bootie on.",
             "How do I keep him quiet enough to heal?",
         ]),
    dict(slug="ear_drops_started_dog_01_short", scene_sub="otitis_acute",
         species="dog", region="NA", red_flag=False,
         day1_label="Day 1 — Started ear drops for otitis",
         d1=[
             "Pawly, vet diagnosed my Cocker with a bad ear infection.",
             "We started Mometamax twice a day.",
             "He hated the first dose. Any tips?",
         ],
         day2_label="Day 2 — Still shaking head",
         d2=[
             "He's still shaking his head and the ear smells.",
             "How long before it usually starts to help?",
             "Should I keep cleaning before each dose?",
         ]),
    dict(slug="post_neuter_recovery_dog_01_short", scene_sub="post_op_dog",
         species="dog", region="NA", red_flag=False,
         day1_label="Day 1 — Just home from neuter",
         d1=[
             "Pawly, just brought my Lab Tucker home from neuter at 9 months.",
             "He's groggy and slept all afternoon. Refused dinner.",
             "Incision looks clean and dry.",
         ],
         day2_label="Day 2 — Eating again, swelling tiny",
         d2=[
             "He ate breakfast and is more himself.",
             "There's a tiny bit of swelling around the scrotum. Normal?",
             "He keeps wanting to play, how do I keep him calm?",
         ]),
]


def _make_pet(seed):
    species = seed["species"]
    region = seed["region"]
    seq = len(CASES)
    name_pool = {
        ("dog", "NA"): DOG_NAMES_NA, ("dog", "SG"): DOG_NAMES_SG,
        ("cat", "NA"): CAT_NAMES_NA, ("cat", "SG"): CAT_NAMES_SG,
    }[(species, region)]
    breed_pool = {
        ("dog", "NA"): DOG_BREEDS_NA, ("dog", "SG"): DOG_BREEDS_SG,
        ("cat", "NA"): CAT_BREEDS, ("cat", "SG"): CAT_BREEDS,
    }[(species, region)]
    name = pick(name_pool, seq + 3)
    # Pick breed that fits the scenario (heuristic)
    breed = pick(breed_pool, seq + 1)
    if "frenchie" in seed["slug"] or "BOAS" in seed["scene_sub"]:
        breed = "French Bulldog"
    if "pug" in seed["slug"]:
        breed = "Pug"
    if "gsd" in seed["slug"] or "german_shepherd" in seed["slug"]:
        breed = "German Shepherd"
    if "dane" in seed["slug"]:
        breed = "Great Dane"
    if "pomeranian" in seed["slug"]:
        breed = "Pomeranian"
    if "chihuahua" in seed["slug"]:
        breed = "Chihuahua"
    if "yorkie" in seed["slug"]:
        breed = "Yorkshire Terrier"
    if "lab" in seed["slug"]:
        breed = "Labrador Retriever"
    if "shih" in seed["slug"]:
        breed = "Shih Tzu"
    if "cocker" in seed["slug"]:
        breed = "Cocker Spaniel"
    if "beagle" in seed["slug"]:
        breed = "Beagle"
    if "schnauzer" in seed["slug"]:
        breed = "Miniature Schnauzer"
    if "maltese" in seed["slug"]:
        breed = "Maltese"
    age = [12, 24, 36, 48, 60, 84, 108, 132][seq % 8]
    if "puppy" in seed["slug"] or "kitten" in seed["slug"]:
        age = [2, 3, 4, 5][seq % 4]
    gender = "male" if "male" in seed["slug"] else ("female" if "female" in seed["slug"] else ("male" if seq % 2 == 0 else "female"))
    neutered = "no" if "intact" in seed["slug"] else "yes"
    weight = round({"dog": 6.0 + (seq * 1.3) % 26.0, "cat": 3.0 + (seq * 0.3) % 4.0}[species], 1)
    if "dane" in seed["slug"]:
        weight = 55.0
    if "pomeranian" in seed["slug"] or "chihuahua" in seed["slug"] or "yorkie" in seed["slug"]:
        weight = 1.5
    builder = cat if species == "cat" else dog
    return builder(name, breed, age, gender, neutered, weight)


for _seed in _ACUTE_SEEDS:
    _pet = _make_pet(_seed)
    _region = _seed["region"]
    _owner = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, len(CASES))
    CASES.append(acute_case(
        slug=_seed["slug"],
        owner=_owner,
        pet=_pet,
        region=_region,
        scene_sub=_seed["scene_sub"],
        day1_label=_seed["day1_label"],
        day1_turns=_seed["d1"],
        day2_label=_seed["day2_label"],
        day2_turns=_seed["d2"],
        day3_label=_seed.get("day3_label"),
        day3_turns=_seed.get("d3"),
        red_flag=_seed.get("red_flag", False),
    ))


# fill remaining acute slots up to 35 acute total (we currently have 35? count)
# 35 seeds defined above — verified by len(_ACUTE_SEEDS)
assert len([c for c in CASES if c["metadata"]["scene_main"] == "acute"]) == 35, (
    f"acute count {len([c for c in CASES if c['metadata']['scene_main']=='acute'])}")


# ─── 1.C Behavioural short (7 cases) ─────────────────────────────────────────

_BEHAV_SHORT_SEEDS = [
    ("crate_first_week", "puppy crate training week 1", "dog", "NA", "M3", "M14"),
    ("name_recall_kitten", "kitten responding to name", "cat", "SG", "M3", "M10"),
    ("leash_pulling_first_walks", "leash manners early sessions", "dog", "NA", "M3", "M13"),
    ("litter_box_relocation", "cat re-learning new litter spot", "cat", "NA", "M1", "M6"),
    ("first_groom_intro", "puppy desensitisation to brushing", "dog", "SG", "M3", "M14"),
    ("car_ride_intro", "cat learning carrier + car", "cat", "NA", "M3", "M14"),
    ("guarding_food_bowl_early", "early resource guarding sign", "dog", "NA", "M4", "M8"),
]

for _i, (_sub, _desc, _sp, _region, _d1, _d2) in enumerate(_BEHAV_SHORT_SEEDS):
    _name_pool = {("dog", "NA"): DOG_NAMES_NA, ("dog", "SG"): DOG_NAMES_SG,
                  ("cat", "NA"): CAT_NAMES_NA, ("cat", "SG"): CAT_NAMES_SG}[(_sp, _region)]
    _breed_pool = {"dog": DOG_BREEDS_NA if _region == "NA" else DOG_BREEDS_SG,
                   "cat": CAT_BREEDS}[_sp]
    _pet_name = pick(_name_pool, _i + 5)
    _breed = pick(_breed_pool, _i)
    _age = [3, 4, 5, 6, 8, 10, 12][_i]
    _w = 4.0 if _sp == "cat" else round(3.5 + _i * 1.2, 1)
    _builder = cat if _sp == "cat" else dog
    _pet = _builder(_pet_name, _breed, _age, "male" if _i % 2 else "female",
                    "yes" if _i % 3 != 0 else "no", _w)
    _owner = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, _i + 4)
    _slug = f"behav_{_sub}_{_i:02d}_short"
    _scenario = (
        f"{_owner} is working on {_desc} with {_pet['name']}. Over 3-4 short days "
        "Pawly should remember what was tried, what worked, and what to try next."
    )
    _outcome = (
        "On day 2/3 Pawly recalls the specific technique used on day 1, names the "
        "incremental milestone (e.g. holds for 5 seconds, eats in crate, walks 3 "
        "blocks without pulling) and suggests the next progression step."
    )
    _d1_turns = [
        f"Hi Pawly, working on {_desc} with {_pet['name']} today.",
        "We did about 3 short sessions. She did okay but lost focus after about 10 min.",
        "What should I try tomorrow to build on this?",
    ]
    _d2_turns = [
        f"Day 2 of {_desc} with {_pet['name']}.",
        "Followed your suggestion. She got the first part but resisted the second.",
        "Stay on this step or push forward?",
    ]
    _d3_turns = [
        f"Day 3 — {_pet['name']} actually nailed it twice in a row today.",
        "Should I add the new criterion now or wait one more day?",
    ]
    CASES.append(case(
        name=_slug, scenario=_scenario, expected_outcome=_outcome,
        chatbot_role=(f"Pawly is a pet care assistant guiding a {_desc} progression "
                      "across multiple short sessions."),
        criteria=BEHAVIOR_CRIT,
        pet_profile=_pet,
        days=[
            session(f"Day 1 — start {_desc}", _d1_turns, True, True),
            session(f"Day 2 — second session", _d2_turns, True, True),
            session(f"Day 3 — third session", _d3_turns, True, True),
        ],
        time_span="short", density="medium",
        scene="behavioral", scene_sub=_sub, region=_region,
        m_dims=(_d1, _d2, "M14"),
    ))


# ─── 1.D Chronic-management starts (5 cases, short span) ─────────────────────

_CHRONIC_SHORT_SEEDS = [
    ("insulin_dose_titration_day1_3", "newly diagnosed diabetic cat starting insulin", "cat", "NA", False),
    ("ckd_subq_fluids_at_home_intro", "owner learning to give SubQ fluids", "cat", "SG", False),
    ("nsaid_started_arthritis_dog", "senior dog day 1-3 on carprofen", "dog", "NA", False),
    ("levothyroxine_intro_dog", "hypothyroid dog starting levothyroxine", "dog", "NA", False),
    ("methimazole_intro_cat", "hyperthyroid cat starting methimazole", "cat", "NA", False),
]
for _i, (_sub, _desc, _sp, _region, _rf) in enumerate(_CHRONIC_SHORT_SEEDS):
    _name_pool = {("dog", "NA"): DOG_NAMES_NA, ("dog", "SG"): DOG_NAMES_SG,
                  ("cat", "NA"): CAT_NAMES_NA, ("cat", "SG"): CAT_NAMES_SG}[(_sp, _region)]
    _breed_pool = {"dog": DOG_BREEDS_NA if _region == "NA" else DOG_BREEDS_SG,
                   "cat": CAT_BREEDS}[_sp]
    _pet_name = pick(_name_pool, _i + 9)
    _breed = pick(_breed_pool, _i + 3)
    _age = [108, 132, 96, 144, 120][_i]
    _w = 5.0 if _sp == "cat" else round(8.0 + _i * 2.5, 1)
    _builder = cat if _sp == "cat" else dog
    _pet = _builder(_pet_name, _breed, _age, "female" if _i % 2 else "male", "yes", _w)
    _owner = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, _i + 11)
    _slug = f"chronic_short_{_sub}_{_i:02d}"
    _d1_turns = [
        f"Hi Pawly, {_pet['name']} just started treatment today for {_desc.split(' starting ')[-1] if ' starting ' in _desc else _desc}.",
        "Vet showed us the technique and the first dose went okay.",
        "What should we be watching for in the next 24-48 hours?",
    ]
    _d2_turns = [
        "Day 2 update — gave the dose this morning, she ate after.",
        "She seems okay, maybe a touch sleepy. Should I be tracking anything specific?",
        "How will I know it's working in the first week?",
    ]
    _d3_turns = [
        "Day 3 — second full day on the new med.",
        "No side effects yet. When's the next vet recheck again?",
    ]
    CASES.append(case(
        name=_slug,
        scenario=f"{_owner} is in the first 3 days of {_desc} for {_pet['name']}. Each day "
                 "Pawly should layer onto what's already known rather than restart.",
        expected_outcome=("By day 2/3 Pawly knows the medication, dose, what's already "
                          "happened and reframes the new info into the running picture."),
        chatbot_role=(f"Pawly is a pet care assistant supporting the first days of "
                      f"{_desc}."),
        criteria=CHRONIC_CRIT,
        pet_profile=_pet,
        days=[
            session("Day 1 — start of treatment", _d1_turns, True, True),
            session("Day 2 — second day update", _d2_turns, True, True),
            session("Day 3 — third day check-in", _d3_turns, True, True),
        ],
        time_span="short", density="medium",
        scene="chronic", scene_sub=_sub, region=_region,
        m_dims=("M1", "M12", "M14"),
    ))


# ─── 1.E Pathology-early signs in 1-7 days (5 cases) ─────────────────────────

_PATH_SHORT_SEEDS = [
    ("ckd_pupd_early_cat", "cat suddenly drinking and peeing more (PU/PD)", "cat", "NA"),
    ("appetite_decline_3day_cat", "older cat appetite drop over 3 days", "cat", "SG"),
    ("intermittent_limping_dog", "dog limping that comes and goes", "dog", "NA"),
    ("lump_grew_overnight_dog", "lump grew noticeably in 5 days", "dog", "NA"),
    ("eye_change_iris_cat", "iris colour change over a week (lymphoma flag)", "cat", "NA"),
]
for _i, (_sub, _desc, _sp, _region) in enumerate(_PATH_SHORT_SEEDS):
    _name_pool = {("dog", "NA"): DOG_NAMES_NA, ("dog", "SG"): DOG_NAMES_SG,
                  ("cat", "NA"): CAT_NAMES_NA, ("cat", "SG"): CAT_NAMES_SG}[(_sp, _region)]
    _breed_pool = {"dog": DOG_BREEDS_NA if _region == "NA" else DOG_BREEDS_SG,
                   "cat": CAT_BREEDS}[_sp]
    _pet_name = pick(_name_pool, _i + 13)
    _breed = pick(_breed_pool, _i + 5)
    _age = [120, 144, 96, 84, 132][_i]
    _w = 4.5 if _sp == "cat" else round(10.0 + _i * 3.0, 1)
    _builder = cat if _sp == "cat" else dog
    _pet = _builder(_pet_name, _breed, _age, "female" if _i % 2 else "male", "yes", _w)
    _owner = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, _i + 13)
    _slug = f"path_short_{_sub}_{_i:02d}"
    _scenario = (
        f"{_owner} reports a subtle but persistent change in {_pet['name']} over "
        f"a few days — {_desc}. Pawly must track the trajectory rather than dismiss "
        "any single day's reading."
    )
    _outcome = (
        "By day 3/5 Pawly recognises the running pattern, anchors to the day-1 "
        "observation, and recommends a vet workup at the right urgency tier."
    )
    _d1_turns = [
        f"Hi Pawly, I noticed something odd with {_pet['name']} starting today.",
        f"It's {_desc}. Could be nothing, but it's not how she usually is.",
        "What should I track for the next couple of days?",
    ]
    _d2_turns = [
        f"Day 2-3 check. The {_sub.split('_')[0]} thing is still happening, slightly worse.",
        "I tried what you suggested but it's not really changing.",
        "Should I get her seen?",
    ]
    _d3_turns = [
        f"Day 5 — still going, and now she's also a bit more tired than usual.",
        "Booking a vet appointment. What should I make sure they check?",
    ]
    CASES.append(case(
        name=_slug, scenario=_scenario, expected_outcome=_outcome,
        chatbot_role=(f"Pawly is a pet care assistant tracking an early subtle pathology "
                      "signal across 3-5 days."),
        criteria=ESCALATION_CRIT,
        pet_profile=_pet,
        days=[
            session("Day 1 — first odd day", _d1_turns, True, True),
            session("Day 3 — still off", _d2_turns, True, True),
            session("Day 5 — pattern + tired", _d3_turns, True, True),
        ],
        time_span="short", density="medium",
        scene="pathology", scene_sub=_sub, region=_region,
        m_dims=("M2", "M4", "M10"),
    ))


# ─── 1.F Owner-side scenarios short (3 cases) ────────────────────────────────

_OWNER_SHORT_SEEDS = [
    ("late_night_anxiety_first_pet", "U2 high-anxiety first-time owner chatting at 2am", "NA"),
    ("denial_minimisation", "owner downplaying clear red-flag symptoms", "NA"),
    ("google_self_medicating", "owner already started OTC meds based on Google", "SG"),
]
for _i, (_sub, _desc, _region) in enumerate(_OWNER_SHORT_SEEDS):
    _sp = "dog" if _i % 2 == 0 else "cat"
    _name_pool = {("dog", "NA"): DOG_NAMES_NA, ("dog", "SG"): DOG_NAMES_SG,
                  ("cat", "NA"): CAT_NAMES_NA, ("cat", "SG"): CAT_NAMES_SG}[(_sp, _region)]
    _breed_pool = {"dog": DOG_BREEDS_NA if _region == "NA" else DOG_BREEDS_SG,
                   "cat": CAT_BREEDS}[_sp]
    _pet_name = pick(_name_pool, _i + 17)
    _breed = pick(_breed_pool, _i + 7)
    _pet = (cat if _sp == "cat" else dog)(_pet_name, _breed, 24, "female", "yes", 4.0 if _sp == "cat" else 12.0)
    _owner = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, _i + 19)
    _slug = f"owner_short_{_sub}_{_i:02d}"
    if _sub == "late_night_anxiety_first_pet":
        _d1 = [
            "Pawly are you there?? It's 2am and I'm freaking out about my puppy.",
            "She's just breathing fast in her sleep. Is that normal??",
            "I keep checking her every 10 minutes.",
        ]
        _d2 = [
            "Pawly hi again — slept maybe 2 hours. She's fine, eating, playing.",
            "I know I overreacted last night.",
            "Can you help me figure out what's actually worth waking up for?",
        ]
    elif _sub == "denial_minimisation":
        _d1 = [
            "Pawly, my cat threw up twice today but it's probably nothing.",
            "She's fine, just a hairball I think. She's a little quieter but eating.",
            "I don't think we need a vet for this right?",
        ]
        _d2 = [
            "Okay so today she vomited again and didn't touch breakfast.",
            "Still probably hairballs though?",
            "She's hiding under the bed but she does that sometimes.",
        ]
    else:  # google_self_medicating
        _d1 = [
            "Pawly, my dog has been scratching and I gave her a Benadryl based on what I read.",
            "I gave her 25mg, she's about 8kg.",
            "Is that the right dose?",
        ]
        _d2 = [
            "She slept a lot, scratched less but still scratching today.",
            "I was about to give her another Benadryl plus some leftover prednisolone we have.",
            "Is that okay together?",
        ]
    _scenario = f"{_desc}. The challenge is for Pawly to read the owner-side pattern and not just react to surface words."
    _outcome = ("Pawly recognises the owner-side signal — anxiety / denial / self-medication — "
                "reorients to the pet's actual state, and either de-escalates the panic or escalates the under-reaction.")
    CASES.append(case(
        name=_slug, scenario=_scenario, expected_outcome=_outcome,
        chatbot_role="Pawly is a pet care assistant balancing owner emotion against pet evidence.",
        criteria=OWNER_CRIT,
        pet_profile=_pet,
        days=[
            session("Day 1 — owner-side framing", _d1, True, True),
            session("Day 2 — pattern persists", _d2, False, False),
        ],
        time_span="short", density="dense",
        scene="owner", scene_sub=_sub, region=_region,
        m_dims=("M7", "M8"),
    ))


# Sanity: Batch 1 total = 70
_b1 = [c for c in CASES if c["metadata"]["time_span"] == "short"]
assert len(_b1) == 70, f"Batch 1 has {len(_b1)} cases (expected 70)"


# ═════════════════════════════════════════════════════════════════════════════
# BATCH 2 — Weeks span (2-8 weeks). Target: 60 cases.
#   Mix: 10 healthy programmes, 5 acute follow-ups, 15 behavioural programmes,
#        12 chronic mgmt, 10 pathology evolution, 8 owner-side / multi-pet.
# ═════════════════════════════════════════════════════════════════════════════

def weeks_case(slug, scene, scene_sub, region, pet, owner, sessions, dims,
               density="sparse", red_flag=False, criteria=None):
    scenario = (
        f"Across {len(sessions)} sessions spanning a few weeks, {owner} updates "
        f"Pawly on {pet['name']}'s {scene_sub.replace('_', ' ')} journey. The bot "
        "must connect each weekly check-in to the prior weeks rather than restart."
    )
    expected_outcome = (
        f"By the final session Pawly has a coherent multi-week picture of "
        f"{pet['name']}: which interventions were tried, what changed, and what "
        "comes next, with explicit reference to the earlier weeks' content."
    )
    chosen = criteria or RECOVERY_CRIT
    return case(
        name=slug, scenario=scenario, expected_outcome=expected_outcome,
        chatbot_role=(f"Pawly is a pet care assistant tracking {pet['name']} through a "
                      f"{scene_sub.replace('_', ' ')} programme over multiple weeks."),
        criteria=chosen,
        pet_profile=pet, days=sessions,
        time_span="weeks", density=density,
        scene=scene, scene_sub=scene_sub,
        region=region, m_dims=dims, red_flag=red_flag,
    )


def _w_pet(slug, sp, region, idx, age=None, breed=None, weight=None,
           gender=None, neutered=None):
    pools = {("dog", "NA"): (DOG_NAMES_NA, DOG_BREEDS_NA),
             ("dog", "SG"): (DOG_NAMES_SG, DOG_BREEDS_SG),
             ("cat", "NA"): (CAT_NAMES_NA, CAT_BREEDS),
             ("cat", "SG"): (CAT_NAMES_SG, CAT_BREEDS)}
    npool, bpool = pools[(sp, region)]
    n = pick(npool, idx + 21)
    b = breed or pick(bpool, idx + 13)
    a = age if age is not None else [6, 12, 24, 36, 48, 60, 84, 108][idx % 8]
    g = gender or ("male" if idx % 2 else "female")
    nt = neutered or "yes"
    w = weight if weight is not None else (4.5 if sp == "cat" else round(8.0 + idx * 1.5, 1))
    return (cat if sp == "cat" else dog)(n, b, a, g, nt, w)


# 2.A Healthy programmes (10) — onboarding programme, food transition, weight loss start
_HEALTHY_WEEKS_SEEDS = [
    ("onboarding_program_week", "Pawly onboarding 4-week programme", "dog", "NA"),
    ("onboarding_program_week_cat", "Pawly onboarding 4-week programme", "cat", "SG"),
    ("food_transition_kibble_wet", "transitioning from kibble to wet", "cat", "NA"),
    ("weight_loss_program_start", "vet-led weight loss programme start", "dog", "NA"),
    ("puppy_growth_8_to_16wk", "puppy growth tracking 8-16 weeks", "dog", "NA"),
    ("kitten_growth_10_to_18wk", "kitten growth 10-18 weeks", "cat", "SG"),
    ("dental_brushing_intro_program", "4-week dental brushing introduction", "dog", "SG"),
    ("senior_baseline_program", "senior baseline establishment 4 weeks", "cat", "NA"),
    ("indoor_to_outdoor_program", "indoor cat introduced to safe outdoor", "cat", "NA"),
    ("puppy_socialisation_4wk", "puppy socialisation programme", "dog", "NA"),
]
for _i, (_sub, _desc, _sp, _region) in enumerate(_HEALTHY_WEEKS_SEEDS):
    _pet = _w_pet(_sub, _sp, _region, _i, age=(3 if "puppy" in _sub or "kitten" in _sub else 36))
    _own = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, _i + 23)
    _slug = f"weeks_healthy_{_sub}_{_i:02d}"
    _sessions = [
        session("Week 1 — start of programme",
                [
                    f"Hi Pawly, kicking off {_desc} with {_pet['name']} today.",
                    "She's a bit hesitant but we did the first 2 days okay.",
                    "What's the milestone for the first week?",
                ], True, True),
        session("Week 2 — mid-programme",
                [
                    f"Week 2 update — {_pet['name']} is more consistent now.",
                    "Following your suggestions, we hit the week-1 milestone.",
                    "What's the criterion for moving to phase 2?",
                ], True, True),
        session("Week 3 — adjustment",
                [
                    "Week 3 — hit a plateau, she's not progressing further.",
                    "Should we stay here longer or change the approach?",
                ], True, False),
        session("Week 4 — programme wrap",
                [
                    f"Week 4 wrap — {_pet['name']} is consistent now.",
                    "Where do we go from here?",
                    "Anything I should keep monitoring?",
                ], True, True),
    ]
    CASES.append(weeks_case(_slug, "healthy", _sub, _region, _pet, _own,
                            _sessions, ("M1", "M3", "M10")))


# 2.B Acute follow-ups across weeks (5) — post-op, post-illness recovery
_ACUTE_WEEKS_SEEDS = [
    ("post_tplo_recovery_program", "8-week TPLO post-op recovery", "dog", "NA"),
    ("post_spay_2wk_recovery", "2-week post-spay recovery in detail", "dog", "SG"),
    ("post_dental_extraction_2wk", "2-week recovery after multiple extractions", "cat", "NA"),
    ("acute_pancreatitis_4wk_diet", "acute pancreatitis 4-week diet recovery", "dog", "NA"),
    ("post_blockage_3wk_uwatch", "3-week urinary watch post unblock", "cat", "NA"),
]
for _i, (_sub, _desc, _sp, _region) in enumerate(_ACUTE_WEEKS_SEEDS):
    _pet = _w_pet(_sub, _sp, _region, _i + 11, age=72)
    _own = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, _i + 27)
    _slug = f"weeks_acute_{_sub}_{_i:02d}"
    _sessions = [
        session("Week 1 — discharge week",
                [
                    f"Pawly, {_pet['name']} just came home from {_desc.split(' ')[1]}.",
                    "Vet's instructions: confinement, meds, recheck in 2 weeks.",
                    "What do I watch for in the first 7 days?",
                ], True, True),
        session("Week 2 — first vet recheck",
                [
                    "Week 2 — vet was happy with the recheck. Sutures out.",
                    "She's pushing to do more activity. How much is okay?",
                ], True, True),
        session("Week 4 — back to walking",
                [
                    "Week 4 — back to short walks. No issues so far.",
                    "When can we resume jogging?",
                ], False, False),
        session("Week 6 — fully recovered",
                [
                    "Week 6 — she's back to normal activity, no signs of issues.",
                    "Any long-term watch points?",
                ], False, False),
    ]
    CASES.append(weeks_case(_slug, "acute", _sub, _region, _pet, _own,
                            _sessions, ("M1", "M3", "M10", "M14"),
                            density="sparse"))


# 2.C Behavioural programmes weeks (15)
_BEHAV_WEEKS_SEEDS = [
    "separation_anxiety_4wk_program",
    "leash_manners_6wk",
    "crate_to_freedom_4wk",
    "puppy_potty_4wk",
    "kitten_litter_3wk",
    "reactivity_threshold_work_6wk",
    "recall_training_4wk",
    "barking_quiet_cue_3wk",
    "multi_cat_intro_6wk",
    "dog_dog_new_intro_4wk",
    "feline_inter_cat_aggression_4wk",
    "noise_phobia_thunder_4wk",
    "carrier_desensitisation_3wk",
    "groomer_handling_4wk",
    "vet_visit_desensitisation_4wk",
]
for _i, _sub in enumerate(_BEHAV_WEEKS_SEEDS):
    _sp = "cat" if "feline" in _sub or "kitten" in _sub or "multi_cat" in _sub else "dog"
    _region = ["NA", "SG"][_i % 2]
    _pet = _w_pet(_sub, _sp, _region, _i + 23)
    _own = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, _i + 31)
    _slug = f"weeks_behav_{_sub}_{_i:02d}"
    _sessions = [
        session("Week 1 — programme start",
                [f"Pawly, starting a {_sub.replace('_', ' ')} programme with {_pet['name']}.",
                 "Today we did the baseline assessment. She struggled with the trigger.",
                 "What's the first week's goal?"], True, True),
        session("Week 2 — first progress",
                [f"Week 2 — {_pet['name']} is making slow but steady progress.",
                 "We hit the threshold drop you suggested.",
                 "What's next week's milestone?"], True, True),
        session("Week 3 — plateau",
                ["Week 3 — we're stuck at the current level.",
                 "She regresses when I push.",
                 "Stay here or adjust?"], True, False),
        session("Week 4 — push through",
                ["Week 4 — broke through, much better today.",
                 "She handled the bigger trigger well.",
                 "Programme wrap-up plan?"], True, True),
    ]
    CASES.append(weeks_case(_slug, "behavioral", _sub, _region, _pet, _own,
                            _sessions, ("M1", "M3", "M14"), density="sparse",
                            criteria=BEHAVIOR_CRIT))


# 2.D Chronic management mid-week phase (12) — programme-period chronic
_CHRONIC_WEEKS_SEEDS = [
    "diabetes_dog_insulin_titration_6wk",
    "diabetes_cat_insulin_titration_6wk",
    "ckd_iris_stage2_8wk",
    "ckd_iris_stage3_8wk",
    "hcm_diuretic_titration_6wk",
    "ibd_diet_trial_8wk",
    "atopy_apoquel_6wk",
    "cushings_trilostane_6wk",
    "hypothyroid_levo_titration_8wk",
    "hyperthyroid_methimazole_titration_8wk",
    "epi_enzyme_replacement_6wk",
    "addison_percorten_8wk",
]
for _i, _sub in enumerate(_CHRONIC_WEEKS_SEEDS):
    _sp = "cat" if "cat" in _sub or "hyperthyroid" in _sub else "dog"
    _region = ["NA", "SG"][_i % 2]
    _pet = _w_pet(_sub, _sp, _region, _i + 37, age=120)
    _own = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, _i + 41)
    _slug = f"weeks_chronic_{_sub}_{_i:02d}"
    _sessions = [
        session("Week 1 — diagnosis + start",
                [f"Pawly, vet just confirmed {_sub.split('_')[0]} for {_pet['name']}.",
                 "We started the treatment plan today. Some side effects warned about.",
                 "What's the first-week priority for monitoring?"], True, True),
        session("Week 3 — first recheck",
                ["Week 3 — first recheck went well. Vet adjusted the dose.",
                 "She seems more like herself now.",
                 "What's the next data point I should track?"], True, True),
        session("Week 6 — second adjustment",
                ["Week 6 — second adjustment. We're closer to therapeutic now.",
                 "I noticed she's drinking a touch more again.",
                 "Is that the disease or the meds?"], True, False),
        session("Week 8 — stable phase enters",
                ["Week 8 — labs are within target range.",
                 "She's stable now. What's the long-term cadence?",
                 "Any side effects I'm still watching for?"], True, True),
    ]
    CASES.append(weeks_case(_slug, "chronic", _sub, _region, _pet, _own,
                            _sessions, ("M1", "M2", "M12"), density="sparse",
                            criteria=CHRONIC_CRIT))


# 2.E Pathology evolution weeks (10) — signs cluster, evolve over weeks
_PATH_WEEKS_SEEDS = [
    "pupd_to_dx_workup_6wk_dog",
    "weight_loss_dx_workup_6wk_cat",
    "limping_progressive_4wk_dog",
    "skin_lump_growing_6wk_dog",
    "chronic_cough_evolving_4wk_dog",
    "cat_chronic_diarrhea_6wk",
    "behaviour_change_dementia_8wk",
    "vision_decline_progressive_8wk_dog",
    "tremor_intermittent_4wk_dog",
    "muscle_wasting_4wk_cat",
]
for _i, _sub in enumerate(_PATH_WEEKS_SEEDS):
    _sp = "cat" if "cat" in _sub else "dog"
    _region = ["NA", "SG"][_i % 2]
    _pet = _w_pet(_sub, _sp, _region, _i + 51, age=132)
    _own = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, _i + 53)
    _slug = f"weeks_path_{_sub}_{_i:02d}"
    _sessions = [
        session("Week 1 — first noticed",
                [f"Hi Pawly, started noticing {_sub.replace('_', ' ')} with {_pet['name']} this week.",
                 "It's subtle but consistent. Not enough for an ER visit.",
                 "What do I document over the next weeks?"], True, True),
        session("Week 2 — pattern clear",
                ["Week 2 — definitely a pattern now, not a one-off.",
                 "I have notes. Should I book a vet appointment?"], True, True),
        session("Week 4 — vet workup begun",
                ["Week 4 — vet ran initial labs and imaging.",
                 "Results came back with abnormalities. They want more tests.",
                 "What should I be asking the vet next?"], True, False),
        session("Week 6 — diagnosis arriving",
                ["Week 6 — preliminary diagnosis is in.",
                 "It's something we'll need to manage longer term.",
                 "Where do we go from here in terms of monitoring?"], True, True),
    ]
    CASES.append(weeks_case(_slug, "pathology", _sub, _region, _pet, _own,
                            _sessions, ("M2", "M4", "M10", "M12"), density="sparse",
                            criteria=ESCALATION_CRIT))


# 2.F Owner-side + multi-pet across weeks (8)
_OWNER_WEEKS_SEEDS = [
    ("multi_pet_two_cats_one_url", "two-cat household, only one has URI symptoms", "cat", "NA", MULTI_PET_CRIT, ("M9",)),
    ("multi_pet_dog_cat_household_separate_issues", "dog and cat with separate concerns", "dog", "SG", MULTI_PET_CRIT, ("M9",)),
    ("multi_pet_three_dogs_diff_ages", "three dogs different life stages", "dog", "NA", MULTI_PET_CRIT, ("M9",)),
    ("owner_non_adherence_meds_skipped", "owner skipping doses, hasn't told vet", "dog", "NA", OWNER_CRIT, ("M7",)),
    ("owner_switching_vets_mid_workup", "owner switched vet mid-workup", "cat", "NA", OWNER_CRIT, ("M7",)),
    ("owner_finance_constraints_compromise", "limited budget changes the plan", "dog", "SG", OWNER_CRIT, ("M7",)),
    ("multi_caregiver_information_mismatch", "different family members report differently", "cat", "NA", OWNER_CRIT, ("M7", "M9")),
    ("owner_information_overload_anxiety", "owner overwhelmed by detail", "dog", "NA", OWNER_CRIT, ("M7", "M8")),
]
for _i, (_sub, _desc, _sp, _region, _crit, _dims) in enumerate(_OWNER_WEEKS_SEEDS):
    _pet = _w_pet(_sub, _sp, _region, _i + 61)
    _own = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, _i + 67)
    _slug = f"weeks_owner_{_sub}_{_i:02d}"
    _sessions = [
        session("Week 1 — situation introduced",
                [f"Pawly, situation with my pets: {_desc}.",
                 f"{_pet['name']} is the one I'm most concerned about right now.",
                 "What's the priority here?"], True, True),
        session("Week 2 — situation evolves",
                ["Week 2 — things shifted a bit.",
                 "I've been doing some of what you said but couldn't do all of it.",
                 "Where does that leave us?"], True, True),
        session("Week 4 — outcome",
                ["Week 4 update — here's what actually happened.",
                 "Some good, some not. Tell me where I should re-focus.",
                 "What's next?"], True, False),
    ]
    CASES.append(weeks_case(_slug, "owner", _sub, _region, _pet, _own,
                            _sessions, _dims, density="sparse",
                            criteria=_crit))


# Sanity: Batch 2 total = 60
_b2 = [c for c in CASES if c["metadata"]["time_span"] == "weeks"]
assert len(_b2) == 60, f"Batch 2 has {len(_b2)} cases (expected 60)"


# ═════════════════════════════════════════════════════════════════════════════
# BATCH 3 — Months span (2-6 months). Target: 40 cases.
#   Mix: 5 healthy, 3 behaviour, 12 chronic, 15 pathology, 5 owner-side.
#   Density: sparse to very_sparse (monthly to bi-weekly check-ins).
# ═════════════════════════════════════════════════════════════════════════════

def months_case(slug, scene, scene_sub, region, pet, owner, sessions, dims,
                density="very_sparse", red_flag=False, criteria=None):
    span = len(sessions)
    scenario = (
        f"Over {span} sessions spread across 2-6 months, {owner} reports on "
        f"{pet['name']}'s {scene_sub.replace('_', ' ')} journey at roughly monthly "
        "intervals. Pawly must connect each month to the prior months and the "
        "long arc rather than treat each check-in as a new chat."
    )
    expected_outcome = (
        f"By the final check-in Pawly references the multi-month trajectory of "
        f"{pet['name']}, names which interventions held, what changed, and what "
        "is now the running baseline — with explicit reference to month-1 numbers."
    )
    return case(
        name=slug, scenario=scenario, expected_outcome=expected_outcome,
        chatbot_role=(f"Pawly is a pet care assistant tracking {pet['name']} across "
                      f"multiple months of {scene_sub.replace('_', ' ')} management."),
        criteria=criteria or CHRONIC_CRIT,
        pet_profile=pet, days=sessions,
        time_span="months", density=density,
        scene=scene, scene_sub=scene_sub,
        region=region, m_dims=dims, red_flag=red_flag,
    )


def _m_pet(slug, sp, region, idx, age=None, breed=None, weight=None,
           gender=None, neutered=None):
    pools = {("dog", "NA"): (DOG_NAMES_NA, DOG_BREEDS_NA),
             ("dog", "SG"): (DOG_NAMES_SG, DOG_BREEDS_SG),
             ("cat", "NA"): (CAT_NAMES_NA, CAT_BREEDS),
             ("cat", "SG"): (CAT_NAMES_SG, CAT_BREEDS)}
    npool, bpool = pools[(sp, region)]
    n = pick(npool, idx + 41)
    b = breed or pick(bpool, idx + 17)
    a = age if age is not None else 132
    g = gender or ("male" if idx % 2 else "female")
    nt = neutered or "yes"
    w = weight if weight is not None else (5.0 if sp == "cat" else round(10.0 + idx * 1.8, 1))
    return (cat if sp == "cat" else dog)(n, b, a, g, nt, w)


# 3.A Healthy long monitoring (5)
_HEALTHY_MONTHS_SEEDS = [
    ("seasonal_weight_swing_3mo", "winter-to-summer body condition swing", "dog", "NA"),
    ("indoor_to_outdoor_safe_4mo", "indoor-to-outdoor cat over 4 months", "cat", "NA"),
    ("puppy_to_adolescent_6mo", "puppy to adolescent maturation", "dog", "NA"),
    ("kitten_to_juvenile_6mo", "kitten to juvenile growth arc", "cat", "SG"),
    ("senior_baseline_quarterly_3mo", "senior cat quarterly check programme", "cat", "NA"),
]
for _i, (_sub, _desc, _sp, _region) in enumerate(_HEALTHY_MONTHS_SEEDS):
    _pet = _m_pet(_sub, _sp, _region, _i,
                  age=4 if "puppy" in _sub or "kitten" in _sub else 132)
    _own = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, _i + 71)
    _slug = f"months_healthy_{_sub}_{_i:02d}"
    _sessions = [
        session("Month 1 — baseline locked",
                [f"Pawly, kicking off {_desc} with {_pet['name']}.",
                 "Today's baseline numbers established.",
                 "What do I check at each monthly milestone?"], True, True),
        session("Month 2 — first delta",
                ["Month 2 — minor shifts. Still mostly stable.",
                 "Reading is within the band you said is normal.",
                 "Anything to adjust?"], True, True),
        session("Month 4 — drift detected",
                ["Month 4 — there's a drift now, gradual but real.",
                 "Hard to tell if this is season, diet or development.",
                 "Help me parse it."], True, True),
        session("Month 6 — full picture",
                ["Month 6 — re-anchored to the trajectory.",
                 "What's the new baseline I should hold to from here?"], True, True),
    ]
    CASES.append(months_case(_slug, "healthy", _sub, _region, _pet, _own,
                             _sessions, ("M2", "M3", "M10"), density="very_sparse",
                             criteria=BASELINE_CRIT))


# 3.B Behavioural long arc (3)
_BEHAV_MONTHS_SEEDS = [
    "separation_anxiety_meds_plus_behaviour_4mo",
    "reactivity_long_arc_6mo",
    "house_soiling_resolution_3mo",
]
for _i, _sub in enumerate(_BEHAV_MONTHS_SEEDS):
    _sp = "cat" if "house_soil" in _sub else "dog"
    _region = ["NA", "SG"][_i % 2]
    _pet = _m_pet(_sub, _sp, _region, _i + 7)
    _own = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, _i + 73)
    _slug = f"months_behav_{_sub}_{_i:02d}"
    _sessions = [
        session("Month 1 — start", [f"Starting the {_sub.replace('_', ' ')} arc with {_pet['name']}.",
                                     "Baseline trigger map captured.",
                                     "What's the month-1 goal?"], True, True),
        session("Month 2 — mid arc", ["Month 2 — partial improvement but flares occasionally.",
                                       "Tell me if I push or hold."], True, True),
        session("Month 4 — late arc", ["Month 4 — flares are rare and milder.",
                                        "Does this count as stable?"], True, False),
    ]
    CASES.append(months_case(_slug, "behavioral", _sub, _region, _pet, _own,
                             _sessions, ("M1", "M3", "M5", "M10"),
                             criteria=BEHAVIOR_CRIT))


# 3.C Chronic mgmt across months (12)
_CHRONIC_MONTHS_SEEDS = [
    "ckd_iris_2_quarterly_6mo_cat",
    "ckd_iris_3_quarterly_6mo_cat",
    "diabetes_dog_glucose_curve_6mo",
    "diabetes_cat_remission_attempt_6mo",
    "hcm_srr_monthly_6mo_cat",
    "dcm_dog_6mo",
    "arthritis_nsaid_galliprant_6mo",
    "ibd_long_term_diet_6mo",
    "atopy_apoquel_6mo_long",
    "addison_long_term_6mo",
    "hypothyroid_long_term_6mo",
    "epilepsy_phenobarb_titration_6mo",
]
for _i, _sub in enumerate(_CHRONIC_MONTHS_SEEDS):
    _sp = "cat" if "cat" in _sub else "dog"
    _region = ["NA", "SG"][_i % 2]
    _pet = _m_pet(_sub, _sp, _region, _i + 13, age=144)
    _own = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, _i + 79)
    _slug = f"months_chronic_{_sub}_{_i:02d}"
    _sessions = [
        session("Month 1 — already on therapy",
                [f"Month 1 update — {_pet['name']} is on therapy for {_sub.split('_')[0]}.",
                 "Latest labs are within the target window.",
                 "What's my month-1 priority?"], True, True),
        session("Month 2 — small dose change",
                ["Month 2 — vet bumped the dose slightly.",
                 "She's tolerating it. Still drinking a touch more.",
                 "Is that the disease or the drug?"], True, True),
        session("Month 4 — second recheck",
                ["Month 4 — recheck went well, lab values trending the right way.",
                 "She's a bit slower than 6 months ago.",
                 "Is that ageing or the disease?"], True, False),
        session("Month 6 — six-month mark",
                ["Month 6 — at the recheck again. Vet says stable.",
                 "What's my new long-term cadence?"], True, True),
    ]
    CASES.append(months_case(_slug, "chronic", _sub, _region, _pet, _own,
                             _sessions, ("M1", "M2", "M10", "M12"),
                             criteria=CHRONIC_CRIT))


# 3.D Pathology evolution across months (15)
_PATH_MONTHS_SEEDS = [
    "early_ckd_pupd_to_dx_3mo_cat",
    "early_diabetes_pupd_to_dx_3mo_dog",
    "lump_mass_growing_4mo_dog",
    "cat_chronic_diarrhea_dx_4mo",
    "dog_cough_progressive_4mo",
    "cat_oral_mass_progress_3mo",
    "muscle_wasting_senior_4mo_cat",
    "intermittent_lameness_progressive_4mo_dog",
    "behaviour_change_dementia_progress_6mo",
    "seizure_workup_4mo",
    "weight_loss_workup_6mo_cat",
    "vision_decline_workup_4mo_dog",
    "skin_recurrent_lesion_4mo_cat",
    "spinal_pain_progressive_4mo_dog",
    "endocrine_workup_long_4mo_dog",
]
for _i, _sub in enumerate(_PATH_MONTHS_SEEDS):
    _sp = "cat" if "cat" in _sub else "dog"
    _region = ["NA", "SG"][_i % 2]
    _pet = _m_pet(_sub, _sp, _region, _i + 27, age=144)
    _own = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, _i + 89)
    _slug = f"months_path_{_sub}_{_i:02d}"
    _sessions = [
        session("Month 1 — first sign",
                [f"Pawly, started noticing something subtle about {_pet['name']}.",
                 f"It's {_sub.replace('_', ' ')}. Could be nothing.",
                 "What do I document over the next month?"], True, True),
        session("Month 2 — still progressing",
                ["Month 2 — still happening, slightly more pronounced.",
                 "Vet ran initial labs — some flags but nothing definitive.",
                 "More tests?"], True, True),
        session("Month 3 — diagnosis emerging",
                ["Month 3 — vet has a working diagnosis.",
                 "Treatment plan being discussed.",
                 "What do I push for clarity on?"], True, False),
        session("Month 4 — plan in motion",
                ["Month 4 — on the treatment plan now.",
                 "Some early improvement. Long-term outlook?"], True, True),
    ]
    CASES.append(months_case(_slug, "pathology", _sub, _region, _pet, _own,
                             _sessions, ("M2", "M4", "M10", "M12"),
                             criteria=ESCALATION_CRIT))


# 3.E Owner-side long arc (5)
_OWNER_MONTHS_SEEDS = [
    "owner_program_dropout_3mo",
    "owner_vet_switch_4mo",
    "owner_chronic_anxiety_3mo",
    "owner_two_caregivers_drift_4mo",
    "owner_remote_relocation_4mo",
]
for _i, _sub in enumerate(_OWNER_MONTHS_SEEDS):
    _sp = "cat" if _i % 2 else "dog"
    _region = "NA"
    _pet = _m_pet(_sub, _sp, _region, _i + 43)
    _own = pick(OWNERS_NA, _i + 101)
    _slug = f"months_owner_{_sub}_{_i:02d}"
    _sessions = [
        session("Month 1 — owner situation",
                [f"Pawly, situation: {_sub.replace('_', ' ')}.",
                 f"Affects how I can care for {_pet['name']} right now.",
                 "What can we still do?"], True, True),
        session("Month 2 — mid-situation",
                ["Month 2 — adapted somewhat.",
                 "Some of the plan is still in place, some isn't.",
                 "Where's the gap I should close first?"], True, True),
        session("Month 4 — outcome",
                ["Month 4 — here's where we landed.",
                 f"Tell me where {_pet['name']} stands now."], True, False),
    ]
    CASES.append(months_case(_slug, "owner", _sub, _region, _pet, _own,
                             _sessions, ("M1", "M7", "M14"),
                             criteria=OWNER_CRIT))


# Sanity: Batch 3 total = 40
_b3 = [c for c in CASES if c["metadata"]["time_span"] == "months"]
assert len(_b3) == 40, f"Batch 3 has {len(_b3)} cases (expected 40)"


# ═════════════════════════════════════════════════════════════════════════════
# BATCH 4 — Years span (1-3 years). Target: 20 regular + 10 extreme = 30 cases.
# Cadence: quarterly to semi-annual check-ins. Total turns ≤50 each, target 25-35.
# ═════════════════════════════════════════════════════════════════════════════

def years_case(slug, scene, scene_sub, region, pet, owner, sessions, dims,
               density="very_sparse", red_flag=False, criteria=None,
               time_span="years"):
    span_n = len(sessions)
    scenario = (
        f"Across {span_n} sessions spanning 1-3 years, {owner} returns to Pawly "
        f"at quarterly to semi-annual intervals for {pet['name']}'s "
        f"{scene_sub.replace('_', ' ')} arc. Pawly must thread the entire arc "
        "and identify what is part of the long pattern vs. a new event."
    )
    expected_outcome = (
        f"In the final session Pawly recalls the multi-year arc — onset, mid-arc "
        f"changes, recent baseline — and frames the current state in that long "
        "history rather than treating it in isolation."
    )
    return case(
        name=slug, scenario=scenario, expected_outcome=expected_outcome,
        chatbot_role=(f"Pawly is a pet care assistant providing multi-year continuity "
                      f"for {pet['name']}'s {scene_sub.replace('_', ' ')} journey."),
        criteria=criteria or CHRONIC_CRIT,
        pet_profile=pet, days=sessions,
        time_span=time_span, density=density,
        scene=scene, scene_sub=scene_sub,
        region=region, m_dims=dims, red_flag=red_flag,
    )


def _y_pet(slug, sp, region, idx, age=None, breed=None, weight=None,
           gender=None, neutered=None):
    pools = {("dog", "NA"): (DOG_NAMES_NA, DOG_BREEDS_NA),
             ("dog", "SG"): (DOG_NAMES_SG, DOG_BREEDS_SG),
             ("cat", "NA"): (CAT_NAMES_NA, CAT_BREEDS),
             ("cat", "SG"): (CAT_NAMES_SG, CAT_BREEDS)}
    npool, bpool = pools[(sp, region)]
    n = pick(npool, idx + 53)
    b = breed or pick(bpool, idx + 19)
    a = age if age is not None else 132
    g = gender or ("female" if idx % 2 else "male")
    nt = neutered or "yes"
    w = weight if weight is not None else (5.0 if sp == "cat" else round(12.0 + idx * 1.6, 1))
    return (cat if sp == "cat" else dog)(n, b, a, g, nt, w)


# 4.A 20 regular year-span cases (chronic + pathology + healthy + behaviour)
_YEAR_SEEDS = [
    # Chronic (8)
    ("ckd_long_term_2yr_cat", "chronic", "M1,M2,M10,M12"),
    ("diabetes_2yr_dog", "chronic", "M1,M2,M10,M12"),
    ("hcm_long_2yr_cat", "chronic", "M2,M10,M12"),
    ("arthritis_long_2yr_dog", "chronic", "M2,M10,M12"),
    ("hypothyroid_long_2yr_dog", "chronic", "M1,M12"),
    ("hyperthyroid_long_2yr_cat", "chronic", "M1,M12"),
    ("addison_long_2yr_dog", "chronic", "M1,M12"),
    ("epilepsy_long_2yr_dog", "chronic", "M1,M12"),
    # Pathology evolution (5)
    ("renal_progression_stage2_to_4_2yr_cat", "pathology", "M4,M10"),
    ("cardiac_progression_to_chf_2yr_cat", "pathology", "M4,M10"),
    ("oncology_lymphoma_treatment_arc_2yr_dog", "pathology", "M4,M10,M12"),
    ("cushings_progression_2yr_dog", "pathology", "M4,M12"),
    ("cognitive_decline_2yr_dog", "pathology", "M4,M10"),
    # Behaviour (2)
    ("anxiety_long_term_2yr_dog", "behavioral", "M1,M3,M14"),
    ("territorial_long_2yr_cat", "behavioral", "M1,M3"),
    # Healthy (3) — longitudinal baseline arcs
    ("adolescent_to_adult_dog_2yr", "healthy", "M2,M3,M10"),
    ("kitten_to_adult_cat_2yr", "healthy", "M2,M3,M10"),
    ("senior_baseline_long_2yr_cat", "healthy", "M2,M10"),
    # Acute follow-up arc (2 — chronic from acute origin)
    ("post_tplo_2yr_followup_dog", "acute", "M3,M10"),
    ("post_blockage_2yr_followup_cat", "acute", "M1,M3,M10"),
]
for _i, (_sub, _scene, _dims_str) in enumerate(_YEAR_SEEDS):
    _sp = "cat" if "cat" in _sub else "dog"
    _region = ["NA", "SG"][_i % 2]
    _age = 36 if "adolescent" in _sub or "kitten" in _sub else 132
    _pet = _y_pet(_sub, _sp, _region, _i, age=_age)
    _own = pick(OWNERS_NA if _region == "NA" else OWNERS_SG, _i + 113)
    _slug = f"years_{_scene}_{_sub}_{_i:02d}"
    _dims = tuple(_dims_str.split(","))
    _crit = {"chronic": CHRONIC_CRIT, "pathology": ESCALATION_CRIT,
             "behavioral": BEHAVIOR_CRIT, "healthy": BASELINE_CRIT,
             "acute": RECOVERY_CRIT}[_scene]
    _sessions = [
        session("Year 1 Q1 — baseline",
                [f"Pawly, kicking off the long arc tracking for {_pet['name']} on {_sub.replace('_', ' ')}.",
                 "Today's numbers and current status logged.",
                 "What's the year-1 priority?"], True, True),
        session("Year 1 Q3 — first re-anchor",
                ["Two quarters in. Current readings logged.",
                 "Slight drift from baseline — meaningful or noise?"], True, True),
        session("Year 2 Q1 — one-year mark",
                ["One year in. Annual recheck just happened.",
                 "Big-picture: stable but with one shift you should know about.",
                 "Should we adjust the long-term plan?"], True, False),
        session("Year 2 Q3 — late stage of arc",
                ["18 months in. Things have settled into a pattern.",
                 "What's the new long-term baseline?"], True, False),
        session("Year 3 Q1 — two-year mark",
                [f"Two years in with {_pet['name']}.",
                 "Annual labs/imaging done. Trajectory holds.",
                 "Where do we focus the next year?"], True, True),
    ]
    CASES.append(years_case(_slug, _scene, _sub, _region, _pet, _own,
                            _sessions, _dims, criteria=_crit))


# ─── 4.B Ten extreme story arcs (E1-E10) ─────────────────────────────────────
# Each: multi-year arc, 6-15 sessions, total turns 25-45 (within the 50 cap).

# E1 — Maine Coon HCM arc (3 years)
_e1_pet = cat("Atlas", "Maine Coon", 6, "male", "yes", 4.8)
CASES.append(case(
    name="E1_maine_coon_hcm_3yr_arc",
    scenario=(
        "Atlas, a Maine Coon, is adopted at 6 months. At 12 months a routine "
        "scan flags early HCM. By 18 months his SRR rises; at 24 months he has "
        "acute CHF, is rescued, stabilises on lifelong therapy; three years in "
        "he has a second acute event leading to a QoL decision."
    ),
    expected_outcome=(
        "On the final sessions Pawly references the HCM diagnosis at year 1, the "
        "SRR rise, the year-2 CHF event, the post-rescue therapy regime, and uses "
        "HHHHHMM QoL framing for the terminal decision."
    ),
    chatbot_role="Pawly is a pet care assistant supporting a Maine Coon family across a 3-year HCM arc.",
    criteria=CHRONIC_CRIT,
    pet_profile=_e1_pet,
    days=[
        session("Month 6 — adoption + baseline",
                ["Pawly, just adopted Atlas, a Maine Coon kitten.",
                 "Vet wants annual cardiac echos because of breed risk.",
                 "What's my first-year priority?"], True, True),
        session("Month 12 — early HCM flagged",
                ["First echo done. Mild HCM detected.",
                 "Vet says no meds yet, just monitoring + SRR at home.",
                 "How do I track SRR consistently?"], True, True),
        session("Month 18 — SRR rising",
                ["6 months in. SRR drifted from 24 to 32 over the last month.",
                 "Still acting fine but it's a clear shift from baseline.",
                 "Recheck now or wait?"], True, True),
        session("Month 24 — acute CHF event",
                ["Pawly, Atlas just collapsed while breathing fast and open-mouth.",
                 "We're rushing him in. SRR was 50+ before we left.",
                 "What do I tell the ER?"], True, True),
        session("Month 25 — discharged on meds",
                ["He survived. They started furosemide, pimobendan, clopidogrel.",
                 "He's home, eating, calmer.",
                 "What's my SRR target now?"], True, True),
        session("Year 3 — stable phase",
                ["A year on the meds. SRR holding 24-28.",
                 "Echo shows controlled disease.",
                 "Anything changing for year 3?"], False, False),
        session("Year 3 Q4 — second acute event",
                ["Pawly, Atlas is in distress again — breathing 60+, hiding.",
                 "He's not the same as last time. Vet says he's reached the limit.",
                 "Help me think through QoL."], True, True),
    ],
    time_span="extreme", density="very_sparse",
    scene="pathology", scene_sub="hcm_3yr_arc",
    region="NA",
    m_dims=("M1", "M2", "M3", "M4", "M10", "M12"),
    red_flag=True,
))


# E2 — Corgi IVDD multi-event 5-year arc
_e2_pet = dog("Biscuit", "Corgi", 8, "male", "yes", 11.0)
CASES.append(case(
    name="E2_corgi_ivdd_5yr_arc",
    scenario=(
        "Biscuit the Corgi starts as a puppy. At 1 year first IVDD warning. "
        "At 3 years he has acute paralysis requiring decompression surgery; 8 "
        "months of rehab follow with partial recovery. At 5 years a second "
        "neurological event."
    ),
    expected_outcome=(
        "Final sessions Pawly recalls the year-1 warning, the year-3 surgery, "
        "the rehab trajectory and the persistent residual deficits, framing the "
        "year-5 event as a second event on a known IVDD patient — not a fresh case."
    ),
    chatbot_role="Pawly tracks a 5-year IVDD arc in a Corgi from puppy through second flare.",
    criteria=CHRONIC_CRIT,
    pet_profile=_e2_pet,
    days=[
        session("Month 8 — puppy baseline",
                ["Pawly, Biscuit is a Corgi puppy 8 months old.",
                 "I want to set him up to avoid IVDD long-term.",
                 "What habits do I build now?"], True, True),
        session("Year 1 — first warning",
                ["Year 1 — he yelped jumping off the sofa.",
                 "Walked fine after but I'm worried.",
                 "Imaging now or watch?"], True, True),
        session("Year 3 — acute paralysis",
                ["Pawly emergency — Biscuit's back legs aren't working.",
                 "He was fine this morning. Now he's dragging them.",
                 "Where do I go?"], True, True),
        session("Year 3 Month 1 — post-op",
                ["Surgery done — hemilaminectomy at the neurology referral.",
                 "He's home, paralysed back legs but some deep pain.",
                 "Rehab plan?"], True, True),
        session("Year 3 Month 6 — partial recovery",
                ["6 months post-op. He can stand and walk short distances.",
                 "Still wobbly. Continence is good.",
                 "Is this his new normal?"], True, False),
        session("Year 5 — second event",
                ["Pawly, Biscuit is yelping again, won't move much.",
                 "Different segment this time per the vet exam.",
                 "Same playbook?"], True, True),
    ],
    time_span="extreme", density="very_sparse",
    scene="pathology", scene_sub="ivdd_5yr_arc",
    region="NA",
    m_dims=("M1", "M2", "M3", "M4", "M10", "M12"),
    red_flag=True,
))


# E3 — Frenchie BOAS 5-year arc
_e3_pet = dog("Pepper", "French Bulldog", 6, "male", "yes", 12.0)
CASES.append(case(
    name="E3_frenchie_boas_5yr_arc",
    scenario=(
        "Pepper, a French Bulldog, is monitored from 6 months for BOAS. Soft "
        "palate + nare resection at 1 year. Six months of recovery. At 3 years "
        "a heat-related crisis. At 5 years progressive chronic airway disease."
    ),
    expected_outcome=(
        "Pawly references the BOAS surgery at year 1, the heat crisis at year 3, "
        "and frames year-5 chronic airway disease as expected progression — not a "
        "new problem — with season-aware exercise advice."
    ),
    chatbot_role="Pawly tracks a 5-year BOAS arc in a French Bulldog.",
    criteria=CHRONIC_CRIT,
    pet_profile=_e3_pet,
    days=[
        session("Month 6 — BOAS baseline",
                ["Pawly, Pepper is a 6-month Frenchie.",
                 "Vet flagged BOAS risk, breathing is noisy at rest.",
                 "Plan?"], True, True),
        session("Year 1 — BOAS surgery",
                ["Year 1 — he had soft palate + nare resection.",
                 "Recovery looks good. What's the long-term care?"], True, True),
        session("Year 1.5 — six months post-op",
                ["6 months post-op. Breathing much quieter.",
                 "Can we resume normal walks?"], True, False),
        session("Year 3 — heat crisis",
                ["Pawly — Pepper overheated on a humid walk.",
                 "Tongue blue, panting non-stop, dragging.",
                 "ER now?"], True, True),
        session("Year 3 Q4 — recovered + lessons",
                ["He recovered. ER said his BOAS is partially relapsed.",
                 "What do I change permanently?"], True, True),
        session("Year 5 — chronic airway",
                ["Year 5 — his exercise tolerance has dropped over the past months.",
                 "Stertor is back even at rest.",
                 "Is this the BOAS again or something new?"], True, True),
    ],
    time_span="extreme", density="very_sparse",
    scene="pathology", scene_sub="boas_5yr_arc",
    region="SG",
    m_dims=("M1", "M2", "M3", "M4", "M10", "M12"),
    red_flag=True,
))


# E4 — Lab POMC obesity → DM → DKA → CKD comorbidity (6 years)
_e4_pet = dog("Buddy", "Labrador Retriever", 24, "male", "yes", 38.0)
CASES.append(case(
    name="E4_lab_pomc_dm_ckd_6yr_arc",
    scenario=(
        "Buddy, a Lab with POMC obesity flag, is on weight management at year 2. "
        "Diabetes at year 4. DKA crisis at year 6 — rescued. CKD comorbidity "
        "emerges at year 8. Multi-disease management."
    ),
    expected_outcome=(
        "Final sessions Pawly recalls the POMC label, the DM diagnosis, the DKA "
        "rescue, the CKD comorbidity, and provides advice that respects all of them."
    ),
    chatbot_role="Pawly tracks a Lab through 6+ years of progressive comorbidities.",
    criteria=CHRONIC_CRIT,
    pet_profile=_e4_pet,
    days=[
        session("Year 2 — POMC + weight",
                ["Pawly, vet said Buddy has the POMC gene + obesity tendency.",
                 "Started weight loss plan.",
                 "What's the long-term plan?"], True, True),
        session("Year 4 — diabetes",
                ["Year 4 — Buddy diagnosed with diabetes.",
                 "Started insulin, glucose curves done.",
                 "Long-term outlook?"], True, True),
        session("Year 6 — DKA crisis",
                ["Pawly — Buddy is in crisis: vomiting, lethargic, sweet breath.",
                 "Blood glucose 32 mmol/L.",
                 "ER now?"], True, True),
        session("Year 6 + 1 month — discharged",
                ["He survived DKA. Insulin protocol revised.",
                 "Diet too. What do I monitor more closely?"], True, False),
        session("Year 8 — CKD comorbidity",
                ["Year 8 — bloodwork shows kidney enzymes rising.",
                 "Vet diagnosed early CKD on top of the DM.",
                 "How do I manage both?"], True, True),
    ],
    time_span="extreme", density="very_sparse",
    scene="pathology", scene_sub="dm_ckd_comorbid_6yr",
    region="NA",
    m_dims=("M1", "M2", "M3", "M4", "M10", "M12"),
    red_flag=True,
))


# E5 — Cat CKD stage 2 to euthanasia + new cat onboarding (5+ years)
_e5_pet = cat("Cleo", "Domestic Shorthair", 96, "female", "yes", 4.2)
CASES.append(case(
    name="E5_cat_ckd_terminal_new_cat_5yr_arc",
    scenario=(
        "Cleo, 8yo cat, is staged CKD IRIS 2 at year 1. Progresses to stage 4 "
        "by year 4. Euthanasia decision at year 5; grief support. Six months "
        "later owner adopts a new cat — Pawly transitions the conversation "
        "without conflating the two pets."
    ),
    expected_outcome=(
        "After the loss Pawly handles grief; when the new cat arrives Pawly does "
        "NOT confuse Cleo's history with the new cat's baseline."
    ),
    chatbot_role="Pawly supports a CKD terminal arc, bereavement, and a new-cat onboarding without conflation.",
    criteria=MULTI_PET_CRIT,
    pet_profile=_e5_pet,
    days=[
        session("Year 1 — IRIS 2 diagnosed",
                ["Pawly, Cleo's labs show CKD IRIS 2.",
                 "Renal diet started, no meds yet.",
                 "What's my year-1 priority?"], True, True),
        session("Year 3 — IRIS 3",
                ["Year 3 — progression to stage 3.",
                 "Added benazepril and a phosphate binder.",
                 "What changes at home?"], True, True),
        session("Year 4 — IRIS 4 / declining",
                ["Year 4 — she's stage 4 now.",
                 "We're on subQ fluids every other day.",
                 "Honest QoL view?"], True, True),
        session("Year 5 — euthanasia decision",
                ["Pawly — she's stopped eating completely, not engaging.",
                 "Vet says it's time to talk about peaceful options.",
                 "Help me think about HHHHHMM."], True, True),
        session("Year 5 + 1 month — grief",
                ["She passed peacefully at home.",
                 "I'm a mess but I want to thank you for being there.",
                 "How do I think about the next one?"], False, False),
        session("Year 5 + 6 months — new cat",
                ["Pawly — I adopted a new kitten, Marshmallow.",
                 "She's a 4-month DSH. Healthy as far as I know.",
                 "Help me start her baseline — not Cleo's."], True, True),
    ],
    time_span="extreme", density="very_sparse",
    scene="pathology", scene_sub="ckd_terminal_new_cat_5yr",
    region="NA",
    m_dims=("M1", "M3", "M9", "M10", "M12"),
    red_flag=False,
))


# E6 — Schnauzer pancreatitis + DM comorbidity (4 years)
_e6_pet = dog("Rocky", "Miniature Schnauzer", 36, "male", "yes", 9.5)
CASES.append(case(
    name="E6_schnauzer_pancreatitis_dm_4yr_arc",
    scenario=(
        "Rocky, a Mini Schnauzer, has first acute pancreatitis at year 3; "
        "managed on low-fat diet. Year 5 second episode after dietary indiscretion. "
        "Year 7 chronic pancreatitis + DM comorbidity."
    ),
    expected_outcome=(
        "Final session Pawly recalls both pancreatitis events, the breed-specific "
        "lipid risk, and frames DM as predictable comorbidity."
    ),
    chatbot_role="Pawly tracks a 4-year pancreatitis-to-DM arc in a Schnauzer.",
    criteria=CHRONIC_CRIT,
    pet_profile=_e6_pet,
    days=[
        session("Year 3 — first pancreatitis",
                ["Pawly — Rocky has acute pancreatitis confirmed.",
                 "Vet says lifelong low-fat diet.",
                 "What changes permanently?"], True, True),
        session("Year 3 Month 3 — recovered",
                ["Recovered well, lipids dropping with the diet.",
                 "Anything to add long-term?"], True, False),
        session("Year 5 — second episode",
                ["Pawly — second pancreatitis episode after he stole bacon.",
                 "Vet has him on IV fluids.",
                 "Worse than last time?"], True, True),
        session("Year 5 Month 6 — chronic phase",
                ["Year 5.5 — vet says chronic pancreatitis on top of acute history.",
                 "Lipase persistently elevated.",
                 "What's the lifelong protocol?"], True, True),
        session("Year 7 — DM joins",
                ["Year 7 — now diagnosed with diabetes too.",
                 "Schnauzer with pancreatitis + DM. Insulin started.",
                 "How do I manage both?"], True, True),
    ],
    time_span="extreme", density="very_sparse",
    scene="pathology", scene_sub="pancreatitis_dm_4yr",
    region="NA",
    m_dims=("M1", "M2", "M4", "M10", "M12"),
    red_flag=False,
))


# E7 — Intact female: pyometra → mammary tumor (6 years)
_e7_pet = dog("Daisy", "Cocker Spaniel", 48, "female", "no", 13.5)
CASES.append(case(
    name="E7_intact_female_pyometra_mammary_6yr_arc",
    scenario=(
        "Daisy, an intact female Cocker, has acute pyometra at year 4 — emergency "
        "OVH. Year 6 false pregnancy. Year 8 mammary tumour — biopsy, surgery, "
        "chemotherapy. Year 10 in remission."
    ),
    expected_outcome=(
        "Final sessions Pawly recalls the pyometra at year 4, false pregnancy at "
        "year 6, mammary tumour at year 8, and frames remission with appropriate "
        "monitoring without re-asking the entire history."
    ),
    chatbot_role="Pawly tracks an intact-female reproductive disease arc from acute pyometra to oncology.",
    criteria=CHRONIC_CRIT,
    pet_profile=_e7_pet,
    days=[
        session("Year 4 — pyometra emergency",
                ["Pawly — Daisy is intact, lethargic, drinking lots.",
                 "Heat 5 weeks ago, brown discharge.",
                 "Pyometra?"], True, True),
        session("Year 4 Month 1 — post-OVH",
                ["She survived emergency OVH.",
                 "On antibiotics, recovering.",
                 "Long-term watch points?"], True, False),
        session("Year 6 — false pregnancy",
                ["Year 6 — she's nesting and her mammary glands are enlarged.",
                 "Wait — she's spayed. What is this?"], True, True),
        session("Year 8 — mammary mass",
                ["Pawly — I found a firm lump in her mammary chain.",
                 "Bigger than a pea, irritated.",
                 "Concerning?"], True, True),
        session("Year 8 + 3 months — chemo",
                ["Biopsy confirmed malignancy. Surgery + chemo.",
                 "She's tolerating it.",
                 "What's the timeline?"], True, False),
        session("Year 10 — remission",
                ["Year 10 — 2-year remission. No new masses.",
                 "What's my long-term surveillance?"], True, True),
    ],
    time_span="extreme", density="very_sparse",
    scene="pathology", scene_sub="pyometra_mammary_6yr",
    region="NA",
    m_dims=("M1", "M3", "M10", "M12"),
    red_flag=True,
))


# E8 — Pomeranian lifetime toy-breed arc (12 years compressed)
_e8_pet = dog("Boba", "Pomeranian", 3, "female", "yes", 2.4)
CASES.append(case(
    name="E8_pomeranian_lifetime_toy_breed_arc",
    scenario=(
        "Boba, a Pomeranian, has multiple toy-breed chronic conditions across her "
        "life: puppy hypoglycaemia episodes, year-3 patellar luxation grade 2, "
        "year-7 tracheal collapse, year-10 dental disease + CHF."
    ),
    expected_outcome=(
        "Pawly tracks Boba across her lifetime, linking each new disease to her "
        "toy-breed profile and prior history."
    ),
    chatbot_role="Pawly supports a Pomeranian across a 12-year toy-breed arc.",
    criteria=CHRONIC_CRIT,
    pet_profile=_e8_pet,
    days=[
        session("Month 3 — puppy hypos",
                ["Pawly — Boba just had her second hypoglycaemia episode.",
                 "She's 2.4kg, 12 weeks.",
                 "How do I prevent more?"], True, True),
        session("Year 3 — patellar luxation",
                ["Year 3 — she's been skipping a step then trotting on the rear.",
                 "Vet says grade 2 patellar luxation.",
                 "Surgery or manage?"], True, True),
        session("Year 7 — tracheal collapse",
                ["Year 7 — she's coughing like a goose honk after walks.",
                 "Vet diagnosed tracheal collapse.",
                 "How bad does this usually get?"], True, True),
        session("Year 10 — dental + CHF",
                ["Year 10 — bad dental disease + early CHF.",
                 "Vet wants dental clearance under careful anaesthesia.",
                 "How do I weigh the risk?"], True, True),
        session("Year 11 — stable on meds",
                ["Year 11 — on furosemide + pimobendan.",
                 "Doing okay for her age.",
                 "What's the cadence now?"], False, False),
    ],
    time_span="extreme", density="very_sparse",
    scene="pathology", scene_sub="toy_breed_lifetime",
    region="SG",
    m_dims=("M1", "M2", "M3", "M10", "M12"),
    red_flag=False,
))


# E9 — Multi-pet household stress arc (2 years)
_e9_pet = dog("Max", "Labrador Retriever", 48, "male", "yes", 28.0)
CASES.append(case(
    name="E9_multi_pet_household_2yr_arc",
    scenario=(
        "Max (adult Lab) lives with a new kitten Mochi who arrives at month 1. "
        "4 weeks of introduction. Year 1 Max develops arthritis affecting the "
        "dynamic. Year 2 Mochi develops FIC from stress. Multi-pet, multi-event."
    ),
    expected_outcome=(
        "Pawly correctly attributes events to Max vs Mochi, recognises the "
        "interactions (Max's arthritis affecting Mochi's stress)."
    ),
    chatbot_role="Pawly tracks a multi-pet household across 2 years, attributing correctly.",
    criteria=MULTI_PET_CRIT,
    pet_profile=_e9_pet,
    days=[
        session("Month 1 — new kitten Mochi",
                ["Pawly — adopting a new kitten Mochi, our Lab Max is the resident.",
                 "Mochi is 10 weeks, healthy. Max is 4yo, friendly.",
                 "Intro plan?"], True, True),
        session("Month 2 — intro working",
                ["Month 2 — they coexist, even nap near each other.",
                 "Both eating well.",
                 "Anything to watch?"], True, False),
        session("Year 1 — Max arthritis",
                ["Year 1 — Max has stiffness in the rear after walks.",
                 "Vet says early arthritis, started carprofen.",
                 "Mochi seems to sense it and gives him space.",
                 "Anything else to change?"], True, True),
        session("Year 2 — Mochi FIC",
                ["Pawly — Mochi has been straining in the litter box and licking belly.",
                 "Vet says FIC, likely stress-related.",
                 "Could Max's slow-down be stressing her?"], True, True),
        session("Year 2 Q2 — household reset",
                ["Reorganised feeding stations, added Feliway, separated rest spots.",
                 "Mochi's FIC is down to one episode in 4 weeks.",
                 "Max stable on his meds.",
                 "What's the long-term plan?"], True, True),
    ],
    time_span="extreme", density="very_sparse",
    scene="pathology", scene_sub="multi_pet_arc_2yr",
    region="NA",
    m_dims=("M1", "M9", "M10", "M13"),
    red_flag=False,
))


# E10 — Scottish Fold OCD + tumor (4 years)
_e10_pet = cat("Luna", "Scottish Fold", 12, "female", "yes", 4.5)
CASES.append(case(
    name="E10_scottish_fold_ocd_oncology_4yr_arc",
    scenario=(
        "Luna, a Scottish Fold, is diagnosed with osteochondrodysplasia at year 1. "
        "Lifelong joint supplements + diet. Year 3 sudden mass found on neck — "
        "lymphoma. Chemo. OCD worsens during chemo. QoL decision at year 4."
    ),
    expected_outcome=(
        "Pawly recalls the OCD lifelong management, the lymphoma diagnosis, the "
        "chemo, and supports a HHHHHMM-framed QoL decision integrating both."
    ),
    chatbot_role="Pawly supports a Scottish Fold across OCD + oncology arc with a final QoL decision.",
    criteria=CHRONIC_CRIT,
    pet_profile=_e10_pet,
    days=[
        session("Year 1 — OCD diagnosed",
                ["Pawly — Luna's vet diagnosed osteochondrodysplasia.",
                 "She's stiff and reluctant to jump.",
                 "What's lifelong management?"], True, True),
        session("Year 2 — stable on plan",
                ["Year 2 — joint supplements, controlled weight, low-impact play.",
                 "She's stable.",
                 "Anything to add?"], True, False),
        session("Year 3 — neck mass",
                ["Pawly — I just felt a firm mass on her neck.",
                 "About the size of a marble.",
                 "Should I be worried?"], True, True),
        session("Year 3 Month 2 — chemo started",
                ["Biopsy: lymphoma. Started CHOP chemo.",
                 "She's tolerating session 2 reasonably.",
                 "How do I support her joints during chemo?"], True, True),
        session("Year 4 — QoL decision",
                ["Year 4 — chemo plateaued. OCD pain is worse.",
                 "She's barely engaging now.",
                 "Help me think about HHHHHMM honestly."], True, True),
    ],
    time_span="extreme", density="very_sparse",
    scene="pathology", scene_sub="ocd_lymphoma_4yr",
    region="NA",
    m_dims=("M1", "M3", "M10", "M12"),
    red_flag=False,
))


# Sanity: Batch 4 total = 30
_b4 = [c for c in CASES if c["metadata"]["time_span"] in ("years", "extreme")]
assert len(_b4) == 30, f"Batch 4 has {len(_b4)} cases (expected 30)"


# ─── Final validation + write ────────────────────────────────────────────────
assert len(CASES) == 200, f"Total {len(CASES)} != 200"
_names = [c["name"] for c in CASES]
assert len(set(_names)) == len(_names), "Duplicate case names"
_max_turns = max(c["metadata"]["total_turns"] for c in CASES)
_avg_turns = sum(c["metadata"]["total_turns"] for c in CASES) / len(CASES)
assert _max_turns <= 50, f"Max turns {_max_turns} exceeds cap"

# ─── Bulk-up turns to target 20-30 per case ──────────────────────────────────
# Hard cap 50 per case (Wanxin 2026-06-06). Each session gets padded with
# contextually-appropriate follow-up turns until the case reaches ≥20 turns,
# preferring 22-28. Padding draws from a category-aware pool so the added
# turns read naturally.

_PAD_POOL = {
    "healthy": [
        "Anything you want me to track more carefully between now and the next check-in?",
        "How does this compare to what you'd expect for her age and breed?",
        "Should I log this in a particular format so it's easier to follow over time?",
        "Are there subtle signs I'm probably missing that matter at this stage?",
        "What does the next milestone look like — what should I aim for?",
    ],
    "acute": [
        "What's the worst case here if I wait another few hours?",
        "Should I be ready to escalate again if she changes?",
        "What's the most important thing to watch for tonight?",
        "Are there any pain signs I might be missing — she's stoic?",
        "Anything I should specifically ask the vet on the next visit?",
        "How do I tell improvement from her just being tired?",
    ],
    "chronic": [
        "How does this fit the long-term picture vs the early phase?",
        "What's the marker that would tell me the plan isn't working?",
        "Should I be doing anything differently around her medications today?",
        "Is there a quality-of-life signal I should be watching beyond labs?",
        "Anything to bring up with the specialist at the next recheck?",
        "What's the normal variation here vs a real shift?",
    ],
    "behavioral": [
        "If she regresses next week, do we go back a step or hold?",
        "What's the criterion to know she's truly 'got it'?",
        "Should I add a second daily session or keep one?",
        "How long should each session be at this stage?",
        "Anything I'm probably reinforcing without realising?",
    ],
    "pathology": [
        "What's the most likely diagnosis given the pattern so far?",
        "What test would confirm vs rule out the worst case?",
        "If this keeps progressing, what's the typical timeline?",
        "Anything I should be documenting at home that the vet would want?",
        "How urgent is the next step — days or weeks?",
        "Is there a safer first-line test I should ask for?",
    ],
    "owner": [
        "I know I'm being a lot today — am I overreading or under-reading?",
        "What's the one thing that actually matters this week?",
        "How do I avoid spiralling when nothing definitive is happening?",
        "If I had to pick one thing to do today, what is it?",
        "How honest can I be with the vet about what I haven't been doing?",
    ],
}


def _pad_case(c: dict, target: int, hard_cap: int = 50):
    pool = _PAD_POOL.get(c["metadata"]["scene_main"], _PAD_POOL["healthy"])
    total = sum(len(d["user_turns"]) for d in c["days"])
    pad_idx = 0
    seq = c["metadata"].get("scene_sub", "x")
    while total < target and total < hard_cap:
        d = c["days"][pad_idx % len(c["days"])]
        pick_idx = (hash(seq) + pad_idx) % len(pool)
        d["user_turns"].append(pool[pick_idx])
        pad_idx += 1
        total += 1
    c["metadata"]["total_turns"] = total


# Deterministic per-case target spread across 20-30, weighted toward 22-28.
# Spread uses the index into CASES so we cover the band evenly without RNG.
_SPREAD = [22, 24, 26, 28, 23, 25, 27, 29, 21, 30, 24, 26, 22, 28, 25]
for _i, _c in enumerate(CASES):
    _target = _SPREAD[_i % len(_SPREAD)]
    _pad_case(_c, target=_target)

# Re-validate after padding
_max_turns = max(c["metadata"]["total_turns"] for c in CASES)
_avg_turns = sum(c["metadata"]["total_turns"] for c in CASES) / len(CASES)
_min_turns = min(c["metadata"]["total_turns"] for c in CASES)
assert _max_turns <= 50, f"Max turns {_max_turns} exceeds cap"

print(f"Total cases: {len(CASES)}")
print(f"Turns: min={_min_turns}, max={_max_turns}, mean={_avg_turns:.1f}")
print(f"Short: {sum(1 for c in CASES if c['metadata']['time_span']=='short')}")
print(f"Weeks: {sum(1 for c in CASES if c['metadata']['time_span']=='weeks')}")
print(f"Months: {sum(1 for c in CASES if c['metadata']['time_span']=='months')}")
print(f"Years: {sum(1 for c in CASES if c['metadata']['time_span']=='years')}")
print(f"Extreme: {sum(1 for c in CASES if c['metadata']['time_span']=='extreme')}")
print(f"Red-flag cases: {sum(1 for c in CASES if c['metadata']['red_flag'])}")

OUT.write_text(json.dumps(CASES, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Written to {OUT}")
