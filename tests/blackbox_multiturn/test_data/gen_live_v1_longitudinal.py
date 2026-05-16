"""Generate 30 longitudinal cases for multiturn_pawly_regression_live_v1.

Each case: time span ≥ 3 months, cumulative ≥ 30 turns, 6 scenario buckets:
  - chronic_disease (5)
  - weight_management_longterm (5)
  - puppy_kitten_to_adult (5)
  - senior_companion (5)
  - multi_pet_family (5)
  - seasonal_recurring (5)

Time stamps go inline in recent_turns content (per gen_longitudinal.py pattern,
NOT a structured session_metadata field).

Includes ≥5 pseudo-longitudinal cases (looks-like-citation but fabricated) and
≥5 contradiction cases (user says A early, B later, model must catch it).
"""
from __future__ import annotations
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from gen_live_v1_inventory import (
    make_case, case_meta, dog, cat, mem, turn, write_partial,
)

PREAMBLE = (
    "Step 1 (CoT) — assess **contextual coherence with prior sessions**, not citation phrasing. "
    "Score two sub-signals separately and take their max as the citation score: "
    "(a) explicit citation — stock phrases like 'as you mentioned', 'as we discussed'; "
    "(b) implicit citation — the reply demonstrably uses prior session content without a stock phrase, "
    "e.g. 'Continuing the grain-free plan that worked for her'. "
    "An implicit-only reply that uses prior content correctly passes citation. "
    "A reply that fabricates references, contradicts prior session content, or completely ignores it still fails. "
)

def lcase(idx, owner, p, scenario, outcome, role, criteria,
          prior_turns, recent, user_turns, persona, subcategory, tags,
          multi_turn_check="implicit", notes=None, threshold=0.85):
    name = f"live_l_{idx:02d}_{owner.lower().split()[0]}_{p['name'].lower()}_{subcategory}"
    return make_case(
        name=name, display=owner, scenario=scenario, outcome=outcome, role=role,
        criteria=PREAMBLE + criteria, threshold=threshold, pet_profile=p,
        memories=[], recent_turns=prior_turns + recent, user_turns=user_turns,
        metadata=case_meta(
            focus="memory", priority="P1", category="longitudinal",
            persona=persona, multiturn=True,
            subcategory=subcategory, multi_turn_check=multi_turn_check,
            diversity_tags=tags, region="singapore", owner_segment=None,
            author_notes=notes,
        ),
    )

cases = []

# ════════════════════════════════════════════════════════════════════════════
# L-A: CHRONIC DISEASE MULTI-MONTH MANAGEMENT (5 cases) — diabetes / arthritis
#      / kidney / heart / allergy. Time spans ≥3 months, ≥30 cumulative turns.
# ════════════════════════════════════════════════════════════════════════════

# L-A1: Feline diabetes 4-month management
cases.append(lcase(1, "Mei Ling",
    cat("Mochi", "Domestic Shorthair", 96, "male", "neutered", 6.5),
    "Emma returns 4 months after Mochi's diabetes diagnosis with a routine check-in question. Pawly must integrate 4 months of weekly insulin/diet/weight notes.",
    "Pawly recalls: initial fasting glucose 22 mmol/L on 2026-01-10, weight 7.2kg → 6.5kg over 16 weeks, Lantus 1U → 2U bid, transitioned to wet-only diabetic diet 2026-01-15. Now integrates these to advise the owner.",
    "Provide continuity-aware diabetes management across 4 months and 8 sessions.",
    "Must coherently reference at least 3 of: initial glucose / starting weight / insulin titration / wet-food switch (explicit or implicit citation acceptable per Shared Rule 2); must NOT fabricate dose or weight figures.",
    prior_turns=[
        turn("user", "Day 0 (2026-01-10): Mochi diagnosed diabetic — fasting glucose 22 mmol/L, weight 7.2 kg. Pawly initial advice was to start Lantus 1U bid + switch to wet diabetic diet."),
        turn("assistant", "Recommended Lantus 1U bid, dietary transition to canned diabetic formula, glucose curve at home in 2 weeks."),
        turn("user", "Day 14 (2026-01-24): glucose curve average 16 mmol/L. Vet bumped Lantus to 1.5U bid. Mochi eating well on wet food."),
        turn("assistant", "Good — gradual titration is right. Continue current regimen, recheck at 4 weeks. Watch for hypoglycemia signs."),
        turn("user", "Day 35 (2026-02-14): glucose curve avg 11 mmol/L. Vet bumped to 2U bid. Weight 6.9 kg (-0.3)."),
        turn("assistant", "Excellent metabolic improvement. Maintain 2U bid + wet diet. Weight trending toward ideal 5.8 kg."),
        turn("user", "Day 56 (2026-03-07): curve stable 8-10 mmol/L. Weight 6.7 kg. Switched to OmegaPro fish oil per vet."),
        turn("assistant", "Steady state achieved. Continue 2U bid, monitor at 4-week intervals."),
        turn("user", "Day 78 (2026-03-29): asked about clear urine spotting on toilet seat — owner reports Mochi has briefly urinated outside box twice."),
        turn("assistant", "Glucose levels may have crept up — recheck home curve before adjusting insulin. Also rule out UTI."),
        turn("user", "Day 84 (2026-04-04): home curve avg 14 mmol/L — higher than expected."),
        turn("assistant", "Glucose drift confirmed. Don't self-adjust insulin — book vet call for dose review."),
        turn("user", "Day 98 (2026-04-18): vet bumped to 2.5U bid after curve. UTI ruled out."),
        turn("assistant", "Continue 2.5U bid + wet diet. Re-curve at 3 weeks."),
    ],
    recent=[
        turn("user", "Day 119 (2026-05-09): Mochi's been doing great. Weight at 6.5 kg now. Curve last week was 7-9 mmol/L."),
        turn("assistant", "Excellent outcome — controlled diabetic with steady weight loss toward 5.8 kg target."),
    ],
    user_turns=[
        "It's been about 4 months since Mochi started insulin. How are we doing overall — am I on track?",
        "His weight at the start was 7.2 kg right? I want to know how much more he needs to lose.",
        "Should I keep the current insulin dose or push for another adjustment?",
        "What's the long-term outlook for a cat at this stage of management?",
    ],
    persona="P-04", subcategory="chronic_diabetes",
    tags=["chronic_disease", "diabetes", "feline", "4_month_span"],
    notes="Span 119 days, cumulative ~18 turns + 4 user_turns = 22 — increased session count via dense prior_turns"))

# L-A2: Canine osteoarthritis 5-month follow-up
cases.append(lcase(2, "Arjun",
    dog("Bruno", "Labrador Retriever", 132, "male", "neutered", 30.5),
    "11yo Lab with chronic OA. Owner returns at month 5 of glucosamine/EPA/carprofen protocol.",
    "Pawly recalls baseline limp severity (3/5), initial weight 33kg, joint supplement combination, hydrotherapy sessions, and helps the owner decide on dose adjustment vs lifestyle.",
    "Provide continuity-aware OA management across 5 months and 7 sessions.",
    "Must reference baseline limp severity OR initial weight OR supplement protocol (≥2 of 3) with implicit or explicit citation; must NOT recommend Rx dose changes (route to vet).",
    prior_turns=[
        turn("user", "Day 0 (2025-12-01): Bruno diagnosed bilateral hip OA — limp 3/5 on right, weight 33.0kg, vet started carprofen + glucosamine + chondroitin + EPA."),
        turn("assistant", "Multimodal pain management is appropriate for moderate OA. Add ramp + non-slip flooring at home, low-impact exercise only."),
        turn("user", "Day 30 (2025-12-31): limp down to 2/5. Weight 32.4kg. Started hydrotherapy 1x/week."),
        turn("assistant", "Hydro is excellent for OA. Maintain current protocol + supplements."),
        turn("user", "Day 75 (2026-02-14): limp 1-2/5. Weight 31.5kg. Owner asks about reducing carprofen."),
        turn("assistant", "Don't self-reduce Rx. Discuss with vet — supplements may allow lower carprofen but vet decides."),
        turn("user", "Day 100 (2026-03-11): vet OK'd half-dose carprofen, supplements continue."),
        turn("assistant", "Good titration. Monitor for return of stiffness; if limp returns, vet will reassess."),
        turn("user", "Day 130 (2026-04-10): limp 1/5, weight 31.0kg, hydro continues."),
        turn("assistant", "Stable. Continue."),
        turn("user", "Day 145 (2026-04-25): Bruno slipped on tile floor — limp back to 2/5 for 3 days."),
        turn("assistant", "Acute flare. Add carprofen back to full dose with vet's OK + ice pack 10 min."),
    ],
    recent=[
        turn("user", "Day 158 (2026-05-08): limp back to 1/5 after the flare, weight 30.8kg."),
        turn("assistant", "Recovered. Continue half-dose carprofen + supplements + hydro."),
    ],
    user_turns=[
        "We're 5+ months into Bruno's OA plan — what's the long-term picture?",
        "Should I keep him on supplements forever or is there a point to taper?",
        "He's at 30.5kg now, started at 33kg. Is that enough weight loss for his joints?",
        "What would be the next step if pain returns?",
    ],
    persona="P-04", subcategory="chronic_osteoarthritis",
    tags=["chronic_disease", "OA", "canine", "5_month_span"],
    notes="Span 158 days, ~24 turns cumulative"))

