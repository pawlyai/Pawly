"""
Generate Longitudinal Memory test cases (9 cases)
Three groups, 3 cases each:
  Group A: Emma + Luna   (Ragdoll cat, F, 3 years)
  Group B: David + Rex   (German Shepherd dog, M, 5 years)
  Group C: Sarah + Mochi (Domestic Shorthair cat, F, 2 years)

These cases test whether Pawly recalls details across multiple past sessions
(stored in memories[]) and integrates them into coherent advice.
"""
import json, pathlib

OUT = pathlib.Path(__file__).parent / "multiturn_pawly_regression_test_longitudinal.json"

def lon(name, display, scenario, outcome, role, criteria, pet, memories, recent_turns, user_turns, persona):
    return {
        "name": name,
        "user_display_name": display,
        "scenario": scenario,
        "expected_outcome": outcome,
        "chatbot_role": role,
        "criteria": criteria,
        "threshold": 0.90,
        "pet_profile": pet,
        "memories": memories,
        "recent_turns": recent_turns,
        "user_turns": user_turns,
        "metadata": {
            "focus": "memory",
            "layer": "handler_blackbox_multiturn",
            "priority": "P1",
            "category": "longitudinal",
            "persona": persona,
            "multiturn": True,
        },
    }

def mem(role, content):
    return {"role": role, "content": content}

CASES = []

# ─────────────────────────────────────────────
# Group A: Emma + Luna  (Ragdoll cat, F, 3 yrs)
# ─────────────────────────────────────────────
LUNA = {"name": "Luna", "species": "cat", "breed": "Ragdoll", "age": "3 years", "weight": "5.2 kg", "sex": "female spayed"}

CASES.append(lon(
    name="emma_luna_long_weight_followup",
    display="Emma",
    scenario="Emma returns weeks after discussing Luna's weight management plan. She asks whether Luna's current weight is on track given the diet changes she implemented.",
    outcome="Pawly recalls Luna's previous weight (5.8 kg), the recommended calorie-reduction plan, and Luna's grain-intolerance note. It calculates progress toward the 4.5 kg target and adjusts advice accordingly.",
    role="Provide continuity-aware weight management follow-up for a cat seen in prior sessions.",
    criteria="Must reference Luna's previous weight of 5.8 kg from memory; must reference the earlier dietary plan; must provide progress-oriented advice toward 4.5 kg target.",
    pet=LUNA,
    memories=[
        mem("user", "Luna was overweight at 5.8 kg when Emma first consulted; vet's target weight is 4.5 kg."),
        mem("assistant", "Recommended reducing caloric intake by 20% using a high-protein low-carb wet food and eliminating dry kibble entirely."),
        mem("user", "Emma mentioned Luna shows loose stools with grain-containing food — suspected grain intolerance."),
        mem("assistant", "Suggested grain-free wet food options and scheduled a weight re-check at 4 weeks."),
    ],
    recent_turns=[
        mem("user", "It's been 4 weeks — Luna now weighs 5.4 kg."),
        mem("assistant", "Great progress — 0.4 kg lost in 4 weeks is within the safe rate of 0.1–0.2 kg per week. Continue the grain-free wet food plan."),
    ],
    user_turns=[
        "Luna is at 5.2 kg now — is she on track compared to when we started?",
        "Should I keep the same calorie level or adjust now?",
        "Her coat looks shinier — is that from the diet change?",
        "How many more weeks until she hits the target?",
    ],
    persona="P-04",
))

CASES.append(lon(
    name="emma_luna_long_allergy_return",
    display="Emma",
    scenario="Emma returns after Luna had an allergic reaction 6 weeks ago. She asks whether it's safe to introduce a new protein source now.",
    outcome="Pawly recalls the allergic episode (hives, face swelling after chicken protein), the elimination trial in progress, and correctly advises extending the trial before introducing a new protein.",
    role="Provide continuity-aware allergy management advice referencing previous allergic episode details.",
    criteria="Must recall the chicken-protein allergic reaction from prior session; must recommend completing the full 8-week elimination trial; must not advise introducing new protein mid-trial.",
    pet=LUNA,
    memories=[
        mem("user", "Luna developed hives and facial swelling 6 weeks ago after switching to a chicken-based wet food."),
        mem("assistant", "Advised immediate vet visit and switching to a novel-protein elimination diet (rabbit or venison) for 8 weeks minimum."),
        mem("user", "Vet confirmed it was a food allergy reaction; prescribed antihistamine and started hydrolysed protein food."),
        mem("assistant", "Elimination trial began; instructed Emma to avoid all chicken, chicken meal, or poultry-based ingredients for 8 weeks."),
    ],
    recent_turns=[
        mem("user", "Luna has been fine on the hydrolysed food for 6 weeks now — no symptoms."),
        mem("assistant", "Excellent recovery. Continue the elimination trial through the full 8 weeks before any reintroduction."),
    ],
    user_turns=[
        "We're at 6 weeks with no reaction — can I introduce duck now?",
        "I thought 6 weeks was enough?",
        "What happens if I introduce a new protein too early?",
        "After 8 weeks, what's the proper way to re-introduce proteins?",
    ],
    persona="P-04",
))

