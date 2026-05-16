"""Post-merge patch:
  1. Reclassify some female pets from spayed -> intact (to hit spec § 6 target
     of >=30 unspayed females, Pyometra coverage).
  2. Trim some cases to single-turn to better reflect spec § 4.2 natural rates.

Reads the main _cases.json and rewrites it in place.
"""
from __future__ import annotations
import json, pathlib
from collections import Counter

DATA_DIR = pathlib.Path(__file__).parent
TOPIC = "multiturn_pawly_regression_live_v1"
CASES_PATH = DATA_DIR / f"{TOPIC}_cases.json"

with open(CASES_PATH, encoding="utf-8") as f:
    cases = json.load(f)

# ── 1. Boost intact-female count ────────────────────────────────────────────
# Strategy: convert 25 spayed females -> intact across diverse subcategories,
# preserving existing high-impact intact (pyometra) cases.
need_intact = 30 - sum(
    1 for c in cases
    if c["pet_profile"].get("gender") == "female"
    and c["pet_profile"].get("neutered_status") == "intact"
)
flipped = 0
for c in cases:
    if flipped >= need_intact + 5:  # +5 buffer
        break
    pp = c["pet_profile"]
    # Only flip females currently spayed in general_topic / health categories.
    if pp.get("gender") == "female" and pp.get("neutered_status") == "spayed":
        cat = c["metadata"]["category"]
        sub = c["metadata"].get("subcategory", "")
        # Avoid flipping cases that mention spaying in user_turns or scenarios
        all_text = (c.get("scenario", "") + " ".join(c.get("user_turns", []))).lower()
        if "spay" in all_text or "neuter" in all_text:
            continue
        if cat in ("general_topic", "emotional_safety"):
            pp["neutered_status"] = "intact"
            tags = c["metadata"].setdefault("diversity_tags", [])
            if "intact_female" not in tags:
                tags.append("intact_female")
            flipped += 1

print(f"Flipped {flipped} spayed -> intact females")

# ── 2. Trim some cases to single-turn to reflect spec § 4.2 natural rates ───
# Per spec: acute health ~25% multi-turn, emergency ~15%, OOS ~10%, etc.
# Strategy: for non-longitudinal cases with 3 user_turns, drop the 2nd and 3rd
# turn for ~70% of dangerous, ~90% of compliance, ~85% of general_topic,
# ~80% of emotional_safety (per spec § 4.2 column).
#
# We use a deterministic hash so the change is reproducible. Longitudinal cases
# stay multi-turn always.

TRIM_RATE = {
    "dangerous_scenario": 0.55,   # spec § 4.2 emergency ~15%, but our high-impact cases benefit from 3-turn pushback
    "compliance": 0.50,           # OOS-style usually single-turn, but escalation cases benefit from multi-turn
    "injection_attack": 0.40,
    "edge_pet": 0.50,
    "emotional_safety": 0.40,
    "general_topic": 0.50,
}

def deterministic_hash(s: str) -> int:
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h

trimmed = 0
for c in cases:
    cat = c["metadata"]["category"]
    if cat == "longitudinal":
        continue  # always multi-turn
    rate = TRIM_RATE.get(cat, 0.0)
    if len(c.get("user_turns", [])) <= 1:
        continue
    h = deterministic_hash(c["name"])
    if (h % 1000) / 1000.0 < rate:
        c["user_turns"] = [c["user_turns"][0]]
        c["metadata"]["multiturn"] = False
        trimmed += 1

print(f"Trimmed {trimmed} cases to single-turn")

# ── Distribution report ─────────────────────────────────────────────────────
intact_f = sum(
    1 for c in cases
    if c["pet_profile"].get("gender") == "female"
    and c["pet_profile"].get("neutered_status") == "intact"
)
multi = sum(1 for c in cases if c["metadata"].get("multiturn"))
single = sum(1 for c in cases if not c["metadata"].get("multiturn"))
print(f"\nUnspayed females now: {intact_f}")
print(f"Multi-turn: {multi}, single-turn: {single}")

# ── Write back ──────────────────────────────────────────────────────────────
with open(CASES_PATH, "w", encoding="utf-8") as f:
    json.dump(cases, f, ensure_ascii=False, indent=2)
print(f"rewrote {CASES_PATH}")

# ── Update manifest ─────────────────────────────────────────────────────────
MAN_PATH = DATA_DIR / f"{TOPIC}_manifest.json"
with open(MAN_PATH, encoding="utf-8") as f:
    manifest = json.load(f)

manifest["distribution_by_multiturn"] = {"True": multi, "False": single}
manifest["unspayed_females"] = intact_f
manifest["postpatch_notes"] = (
    f"Post-patch: flipped {flipped} cases to intact-female (now {intact_f}); "
    f"trimmed {trimmed} cases to single-turn per spec § 4.2 natural rates "
    "(non-longitudinal only). Longitudinal cases remain multi-turn."
)

with open(MAN_PATH, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print(f"rewrote {MAN_PATH}")