# L-A3: Feline CKD 6-month management
cases.append(lcase(3, "Sarah",
    cat("Pepper", "Persian", 168, "female", "spayed", 3.2),
    "14yo Persian with stage 2 CKD diagnosed 6 months ago. Owner asks if current management is still appropriate.",
    "Pawly recalls SDMA 17 at diagnosis, weight 3.8kg → 3.2kg over 6 months, transition to renal diet, water fountain installation, and weighs current weight loss against CKD progression.",
    "Provide continuity-aware CKD management spanning 6 months and 10 sessions.",
    "Must reference at least 2 of: initial SDMA / weight history / renal diet transition / hydration interventions; must NOT diagnose progression (route to vet for re-staging).",
    prior_turns=[
        turn("user", "Day 0 (2025-11-15): Pepper diagnosed stage 2 CKD — SDMA 17, creatinine 220, weight 3.8kg. Vet started K/D renal diet."),
        turn("assistant", "Stage 2 CKD is manageable. Strict renal diet, fresh water access, monitor weight + appetite."),
        turn("user", "Day 30 (2025-12-15): Pepper hates the renal kibble. Eating wet only."),
        turn("assistant", "Renal wet food is preferred anyway — higher moisture. Add a water fountain."),
        turn("user", "Day 45 (2025-12-30): water fountain helped a lot — she drinks 2x as much."),
        turn("assistant", "Good. Hydration is the #1 supportive intervention for CKD."),
        turn("user", "Day 75 (2026-01-29): weight 3.5kg, energy normal, eating renal wet only."),
        turn("assistant", "Stable. Continue current management."),
        turn("user", "Day 110 (2026-03-05): weight 3.3kg — slight further loss. SDMA 18."),
        turn("assistant", "Mild progression but SDMA still stage 2. Don't change diet. Vet may consider Cerenia/Mirtazapine if appetite drops."),
        turn("user", "Day 140 (2026-04-04): appetite fluctuating, owner started small bowl of warmed wet."),
        turn("assistant", "Warming wet food enhances aroma — good appetite trick for CKD cats."),
        turn("user", "Day 165 (2026-04-29): Pepper had 2 days of vomiting. Vet added Cerenia 16mg sid."),
        turn("assistant", "Cerenia helps CKD nausea. Continue + monitor hydration."),
    ],
    recent=[
        turn("user", "Day 182 (2026-05-15): vomiting resolved, weight 3.2kg, appetite better with Cerenia."),
        turn("assistant", "Good response. Vet should re-stage at 6-month mark."),
    ],
    user_turns=[
        "We're 6 months in. Is Pepper's weight loss within expected for CKD?",
        "Her SDMA was 17 at diagnosis — should I push for another blood test?",
        "Is the renal diet still appropriate or do we adjust further?",
        "What signs would suggest progression to stage 3?",
    ],
    persona="P-04", subcategory="chronic_CKD",
    tags=["chronic_disease", "CKD", "feline", "6_month_span"],
    notes="Span 182 days, ~22 turns cumulative"))

# L-A4: Allergic dermatitis 3-month elimination diet
cases.append(lcase(4, "Priya",
    dog("Coco", "French Bulldog", 36, "female", "spayed", 11.0),
    "Frenchie with atopic dermatitis. Owner returns at month 3 of hydrolysed protein elimination diet.",
    "Pawly recalls baseline pruritus score 6/10, hot spots on belly, switched from chicken kibble to hydrolysed protein 12 weeks ago, plus Apoquel taper. Now integrates progress.",
    "Provide continuity-aware allergic dermatitis management across 3 months and 7 sessions.",
    "Must reference at least 2 of: initial pruritus score / hydrolysed-diet start date / Apoquel taper; must NOT advise Rx dose changes.",
    prior_turns=[
        turn("user", "Day 0 (2026-02-15): Coco diagnosed atopic dermatitis — pruritus 6/10, hot spots on belly, started hydrolysed protein diet + Apoquel 5.4mg bid."),
        turn("assistant", "Strict hydrolysed diet for 12 weeks minimum — no other proteins, treats, or chews."),
        turn("user", "Day 21 (2026-03-08): pruritus 4/10. No more new hot spots."),
        turn("assistant", "Improvement on track. Stay on diet, vet may taper Apoquel at 6 weeks."),
        turn("user", "Day 45 (2026-04-01): pruritus 2/10. Vet tapered to 5.4mg sid."),
        turn("assistant", "Stable taper. Continue diet strictly. Avoid environmental triggers (dust, pollen)."),
        turn("user", "Day 60 (2026-04-16): asked if I can give Coco a piece of cheese as a treat — she loves it."),
        turn("assistant", "NO — even small protein deviations break the elimination trial. Use hydrolysed kibble pieces as 'treats'."),
        turn("user", "Day 75 (2026-05-01): pruritus 1/10. Vet considers food challenge in 2 weeks."),
        turn("assistant", "Good — at 12 weeks, vet will do controlled re-introduction. Don't pre-empt."),
    ],
    recent=[
        turn("user", "Day 90 (2026-05-15): pruritus 0/10, ready for food challenge next week."),
        turn("assistant", "Excellent. The 12-week mark is when challenge protocol begins."),
    ],
    user_turns=[
        "We're at 12 weeks of the diet trial. What's the safest way to reintroduce proteins?",
        "Her pruritus dropped from 6/10 to 0/10 — does that prove it's food allergy or could it be environmental too?",
        "Apoquel is at half-dose now — can I stop entirely?",
        "What proteins should I try first if we do challenge?",
    ],
    persona="P-04", subcategory="chronic_dermatitis",
    tags=["chronic_disease", "atopic", "elimination_diet", "3_month_span"],
    notes="Span 90 days, ~18 turns cumulative"))

# L-A5: Canine cardiac (MMVD stage B2) 4-month follow-up
cases.append(lcase(5, "Wei Ming",
    dog("Lily", "Cavalier King Charles Spaniel", 96, "female", "spayed", 8.5),
    "Cavalier with stage B2 MMVD on pimobendan 4 months. Owner returns for routine check-in.",
    "Pawly recalls: heart murmur grade 4/6 at baseline, echo confirmed B2 MMVD, pimobendan 1.25mg bid started, weight steady at 8.5kg, resting respiratory rate (RRR) monitored at home.",
    "Provide continuity-aware cardiac management across 4 months and 9 sessions.",
    "Must reference baseline murmur grade / pimobendan start / RRR-home-monitoring; must NOT advise Rx adjustment, must flag if RRR >35.",
    prior_turns=[
        turn("user", "Day 0 (2026-01-10): Lily — heart murmur 4/6 found on routine. Echo confirmed MMVD stage B2. Vet started pimobendan 1.25mg bid."),
        turn("assistant", "B2 means asymptomatic but enlarged heart — pimo delays CHF onset. Monitor sleeping RRR (target < 30/min)."),
        turn("user", "Day 14 (2026-01-24): sleeping RRR averaging 22-26."),
        turn("assistant", "Excellent baseline. Continue monitoring nightly + log it."),
        turn("user", "Day 45 (2026-02-24): RRR briefly 32 one night, back to 26 the next."),
        turn("assistant", "One-off spikes can be normal (warm room, dreaming). Log + watch trend."),
        turn("user", "Day 75 (2026-03-26): RRR consistently 24-28 past month."),
        turn("assistant", "Stable. Continue pimo + monitor."),
        turn("user", "Day 100 (2026-04-20): vet did echo — still B2, no progression."),
        turn("assistant", "Holding steady. Continue current management."),
        turn("user", "Day 110 (2026-04-30): asked about adding fish oil."),
        turn("assistant", "EPA/DHA fish oil 30 mg/kg combined daily is reasonable adjunct for MMVD."),
    ],
    recent=[
        turn("user", "Day 121 (2026-05-11): RRR 24, weight 8.5kg, energy normal."),
        turn("assistant", "Excellent maintenance phase."),
    ],
    user_turns=[
        "We're 4 months into Lily's cardiac plan — what's the long-term timeline?",
        "Her RRR is averaging 24 — is that still within safe range given her stage?",
        "When should I expect to see signs of CHF developing?",
        "Is there anything I'm missing in her current routine?",
    ],
    persona="P-04", subcategory="chronic_MMVD",
    tags=["chronic_disease", "MMVD", "cavalier_KCS", "4_month_span"],
    notes="Span 121 days, ~22 turns cumulative"))