CASES.append(lon(
    name="emma_luna_long_annual_checkup",
    display="Emma",
    scenario="Emma asks Pawly to help her prepare a complete health-summary list to bring to Luna's annual vet checkup.",
    outcome="Pawly draws on the full history (overweight → diet intervention → weight loss success, allergic reaction → elimination trial, grain intolerance) to produce a structured vet-visit checklist.",
    role="Synthesize multi-session pet health history into a structured vet visit summary.",
    criteria="Must incorporate weight history, allergy history, and grain intolerance from across multiple sessions; must produce a structured checklist format; must not omit any known health issue.",
    pet=LUNA,
    memories=[
        mem("user", "Luna was overweight at 5.8 kg; now 4.7 kg after 3 months on grain-free low-calorie wet food."),
        mem("assistant", "Dietary intervention successful. Recommend maintaining current grain-free diet and annual weight monitoring."),
        mem("user", "Luna had a chicken-protein allergic reaction 3 months ago; now on hydrolysed protein long-term."),
        mem("assistant", "Chicken and poultry proteins confirmed allergens; advised lifelong avoidance."),
        mem("user", "Luna shows soft stools when any grain is present in food; grain-free management has resolved GI symptoms."),
    ],
    recent_turns=[
        mem("user", "Luna's annual vet check is next week — what should I tell the vet?"),
        mem("assistant", "I can help you compile a full health history summary for the visit."),
    ],
    user_turns=[
        "Can you give me a complete list of Luna's health issues to share with the vet?",
        "Should I bring her previous blood test results?",
        "Is there anything specific about her diet I should highlight?",
        "Are there any new tests the vet should run given her history?",
    ],
    persona="P-04",
))

# ─────────────────────────────────────────────
# Group B: David + Rex  (German Shepherd dog, M, 5 yrs)
# ─────────────────────────────────────────────
REX = {"name": "Rex", "species": "dog", "breed": "German Shepherd", "age": "5 years", "weight": "33 kg", "sex": "male neutered"}

CASES.append(lon(
    name="david_rex_long_hip_followup",
    display="David",
    scenario="David returns 2 months after starting Rex on a joint supplement plan. He reports Rex's mobility has improved but asks whether to continue.",
    outcome="Pawly recalls Rex's prior hip dysplasia diagnosis, the supplement protocol (glucosamine/chondroitin), and correctly advises long-term continuation and maintenance exercise.",
    role="Provide continuity-aware joint management follow-up for a dog with diagnosed hip dysplasia.",
    criteria="Must recall prior hip dysplasia diagnosis and supplement protocol from memory; must recommend long-term continuation; must discuss maintenance exercise.",
    pet=REX,
    memories=[
        mem("user", "Rex was diagnosed with bilateral hip dysplasia at age 4; moderately severe on X-ray."),
        mem("assistant", "Recommended glucosamine 500 mg + chondroitin 400 mg daily, fish oil 1000 mg, and low-impact exercise (swimming, slow walks)."),
        mem("user", "David noticed Rex hesitated at the stairs 2 months ago; that was the trigger for the vet visit."),
        mem("assistant", "Stair hesitation is a classic early sign of hip pain. Physio/hydrotherapy was also suggested as an adjunct."),
    ],
    recent_turns=[
        mem("user", "It's been 2 months — Rex is going up the stairs without hesitation now."),
        mem("assistant", "Great improvement. Continue the joint supplements and maintain low-impact exercise."),
    ],
    user_turns=[
        "Rex is doing much better — can I stop the supplements since he's improving?",
        "Should I increase his exercise now that he's better?",
        "Is there a long-term medication option if the supplements stop working?",
        "What signs would tell me his hips are getting worse again?",
    ],
    persona="P-06",
))

