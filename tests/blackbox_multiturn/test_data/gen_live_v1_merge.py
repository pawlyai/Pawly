"""Merge all gen_live_v1_*.json partials into the final dataset + manifest.

Trims general_topic to target distribution. Reclassifies self-harm cases
that landed under dangerous_scenario (lacking disease_mention_layer semantics)
back into compliance/medical_oos.

Final target: ~1000 cases approximating spec § 3 distribution:
  dangerous_scenario  95
  compliance          30
  injection_attack    10
  edge_pet             8
  longitudinal        30
  emotional_safety   161
  general_topic      666
"""
from __future__ import annotations
import json, pathlib
from collections import Counter

DATA_DIR = pathlib.Path(__file__).parent
TOPIC = "multiturn_pawly_regression_live_v1"

PARTIALS = ["dangerous", "longitudinal", "compliance", "injection", "edge",
            "emotional", "general"]

# ── Load all partials ────────────────────────────────────────────────────────
all_cases = []
for slug in PARTIALS:
    path = DATA_DIR / f"{TOPIC}_partial_{slug}.json"
    with open(path, encoding="utf-8") as f:
        partial = json.load(f)
    print(f"loaded {slug}: {len(partial)} cases")
    all_cases.extend(partial)

print(f"raw total: {len(all_cases)}")

# ── Reclassify dangerous_scenario self-harm → compliance/medical_oos ─────────
# These were the 3 high-impact § 7 self-harm cases (live_d_040..042). They are
# better categorized as compliance/medical_oos per § 5.2 mapping.
for c in all_cases:
    if c["metadata"].get("subcategory") == "self_harm_disclosure":
        c["metadata"]["category"] = "compliance"
        c["metadata"]["priority"] = "P0"
        c["metadata"]["focus"] = "compliance"
        c["metadata"]["oos_subtype"] = "medical_oos"
        c["metadata"].pop("disease_mention_layer", None)

# ── Target distribution ──────────────────────────────────────────────────────
TARGET = {
    "dangerous_scenario": 95,
    "compliance": 30,
    "injection_attack": 10,
    "edge_pet": 8,
    "longitudinal": 30,
    "emotional_safety": 161,
    "general_topic": 666,
}

# ── Bucket cases by category, keep first N matching target ──────────────────
buckets = {cat: [] for cat in TARGET}
for c in all_cases:
    cat = c["metadata"]["category"]
    if cat in buckets:
        buckets[cat].append(c)

final = []
for cat, target_n in TARGET.items():
    pool = buckets[cat]
    keep = pool[:target_n]
    print(f"{cat}: pool {len(pool)} -> kept {len(keep)} (target {target_n})")
    final.extend(keep)

# ── Dedup by name (safety) ───────────────────────────────────────────────────
seen = set()
deduped = []
for c in final:
    if c["name"] not in seen:
        deduped.append(c)
        seen.add(c["name"])
final = deduped

print(f"final total: {len(final)}")

# ── Distribution stats ───────────────────────────────────────────────────────
cat_dist = Counter(c["metadata"]["category"] for c in final)
prio_dist = Counter(c["metadata"]["priority"] for c in final)
focus_dist = Counter(c["metadata"]["focus"] for c in final)
species_dist = Counter(c["pet_profile"]["species"] for c in final)
breed_dist = Counter(c["pet_profile"].get("breed", "?") for c in final)
multi_dist = Counter(c["metadata"]["multiturn"] for c in final)

print("\n=== Distribution ===")
print("category:", dict(cat_dist))
print("priority:", dict(prio_dist))
print("focus:", dict(focus_dist))
print("species:", dict(species_dist))
print("multiturn:", dict(multi_dist))

# ── Write main dataset ───────────────────────────────────────────────────────
OUT = DATA_DIR / f"{TOPIC}_cases.json"
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(final, f, ensure_ascii=False, indent=2)
print(f"\nwrote {OUT}")

# ── Subcategory distribution ────────────────────────────────────────────────
sub_dist = Counter(c["metadata"].get("subcategory", "?") for c in final)
top_breeds = breed_dist.most_common(15)
top_subs = sub_dist.most_common(40)

# ── Write manifest ───────────────────────────────────────────────────────────
manifest = {
    "version": "v1",
    "generated_date": "2026-05-16",
    "spec_doc": "PAW-64",
    "total_cases": len(final),
    "schema_version": "v0.3",
    "distribution_by_category": dict(cat_dist),
    "distribution_by_priority": dict(prio_dist),
    "distribution_by_focus": dict(focus_dist),
    "distribution_by_species": dict(species_dist),
    "distribution_by_multiturn": {str(k): v for k, v in multi_dist.items()},
    "top_breeds": dict(top_breeds),
    "subcategory_distribution": dict(top_subs),
    "notes": (
        "Phase B-1 bulk generation. § 7 high-impact scenarios all present "
        "(Pyometra ×4, BOAS heatstroke ×4, toy hypoglycemia ×3, chocolate ×4, "
        "feline UO ×3, GDV ×3, Scottish Fold FOCD ×3, POMC Lab ×3, senior Golden "
        "tumor ×3, multi-child overfeeding ×3, multi-pet intro ×3, Rx-dose refusal "
        "×3, self-harm SOS ×3). Longitudinal: 30 cases spanning 3-26 months with "
        "inline timestamps in recent_turns. Includes 2 pseudo-longitudinal traps "
        "(L-B4, L-C4) and 1 contradiction trap (L-B5). "
        "Phase E (5% human spot-check) still required before final sign-off."
    ),
}
MAN = DATA_DIR / f"{TOPIC}_manifest.json"
with open(MAN, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print(f"wrote {MAN}")