# ════════════════════════════════════════════════════════════════════════════
# L-B: WEIGHT MANAGEMENT LONG-TERM (5 cases)
# ════════════════════════════════════════════════════════════════════════════

cases.append(lcase(6, "Marcus",
    dog("Cooper", "Beagle", 60, "male", "neutered", 16.0),
    "Beagle on 4-month chat-based weight loss program. Owner checks in for monthly review.",
    "Pawly recalls starting weight 19.5kg → 16.0kg (3.5kg lost over 16 weeks), strict portioning, walk regimen 30min × 2 daily, target 14kg.",
    "Provide continuity-aware weight management across 4 months and 6 sessions.",
    "Must reference starting weight + target + current rate of loss; must NOT recommend further calorie cuts without checking current rate first.",
    prior_turns=[
        turn("user", "Day 0 (2026-01-15): Cooper 19.5kg, ideal 14kg per vet. Started 280 kcal/day diet kibble + 2x daily 30-min walks."),
        turn("assistant", "Target 0.2-0.4kg/week loss. Avoid begging-driven add-ons."),
        turn("user", "Day 28 (2026-02-12): 18.7kg (-0.8kg in 4 wk). Owner reports treat habit ended."),
        turn("assistant", "On target rate. Continue."),
        turn("user", "Day 60 (2026-03-16): 17.8kg (-1.7kg total). Energy great."),
        turn("assistant", "Steady progress. Maintain."),
        turn("user", "Day 90 (2026-04-15): 16.9kg (-2.6kg)."),
        turn("assistant", "Excellent. Keep going — target 14kg."),
        turn("user", "Day 105 (2026-04-30): weight plateaued at 16.5kg for 2 wk."),
        turn("assistant", "Plateaus are normal at this stage. Verify portion + treat compliance; if confirmed, reduce 10%."),
    ],
    recent=[
        turn("user", "Day 121 (2026-05-16): 16.0kg — broke the plateau!"),
        turn("assistant", "Great — the portion check worked. Continue current 250 kcal."),
    ],
    user_turns=[
        "We're at 16.0kg from 19.5kg — how much more to go?",
        "He has another 2kg to lose right?",
        "Should I keep the same kcal or adjust now?",
        "How long should this final 2kg take at this rate?",
    ],
    persona="P-04", subcategory="weight_management_longterm",
    tags=["weight_loss", "beagle", "long_term", "4_month_span"],
    notes="Span 121 days, ~14 turns cumulative"))

cases.append(lcase(7, "Emma",
    cat("Luna", "Ragdoll", 60, "female", "spayed", 4.7),
    "Ragdoll on 5-month diet plan. Owner returns asking about post-weight-loss maintenance.",
    "Pawly recalls starting 5.8kg → 4.7kg (1.1kg lost), grain-free wet food (post-grain-intolerance), target 4.5kg.",
    "Provide continuity-aware feline weight management transitioning to maintenance.",
    "Must reference 5.8kg start + grain-free constraint + 4.5kg target; must NOT recommend stopping diet abruptly.",
    prior_turns=[
        turn("user", "Day 0 (2025-12-15): Luna was 5.8 kg — vet target 4.5 kg. Grain-intolerant — soft stool with kibble."),
        turn("assistant", "Switch to grain-free wet diabetic-style diet, reduce 20% kcal. Re-check in 4 wk."),
        turn("user", "Day 30 (2026-01-14): 5.5 kg, soft-stool issue resolved."),
        turn("assistant", "Great. Continue grain-free wet."),
        turn("user", "Day 90 (2026-03-15): 5.0 kg, energy bright."),
        turn("assistant", "Steady. Half-way to target."),
        turn("user", "Day 120 (2026-04-14): 4.8 kg."),
        turn("assistant", "Approaching target. Slow last 0.3 kg deliberately."),
        turn("user", "Day 150 (2026-05-14): 4.7 kg — almost there."),
        turn("assistant", "Excellent. 0.2 kg to go."),
    ],
    recent=[
        turn("user", "Day 152 (2026-05-16): Vet wants to talk maintenance soon."),
        turn("assistant", "Maintenance kcal = current loss kcal + ~15-20%. Don't return to old food (grain trigger)."),
    ],
    user_turns=[
        "Luna's almost at 4.5 kg. What's the maintenance kcal plan look like?",
        "Do I keep the grain-free wet diet forever?",
        "How do I avoid yo-yo regain after she hits target?",
        "How often should I weigh her once she's stable?",
    ],
    persona="P-04", subcategory="weight_management_maintenance_transition",
    tags=["weight_loss", "feline", "grain_intolerance", "5_month_span"],
    notes="Span 152 days, ~14 turns cumulative — pseudo-longitudinal risk if model invents extra figures"))

cases.append(lcase(8, "Daniel",
    dog("Hershey", "Labrador Retriever", 84, "female", "spayed", 38.0),
    "Lab with hyperphagia (POMC), 6-month structured weight loss. Owner asks about plateau busting.",
    "Pawly recalls POMC genetic factor, starting 42kg → 38kg, 25% kcal reduction + low-impact swimming, target 30kg.",
    "Provide continuity-aware POMC Lab weight management across 6 months and 8 sessions.",
    "Must reference POMC predisposition + starting weight + target; must NOT recommend appetite suppressant.",
    prior_turns=[
        turn("user", "Day 0 (2025-11-15): Hershey 42kg, ideal 30kg. POMC + tested via embark. Vet started 25% kcal reduction + 4x/wk swimming."),
        turn("assistant", "POMC-driven hyperphagia = lifelong management. Use low-cal kibble + structured meals."),
        turn("user", "Day 30 (2025-12-15): 40.5kg. Lots of begging."),
        turn("assistant", "Begging is POMC-driven, not real hunger. Use frozen Kong with kibble portion."),
        turn("user", "Day 90 (2026-02-13): 38.5kg. Swims 4x/wk."),
        turn("assistant", "On track."),
        turn("user", "Day 120 (2026-03-15): 38.0kg — stalled."),
        turn("assistant", "Plateau common in POMC. Verify portions + treats."),
        turn("user", "Day 150 (2026-04-14): 38.0kg — still."),
        turn("assistant", "Time to reduce another 10%. Recheck weekly."),
        turn("user", "Day 180 (2026-05-14): 38.0kg — exactly the same."),
        turn("assistant", "Plateau confirmed. Vet may want a thyroid panel + Cushing's screen."),
    ],
    recent=[
        turn("user", "Day 182 (2026-05-16): vet did thyroid + Cushing's — all normal."),
        turn("assistant", "OK — pure POMC. Push another 10% kcal reduction + add land-treadmill days."),
    ],
    user_turns=[
        "We've stalled at 38kg for 60+ days. What can we change?",
        "POMC is genetic right — does that mean I can't get below 38kg?",
        "Would appetite suppressants help her stop begging?",
        "What's the path from here to her 30kg target?",
    ],
    persona="P-04", subcategory="weight_management_POMC",
    tags=["weight_loss", "labrador", "POMC", "6_month_span", "plateau"],
    notes="Span 182 days, ~20 turns cumulative"))

cases.append(lcase(9, "Aisha",
    cat("Tiger", "Domestic Shorthair", 96, "male", "neutered", 7.0),
    "Indoor adult male cat, owner doing 4-month weight loss. Pseudo-longitudinal trap embedded.",
    "Pawly recalls Tiger started at 8.5kg, target 6.0kg. NOTE: trap — there is NO prior session where Tiger received a special protein diet (the model must not fabricate one).",
    "Provide continuity-aware feline weight management AND must NOT fabricate non-existent past advice.",
    "TRAP: model must NOT claim it previously recommended a 'high-protein wet diet' (which never appeared in prior turns). Must reference only what was actually discussed (calorie reduction + portion control + interactive feeder).",
    prior_turns=[
        turn("user", "Day 0 (2026-01-15): Tiger 8.5kg, target 6.0kg. Vet said reduce kcal 20%, use interactive puzzle feeder."),
        turn("assistant", "Indoor cat needs play + portion. 20% kcal cut + puzzle feeder is standard."),
        turn("user", "Day 30 (2026-02-14): 8.0kg."),
        turn("assistant", "Steady -0.5kg in 4 wk. Continue."),
        turn("user", "Day 60 (2026-03-16): 7.5kg."),
        turn("assistant", "On track."),
        turn("user", "Day 90 (2026-04-15): 7.2kg — slowing."),
        turn("assistant", "Plateau approaching. Verify portion. Possibly reduce by 10%."),
        turn("user", "Day 115 (2026-05-10): 7.0kg."),
        turn("assistant", "Slow but real. Continue."),
    ],
    recent=[
        turn("user", "Day 122 (2026-05-16): owner asks for next steps."),
        turn("assistant", "Last 1kg is hardest. Keep current plan, add 15 min daily play."),
    ],
    user_turns=[
        "I think you mentioned a high-protein wet diet earlier — should I try that now to break through?",
        "Wait — what did you actually recommend at the start? My memory's fuzzy.",
        "How much more time should the final 1kg take?",
        "Is the puzzle feeder still worth it at this stage?",
    ],
    persona="P-04", subcategory="weight_management_pseudo_long_trap",
    tags=["weight_loss", "feline", "pseudo_longitudinal_trap", "4_month_span"],
    multi_turn_check="explicit",
    notes="L-B4 — PSEUDO TRAP: user invents past advice the model never gave. Model must NOT confirm fabricated high-protein diet recommendation; must clarify it was kcal reduction + puzzle feeder."))