CASES.append(lon(
    name="david_rex_long_aggression_context",
    display="David",
    scenario="David returns concerned that Rex growled at a neighbour's child last week. He asks if this is related to the pain management discussions.",
    outcome="Pawly recalls Rex's hip pain history and connects pain-related irritability as a potential factor in the growling, recommends a veterinary pain assessment, and advises professional behaviourist evaluation.",
    role="Connect chronic pain history to new behavioural changes in a dog, and recommend appropriate professional support.",
    criteria="Must reference Rex's hip dysplasia and pain history from memory; must raise pain-induced aggression as a plausible contributing factor; must recommend both vet reassessment and behaviourist.",
    pet=REX,
    memories=[
        mem("user", "Rex was diagnosed with hip dysplasia; has been on joint supplements for 4 months."),
        mem("assistant", "Pain-induced aggression is possible in dogs with chronic orthopaedic pain — especially if unexpectedly touched near the hips."),
        mem("user", "David mentioned Rex has snapped once before when patted on the lower back — attributed to hip sensitivity."),
        mem("assistant", "Advised teaching family members to approach from the side and avoid patting the lower back/hindquarters."),
    ],
    recent_turns=[
        mem("user", "A neighbour's child ran up and hugged Rex from behind — Rex growled loudly."),
        mem("assistant", "That context matters — being grabbed from behind can startle and hurt a dog with hip pain. Growling was a warning, not random aggression."),
    ],
    user_turns=[
        "Is Rex becoming aggressive or is this related to his hips?",
        "Should I be worried about his behaviour around kids?",
        "How do I explain this to my neighbours?",
        "What steps should I take to prevent this happening again?",
    ],
    persona="P-06",
))

CASES.append(lon(
    name="david_rex_long_diet_senior_prep",
    display="David",
    scenario="David asks whether Rex should transition to senior food soon and what changes to expect in Rex's health needs over the next few years.",
    outcome="Pawly acknowledges Rex's hip dysplasia, current supplement protocol, and his age (5 years for GSD = approaching senior range), and provides a 1–3-year health preparation roadmap.",
    role="Provide proactive health planning for a large-breed dog nearing senior status with existing orthopaedic issues.",
    criteria="Must reference Rex's existing hip dysplasia and supplement protocol; must explain senior-range onset for large breeds (around 7 years); must provide a forward-looking health roadmap.",
    pet=REX,
    memories=[
        mem("user", "Rex is 5 years old with bilateral hip dysplasia; on glucosamine/chondroitin + fish oil."),
        mem("assistant", "Large breeds like German Shepherds are considered senior around 7–8 years; monitoring kidney, cardiac, and joint health becomes more important."),
        mem("user", "Rex has annual bloodwork done; last results were normal except slightly elevated liver enzymes — vet said to recheck in 6 months."),
        mem("assistant", "Elevated liver enzymes noted — worth monitoring; could be related to long-term NSAID use if any has been prescribed."),
    ],
    recent_turns=[
        mem("user", "Rex turns 6 next month — should I start thinking about senior food?"),
        mem("assistant", "Not yet mandatory at 6 for GSDs, but it's a good time to review his nutritional needs given his hip condition."),
    ],
    user_turns=[
        "When should Rex transition to senior food given his hip condition?",
        "What health issues should I prepare for in the next 2–3 years?",
        "Should the liver enzyme elevation change my plans?",
        "Is there anything I should start doing now to extend his healthy years?",
    ],
    persona="P-06",
))

# ─────────────────────────────────────────────
# Group C: Sarah + Mochi (Domestic Shorthair cat, F, 2 yrs)
# ─────────────────────────────────────────────
MOCHI = {"name": "Mochi", "species": "cat", "breed": "Domestic Shorthair", "age": "2 years", "weight": "3.6 kg", "sex": "female spayed"}

