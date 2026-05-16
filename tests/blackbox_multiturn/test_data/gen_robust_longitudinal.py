"""
Generate Robust Longitudinal Memory test cases (9 cases) — NEW V1 robust test cases.
Different from the original 9 in gen_longitudinal.py (Emma/Luna, David/Rex, Sarah/Mochi).

Three groups, 3 cases each:
  Group A: Priya + Koko  (2-year-old female intact Ragamuffin cat, 4.5 kg)
  Group B: Marcus + Bruno (5-year-old male neutered Bulldog, 25 kg)
  Group C: Natasha + Miso (8-month-old male intact Shiba Inu, 8 kg)

These cases test whether Pawly recalls details across multiple past sessions
(stored in recent_turns) and integrates them into coherent advice.

Citation grading (Shared Rule 2): the longitudinal rubric measures
**contextual coherence**, not literal citation phrasing. The grader scores
explicit and implicit citation separately and takes the max:

  - explicit: stock phrases like "as you mentioned", "as we discussed",
    "remembering Koko's ear issue"
  - implicit: demonstrably uses prior session content without a stock phrase,
    e.g. "Building on the ear drops treatment Koko started...", "Given Bruno's
    bilious vomiting diagnosis..."

A faux-longitudinal reply that fabricates references or contradicts prior
session content still fails. Replies that completely ignore prior session
content also fail.
"""
import json, pathlib

OUT = pathlib.Path(__file__).parent / "multiturn_pawly_regression_test_robust_longitudinal.json"

# Inserted into every longitudinal criteria so the grader scores explicit and
# implicit citation separately and takes the max.
CITATION_PREAMBLE = (
    "Step 1 (CoT) — assess **contextual coherence with prior sessions**, not citation phrasing. "
    "Score two sub-signals separately and take their max as the citation score: "
    "(a) explicit citation — stock phrases like 'as you mentioned', 'as we discussed', 'remembering Koko's ear issue'; "
    "(b) implicit citation — the reply demonstrably uses prior session content without a stock phrase, "
    "e.g. 'Building on the ear drops treatment Koko started...', 'Given Bruno's bilious vomiting diagnosis...'. "
    "An implicit-only reply that uses prior content correctly passes citation. "
    "A reply that fabricates references, contradicts prior session content, or completely ignores it still fails. "
)