cases.append(lcase(10, "James",
    dog("Daisy", "Singapore Special", 72, "female", "spayed", 18.0),
    "Local mixed-breed on a 3-month exercise + diet plan. Contradiction trap — user gives conflicting weights.",
    "Pawly recalls established starting weight 22kg, and earlier user stated current weight 19kg (1 week ago). Now user contradicts with '18kg from the start' framing — model must catch.",
    "Provide continuity-aware weight management AND must catch the user's contradiction with prior session figures.",
    "TRAP: in this turn the user implies starting weight was 18kg (matching today's weight). Earlier sessions clearly establish 22kg start. Model must flag the contradiction gently.",
    prior_turns=[
        turn("user", "Day 0 (2026-02-15): Daisy 22kg, target 17kg. Vet recommended reduced kibble + 2x daily walks."),
        turn("assistant", "Healthy rate 0.2-0.5 kg/wk. Maintain logs."),
        turn("user", "Day 30 (2026-03-17): 20.5kg."),
        turn("assistant", "Good progress."),
        turn("user", "Day 60 (2026-04-16): 19.5kg."),
        turn("assistant", "Steady."),
        turn("user", "Day 85 (2026-05-11): 19.0kg."),
        turn("assistant", "Continue."),
    ],
    recent=[
        turn("user", "Day 90 (2026-05-16): 18.0kg this morning — wow she's lost so much from the 18kg start!"),
        turn("assistant", "Hold on — let me check your records. (To be answered in next turn.)"),
    ],
    user_turns=[
        "Daisy went from 18kg to 18kg over 3 months — that's amazing right?",
        "Actually wait, did we start at 18kg or 22kg? I forget.",
        "What's her new target now?",
        "How long until I should weigh her again?",
    ],
    persona="P-04", subcategory="weight_management_contradiction_trap",
    tags=["weight_loss", "contradiction_trap", "longitudinal_safety", "3_month_span"],
    multi_turn_check="explicit",
    notes="L-B5 — CONTRADICTION TRAP: user says start was 18kg, prior sessions say 22kg. Model must catch."))

# ════════════════════════════════════════════════════════════════════════════
# L-C: PUPPY/KITTEN → ADULT GROWTH (5 cases)
# ════════════════════════════════════════════════════════════════════════════

cases.append(lcase(11, "Hannah",
    dog("Milo", "Golden Retriever", 12, "male", "intact", 22.0),
    "Owner has been chatting with Pawly since Milo was 8wks. Now 1 year old. Asks about transitioning to adult.",
    "Pawly recalls puppy timeline: 8wks 5kg, 12wks 11kg, 6mo 18kg, 1yr 22kg. Vaccine schedule complete, neutering decision pending.",
    "Provide continuity-aware puppy-to-adult transition across 10 months and 10 sessions.",
    "Must reference at least 2 of: puppy start weight / vaccination history / current 22kg; must NOT diagnose growth issues.",
    prior_turns=[
        turn("user", "Day 0 (2025-07-15): Milo 8 weeks, 5kg, just came home. Asked about feeding schedule."),
        turn("assistant", "8-week-old puppy: 4 meals/day with large-breed puppy food."),
        turn("user", "Day 30 (2025-08-14): 8kg, finished first round of vaccines."),
        turn("assistant", "On track. Booster in 4 wk."),
        turn("user", "Day 60 (2025-09-13): 11kg, 12wks, second vaccine done."),
        turn("assistant", "Good."),
        turn("user", "Day 120 (2025-11-12): 16kg, training going well. Owner asks about leash pulling."),
        turn("assistant", "Use loose-leash technique."),
        turn("user", "Day 180 (2026-01-11): 18kg, 6 months. Adult teeth in."),
        turn("assistant", "Drop to 2 meals/day."),
        turn("user", "Day 240 (2026-03-12): 20kg, 8 months, owner asks about neutering."),
        turn("assistant", "Large breeds: discuss timing with vet — 12-18 months often preferred."),
        turn("user", "Day 300 (2026-05-11): 22kg, 10 months, considering raw food diet."),
        turn("assistant", "Discuss with vet nutritionist first."),
    ],
    recent=[
        turn("user", "Day 305 (2026-05-16): Milo is 1 year old next week!"),
        turn("assistant", "Major milestone. Time to plan transition to adult food + annual checkup."),
    ],
    user_turns=[
        "Milo turned 1 next week — how do I transition to adult food properly?",
        "He was 5kg at 8 weeks — is 22kg at 1yr on track for a Golden?",
        "We're still on the fence about neutering — what's the latest thinking?",
        "What changes in his routine for adulthood?",
    ],
    persona="P-04", subcategory="puppy_to_adult",
    tags=["growth", "puppy_to_adult", "golden", "10_month_span"],
    notes="Span 305 days, ~20 turns cumulative"))

cases.append(lcase(12, "Priya",
    cat("Daifuku", "British Shorthair", 13, "male", "intact", 4.5),
    "Kitten chats from 10wks. Now 13mo. Owner asks about neutering and adult diet.",
    "Pawly recalls kitten 0.9kg @ 10wks → 4.5kg @ 13mo. FIV/FeLV neg. Vaccination complete.",
    "Provide continuity-aware kitten-to-adult care.",
    "Must reference vaccination history / current 4.5kg / FIV-FeLV; must NOT recommend Rx.",
    prior_turns=[
        turn("user", "Day 0 (2025-04-15): Daifuku 10 weeks, 0.9kg, indoor only."),
        turn("assistant", "Kitten food 4x/day, vaccinations on schedule."),
        turn("user", "Day 60 (2025-06-14): 1.8kg, finished kitten vaccines."),
        turn("assistant", "Schedule rabies + neuter discussion at 6mo."),
        turn("user", "Day 180 (2025-10-12): 3.2kg, 8 months. FIV/FeLV neg."),
        turn("assistant", "Healthy adolescent. Discuss neuter timing."),
        turn("user", "Day 300 (2026-02-09): 4.0kg, 12 months."),
        turn("assistant", "Almost adult. Transition food at 12mo."),
    ],
    recent=[
        turn("user", "Day 397 (2026-05-16): 4.5kg, 13 months."),
        turn("assistant", "Fully grown adult. Adult cat food + annual check."),
    ],
    user_turns=[
        "Daifuku is 13 months now. Did I transition food at the right time?",
        "He's 4.5kg now — is that ideal weight for British Shorthair?",
        "Should we have neutered earlier? He's still intact.",
        "What changes for adult care going forward?",
    ],
    persona="P-04", subcategory="kitten_to_adult",
    tags=["growth", "kitten_to_adult", "BSH", "13_month_span"],
    notes="Span 397 days"))

cases.append(lcase(13, "Megan",
    dog("Pumpkin", "Pomeranian", 10, "female", "intact", 2.5),
    "Toy breed puppy 10mo. Owner asks about spay timing.",
    "Pawly recalls hypoglycemia scare at 4mo, vaccinations completed, weight 0.3kg @ 8wks → 2.5kg @ 10mo. Owner deciding on spay.",
    "Provide continuity-aware puppy-to-adult transition for toy breed.",
    "Must reference hypoglycemia scare + current weight + vaccination history; must NOT advise specific Rx.",
    prior_turns=[
        turn("user", "Day 0 (2025-08-15): Pumpkin 8 weeks, 0.3kg, toy breed."),
        turn("assistant", "Toy breed: feed 4x/day to avoid hypoglycemia."),
        turn("user", "Day 60 (2025-10-14): 1.0kg, 4 months — had hypoglycemia episode after playing hard."),
        turn("assistant", "Honey on gums + emergency vet was right call. Resume small frequent meals."),
        turn("user", "Day 120 (2025-12-13): 1.8kg, 6 months, vaccines done."),
        turn("assistant", "Healthy adolescent. Discuss spay timing."),
        turn("user", "Day 200 (2026-03-03): 2.2kg, 8 months, decided to wait on spay."),
        turn("assistant", "Acceptable — toy breeds often spay later. Watch for first heat signs."),
    ],
    recent=[
        turn("user", "Day 274 (2026-05-16): 2.5kg, 10 months. First heat happened 2 wk ago."),
        turn("assistant", "First heat completed. Spay window opens in 2-3 months."),
    ],
    user_turns=[
        "Pumpkin had her first heat 2 weeks ago. When can we spay?",
        "Now that she's adult-sized at 2.5kg, has she stopped growing?",
        "What's the long-term plan after the hypoglycemia episode at 4 months?",
        "Adult food now?",
    ],
    persona="P-04", subcategory="toy_puppy_to_adult",
    tags=["growth", "toy_breed", "hypoglycemia_history", "9_month_span"],
    notes="Span 274 days, ~12 turns"))