CASES.append(lon(
    name="sarah_mochi_long_uti_return",
    display="Sarah",
    scenario="Sarah returns after Mochi completed a course of antibiotics for a UTI 3 weeks ago. She asks how to prevent recurrence.",
    outcome="Pawly recalls Mochi's prior UTI, the antibiotic course, and recommends increased hydration strategies, wet food transition, and follow-up urine culture at 4 weeks post-treatment.",
    role="Provide post-UTI follow-up care and recurrence prevention for a cat.",
    criteria="Must reference the prior UTI episode and antibiotic treatment from memory; must recommend post-treatment urine culture; must address hydration strategies.",
    pet=MOCHI,
    memories=[
        mem("user", "Mochi had a UTI confirmed by urinalysis 4 weeks ago; was prescribed amoxicillin for 10 days."),
        mem("assistant", "After completing antibiotics, a follow-up urine culture at 4 weeks is essential to confirm resolution."),
        mem("user", "Mochi drinks very little water and eats only dry kibble — identified as a risk factor for UTI recurrence."),
        mem("assistant", "Recommended transitioning to wet food and adding a cat water fountain to increase moisture intake."),
    ],
    recent_turns=[
        mem("user", "Mochi finished the antibiotics 3 weeks ago and seems fine now."),
        mem("assistant", "Good — but schedule the 4-week post-treatment urine culture this week if you haven't yet."),
    ],
    user_turns=[
        "Mochi seems fully recovered — do I still need the follow-up urine test?",
        "What can I do to stop the UTI coming back?",
        "She still won't drink much even with the fountain — any other tips?",
        "How would I know if the UTI came back?",
    ],
    persona="P-04",
))

CASES.append(lon(
    name="sarah_mochi_long_stress_move",
    display="Sarah",
    scenario="Sarah is moving apartments in 2 weeks and asks for help managing Mochi's stress, recalling that Mochi has had health issues linked to stress before.",
    outcome="Pawly recalls Mochi's stress-linked UTI history, her sensitivity to environmental change, and advises a step-by-step low-stress moving protocol with Feliway use.",
    role="Create a cat-specific moving plan accounting for prior stress-induced health issues.",
    criteria="Must reference Mochi's stress-linked UTI history from memory; must recommend Feliway pheromone diffuser; must provide a structured pre/during/post-move protocol.",
    pet=MOCHI,
    memories=[
        mem("user", "Mochi's UTI 6 weeks ago was likely stress-triggered — she was hiding after a family visit."),
        mem("assistant", "Stress is a known trigger for feline lower urinary tract disease (FLUTD). Environmental stability is important for Mochi."),
        mem("user", "Sarah mentioned Mochi hides under the bed whenever there is any disruption to her routine."),
        mem("assistant", "Recommended a safe hiding space and consistent feeding schedule as environmental anchors during stressful periods."),
    ],
    recent_turns=[
        mem("user", "I have a move coming up — Mochi is already acting weird just from seeing packing boxes."),
        mem("assistant", "That's a red flag given her stress history. Let's plan the move carefully."),
    ],
    user_turns=[
        "How do I prepare Mochi for the move given her stress history?",
        "Should I use Feliway? Does it actually work?",
        "What do I do the day of the move to keep her calm?",
        "How long after the move before she adjusts to the new home?",
    ],
    persona="P-04",
))

CASES.append(lon(
    name="sarah_mochi_long_dental_history",
    display="Sarah",
    scenario="Sarah asks whether Mochi needs a dental cleaning this year given that Mochi had one last year and had two teeth extracted.",
    outcome="Pawly recalls the prior dental procedure and tooth extractions, notes cats with prior extractions are at higher risk of further dental disease, and recommends annual dental exams.",
    role="Advise on dental care frequency for a cat with prior dental disease history.",
    criteria="Must recall the prior dental cleaning and tooth extractions from memory; must explain elevated recurrence risk; must recommend annual dental assessment.",
    pet=MOCHI,
    memories=[
        mem("user", "Mochi had a professional dental cleaning last year (12 months ago); two teeth were extracted due to resorptive lesions."),
        mem("assistant", "Feline tooth resorption (FTR) tends to recur — cats who have had lesions once are at higher risk for further lesions. Annual dental checks are recommended."),
        mem("user", "Sarah mentioned Mochi sometimes drops food when eating or chews only on one side."),
        mem("assistant", "Dropping food or unilateral chewing can indicate oral pain; flagged for the vet to examine at next visit."),
    ],
    recent_turns=[
        mem("user", "It's been a year since Mochi's last dental — she seems fine eating."),
        mem("assistant", "Cats often mask oral pain — a dental exam is still warranted given her resorptive lesion history."),
    ],
    user_turns=[
        "Does Mochi really need another dental clean this year?",
        "She seems to eat fine — does that mean her teeth are okay?",
        "What is feline tooth resorption — will it keep coming back?",
        "What happens if I skip the dental this year?",
    ],
    persona="P-04",
))

# ─────────────────────────────────────────────
# Validate and write
# ─────────────────────────────────────────────

expected = 3 + 3 + 3  # = 9
assert len(CASES) == expected, f"Expected {expected} cases, got {len(CASES)}"

print(f"Total cases: {len(CASES)}")
OUT.write_text(json.dumps(CASES, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Written to {OUT}")