def lon(name, display, scenario, outcome, role, criteria, pet,
        prior_session_turns, recent_turns, user_turns, persona):
    """Build a longitudinal case.

    `prior_session_turns` is conversation from earlier sessions (older than
    `recent_turns`); both get concatenated into the case's `recent_turns`
    field so the bot sees them as continuous history.
    """
    return {
        "name": name,
        "user_display_name": display,
        "scenario": scenario,
        "expected_outcome": outcome,
        "chatbot_role": role,
        "criteria": CITATION_PREAMBLE + criteria,
        "threshold": 0.90,
        "pet_profile": pet,
        "memories": [],
        "recent_turns": prior_session_turns + recent_turns,
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


def prior_turn(role, content):
    """Helper for 'this conversation already happened earlier'."""
    return {"role": role, "content": content}

CASES = []

# ─────────────────────────────────────────────
# Group A: Priya + Koko (Ragamuffin cat, F, 2 yrs, 4.5 kg, intact)
# ─────────────────────────────────────────────
KOKO = {"name": "Koko", "species": "cat", "breed": "Ragamuffin", "age": "2 years", "weight": "4.5 kg", "sex": "female intact"}

CASES.append(lon(
    name="priya_koko_long_ear_infection_triage",
    display="Priya",
    scenario="Priya returns 2 weeks after first reporting Koko's ear scratching and head shaking. The vet confirmed otitis externa and Koko is on ear drops. Now Priya notices Koko has lost weight — she asks if the weight loss is related.",
    outcome="Pawly recalls Koko's otitis externa diagnosis and ear drop treatment from the prior session and uses this context when advising on Koko's sudden weight loss — noting that systemic illness, stress from ear pain, or reduced appetite during illness could contribute, and recommending investigation into the cause of weight loss.",
    role="Provide continuity-aware advice referencing Koko's prior otitis externa diagnosis when assessing new weight loss.",
    criteria="Must demonstrate coherent use of Koko's otitis externa diagnosis and ear drop treatment from prior session (explicit or implicit citation acceptable per Shared Rule 2); must raise the connection between the ear infection, systemic illness, or reduced appetite as a possible contributor to weight loss; must recommend vet follow-up for the weight loss.",
    pet=KOKO,
    prior_session_turns=[
        prior_turn("user", "Koko has been scratching her ears constantly and shaking her head for 4 days."),
        prior_turn("assistant", "Head shaking and ear scratching can indicate ear mites or an infection. This is a yellow triage — recommend a vet visit within 48 hours to confirm the cause."),
        prior_turn("user", "The vet confirmed otitis externa. Koko has been started on antibiotic ear drops twice daily."),
        prior_turn("assistant", "Good — otitis externa responds well to antibiotic drops when caught early. Make sure to complete the full course even if symptoms improve, and go back if she's still shaking her head after 5 days."),
    ],
    recent_turns=[
        prior_turn("user", "The ear drops seem to be helping — she's scratching less. But now I've noticed Koko seems thinner."),
        prior_turn("assistant", "It's good that the ear treatment is working. Weight loss alongside a recent illness is worth investigating further."),
    ],
    user_turns=[
        "Could Koko's weight loss be related to the ear infection she just had?",
        "She went from 4.5 kg to 4.2 kg in 2 weeks — is that significant?",
        "What else could cause weight loss in a 2-year-old cat?",
        "Do I need to take her back to the vet now or can I wait and see?",
    ],
    persona="P-04",
))

CASES.append(lon(
    name="priya_koko_long_weight_loss_thyroid",
    display="Priya",
    scenario="6 weeks after the otitis externa episode, Koko is now at 4.0 kg. The vet wants to run a thyroid test. Priya asks Pawly about hyperthyroidism in a 2-year-old cat and whether the ear infection could be connected.",
    outcome="Pawly draws on both prior sessions — the ear infection (A-1) and the weight loss (A-2) — when advising on the thyroid test, explains hyperthyroidism signs, notes that it is unusual in cats under 8 years, and advises Priya to proceed with the thyroid panel while noting other differentials (IBD, intestinal parasites).",
    role="Provide multi-session continuity-aware advice synthesising both the ear infection context and the weight loss trend when advising on hyperthyroidism.",
    criteria="Must demonstrate coherent use of both A-1 (ear infection/otitis) and A-2 (weight loss 4.5→4.2 kg) from prior sessions (explicit or implicit citation acceptable per Shared Rule 2); must explain that hyperthyroidism is unusual in young cats but not impossible; must mention differential diagnoses; must recommend proceeding with vet's thyroid panel.",
    pet=KOKO,
    prior_session_turns=[
        prior_turn("user", "Koko had otitis externa 6 weeks ago and was treated with ear drops. She recovered from the ear infection."),
        prior_turn("assistant", "Glad the ear drops worked. Completing the full course was the right call."),
        prior_turn("user", "But then I noticed Koko had lost weight — she went from 4.5 kg to 4.2 kg over 2 weeks."),
        prior_turn("assistant", "That is a notable weight loss — 0.3 kg in 2 weeks warrants investigation. I recommended seeing the vet about possible systemic illness or appetite issues linked to the ear infection."),
    ],
    recent_turns=[
        prior_turn("user", "Koko is now 4.0 kg — she's lost more weight. The vet wants to run a thyroid panel."),
        prior_turn("assistant", "Continued weight loss from 4.2 to 4.0 kg in another 4 weeks is significant. The vet is right to investigate thyroid function."),
    ],
    user_turns=[
        "Can a 2-year-old cat really get hyperthyroidism?",
        "What would the symptoms of hyperthyroidism look like beyond weight loss?",
        "Could the ear infection be connected to the weight loss and thyroid issue?",
        "Should I proceed with the thyroid test or ask for other tests first?",
    ],
    persona="P-04",
))

CASES.append(lon(
    name="priya_koko_long_health_summary",
    display="Priya",
    scenario="Priya asks Pawly to help her prepare a full health summary of Koko's recent issues to share with a new vet, since she is changing clinics.",
    outcome="Pawly draws on the full history — the otitis externa (A-1), the weight loss trajectory from 4.5 to 4.0 kg (A-2), and the pending thyroid investigation — to produce a structured and complete health summary for Koko.",
    role="Synthesize all prior session health history into a structured, complete vet-visit summary for a new clinic.",
    criteria="Must incorporate all three health episodes: otitis externa (A-1), weight loss 4.5→4.2→4.0 kg (A-2), and pending thyroid investigation (A-3); must produce a structured summary format; must not omit any known health issue from the prior sessions.",
    pet=KOKO,
    prior_session_turns=[
        prior_turn("user", "Koko had otitis externa 2 months ago — confirmed by the vet, treated with antibiotic ear drops for 2 weeks. She recovered."),
        prior_turn("assistant", "Noted — otitis externa, antibiotic ear drops, resolved after 2 weeks."),
        prior_turn("user", "Then she started losing weight. She went from 4.5 kg down to 4.0 kg over about 6 weeks."),
        prior_turn("assistant", "That's a 0.5 kg loss in 6 weeks, which is clinically significant. I recommended a vet workup."),
        prior_turn("user", "The vet has ordered a thyroid panel but results are pending. She's intact, not spayed."),
        prior_turn("assistant", "Thyroid panel is appropriate given her age and weight loss. The intact status is also relevant — reproductive health should be included in the summary."),
    ],
    recent_turns=[
        prior_turn("user", "I'm changing to a new vet clinic and want to give them a full picture of what's been going on with Koko."),
        prior_turn("assistant", "Happy to help you put together a structured health summary for the new clinic."),
    ],
    user_turns=[
        "Can you help me write a complete health summary to bring to the new vet?",
        "Should I include all the weight measurements?",
        "Is there anything about her being intact I should flag to the new vet?",
        "What tests or follow-ups should the new vet know are still pending?",
    ],
    persona="P-04",
))

# ─────────────────────────────────────────────
# Group B: Marcus + Bruno (English Bulldog, M, 5 yrs, 25 kg, neutered)
# ─────────────────────────────────────────────
BRUNO = {"name": "Bruno", "species": "dog", "breed": "English Bulldog", "age": "5 years", "weight": "25 kg", "sex": "male neutered"}

CASES.append(lon(
    name="marcus_bruno_long_vomiting_triage",
    display="Marcus",
    scenario="Bruno has been vomiting clear liquid every morning for a week. Marcus asks Pawly what might be causing this.",
    outcome="Pawly triages as yellow (bilious vomiting syndrome possible — stomach empty overnight, bile reflux), recommends a vet visit within 24–48 hours, and notes that the morning timing and clear/bile content is a characteristic pattern of BVS.",
    role="Triage morning bilious vomiting in an adult Bulldog and recommend appropriate urgency of vet assessment.",
    criteria="Must identify morning clear vomiting pattern as consistent with bilious vomiting syndrome (BVS); must triage as yellow (vet within 24–48 hours); must not dismiss or over-alarm; must explain the BVS mechanism (empty stomach, bile irritation).",
    pet=BRUNO,
    prior_session_turns=[],
    recent_turns=[
        prior_turn("user", "Bruno has been vomiting a clear foamy liquid every morning before breakfast. It's been 7 days."),
        prior_turn("assistant", "Morning vomiting of clear or bile-tinged fluid in an otherwise well dog is a classic pattern for bilious vomiting syndrome. I recommend a vet visit within 24–48 hours to confirm the diagnosis."),
    ],
    user_turns=[
        "The vet said it looks like bilious vomiting syndrome — what causes that exactly?",
        "Is this a serious condition or can we manage it at home?",
        "The vet suggested giving Bruno a late-night snack — will that actually help?",
        "Is BVS something that can be fully cured or does it come back?",
    ],
    persona="P-06",
))

CASES.append(lon(
    name="marcus_bruno_long_bvs_snack_options",
    display="Marcus",
    scenario="A week after the BVS diagnosis, Marcus asks about the best snack options for Bruno's late-night feed and whether this dietary change is safe long-term.",
    outcome="Pawly recalls Bruno's BVS diagnosis from B-1 and advises on appropriate late-night snack options for a Bulldog with BVS — small portion of plain kibble, low-fat treat, or raw carrot — noting that the goal is to buffer stomach acid overnight, and that long-term management with a late-night snack is safe and standard practice for BVS.",
    role="Provide continuity-aware snack recommendations for a dog with diagnosed bilious vomiting syndrome.",
    criteria="Must demonstrate coherent use of the BVS diagnosis from B-1 (explicit or implicit citation acceptable per Shared Rule 2); must recommend appropriate snack options for overnight stomach buffering; must address long-term safety of the approach; must flag vet reassessment if symptoms return.",
    pet=BRUNO,
    prior_session_turns=[
        prior_turn("user", "Bruno had been vomiting clear liquid every morning for a week."),
        prior_turn("assistant", "This was triaged as yellow — bilious vomiting syndrome pattern. Vet visit was recommended."),
        prior_turn("user", "The vet confirmed bilious vomiting syndrome. They suggested a late-night snack to prevent the overnight stomach-empty period."),
        prior_turn("assistant", "Late-night snack is a standard first-line intervention for BVS — it buffers acid production overnight and prevents the empty-stomach bile reflux."),
    ],
    recent_turns=[
        prior_turn("user", "We've started giving Bruno a small snack at 10pm and the morning vomiting has stopped."),
        prior_turn("assistant", "That's excellent — the late-night snack is working as intended for BVS management."),
    ],
    user_turns=[
        "What's the best type of snack to give Bruno at night for his BVS?",
        "Is a small portion of his regular kibble okay or should it be something else?",
        "How much should the snack be — I don't want him to get fat?",
        "Is it safe to do this every night long-term?",
    ],
    persona="P-06",
))

CASES.append(lon(
    name="marcus_bruno_long_skin_fold_rash",
    display="Marcus",
    scenario="Two months after the BVS diagnosis and dietary change, Marcus notices Bruno has developed a skin fold rash on his facial and body folds. He asks for advice on managing it.",
    outcome="Pawly demonstrates memory of Bruno's BVS history (B-1) and the late-night snack dietary addition (B-2) while advising on skin fold hygiene — the two issues are related through Bruno's breed (Bulldog), and Pawly should note the dietary change has not caused the rash while advising on fold hygiene, drying, and when to seek vet treatment for pyoderma.",
    role="Advise on Bulldog skin fold hygiene while demonstrating memory of the BVS vomiting and dietary change from earlier sessions.",
    criteria="Must demonstrate coherent use of B-1 (BVS vomiting diagnosis) and B-2 (dietary late-night snack change) from prior sessions (explicit or implicit citation acceptable per Shared Rule 2); must advise on skin fold hygiene and drying; must note the rash is breed-related not diet-related; must identify signs of pyoderma requiring vet visit.",
    pet=BRUNO,
    prior_session_turns=[
        prior_turn("user", "Bruno had bilious vomiting syndrome diagnosed about 2 months ago."),
        prior_turn("assistant", "BVS confirmed — managed with late-night snack as the primary intervention."),
        prior_turn("user", "We started giving him a small kibble snack at 10pm. The morning vomiting has stopped completely."),
        prior_turn("assistant", "The dietary change is working well for the BVS. Continue monitoring and see the vet if vomiting returns."),
    ],
    recent_turns=[
        prior_turn("user", "The BVS is well controlled now. But I've noticed a new problem — Bruno has red irritated skin in his face folds and under his belly folds."),
        prior_turn("assistant", "Skin fold dermatitis is very common in Bulldogs due to their anatomy. The fold environment traps moisture and bacteria."),
    ],
    user_turns=[
        "Could the new snack at night be causing Bruno's skin fold rash?",
        "How do I clean and manage the skin folds properly?",
        "How often should I clean the folds?",
        "When does a skin fold rash become serious enough to need a vet?",
    ],
    persona="P-06",
))

# ─────────────────────────────────────────────
# Group C: Natasha + Miso (Shiba Inu, M, 8 months, 8 kg, intact)
# ─────────────────────────────────────────────
MISO = {"name": "Miso", "species": "dog", "breed": "Shiba Inu", "age": "8 months", "weight": "8 kg", "sex": "male intact"}

CASES.append(lon(
    name="natasha_miso_long_appetite_loss_triage",
    display="Natasha",
    scenario="Miso has not been eating for 2 days. Natasha asks Pawly what might be causing this.",
    outcome="Pawly triages as yellow, raises both medical (gastrointestinal, infection, pain) and behavioural (intact male hormonal stress, anxiety) causes, and recommends vet assessment within 24–48 hours given the 2-day duration.",
    role="Triage a 2-day appetite loss in an intact male Shiba Inu, considering both medical and behavioural causes.",
    criteria="Must triage as yellow (vet within 24–48 hours); must raise intact male hormonal stress as a potential contributing factor; must list other medical differentials; must not dismiss 2-day anorexia as trivial.",
    pet=MISO,
    prior_session_turns=[],
    recent_turns=[
        prior_turn("user", "Miso hasn't eaten for 2 full days. He's normally enthusiastic about food."),
        prior_turn("assistant", "Two days of appetite loss in an otherwise healthy dog warrants attention. As an intact male, hormonal stress is possible but medical causes should be ruled out first. I recommend a vet visit within 24–48 hours."),
    ],
    user_turns=[
        "Could Miso's appetite loss be because he's intact? I heard that can happen.",
        "What medical reasons could cause a young dog to stop eating?",
        "How long is too long to wait before going to the vet?",
        "He's drinking water and is alert — does that change how worried I should be?",
    ],
    persona="P-04",
))

CASES.append(lon(
    name="natasha_miso_long_neuter_timing",
    display="Natasha",
    scenario="Miso has started eating again 3 days later. Natasha now asks about the best age to neuter a Shiba Inu, referencing the recent appetite episode as a factor in her thinking.",
    outcome="Pawly recalls Miso's 2-day appetite loss episode from C-1 and uses this context when discussing neuter timing — noting that hormonal stress behaviour in intact males may be a contributing factor to the prior episode, and advising on the neuter timing debate for Shiba Inus (typically 12–18 months for medium breeds).",
    role="Provide continuity-aware neuter timing advice that references the prior appetite loss episode.",
    criteria="Must demonstrate coherent use of the appetite loss episode from C-1 (explicit or implicit citation acceptable per Shared Rule 2); must advise on appropriate neuter timing for Shiba Inus (medium breed); must connect hormonal behaviour as a potential factor in the earlier appetite loss; must recommend vet consultation for individual timing decision.",
    pet=MISO,
    prior_session_turns=[
        prior_turn("user", "Miso stopped eating for 2 days at 8 months old."),
        prior_turn("assistant", "Two-day appetite loss triaged as yellow. As an intact male, hormonal stress was raised as a possible contributing factor alongside medical causes. Vet visit was recommended."),
        prior_turn("user", "The vet checked him over. No medical cause found. She thought it might be behavioural and hormonal."),
        prior_turn("assistant", "Intact male adolescence with hormonal fluctuations can cause temporary appetite changes and restlessness. Monitoring was recommended."),
    ],
    recent_turns=[
        prior_turn("user", "Miso is eating normally again now. The vet thought it was just hormonal stress."),
        prior_turn("assistant", "Good to hear he's eating again. Hormonal-related appetite changes in intact males are not uncommon during adolescence."),
    ],
    user_turns=[
        "Should I neuter Miso given the appetite issues? When is the right age for a Shiba Inu?",
        "Would neutering have prevented the appetite loss?",
        "I've read Shiba Inus can be affected by early neutering — what should I consider?",
        "What are the pros and cons of neutering at different ages for a Shiba?",
    ],
    persona="P-04",
))

CASES.append(lon(
    name="natasha_miso_long_postneuter_recovery",
    display="Natasha",
    scenario="Miso has been neutered and 2 weeks post-neuter he is very lethargic and has an inflamed suture site. Natasha asks for advice on post-op monitoring and whether this is normal.",
    outcome="Pawly references the neutering decision from C-2 (and connects it to the earlier appetite/hormonal episode from C-1) while advising on post-neuter monitoring — distinguishing normal post-op lethargy from concerning signs, explaining that suture site inflammation beyond expected healing is a red flag requiring vet review.",
    role="Advise on post-neuter recovery and complication recognition while demonstrating memory of the neutering decision and the prior appetite episode.",
    criteria="Must demonstrate coherent use of C-2 (neutering decision) and reference C-1 (prior appetite and hormonal context) from prior sessions (explicit or implicit citation acceptable per Shared Rule 2); must distinguish normal post-op lethargy from concerning signs; must flag inflamed suture site as requiring vet review; must provide post-neuter monitoring guidance.",
    pet=MISO,
    prior_session_turns=[
        prior_turn("user", "Miso had a 2-day appetite loss at 8 months which was attributed to hormonal stress."),
        prior_turn("assistant", "Hormonal appetite disruption noted — intact male adolescence was the suspected cause."),
        prior_turn("user", "We decided to neuter Miso at 12 months based on advice about medium breeds and Shiba Inus."),
        prior_turn("assistant", "12 months is a reasonable timing for neutering a medium-sized Shiba Inu — allows some maturation while managing hormonal behaviour. Surgery should be followed by careful post-op monitoring."),
    ],
    recent_turns=[
        prior_turn("user", "Miso was neutered 2 weeks ago. He's been very quiet and lethargic. His suture site looks a bit red and swollen."),
        prior_turn("assistant", "Some lethargy in the first week post-neuter is normal, but by 2 weeks most dogs are recovering well. Redness and swelling at the suture site at 2 weeks is a concern — it should be assessed by a vet."),
    ],
    user_turns=[
        "Is it normal for Miso to still be this lethargic 2 weeks after neutering?",
        "What does normal suture healing look like versus something wrong?",
        "Do I need to take him to the vet today or can I wait?",
        "What should I be checking at the suture site every day?",
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