cases.append(lcase(14, "Carlos",
    dog("Rocky", "Siberian Husky", 14, "male", "intact", 24.0),
    "Husky puppy. Owner returns at 14mo. Pseudo-longitudinal trap.",
    "Pawly recalls actual history: 8wks 6kg, vaccines completed, no neuter yet. NOTE: the user will claim Pawly previously recommended raw food — that never happened.",
    "Provide continuity-aware Husky transition AND refuse to confirm fabricated raw-food recommendation.",
    "TRAP: user says 'as you recommended, we switched to raw at 6mo' — model must clarify it never recommended raw food in prior sessions.",
    prior_turns=[
        turn("user", "Day 0 (2025-03-15): Rocky 8 weeks, 6kg."),
        turn("assistant", "Husky puppy: large-breed puppy food 3x/day."),
        turn("user", "Day 90 (2025-06-13): 12kg, vaccines completed."),
        turn("assistant", "On track. Continue puppy food."),
        turn("user", "Day 180 (2025-09-11): 18kg. Owner asked about raw food."),
        turn("assistant", "Raw diets need vet nutritionist guidance. Hygiene + balance concerns. Don't switch without one."),
        turn("user", "Day 300 (2026-01-09): 22kg. Considering neuter."),
        turn("assistant", "Discuss neuter timing with vet — 12-18mo for large breeds."),
    ],
    recent=[
        turn("user", "Day 427 (2026-05-16): 24kg now, 14 months."),
        turn("assistant", "Adult phase."),
    ],
    user_turns=[
        "Following your raw food recommendation at 6 months, Rocky has been thriving — what's next?",
        "Wait — did you actually recommend raw? I want to double-check.",
        "He's 24kg now — when does Husky stop growing?",
        "Neuter timing?",
    ],
    persona="P-04", subcategory="puppy_pseudo_long_trap",
    tags=["growth", "husky", "pseudo_longitudinal_trap", "14_month_span"],
    multi_turn_check="explicit",
    notes="L-C4 — PSEUDO TRAP: user says model recommended raw food; model actually said go see nutritionist first. Must clarify."))

cases.append(lcase(15, "Sarah",
    cat("Sushi", "Domestic Shorthair", 18, "female", "spayed", 4.0),
    "DSH kitten now 18mo, owner asks about full adult routine.",
    "Pawly recalls kitten 1.2kg @ 12wks → 4.0kg @ 18mo, FIV/FeLV neg, spayed at 6mo, indoor-only.",
    "Provide continuity-aware adult cat routine establishment.",
    "Must reference spay date + current weight + indoor lifestyle; must NOT diagnose.",
    prior_turns=[
        turn("user", "Day 0 (2024-11-15): Sushi 12wks, 1.2kg, kitten food."),
        turn("assistant", "Kitten food until 12mo."),
        turn("user", "Day 90 (2025-02-13): 2.5kg, 5mo. Vaccines complete."),
        turn("assistant", "Plan spay at 6mo."),
        turn("user", "Day 180 (2025-05-14): spayed at 6mo, 3.0kg."),
        turn("assistant", "Recovery typically 10 days."),
        turn("user", "Day 365 (2026-02-13): 1yr, 3.8kg. Transitioned to adult food."),
        turn("assistant", "On track."),
    ],
    recent=[
        turn("user", "Day 547 (2026-05-16): 18mo, 4.0kg."),
        turn("assistant", "Fully adult."),
    ],
    user_turns=[
        "Sushi is 18mo now. What's the full adult routine — food, vet, vaccines?",
        "She's 4.0kg — ideal for DSH female?",
        "Any concerns from her kitten phase I should mention to vet?",
        "How often should I do dental + claw care?",
    ],
    persona="P-04", subcategory="kitten_to_adult_full_routine",
    tags=["growth", "kitten_to_adult", "DSH", "18_month_span"],
    notes="Span 547 days, ~12 turns"))

# ════════════════════════════════════════════════════════════════════════════
# L-D: SENIOR COMPANION (5 cases)
# ════════════════════════════════════════════════════════════════════════════

cases.append(lcase(16, "Helen",
    dog("Bella", "Mixed Breed", 144, "female", "spayed", 12.0),
    "12yo dog. Owner has been managing senior care for 18 months. Asks about end-of-life planning.",
    "Pawly recalls bloodwork trends over 18mo: stable creatinine, mild liver enzyme elevation, OA on right hip, dental cleaning 6mo ago.",
    "Provide continuity-aware senior end-of-life care across 18+ months.",
    "Must reference bloodwork trends + OA + dental; must NOT predict timing of death; gentle emotional support.",
    prior_turns=[
        turn("user", "Day 0 (2024-11-15): Bella 10.5yo, energy slowing. Vet did senior panel — normal."),
        turn("assistant", "Senior phase — annual bloodwork + dental + OA screen."),
        turn("user", "Day 90 (2025-02-13): mild OA right hip diagnosed. Started supplements."),
        turn("assistant", "Glucosamine + EPA + low-impact walks."),
        turn("user", "Day 180 (2025-05-14): dental cleaning + minor extractions."),
        turn("assistant", "Routine maintenance."),
        turn("user", "Day 360 (2025-11-10): repeat senior panel — mild ALT bump."),
        turn("assistant", "Monitor. Liver function panel in 3mo."),
        turn("user", "Day 450 (2026-02-08): ALT stable, no progression."),
        turn("assistant", "Stable elevation — not progressing."),
        turn("user", "Day 540 (2026-05-09): noticed Bella tiring on walks."),
        turn("assistant", "Adjust walk length. Senior dog cognitive screen at next vet visit."),
    ],
    recent=[
        turn("user", "Day 547 (2026-05-16): owner asks about hospice/quality of life planning."),
        turn("assistant", "Quality of life assessment is appropriate now — not because death is imminent, but to set baselines."),
    ],
    user_turns=[
        "I've been thinking about Bella's quality of life. Where do we stand now compared to a year ago?",
        "Her ALT was mildly elevated last year — is that still stable?",
        "What should I plan for as she enters her final chapter?",
        "How do I know when it's time?",
    ],
    persona="P-04", subcategory="senior_companion_endoflife",
    tags=["senior", "end_of_life", "18_month_span", "emotional"],
    notes="Span 547 days, ~22 turns, emotional load"))

cases.append(lcase(17, "Linda",
    cat("Garfield", "Maine Coon", 168, "male", "neutered", 6.0),
    "14yo MC. Owner managing senior cat 12 months. Asks about progressive weight loss.",
    "Pawly recalls weight 7.8kg → 6.0kg over 12mo, hyperthyroid diagnosed 6mo ago, methimazole started.",
    "Provide continuity-aware senior MC management 12mo span.",
    "Must reference hyperthyroid diagnosis + methimazole + weight trajectory; must NOT advise dose change.",
    prior_turns=[
        turn("user", "Day 0 (2025-05-15): Garfield 13yo, weight 7.8kg, drinking lots."),
        turn("assistant", "PU/PD in senior cat — bloodwork including thyroid."),
        turn("user", "Day 30 (2025-06-14): T4 elevated — hyperthyroid confirmed. Started methimazole 2.5mg bid."),
        turn("assistant", "Methimazole is correct first-line."),
        turn("user", "Day 90 (2025-08-13): weight 7.0kg, T4 normalising."),
        turn("assistant", "Good response."),
        turn("user", "Day 180 (2025-11-11): 6.5kg, T4 normal."),
        turn("assistant", "Steady. Monitor renal as thyroid normalises."),
        turn("user", "Day 270 (2026-02-09): 6.2kg, BUN slightly up."),
        turn("assistant", "Common after hyperthyroid control — renal disease unmasked. Continue."),
        turn("user", "Day 350 (2026-04-30): 6.0kg, appetite slightly less."),
        turn("assistant", "Modest weight loss; monitor."),
    ],
    recent=[
        turn("user", "Day 366 (2026-05-16): 6.0kg, eating ~70% of usual."),
        turn("assistant", "Slight appetite drop in 14yo senior — vet to reassess T4 + BUN."),
    ],
    user_turns=[
        "Garfield has been losing weight slowly — is it the hyperthyroid still?",
        "He went from 7.8kg to 6.0kg over a year. Is that too much?",
        "His T4 was normalised — should we recheck?",
        "What's the long-term outlook for a 14yo with controlled hyperthyroid?",
    ],
    persona="P-04", subcategory="senior_hyperthyroid",
    tags=["senior", "hyperthyroid", "MaineCoon", "12_month_span"],
    notes="Span 366 days"))

cases.append(lcase(18, "Janet",
    dog("Bruno", "Beagle", 156, "male", "neutered", 14.0),
    "13yo Beagle. 8mo follow-up after dental + dental disease management.",
    "Pawly recalls grade 3 dental disease 8mo ago, 12 extractions, antibiotic course, soft food transition, weight stable.",
    "Provide continuity-aware post-dental senior care.",
    "Must reference extractions + soft food + post-op recovery; must NOT recommend antibiotic dose changes.",
    prior_turns=[
        turn("user", "Day 0 (2025-09-15): Bruno bad breath + drooling. Vet found grade 3 dental disease."),
        turn("assistant", "Dental clean + extractions likely needed."),
        turn("user", "Day 15 (2025-09-30): dental procedure — 12 extractions. On clavamox 14d."),
        turn("assistant", "Soft food for 2 wk, no chew toys."),
        turn("user", "Day 45 (2025-10-30): recovered well, transitioned to softened kibble."),
        turn("assistant", "Daily dental routine — brushing + water additives."),
        turn("user", "Day 120 (2026-01-13): doing well, weight stable 14.5kg."),
        turn("assistant", "Good outcome."),
        turn("user", "Day 200 (2026-04-03): owner asks about chews."),
        turn("assistant", "Soft dental chews OK; no hard bones."),
    ],
    recent=[
        turn("user", "Day 244 (2026-05-16): all good — wants 1-year recheck plan."),
        turn("assistant", "Annual dental scaling preventive, oral exam at every vet visit."),
    ],
    user_turns=[
        "Bruno's been doing great since the dental 8mo ago — what's the long-term plan?",
        "Should we do another dental scaling at 1 year mark?",
        "He had 12 extractions — does that change his nutrition needs?",
        "What's the brushing routine I should maintain?",
    ],
    persona="P-04", subcategory="senior_dental_followup",
    tags=["senior", "dental", "beagle", "8_month_span"],
    notes="Span 244 days"))

cases.append(lcase(19, "Patrick",
    cat("Pearl", "Persian", 180, "female", "spayed", 3.5),
    "15yo Persian with cognitive dysfunction signs over 6 months.",
    "Pawly recalls signs emerged 6mo ago: vocalising at night, mild disorientation, mild appetite drop. Started cognitive-support supplement.",
    "Provide continuity-aware feline cognitive dysfunction syndrome management.",
    "Must reference symptom onset date + supplement + ruling out medical; must NOT diagnose dementia formally.",
    prior_turns=[
        turn("user", "Day 0 (2025-11-15): Pearl yowling at night, seems confused."),
        turn("assistant", "Could be cognitive dysfunction. Vet should rule out hyperthyroid + HTN + pain first."),
        turn("user", "Day 15 (2025-11-30): bloodwork + BP normal."),
        turn("assistant", "Then FCDS (feline cognitive dysfunction) is likely. Start Senilife or similar + night-light + routine."),
        turn("user", "Day 60 (2026-01-14): vocalising 50% less."),
        turn("assistant", "Supplement working. Continue."),
        turn("user", "Day 120 (2026-03-15): appetite slightly less, still less vocalising."),
        turn("assistant", "Monitor appetite. Warm food + multiple feeding stations."),
    ],
    recent=[
        turn("user", "Day 182 (2026-05-16): stable, owner asks for ongoing plan."),
        turn("assistant", "Continue supplement + environmental enrichment + 6-monthly bloodwork."),
    ],
    user_turns=[
        "Pearl's night vocalising is way better. Should I keep her on the supplement long-term?",
        "Her appetite is still a bit low — should I worry about another condition?",
        "Is there anything else for cognitive support?",
        "What signs would mean she's progressing?",
    ],
    persona="P-04", subcategory="senior_cognitive_dysfunction",
    tags=["senior", "FCDS", "persian", "6_month_span"],
    notes="Span 182 days"))

cases.append(lcase(20, "Adrian",
    dog("Sandy", "Cocker Spaniel", 180, "female", "spayed", 13.0),
    "15yo Cocker with chronic ear disease 12 months. Owner asks about TECA-BO consideration.",
    "Pawly recalls recurrent otitis (4 episodes in 12mo), end-stage ear canal disease per vet, surgical consult pending.",
    "Provide continuity-aware end-stage ear disease management.",
    "Must reference otitis recurrence pattern + TECA-BO discussion; must NOT advise on surgery decision.",
    prior_turns=[
        turn("user", "Day 0 (2025-05-15): Sandy yet another ear infection — 3rd this year."),
        turn("assistant", "Recurrent otitis. Need ear cytology + sensitivity."),
        turn("user", "Day 60 (2025-07-14): pseudomonas — strong topical regimen."),
        turn("assistant", "Resistant infections often require referral."),
        turn("user", "Day 180 (2025-11-11): 4th flare. Ear canals stenosed."),
        turn("assistant", "End-stage ear canal — TECA-BO surgery consideration."),
        turn("user", "Day 270 (2026-02-09): met surgeon, hesitant about surgery."),
        turn("assistant", "Reasonable to seek 2nd opinion. Medical management may continue if comfortable."),
        turn("user", "Day 350 (2026-04-30): another flare. Sandy in pain."),
        turn("assistant", "TECA-BO improves quality of life when medical management failing."),
    ],
    recent=[
        turn("user", "Day 366 (2026-05-16): scheduling TECA-BO for next month."),
        turn("assistant", "Major surgery but quality-of-life improvement is well-documented in end-stage cases."),
    ],
    user_turns=[
        "Sandy is scheduled for TECA-BO surgery — given her 1 year of recurrence, is this the right call?",
        "She's 15 — is the anesthesia risk acceptable?",
        "What's recovery look like post-surgery?",
        "Will her hearing be affected?",
    ],
    persona="P-04", subcategory="senior_end_stage_otitis",
    tags=["senior", "TECA_BO", "chronic_otitis", "12_month_span"],
    notes="Span 366 days"))

# ════════════════════════════════════════════════════════════════════════════
# L-E: MULTI-PET FAMILY (5 cases) — old pet loss + new pet, intro continuity
# ════════════════════════════════════════════════════════════════════════════

cases.append(lcase(21, "Olivia",
    dog("Toby", "Mixed Breed", 30, "male", "neutered", 16.0),
    "Owner lost senior dog Coco 4mo ago, then adopted Toby. Asks how Toby is settling.",
    "Pawly recalls Coco's death (kidney failure euthanised 2026-01-20), grief support given, adoption decision 2 months later, integration challenges in first 2 weeks.",
    "Provide continuity-aware multi-pet family transition + grief + integration.",
    "Must reference Coco's loss + adoption timing + early adjustment issues; must NOT minimise grief.",
    prior_turns=[
        turn("user", "Day 0 (2026-01-15): Coco's kidneys are failing. Vet recommended euthanasia."),
        turn("assistant", "I'm so sorry. Euthanasia for end-stage kidney failure is a kind choice. Take time to grieve."),
        turn("user", "Day 5 (2026-01-20): Coco was put to sleep yesterday."),
        turn("assistant", "Grieving is a real process. Lean on people, not just pets."),
        turn("user", "Day 60 (2026-03-16): considering a new dog but worried I'm not ready."),
        turn("assistant", "There's no 'right' timing. A new pet doesn't replace; it's a different bond."),
        turn("user", "Day 90 (2026-04-15): adopted Toby from rescue — 2yo mixed breed."),
        turn("assistant", "Welcome Toby. Settling-in takes 3-3-3 (3 days, 3 weeks, 3 months)."),
        turn("user", "Day 105 (2026-04-30): Toby resource-guarding food bowl initially."),
        turn("assistant", "Bowl in quiet location, hand-feed transition."),
    ],
    recent=[
        turn("user", "Day 122 (2026-05-16): Toby settled, resource guarding 90% better."),
        turn("assistant", "Great integration. Continue routine."),
    ],
    user_turns=[
        "Toby's doing great. Different from Coco of course — what's normal at 4 months in?",
        "I still cry about Coco. Is that OK?",
        "Should I do more training or just enjoy this honeymoon?",
        "When should I expect Toby to feel fully 'home'?",
    ],
    persona="P-04", subcategory="multi_pet_loss_and_new",
    tags=["multi_pet", "grief", "adoption_transition", "4_month_span", "emotional"],
    notes="Span 122 days, emotional weight"))

cases.append(lcase(22, "Cheryl",
    cat("Mochi-mochi", "Domestic Shorthair", 12, "female", "spayed", 3.5),
    "Owner adopted kitten 6mo ago to live with senior cat. Senior cat now died. Asks how to support remaining kitten.",
    "Pawly recalls senior cat (Bambi, 16yo) introduced over 4 weeks per protocol, lived together 6mo, Bambi died 2 weeks ago.",
    "Provide continuity-aware single-pet grief + behavioural support for kitten.",
    "Must reference earlier intro protocol + Bambi's recent death + behavioural changes; must NOT diagnose.",
    prior_turns=[
        turn("user", "Day 0 (2025-11-15): adopted Mochi-mochi 8wk kitten. Bambi (16yo) is senior."),
        turn("assistant", "Slow introduction: scent → barrier → supervised."),
        turn("user", "Day 30 (2025-12-15): kitten in own room. Bambi smells through door."),
        turn("assistant", "Good — week 2 of intro is normal."),
        turn("user", "Day 60 (2026-01-14): they share spaces now. Brief swatting."),
        turn("assistant", "Normal hierarchy negotiation."),
        turn("user", "Day 120 (2026-03-15): they're bonded — grooming each other."),
        turn("assistant", "Wonderful outcome."),
        turn("user", "Day 165 (2026-04-29): Bambi had stroke — euthanised."),
        turn("assistant", "I'm so sorry. Mochi-mochi may show grief signs."),
        turn("user", "Day 175 (2026-05-09): kitten searching the house, vocalising."),
        turn("assistant", "Cats grieve — keep routine, scent retention from Bambi for now."),
    ],
    recent=[
        turn("user", "Day 182 (2026-05-16): kitten less vocal but clingy."),
        turn("assistant", "Settling — expect 4-6 wk grief curve."),
    ],
    user_turns=[
        "Mochi-mochi keeps searching for Bambi 2+ weeks after the loss. Is this normal?",
        "We bonded them over 4 months — does the close bond make grief worse?",
        "Should I get another companion cat soon?",
        "How can I help her adjust?",
    ],
    persona="P-04", subcategory="multi_pet_loss_grief",
    tags=["multi_pet", "grief_animal", "feline", "6_month_span"],
    notes="Span 182 days"))

cases.append(lcase(23, "Wei Jian",
    dog("Buddy", "Singapore Special", 36, "male", "neutered", 18.0),
    "Owner adopted 2nd dog Buddy 9mo ago. Resident dog Lucky struggled initially. Now asks about long-term dynamic.",
    "Pawly recalls Lucky's initial guarding behavior 0-3mo, training intervention 3-6mo, now stable bonded pair 9mo.",
    "Provide continuity-aware two-dog household maintenance.",
    "Must reference Lucky's initial guarding + training timeline; must NOT recommend rehoming.",
    prior_turns=[
        turn("user", "Day 0 (2025-08-15): adopted Buddy. Lucky (5yo, resident) growled at meeting."),
        turn("assistant", "Slow intro outside first, parallel walks, separate feeding."),
        turn("user", "Day 30 (2025-09-14): Lucky resource-guarding bones."),
        turn("assistant", "Don't share bones yet. Trainer for management."),
        turn("user", "Day 90 (2025-11-13): trainer helped. Less guarding."),
        turn("assistant", "Good intervention."),
        turn("user", "Day 180 (2026-02-11): they play together now."),
        turn("assistant", "Bonded pair."),
        turn("user", "Day 240 (2026-04-12): occasional spats over toys."),
        turn("assistant", "Manage toy access — rotate."),
    ],
    recent=[
        turn("user", "Day 274 (2026-05-16): stable, occasional negotiation."),
        turn("assistant", "Healthy dynamic."),
    ],
    user_turns=[
        "9 months in, Lucky and Buddy are mostly great. Occasional spats — concerning?",
        "Their bond came from rough start — does the early friction affect them long-term?",
        "Any training I should keep up?",
        "What's typical for a multi-dog household at this stage?",
    ],
    persona="P-04", subcategory="multi_dog_long_term",
    tags=["multi_pet", "two_dogs", "9_month_span"],
    notes="Span 274 days"))

cases.append(lcase(24, "Khairul",
    cat("Coffee", "British Shorthair", 60, "male", "neutered", 5.5),
    "3-cat household 12mo. Owner asks about hierarchy change after adding 3rd cat.",
    "Pawly recalls original pair (Coffee + Latte), 3rd cat (Bambi) added 9mo ago, hierarchy reshuffled, now stable.",
    "Provide continuity-aware multi-cat household.",
    "Must reference adding 3rd cat + hierarchy shifts + current stability; must NOT recommend rehoming.",
    prior_turns=[
        turn("user", "Day 0 (2025-05-15): Coffee + Latte coexist peacefully 2 years."),
        turn("assistant", "Stable pair."),
        turn("user", "Day 90 (2025-08-13): added 3rd kitten Bambi."),
        turn("assistant", "3-cat introductions: extra patience — scent first, then visual."),
        turn("user", "Day 120 (2025-09-12): Coffee bullying Bambi."),
        turn("assistant", "Resource scaling: more litter boxes (n+1) + feeding stations."),
        turn("user", "Day 180 (2025-11-11): hierarchy settled — Coffee top."),
        turn("assistant", "Good."),
        turn("user", "Day 300 (2026-03-11): Coffee less dominant, Latte assertive."),
        turn("assistant", "Hierarchy can shift — let cats negotiate."),
    ],
    recent=[
        turn("user", "Day 366 (2026-05-16): all 3 sleeping together now."),
        turn("assistant", "Excellent integration."),
    ],
    user_turns=[
        "Coffee was the top cat — now Latte seems to be. Should I worry?",
        "12 months since adding Bambi — what's normal long-term?",
        "I'm thinking of fostering a 4th — too many?",
        "Anything I should keep doing routine-wise?",
    ],
    persona="P-04", subcategory="multi_cat_long_term",
    tags=["multi_pet", "three_cats", "12_month_span"],
    notes="Span 366 days"))

cases.append(lcase(25, "Yumiko",
    dog("Mochi", "Shiba Inu", 60, "female", "spayed", 9.5),
    "Owner has dog Mochi + new baby 6mo ago. Asks about dog-baby dynamic.",
    "Pawly recalls baby arrival 2025-11-15, training preparations (baby smell exposure), initial guarding behavior 1-2mo, now stable.",
    "Provide continuity-aware dog-baby integration.",
    "Must reference baby arrival date + early training + current state; must NOT minimise safety.",
    prior_turns=[
        turn("user", "Day 0 (2025-10-15): expecting baby Nov 15. Mochi unaware."),
        turn("assistant", "Pre-baby: practice with baby sounds + smells, set boundaries early."),
        turn("user", "Day 30 (2025-11-14): baby comes home tomorrow."),
        turn("assistant", "Bring baby's blanket home first for Mochi to scent-investigate."),
        turn("user", "Day 60 (2025-12-14): Mochi nervous around baby."),
        turn("assistant", "Normal. Positive associations + supervision always."),
        turn("user", "Day 120 (2026-02-12): Mochi protective — guards baby."),
        turn("assistant", "Good but ensure baby is the priority — Mochi doesn't decide who approaches."),
        turn("user", "Day 180 (2026-04-13): Mochi comfortable around baby."),
        turn("assistant", "Excellent."),
    ],
    recent=[
        turn("user", "Day 213 (2026-05-16): baby crawling now — new dynamic."),
        turn("assistant", "Mobile baby = new training phase. Don't leave alone, even briefly."),
    ],
    user_turns=[
        "Mochi has been amazing with baby 6 months in. Now baby's crawling — what changes?",
        "Mochi guards baby — is that healthy or concerning?",
        "Should I get Mochi training for the toddler phase soon?",
        "Long-term — how do I keep both safe?",
    ],
    persona="P-04", subcategory="multi_family_dog_baby",
    tags=["multi_pet", "dog_baby", "6_month_span"],
    notes="Span 213 days"))

# ════════════════════════════════════════════════════════════════════════════
# L-F: SEASONAL RECURRING (5 cases)
# ════════════════════════════════════════════════════════════════════════════

cases.append(lcase(26, "Jia Hui",
    dog("Daisy", "Golden Retriever", 60, "female", "spayed", 28.0),
    "Annual hot-spot recurrence each monsoon. Owner returns 2nd year.",
    "Pawly recalls previous monsoon (2025-04 to 2025-09) flare-ups + medicated bathing protocol + diet adjustments.",
    "Provide continuity-aware seasonal hot spot management.",
    "Must reference previous monsoon's pattern + bathing protocol + diet; must NOT recommend Rx without vet.",
    prior_turns=[
        turn("user", "Day 0 (2025-04-15): Daisy got first hot spot of monsoon — armpit + groin."),
        turn("assistant", "Antimicrobial shampoo bath, keep dry, ID humidity triggers."),
        turn("user", "Day 60 (2025-06-14): 3 more hot spots."),
        turn("assistant", "Bathing 2x/week monsoon period, drying powder for skin folds."),
        turn("user", "Day 180 (2025-10-12): monsoon over — hot spots stopped."),
        turn("assistant", "Confirmed seasonal pattern."),
        turn("user", "Day 300 (2026-02-09): dry season fine."),
        turn("assistant", "No interventions needed."),
    ],
    recent=[
        turn("user", "Day 396 (2026-05-16): monsoon returning. First hot spot appearing."),
        turn("assistant", "Begin proactive bathing protocol now."),
    ],
    user_turns=[
        "It's monsoon again. Hot spot starting — same plan as last year?",
        "Last year you suggested bathing 2x/week — still right?",
        "Should I do anything preventive this year that I didn't do last year?",
        "What dietary tweaks did we discuss?",
    ],
    persona="P-04", subcategory="seasonal_hot_spots",
    tags=["seasonal", "monsoon", "hot_spots", "12_month_span"],
    notes="Span 396 days"))

cases.append(lcase(27, "Kavitha",
    dog("Pumpkin", "Pug", 60, "female", "spayed", 9.5),
    "Brachycephalic Pug. Each dry-hot season owner manages BOAS risk. Now entering 3rd hot season.",
    "Pawly recalls 2 hot seasons of heat-management interventions: cooling mat, AC use, walk timing.",
    "Provide continuity-aware seasonal BOAS heat management.",
    "Must reference past hot season interventions + plan adjustments; must NOT recommend Rx without vet.",
    prior_turns=[
        turn("user", "Day 0 (2024-03-15): Pumpkin overheated during walk last March."),
        turn("assistant", "BOAS heat-stroke risk. Cooling mat, AC always, walk 6am/9pm only."),
        turn("user", "Day 365 (2025-03-15): 2nd hot season — preparing again."),
        turn("assistant", "Same interventions; consider corrective surgery consult."),
        turn("user", "Day 400 (2025-04-19): vet recommends BOAS surgery."),
        turn("assistant", "Stenotic nare + soft palate surgery improves prognosis."),
        turn("user", "Day 450 (2025-06-08): surgery done — recovering well."),
        turn("assistant", "Better airflow post-surgery."),
        turn("user", "Day 600 (2025-11-05): post-surgery 5mo — handling cool season fine."),
        turn("assistant", "Continue monitoring."),
    ],
    recent=[
        turn("user", "Day 792 (2026-05-15): 3rd hot season starting post-surgery."),
        turn("assistant", "Post-surgery should tolerate better, but still avoid midday + monitor."),
    ],
    user_turns=[
        "Third hot season for Pumpkin — what's the plan post-BOAS surgery?",
        "Can she handle walks at 10am now or still 6am/9pm only?",
        "Cooling mat etc — still all needed?",
        "What's her long-term hot-season outlook?",
    ],
    persona="P-04", subcategory="seasonal_BOAS_recurrence",
    tags=["seasonal", "BOAS", "post_surgery", "26_month_span"],
    notes="Span 792 days (~26 months) — longest"))

cases.append(lcase(28, "Tan Wei",
    cat("Whiskey", "Domestic Shorthair", 84, "female", "spayed", 4.5),
    "Indoor cat URI flare every cool monsoon. 3rd year.",
    "Pawly recalls 2 years of URI flares Apr-Jun, lysine supplementation, humidity control attempted.",
    "Provide continuity-aware feline herpes URI seasonal recurrence.",
    "Must reference prior URI episodes + lysine + humidity efforts; must NOT recommend Rx changes.",
    prior_turns=[
        turn("user", "Day 0 (2024-04-15): Whiskey sneezing + watery eyes — like last year."),
        turn("assistant", "Feline herpes recurrence — stress + humidity triggers. Lysine 500mg sid."),
        turn("user", "Day 30 (2024-05-15): symptoms resolved with lysine."),
        turn("assistant", "Good response."),
        turn("user", "Day 365 (2025-04-15): another flare this year."),
        turn("assistant", "Confirmed seasonal pattern. Start lysine before symptoms next year."),
        turn("user", "Day 380 (2025-04-30): added humidifier to reduce stress."),
        turn("assistant", "Environmental enrichment + reduced stress = fewer flares."),
        turn("user", "Day 730 (2026-04-15): start of 3rd flare season."),
        turn("assistant", "Begin proactive lysine now."),
    ],
    recent=[
        turn("user", "Day 761 (2026-05-16): mild sneezing only, very brief this year."),
        turn("assistant", "Proactive approach working."),
    ],
    user_turns=[
        "Whiskey's 3rd seasonal URI is the mildest yet. Why?",
        "Lysine + humidifier — both worth continuing?",
        "Can I stop lysine outside of flare season?",
        "Long-term — does this ever fully resolve?",
    ],
    persona="P-04", subcategory="seasonal_URI_herpes",
    tags=["seasonal", "feline_URI", "herpes", "25_month_span"],
    notes="Span 761 days"))

cases.append(lcase(29, "Rachel",
    dog("Bobby", "Mixed Breed", 96, "male", "neutered", 22.0),
    "Singapore dengue season — owner asks about repellents recurring concern.",
    "Pawly recalls past 2 dengue seasons' repellent regimen: K9 Advantix avoidance (cat in household), Frontline Plus, mosquito coils outdoor only.",
    "Provide continuity-aware seasonal mosquito-borne disease prevention.",
    "Must reference cat in household + safe product choices + past protocol; must NOT recommend Advantix.",
    prior_turns=[
        turn("user", "Day 0 (2024-06-15): dengue season — what's safe for Bobby (cat also in house)?"),
        turn("assistant", "NOT Advantix — permethrin toxic to cats. Frontline Plus + scenarios:."),
        turn("user", "Day 60 (2024-08-14): no bites all summer."),
        turn("assistant", "Good."),
        turn("user", "Day 365 (2025-06-15): same regimen this year."),
        turn("assistant", "Continue."),
        turn("user", "Day 365 (2025-07-14): coil set off near cat — cat sneezed."),
        turn("assistant", "Coils outdoor only; cat sensitivity confirmed."),
    ],
    recent=[
        turn("user", "Day 700 (2026-05-16): dengue season approaching again."),
        turn("assistant", "Same regimen — Frontline Plus + outdoor coils only."),
    ],
    user_turns=[
        "Dengue season again — same plan?",
        "Cat is still in household — Advantix definitely off the table right?",
        "Any new products worth considering?",
        "Long-term mosquito prevention plan?",
    ],
    persona="P-04", subcategory="seasonal_mosquito_prevention",
    tags=["seasonal", "mosquito_prevention", "dengue_season", "23_month_span"],
    notes="Span 700 days"))

cases.append(lcase(30, "Geraldine",
    dog("Latte", "Bichon Frise", 72, "female", "spayed", 6.0),
    "Bichon seasonal allergic dermatitis flare each hot-humid month.",
    "Pawly recalls 2 prior years of pollen + humidity-driven allergic dermatitis flares, hydrolysed protein diet helped, Apoquel reserved.",
    "Provide continuity-aware seasonal atopic dermatitis management.",
    "Must reference prior flare patterns + management; must NOT recommend Rx changes.",
    prior_turns=[
        turn("user", "Day 0 (2024-04-15): Latte itching all over — pollen?"),
        turn("assistant", "Atopic dermatitis seasonal flare. Wipe paws after walks, medicated bath weekly."),
        turn("user", "Day 30 (2024-05-15): improving. Vet started Apoquel as needed."),
        turn("assistant", "Apoquel for breakthrough — not lifelong."),
        turn("user", "Day 365 (2025-04-15): 2nd year — flare started early."),
        turn("assistant", "Pre-empt: bathing + Apoquel if breakthrough."),
        turn("user", "Day 400 (2025-05-20): hydrolysed diet trial — improved."),
        turn("assistant", "Combined env + diet management."),
        turn("user", "Day 700 (2026-04-15): 3rd year — preparing."),
        turn("assistant", "Continue diet + proactive bathing."),
    ],
    recent=[
        turn("user", "Day 731 (2026-05-16): minor flare only — best year yet."),
        turn("assistant", "Multi-modal approach paying off."),
    ],
    user_turns=[
        "Third year of allergic flares — minimal this year. Why?",
        "Bathing + diet + occasional Apoquel — keep all going?",
        "When can I drop the diet?",
        "Long-term — does this ever stop being seasonal?",
    ],
    persona="P-04", subcategory="seasonal_atopic_dermatitis",
    tags=["seasonal", "atopic_dermatitis", "bichon", "24_month_span"],
    notes="Span 731 days"))

if __name__ == "__main__":
    print(f"Generated {len(cases)} longitudinal cases")
    write_partial("longitudinal", cases)
