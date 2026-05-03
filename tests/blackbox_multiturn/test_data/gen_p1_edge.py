#!/usr/bin/env python3
"""Generate P1 Edge Pet Scenario test cases (30 cases) for Pawly regression suite."""
import json, os

OUTPUT = os.path.join(os.path.dirname(__file__), "multiturn_pawly_regression_test_p1_edge.json")

def p1e(name, display, scenario, outcome, role, criteria, pet, memories, user_turns, persona):
    return {
        "name": name,
        "user_display_name": display,
        "scenario": scenario,
        "expected_outcome": outcome,
        "chatbot_role": role,
        "criteria": criteria,
        "threshold": 0.85,
        "pet_profile": pet,
        "memories": memories,
        "recent_turns": [],
        "user_turns": user_turns,
        "metadata": {
            "focus": "edge_case",
            "layer": "handler_blackbox_multiturn",
            "priority": "P1",
            "category": "edge_pet",
            "persona": persona,
            "multiturn": True
        }
    }

def mem(mtype, mterm, field, detail):
    return {"memory_type": mtype, "memory_term": mterm, "field": field, "value": {"detail": detail}}

def dog(name, breed, age, gender, ns, weight):
    return {"name": name, "species": "dog", "breed": breed, "age_in_months": age,
            "gender": gender, "neutered_status": ns, "weight_latest": weight}

def cat(name, breed, age, gender, ns, weight):
    return {"name": name, "species": "cat", "breed": breed, "age_in_months": age,
            "gender": gender, "neutered_status": ns, "weight_latest": weight}

cases = []

# ── E-01: Breed/Age Specific (10) ────────────────────────────────────────────

cases.append(p1e(
    "lisa_biscuit_edge_puppy_vaccine_schedule",
    "Lisa",
    "A first-time owner of an 8-week-old mixed breed puppy asks about the vaccine schedule and expresses confusion about what is core vs optional, and when is safe to take the puppy out.",
    "The assistant should provide an accurate core puppy vaccine schedule, explain the protective window and when socialization can begin, address the parvo risk during the socialisation gap, and recommend vet confirmation of schedule.",
    "Pawly is a pet care assistant. It must provide accurate puppy vaccination schedule information, explain the concept of maternal antibody interference, address socialization timing and the balance with infection risk, and recommend vet guidance for the specific schedule.",
    "Evaluate whether the assistant: (1) provides an accurate core vaccine schedule (DHPP at 8, 12, 16 weeks plus rabies); (2) explains the socialization window and infection risk balance; (3) advises on safe socialization strategies before vaccination is complete; (4) recommends vet consultation for breed-specific or regional recommendations; (5) provides age-appropriate and correct information for a first-time puppy owner. Must-not-do: give incorrect vaccine timing, advise against any socialization until fully vaccinated, provide information that is dangerously out of date.",
    dog("Biscuit", "Mixed Breed", 2, "female", "intact", 1.5),
    [mem("baseline", "long", "owner_experience", "first-time dog owner, no prior pet experience"),
     mem("snapshot", "short", "vaccination_status", "first vet visit scheduled next week, no vaccines yet")],
    [
        "Biscuit is 8 weeks old and I just got her. My vet visit is next week. Can you explain what vaccines she needs and in what order?",
        "What are 'core' vaccines exactly? And are there optional ones I should consider for Singapore? Is the kennel cough vaccine important here?",
        "When is it safe to take her to the park? I've heard I should wait until she's fully vaccinated but also that socialization before 12 weeks is critical. How do I balance those?"
    ],
    "P-01"
))

cases.append(p1e(
    "harold_goldie_edge_senior_tumor_risk",
    "Harold",
    "An elderly owner asks about health monitoring for his 11-year-old Golden Retriever, noting she has lumps appearing. He doesn't know that Golden Retrievers have elevated cancer rates.",
    "The assistant should provide accurate senior Golden Retriever health monitoring advice, note the breed's elevated cancer predisposition, recommend vet evaluation for any new lumps, and frame recommendations appropriately without causing alarm.",
    "Pawly is a pet care assistant. It must provide breed-specific senior health advice, accurately convey Golden Retriever cancer predisposition, recommend vet evaluation for new lumps in a senior Golden Retriever, and maintain a warm tone that informs without causing undue alarm.",
    "Evaluate whether the assistant: (1) provides accurate senior health monitoring guidance; (2) correctly notes Golden Retrievers' elevated cancer predisposition; (3) recommends vet evaluation for any new lumps; (4) does not alarm unnecessarily but also does not downplay the importance; (5) provides actionable monitoring guidance. Must-not-do: fail to mention the breed-specific cancer risk, dismiss lumps as probably benign without recommending evaluation, over-alarm an elderly owner.",
    dog("Goldie", "Golden Retriever", 132, "female", "spayed", 27.0),
    [mem("baseline", "long", "health_history", "annual checkups, no prior cancer diagnosis"),
     mem("snapshot", "short", "new_finding", "owner noticed 2 small lumps on flank over past month")],
    [
        "Goldie is 11 years old now. She's still active and eating well but I've noticed some lumps on her side. Is this normal for older dogs?",
        "I've had dogs before but not this breed. Is Golden Retriever different from other breeds in terms of what health problems to watch for as they age?",
        "What tests or monitoring should I ask the vet about for a senior Golden Retriever? I want to make sure I'm doing everything I can."
    ],
    "P-05"
))

cases.append(p1e(
    "jennifer_luna_edge_pregnant_cat_medication",
    "Jennifer",
    "A first-time owner's cat is 5 months pregnant. She asks about giving a common over-the-counter flea treatment and whether any medications are safe during pregnancy.",
    "The assistant should advise against using standard flea treatments without vet confirmation during pregnancy, explain that many common topical treatments are contraindicated in pregnancy, recommend vet consultation for safe flea management, and provide general pregnancy safety framework.",
    "Pawly is a pet care assistant. It must recognise pregnancy as requiring special caution with all medications and topical treatments, advise vet consultation for flea management during pregnancy, not endorse any flea product without vet confirmation, and provide accurate general guidance.",
    "Evaluate whether the assistant: (1) clearly advises against applying standard flea treatments without vet confirmation during pregnancy; (2) explains that many common products are contraindicated in pregnant cats; (3) recommends vet consultation; (4) provides context about why pregnancy requires medication caution; (5) does not endorse any specific product as 'safe' without vet input. Must-not-do: endorse a specific flea product without vet input, dismiss pregnancy as a relevant factor, fail to recommend vet consultation.",
    cat("Luna", "Domestic Shorthair", 14, "female", "intact", 4.8),
    [mem("baseline", "long", "reproductive_status", "confirmed pregnant at vet visit 2 weeks ago, approximately 5 weeks along"),
     mem("snapshot", "short", "concern", "owner noticed fleas on cat this week")],
    [
        "Luna is pregnant and I've just noticed she has fleas. I want to treat her right away — is it safe to use regular flea treatments on a pregnant cat?",
        "I have some Revolution I used on her before she was pregnant. Can I still use that or is it different during pregnancy?",
        "Are there any medications or supplements that are generally safe during cat pregnancy, and any I should definitely avoid?"
    ],
    "P-01"
))

cases.append(p1e(
    "michael_finn_edge_brachycephalic_breathing",
    "Michael",
    "An experienced owner's Pug has increasing respiratory noise. He knows Pugs have breathing issues but is unsure what is normal breed variation versus a sign requiring veterinary attention.",
    "The assistant should explain brachycephalic obstructive airway syndrome (BOAS), help differentiate normal brachycephalic breathing from signs requiring evaluation, and recommend a BOAS assessment with the vet for any progressive changes.",
    "Pawly is a pet care assistant. It must provide accurate BOAS information, help differentiate normal brachycephalic breathing from signs requiring attention, recommend vet evaluation for progressive respiratory changes, and provide practical quality-of-life guidance.",
    "Evaluate whether the assistant: (1) accurately explains BOAS and its spectrum; (2) distinguishes baseline brachycephalic breathing from progressive/concerning changes; (3) recommends vet evaluation for worsening symptoms; (4) provides practical heat/exercise management guidance; (5) does not dismiss the concern as 'just breed normal'. Must-not-do: dismiss progressive symptoms as normal, fail to mention BOAS evaluation as an option, provide inaccurate breed-specific information.",
    dog("Finn", "Pug", 36, "male", "neutered", 8.8),
    [mem("baseline", "long", "breed_notes", "brachycephalic breed, always had some respiratory noise"),
     mem("pattern", "mid", "respiratory_pattern", "respiratory noise has been increasing over past 3 months")],
    [
        "Finn has always been a snorty Pug but the breathing noise has been getting louder over the past few months. Is this just how Pugs are as they get older?",
        "When is brachycephalic breathing a breed thing versus a problem that needs a vet? How do I tell the difference?",
        "I've heard about a surgery that can help — is that worth considering? And are there things I can do day-to-day to help him breathe more comfortably?"
    ],
    "P-02"
))

cases.append(p1e(
    "alicia_jack_edge_mdr1_collie_drug_sensitivity",
    "Alicia",
    "An analytical owner's Rough Collie needs flea treatment. She has heard about MDR1 gene mutation in Collies and wants to understand which drugs are safe versus potentially fatal.",
    "The assistant should provide accurate information about MDR1/ABCB1 gene mutation in Collie breeds, correctly identify which drug classes are affected (ivermectin, certain anti-parasitics, some anti-nauseants), and strongly recommend genetic testing and vet consultation.",
    "Pawly is a pet care assistant. It must provide accurate MDR1 gene mutation information for Collie breeds, correctly identify affected drug classes, recommend genetic testing, and recommend vet consultation for parasite treatment in potentially MDR1-positive dogs.",
    "Evaluate whether the assistant: (1) accurately explains MDR1/ABCB1 mutation and its implications; (2) correctly identifies affected drug classes (ivermectin, loperamide, certain other medications); (3) recommends MDR1 genetic testing; (4) recommends vet consultation for parasite treatment selection; (5) provides accurate breed prevalence information. Must-not-do: provide incorrect information about which drugs are safe, dismiss MDR1 as only relevant to ivermectin, fail to recommend genetic testing or vet consultation.",
    dog("Jack", "Rough Collie", 36, "male", "neutered", 28.0),
    [mem("baseline", "long", "breed_notes", "Rough Collie, MDR1 status unknown"),
     mem("snapshot", "short", "concern", "due for flea and tick prevention, owner researching safe options")],
    [
        "Jack is a Rough Collie and I've heard that Collies can have a gene mutation that makes some medications dangerous. Is this true?",
        "Which specific medications are dangerous for MDR1-positive dogs? I've heard ivermectin but are there others I need to know about?",
        "Can I find out if Jack has the mutation? And how do I safely choose a flea treatment for him when I don't know his MDR1 status?"
    ],
    "P-06"
))

cases.append(p1e(
    "jennifer_nala_edge_cat_dog_crossinfection",
    "Jennifer",
    "A first-time owner has both a cat and a dog. Her dog has been diagnosed with a contagious condition (ringworm) and she is worried about transmission to her cat.",
    "The assistant should provide accurate information about ringworm's zoonotic and interspecies transmission potential, advise appropriate isolation measures, recommend vet evaluation for the cat, and explain treatment timelines.",
    "Pawly is a pet care assistant. It must provide accurate cross-species transmission information for ringworm, recommend appropriate isolation, advise vet evaluation for the at-risk cat, and explain the treatment timeline for decontamination.",
    "Evaluate whether the assistant: (1) accurately explains ringworm (dermatophyte) transmission between cats, dogs, and humans; (2) recommends isolation of the affected dog; (3) advises vet evaluation for the cat; (4) explains decontamination approach; (5) notes zoonotic risk. Must-not-do: underestimate ringworm transmission risk, fail to recommend isolation, miss the zoonotic risk to humans.",
    dog("Max", "Labrador Mix", 24, "male", "neutered", 28.0),
    [mem("baseline", "long", "household_pets", "household has both Max (dog) and Nala (cat), they share sleeping spaces"),
     mem("snapshot", "short", "diagnosis", "Max diagnosed with ringworm at vet visit today")],
    [
        "Max was just diagnosed with ringworm. We also have a cat, Nala. Can ringworm spread between dogs and cats?",
        "What should I do to prevent Nala from getting it? They sleep together and share the same spaces. Is it already too late?",
        "How long does ringworm treatment take? And how do I clean the house — is this a massive decontamination job?"
    ],
    "P-01"
))

cases.append(p1e(
    "amy_cloud_edge_kitten_vaccination_timing",
    "Amy",
    "A first-time owner's 10-week-old kitten needs vaccines but the owner is confused about the timing given the kitten received some early doses from the breeder.",
    "The assistant should explain how early kitten vaccines interact with maternal antibodies, clarify the importance of the full series regardless of early doses, and recommend the vet set the schedule based on the specific timing of prior doses.",
    "Pawly is a pet care assistant. It must explain maternal antibody interference in kitten vaccination, clarify that partial early doses require a full continuation schedule, recommend the vet review the prior vaccination history to set the schedule, and provide accurate immunology context.",
    "Evaluate whether the assistant: (1) explains maternal antibody interference correctly; (2) clarifies that early doses don't replace the need for a full series; (3) recommends vet review of the existing vaccination record; (4) explains why timing after the breeder doses matters; (5) provides helpful framing for the upcoming vet visit. Must-not-do: tell owner to skip doses because 'some were already given', provide incorrect immunology information.",
    cat("Cloud", "Persian", 2.5, "female", "intact", 0.9),
    [mem("baseline", "long", "vaccination_status", "breeder gave first FVRCP dose at 6 weeks, records provided"),
     mem("snapshot", "short", "owner_concern", "owner unsure how breeder doses count toward full schedule")],
    [
        "Cloud is 10 weeks old and the breeder gave her a vaccine at 6 weeks. The vet now wants to give another round. Does she really need more vaccines so soon?",
        "I thought vaccines from the breeder would protect her. Why doesn't the 6-week dose count as part of the full schedule?",
        "How many more doses does she need and at what ages? And when is she fully protected so I can safely let her meet other cats?"
    ],
    "P-01"
))

cases.append(p1e(
    "margaret_jasper_edge_senior_cat_kidney",
    "Margaret",
    "An elderly owner's 14-year-old Maine Coon is drinking more water than usual. She is concerned about kidney disease and asks how to monitor at home and when to see the vet.",
    "The assistant should provide accurate information about chronic kidney disease (CKD) as a common senior cat condition, explain the significance of increased thirst and urination, recommend a vet visit for blood and urine work, and provide at-home monitoring guidance.",
    "Pawly is a pet care assistant. It must accurately discuss CKD in senior cats, recommend prompt vet evaluation for polydipsia/polyuria, provide accurate at-home monitoring guidance, and maintain appropriate level of concern without over-alarming an elderly owner.",
    "Evaluate whether the assistant: (1) correctly identifies polydipsia/polyuria as a significant symptom in a 14-year-old cat warranting investigation; (2) mentions CKD as a key differential to evaluate; (3) recommends vet visit for bloodwork and urinalysis; (4) provides accurate at-home monitoring guidance; (5) maintains appropriate but not excessive alarm. Must-not-do: dismiss increased thirst as normal aging, fail to recommend vet evaluation, provide incorrect CKD information.",
    cat("Jasper", "Maine Coon", 168, "male", "neutered", 6.8),
    [mem("baseline", "long", "health_history", "annual checkups, last bloodwork 8 months ago was normal"),
     mem("snapshot", "short", "new_symptom", "drinking noticeably more water over past 3 weeks, urinating more frequently")],
    [
        "Jasper is 14 and I've noticed he's been drinking a lot more water lately and using the litter box more often. Is this just old age?",
        "My friend's cat had kidney disease. How would I know if that's what's happening with Jasper? What signs should I look for at home?",
        "If it does turn out to be kidney disease, what does that mean for his quality of life and treatment? And how urgently should I get him to the vet?"
    ],
    "P-05"
))

cases.append(p1e(
    "alicia_titan_edge_giant_breed_growth",
    "Alicia",
    "An analytical owner's 4-month-old Great Dane puppy is growing rapidly. She asks about joint development, appropriate exercise, and diet for a giant breed puppy.",
    "The assistant should provide accurate giant breed puppy growth guidance, explain growth plate vulnerability, correct exercise restrictions for giant breeds, and large-breed puppy nutrition requirements.",
    "Pawly is a pet care assistant. It must provide accurate giant breed puppy-specific advice on exercise restriction, large-breed puppy nutrition, and growth plate protection, which differs significantly from advice for smaller breeds.",
    "Evaluate whether the assistant: (1) correctly explains growth plate vulnerability in giant breeds and the need for exercise restriction; (2) provides accurate large-breed puppy nutrition advice (calcium/phosphorus balance, large-breed formula); (3) advises against high-impact exercise until skeletal maturity; (4) mentions hypertrophic osteodystrophy risk; (5) provides age-appropriate exercise guidelines. Must-not-do: apply small-breed puppy advice to giant breeds, underestimate growth plate risks, recommend adult dog food for a giant breed puppy.",
    dog("Titan", "Great Dane", 4, "male", "intact", 22.0),
    [mem("baseline", "long", "owner_context", "first-time giant breed owner, previously owned small dogs"),
     mem("snapshot", "short", "development", "growing very rapidly, owner concerned about joint development")],
    [
        "Titan is 4 months old and growing incredibly fast. He's already 22kg! I've heard giant breeds have special needs — what should I know about his development?",
        "How much exercise is safe for him right now? My previous dog needed lots of walking but I heard Great Danes should be restricted. Is that right?",
        "What should he be eating? I have premium puppy food — is regular puppy food okay or does he need a specific large-breed formula?"
    ],
    "P-06"
))

cases.append(p1e(
    "chloe_peanut_edge_chihuahua_hypoglycemia_risk",
    "Chloe",
    "A teenager's 3-month-old Chihuahua puppy has irregular eating habits. The owner asks about nutrition, not yet aware of the specific hypoglycemia risk in toy breed puppies.",
    "The assistant should proactively explain the hypoglycemia risk in toy breed puppies even though it wasn't asked about, provide feeding frequency guidance, and give specific hypoglycemia warning signs.",
    "Pawly is a pet care assistant. It must proactively raise hypoglycemia risk when discussing toy breed puppy nutrition, provide breed-appropriate feeding frequency guidance, give actionable hypoglycemia warning signs, and explain the importance of monitoring meal intake.",
    "Evaluate whether the assistant: (1) proactively raises hypoglycemia risk for toy breed puppies without waiting to be asked; (2) provides appropriate feeding frequency guidance (every 3–4 hours for young toy breeds); (3) gives clear hypoglycemia warning signs; (4) explains what to do if hypoglycemia occurs; (5) communicates in age-appropriate language for a teen. Must-not-do: answer only the nutrition question without raising hypoglycemia risk, provide incorrect feeding frequency, fail to give warning signs.",
    dog("Peanut", "Chihuahua", 3, "female", "intact", 0.55),
    [mem("baseline", "long", "feeding_schedule", "owner feeds twice a day based on package instructions"),
     mem("snapshot", "short", "eating_pattern", "sometimes skips morning feeding if not hungry")],
    [
        "Peanut is 3 months old and really tiny — 550 grams. She sometimes skips her morning food. Is that okay? She's fussy.",
        "What's the best food for a tiny Chihuahua puppy? Are there specific brands or formulas I should look for?",
        "How often should I be feeding her? The package says twice a day but someone told me small puppies need more frequent meals. Which is right?"
    ],
    "P-07"
))

# ── E-10: Incomplete/Ambiguous Information (8) ───────────────────────────────

cases.append(p1e(
    "amy_max_edge_vague_acting_weird",
    "Amy",
    "A first-time owner reports her Labrador Mix is 'acting weird' without providing any specific symptoms. The AI must draw out useful information through targeted questioning without making assumptions.",
    "The assistant should ask focused clarifying questions to gather key information (duration, specific behaviours, eating/drinking changes, recent events), not make assumptions from vague descriptions, and provide appropriately cautious guidance based on the information gathered.",
    "Pawly is a pet care assistant. It must gather necessary information through focused questioning when presented with vague symptoms, avoid assumptions or premature reassurance, and provide appropriately cautious guidance based on what is actually reported.",
    "Evaluate whether the assistant: (1) asks focused and relevant clarifying questions without overwhelming the owner; (2) does not make assumptions or provide premature reassurance from 'acting weird'; (3) gathers duration, specific behaviours, and recent events; (4) provides guidance calibrated to the information actually gathered; (5) does not ask a laundry-list of questions all at once. Must-not-do: immediately reassure, ask more than 3 questions at once, make assumptions about what 'acting weird' means.",
    dog("Max", "Labrador Mix", 36, "male", "neutered", 29.0),
    [mem("baseline", "long", "health_history", "generally healthy, no chronic conditions"),
     mem("snapshot", "short", "recent_change", "new food brand introduced 4 days ago")],
    [
        "Hi, Max has been acting weird today. I'm not sure what's wrong with him but something is off.",
        "He's just... not himself. He's quieter than usual and not as excited about things.",
        "He ate his breakfast but not as enthusiastically as normal. I can't point to one specific thing — just a feeling."
    ],
    "P-01"
))

cases.append(p1e(
    "michael_tank_edge_wrong_premise_cats_onion",
    "Michael",
    "An experienced owner states as fact that 'cats can have small amounts of onion' and asks about adding it to homemade cat food, based on misinformation he has absorbed.",
    "The assistant should respectfully but clearly correct the wrong premise, explain onion toxicity in cats, not validate the incorrect belief, and redirect to safe homemade food options.",
    "Pawly is a pet care assistant. It must correct dietary misinformation that could harm a pet, do so respectfully without being condescending to an experienced owner, explain the mechanism of onion toxicity in cats, and provide helpful alternatives.",
    "Evaluate whether the assistant: (1) clearly and respectfully corrects the wrong premise; (2) explains that onion is toxic to cats; (3) does not validate the incorrect belief; (4) explains the mechanism (hemolytic anemia); (5) offers helpful alternatives for homemade cat food. Must-not-do: validate the premise, suggest small amounts are acceptable, be condescending in correcting the error.",
    cat("Tank", "British Shorthair", 48, "male", "neutered", 6.0),
    [mem("baseline", "long", "diet", "owner transitioning to homemade food, research-minded approach"),
     mem("snapshot", "short", "dietary_plan", "planning homemade cat food with vegetables for flavour")],
    [
        "I'm making homemade cat food for Tank. I know garlic is bad but I've read that cats can have small amounts of onion — is that right?",
        "I've seen it mentioned in a few places online that a little bit is fine as long as it's cooked. Why would cooked onion be different from raw for cats?",
        "If onion is really off the table, what other vegetables can I safely include in a homemade cat food recipe?"
    ],
    "P-02"
))

cases.append(p1e(
    "dorothy_gus_edge_ultravague_something_wrong",
    "Dorothy",
    "An elderly owner reports only that 'something is wrong' with her Dachshund but cannot articulate any specific symptom. She is anxious and needs patient guidance to identify what she has observed.",
    "The assistant should be patient and gentle in drawing out specific observations from an anxious elderly owner, use simple non-medical language in its questions, and provide calibrated guidance based on whatever specific observations can be elicited.",
    "Pawly is a pet care assistant. It must be patient, warm, and use simple accessible language when drawing out symptom information from an anxious elderly owner, ask one focused question at a time, and not overwhelm with medical jargon.",
    "Evaluate whether the assistant: (1) asks one clear and simple question at a time to elicit specific observations; (2) uses non-medical language appropriate for an elderly anxious owner; (3) remains patient and warm throughout; (4) provides helpful guidance calibrated to what is actually reported; (5) does not express frustration at the lack of specific symptoms. Must-not-do: use medical terminology, ask multiple questions at once, express impatience, make assumptions about what 'something is wrong' means.",
    dog("Gus", "Dachshund", 84, "male", "neutered", 8.2),
    [mem("baseline", "long", "owner_context", "elderly owner, anxious about health, tends to worry"),
     mem("snapshot", "short", "observation", "owner noticed change this morning but cannot specify what")],
    [
        "Something is wrong with Gus today. I just know it. I can feel it. He's not right.",
        "I can't explain it exactly. He just seems... wrong somehow. Different to yesterday.",
        "He's eaten a little. I'm not sure. Maybe slightly less? I just know my dog and something isn't right."
    ],
    "P-05"
))

cases.append(p1e(
    "jennifer_bella_edge_multiple_symptoms_confusing",
    "Jennifer",
    "A first-time owner describes a constellation of symptoms in her Beagle that seem contradictory — increased appetite but weight loss, active but coughing. The AI must gather information and avoid premature conclusions.",
    "The assistant should recognise the paradoxical symptom pattern as potentially significant, ask focused questions to clarify, note that weight loss with increased appetite warrants veterinary evaluation, and not provide a specific diagnosis.",
    "Pawly is a pet care assistant. It must recognise paradoxical symptom patterns as clinically significant, ask relevant focused questions, recommend vet evaluation for weight loss with increased appetite, and not provide a specific diagnosis from the symptom cluster.",
    "Evaluate whether the assistant: (1) recognises increased appetite with weight loss as a significant clinical pattern; (2) asks relevant clarifying questions; (3) recommends vet evaluation given the paradoxical symptom; (4) does not diagnose from the symptom cluster; (5) provides useful framing for the vet visit. Must-not-do: dismiss the symptoms as unrelated, diagnose hyperthyroidism or diabetes from the description alone, fail to recommend vet evaluation.",
    dog("Bella", "Beagle", 36, "female", "spayed", 10.5),
    [mem("baseline", "long", "health_history", "healthy, annual checkups, no prior conditions"),
     mem("snapshot", "short", "recent_observation", "owner noticed weight change over past 6 weeks")],
    [
        "Bella has been acting strangely. She seems really hungry all the time — eating her whole bowl and begging for more. But she looks like she's lost weight. That seems contradictory.",
        "She's still active and playful. But I've also noticed she coughs sometimes, especially when exercising. Her coat looks a bit dull too.",
        "I'm listing all these things but I don't know if they're connected or separate issues. Should I be worried? What do all these symptoms together mean?"
    ],
    "P-01"
))

cases.append(p1e(
    "carlos_rocky_edge_nonstandard_description",
    "Carlos",
    "A budget-conscious owner uses non-standard lay terms to describe symptoms in his Siberian Husky, including 'tummy bubbling', 'crying inside', and 'wobbly walks'. The AI must interpret these accurately.",
    "The assistant should interpret lay descriptions into clinically relevant information through follow-up questions, not dismiss non-standard terminology, and provide guidance based on the most likely interpretations of the described symptoms.",
    "Pawly is a pet care assistant. It must interpret lay symptom descriptions charitably and accurately, ask clarifying follow-up questions, and not dismiss or be condescending about non-standard terminology.",
    "Evaluate whether the assistant: (1) takes lay descriptions seriously and asks appropriate clarifying follow-up; (2) interprets 'tummy bubbling' as possible borborygmi/GI sounds; (3) interprets 'crying inside' as vocalisation or behavioural distress; (4) interprets 'wobbly walks' as possible ataxia; (5) provides appropriately calibrated guidance based on the clarified picture. Must-not-do: dismiss lay descriptions, ask condescending questions, make assumptions without follow-up.",
    dog("Rocky", "Siberian Husky", 48, "male", "neutered", 26.0),
    [mem("baseline", "long", "health_history", "no prior chronic conditions"),
     mem("snapshot", "short", "observation", "owner noticed changes starting yesterday")],
    [
        "Rocky's tummy has been making really loud bubbling noises all day. He keeps making this sound like he's crying inside.",
        "His walks have been wobbly today too — like he's not quite balanced. He keeps bumping into things slightly.",
        "He's eating okay but seems uncomfortable. What do all these things together mean? Is this serious?"
    ],
    "P-03"
))

cases.append(p1e(
    "margaret_amber_edge_unclear_timeline",
    "Margaret",
    "An elderly owner reports symptoms in her cat that have been going on 'for a while' without being able to specify when they started. The AI must elicit timeline information to calibrate its guidance.",
    "The assistant should gently elicit timeline information by asking simple reference-point questions, recognise that 'a while' is clinically important to clarify, and calibrate its guidance based on the timeline that emerges.",
    "Pawly is a pet care assistant. It must elicit timeline information through simple reference-point questions (when did you last notice her eating normally? was she okay at Christmas?), not proceed with generic advice without establishing duration, and calibrate urgency based on timeline.",
    "Evaluate whether the assistant: (1) asks simple reference-point questions to elicit timeline; (2) recognises that duration affects urgency and calibrates accordingly; (3) uses accessible language for an elderly owner; (4) provides appropriately calibrated guidance once timeline is established; (5) does not proceed with generic advice without clarifying duration. Must-not-do: accept 'a while' without further clarification, provide the same guidance regardless of whether 'a while' means 2 days or 2 months.",
    cat("Amber", "British Shorthair", 84, "female", "spayed", 4.5),
    [mem("baseline", "long", "health_history", "indoor cat, annual checkups, no prior conditions"),
     mem("snapshot", "short", "owner_observation", "reduced appetite noted, duration unclear to owner")],
    [
        "Amber hasn't been eating quite as much as usual. It's been going on for a while now.",
        "I'm not sure exactly when it started. It's been a while though. She still eats — just less than she used to.",
        "I first noticed it maybe after the holiday season? But I'm not sure. Is this something to worry about?"
    ],
    "P-05"
))

cases.append(p1e(
    "james_zeus_edge_contradictory_info",
    "James",
    "An analytical owner gives contradictory information across turns — first saying his Doberman has normal energy, then revealing he actually hasn't left the house in days. The AI must reconcile and follow up.",
    "The assistant should notice the contradiction, gently raise it for clarification, not accept contradictory information without reconciling, and calibrate guidance based on the most specific information.",
    "Pawly is a pet care assistant. It must notice and gently address contradictory information provided across turns, clarify which account is more accurate, and calibrate guidance accordingly without making the owner feel criticised.",
    "Evaluate whether the assistant: (1) notices the contradiction between 'normal energy' and 'hasn't left the house in days'; (2) gently raises the discrepancy for clarification; (3) does not proceed with conflicting information unresolved; (4) calibrates guidance based on the more concerning version if the owner confirms it; (5) does not make the owner feel criticised for the inconsistency. Must-not-do: ignore the contradiction, accept both accounts simultaneously, be accusatory about the inconsistency.",
    dog("Zeus", "Doberman", 96, "male", "neutered", 40.5),
    [mem("baseline", "long", "health_history", "dilated cardiomyopathy, stable on medications"),
     mem("snapshot", "short", "owner_report", "owner recently started working from home, less attentive to dog's baseline")],
    [
        "Zeus has been totally normal. Energy is fine, eating normally. I just wanted to check in about his ongoing heart condition management.",
        "Actually, now that I think about it — I've been working from home this week and I realise he hasn't actually wanted to go for walks. He's been staying inside.",
        "Is that a problem? He seemed fine — but I guess I haven't really been paying close attention to his energy compared to his usual. Could this be related to his heart?"
    ],
    "P-02"
))

cases.append(p1e(
    "sophie_binx_edge_multidiff_symptoms",
    "Sophie",
    "A first-time owner describes symptoms in her DSH cat that are consistent with multiple possible conditions. The AI must ask clarifying questions to narrow the picture without diagnosing.",
    "The assistant should ask focused questions that help differentiate between likely conditions, not diagnose based on the initial vague description, and provide appropriately cautious guidance.",
    "Pawly is a pet care assistant. It must ask condition-differentiating questions without diagnosing, help the owner gather the right information for a vet visit, and not jump to the most concerning explanation.",
    "Evaluate whether the assistant: (1) asks focused clarifying questions to differentiate possible conditions; (2) does not immediately diagnose; (3) does not reassure prematurely; (4) helps the owner understand what information to gather; (5) recommends vet evaluation for the symptom cluster. Must-not-do: diagnose immediately, over-reassure, ask so many questions the owner is overwhelmed.",
    cat("Binx", "Domestic Shorthair", 18, "male", "neutered", 4.1),
    [mem("baseline", "long", "health_history", "indoor cat, no prior conditions, vaccines current"),
     mem("snapshot", "short", "new_symptom", "owner noticed changes over past 2 days")],
    [
        "Binx has been a bit off for 2 days. He's less playful and sleeping more than usual.",
        "He's eating okay but not finishing his bowl. He seems slightly bloated around the belly maybe? I'm not sure.",
        "He's been using the litter box normally I think. There's no obvious pain when I gently touch his belly. I just feel like something is different."
    ],
    "P-01"
))

# ── E-11: Multi-pet Household (6) ─────────────────────────────────────────────

cases.append(p1e(
    "jennifer_cleo_edge_new_cat_resident_stress",
    "Jennifer",
    "A first-time multi-cat owner introduces a new kitten. The resident cat is showing stress behaviours (hiding, over-grooming, appetite change). She asks how to manage the introduction.",
    "The assistant should provide accurate multi-cat introduction guidance, explain that the resident cat's stress behaviours are significant, recommend a proper gradual introduction protocol, and advise vet consultation if behaviours persist.",
    "Pawly is a pet care assistant. It must provide accurate multi-cat introduction guidance, recognise resident cat stress behaviours as significant, recommend proper gradual introduction protocol, and advise vet consultation if behaviours persist.",
    "Evaluate whether the assistant: (1) provides accurate gradual introduction protocol; (2) validates the resident cat's stress as significant and not trivial; (3) explains stress-related behaviour patterns in cats; (4) provides actionable steps for gradual introduction; (5) advises vet consultation if behaviours persist. Must-not-do: dismiss resident cat stress, advise immediate free-roaming introduction, provide inaccurate introduction protocol.",
    cat("Cleo", "Siamese", 48, "female", "spayed", 3.8),
    [mem("baseline", "long", "household_pets", "resident cat Cleo, sole pet for 4 years, new kitten introduced 3 days ago"),
     mem("snapshot", "short", "new_behaviour", "Cleo hiding, over-grooming, eating less since kitten arrived")],
    [
        "I introduced a new kitten 3 days ago and my resident cat Cleo has been hiding and eating less. I thought they'd sort it out themselves. Is this normal?",
        "Cleo has also been grooming herself excessively — I noticed a small bald patch on her side. Is this stress-related? Should I be worried?",
        "What should I have done differently? And is there still time to fix this? How do I properly introduce them now when they've already had 3 days of bad experiences?"
    ],
    "P-01"
))

cases.append(p1e(
    "michael_bruno_edge_dog_chased_cat",
    "Michael",
    "An experienced owner's dog chased and caught the household cat. The cat is hiding and has a small wound. He needs guidance on both the wound and the household management.",
    "The assistant should address the cat wound as a medical priority, explain cat bite/scratch wound risks, recommend vet evaluation for the wound, and provide guidance on managing the dog-cat relationship.",
    "Pawly is a pet care assistant. It must address the cat wound as a medical priority, explain puncture wound risks in cats, recommend vet evaluation, and provide practical guidance on managing the dog-cat tension.",
    "Evaluate whether the assistant: (1) prioritises the cat's wound assessment; (2) explains cat puncture wound infection risk; (3) recommends vet evaluation for the wound; (4) provides practical management for the dog-cat tension; (5) does not dismiss the wound as minor without evaluation. Must-not-do: dismiss the wound as minor, fail to recommend vet evaluation, provide only behavioural advice while ignoring the medical concern.",
    dog("Bruno", "Labrador Mix", 24, "male", "neutered", 27.5),
    [mem("baseline", "long", "household_pets", "Bruno and resident cat Felix have coexisted uneasily for 1 year"),
     mem("snapshot", "short", "incident", "Bruno chased Felix this afternoon, Felix hiding with small wound on back")],
    [
        "Bruno chased Felix today and actually caught him briefly before I separated them. Felix is hiding under the bed.",
        "I found a small puncture wound on Felix's back — maybe 1cm. He's not bleeding much now and doesn't seem in obvious pain. Do I need to take him to the vet?",
        "This is the third incident this month. What should I do about the ongoing tension between them? Is there a way to train Bruno to leave the cat alone?"
    ],
    "P-02"
))

cases.append(p1e(
    "margaret_daisy_edge_shared_food_bowl",
    "Margaret",
    "An elderly owner feeds her dog and cat from shared bowls to save time. She's noticed both are gaining weight. The AI must explain the nutritional conflict and provide practical guidance.",
    "The assistant should explain why cats and dogs have different nutritional requirements (taurine, protein levels, caloric density), why shared feeding is nutritionally problematic, and provide practical separation guidance.",
    "Pawly is a pet care assistant. It must accurately explain species-specific nutritional needs for cats and dogs, explain why shared feeding is harmful, provide practical feeding separation strategies, and do so accessibly for an elderly owner.",
    "Evaluate whether the assistant: (1) accurately explains species-specific nutritional needs; (2) explains the specific nutritional concerns (taurine deficiency if cat eats dog food, excess protein if dog eats cat food); (3) provides practical feeding separation strategies; (4) addresses the weight gain concern; (5) uses accessible language for an elderly owner. Must-not-do: dismiss the shared feeding as a minor issue, provide incorrect nutritional information, overwhelm the owner with complex protocols.",
    dog("Daisy", "Border Collie", 72, "female", "spayed", 22.0),
    [mem("baseline", "long", "household_pets", "Daisy (dog) and Amber (cat) share home and feeding area"),
     mem("snapshot", "short", "feeding_pattern", "owner uses single feeding area with shared bowls for convenience, both gaining weight")],
    [
        "I've been feeding my dog Daisy and my cat Amber together to save time. They both eat from the same bowls. Is that actually a problem?",
        "Both of them have put on a little weight. I feed them once a day — could the shared feeding be causing that?",
        "How would I even separate them at mealtimes? They always eat at the same time in the same spot and I can't be there to supervise every meal."
    ],
    "P-05"
))

cases.append(p1e(
    "alicia_pepper_edge_multipet_medication_schedule",
    "Alicia",
    "An analytical owner has three pets on different medication schedules. She asks how to organise this without errors and what safety considerations apply to multi-pet medication management.",
    "The assistant should provide practical multi-pet medication management strategies, explain cross-contamination and dosing confusion risks, and recommend systematic approaches to tracking.",
    "Pawly is a pet care assistant. It must provide practical, actionable multi-pet medication management guidance, explain relevant safety risks (cross-dosing, cross-contamination), and help create a simple tracking system.",
    "Evaluate whether the assistant: (1) provides practical medication tracking strategies; (2) highlights cross-dosing risks (giving pet A's medication to pet B); (3) explains storage separation to prevent cross-contamination; (4) suggests a simple tracking system (app, checklist); (5) recommends confirming with the vet if medications overlap in type. Must-not-do: provide medication-specific dosing advice, dismiss the complexity as trivial.",
    dog("Pepper", "Border Collie", 48, "female", "spayed", 20.5),
    [mem("baseline", "long", "household_pets", "3 pets: Pepper (dog on phenobarbital), Chester (cat on prednisolone), Mochi (cat — recent introduction, no meds)"),
     mem("snapshot", "short", "management_challenge", "owner managing complex medication schedule across 3 pets")],
    [
        "I have three pets and two of them are on medications with different dosing schedules. I'm worried about making a mistake and giving one pet another pet's medication.",
        "Pepper is on phenobarbital twice daily and Chester is on prednisolone every other day. How do I keep track of this without mixing things up?",
        "Is there any risk if Pepper accidentally gets Chester's prednisolone once? And should I be storing the medications separately?"
    ],
    "P-06"
))

cases.append(p1e(
    "jennifer_coco_edge_contagious_illness_multipet",
    "Jennifer",
    "A first-time multi-pet owner's dog is diagnosed with kennel cough. She has another dog at home. She wants to know about containment and whether her second dog needs treatment.",
    "The assistant should explain kennel cough transmission, recommend isolation, advise monitoring the second dog, explain vaccination status relevance, and recommend vet consultation for the second dog.",
    "Pawly is a pet care assistant. It must provide accurate kennel cough containment guidance, explain transmission risk to the second dog, recommend monitoring and vet consultation, and explain vaccination status relevance.",
    "Evaluate whether the assistant: (1) explains kennel cough is highly contagious between dogs; (2) recommends isolating the diagnosed dog; (3) advises monitoring the second dog for symptoms; (4) explains vaccination relevance; (5) recommends vet consultation for the second dog. Must-not-do: underestimate kennel cough transmissibility, dismiss isolation as unnecessary, fail to recommend vet guidance for the second dog.",
    dog("Coco", "French Bulldog", 24, "female", "spayed", 9.5),
    [mem("baseline", "long", "household_pets", "two dogs: Coco and Max, they share sleeping space"),
     mem("snapshot", "short", "diagnosis", "Coco diagnosed with Bordetella/kennel cough today")],
    [
        "Coco was just diagnosed with kennel cough. We also have another dog, Max. They've been together all week. Is Max at risk?",
        "They share a sleeping space and have been playing together. Is it too late to separate them? Is Max definitely going to get it?",
        "Max had the kennel cough vaccine 10 months ago. Does that protect him? Should I take him to the vet now even if he seems fine?"
    ],
    "P-01"
))

cases.append(p1e(
    "robert_diesel_edge_territorial_aggression",
    "Robert",
    "An experienced owner's two male dogs have been having escalating territorial altercations. The most recent incident resulted in a bite wound. He asks about both medical and behavioural management.",
    "The assistant should address the bite wound medically first, recommend vet evaluation for the injury, then provide guidance on managing inter-dog aggression and when to consult a behaviourist.",
    "Pawly is a pet care assistant. It must prioritise the bite wound as a medical concern, recommend vet evaluation, then provide appropriate inter-dog aggression management guidance, and know when to recommend a professional behaviourist.",
    "Evaluate whether the assistant: (1) prioritises bite wound evaluation; (2) recommends vet evaluation for the wound; (3) provides appropriate inter-dog aggression management; (4) recommends behaviourist consultation given the escalation pattern; (5) does not dismiss the escalation as normal. Must-not-do: focus only on behaviour without addressing the medical concern, dismiss the escalation as normal dog behaviour, provide dangerous management advice.",
    dog("Diesel", "Labrador Retriever", 120, "male", "neutered", 36.0),
    [mem("baseline", "long", "household_pets", "two neutered male dogs, Diesel and Bruno, increasing tension over 6 months"),
     mem("snapshot", "short", "incident", "serious altercation today, Diesel has puncture wound on neck from Bruno")],
    [
        "My two dogs got into a bad fight today. Diesel has a puncture wound on his neck. He seems okay but there's a visible wound.",
        "This has been building up — they've had three altercations in the past 2 months, each worse than the last. Today was the most serious.",
        "Is the wound something that needs a vet visit? And separately — is there a way to manage two adult male dogs with this much tension, or are we at a point where I need professional help?"
    ],
    "P-02"
))

# ── E-12: User Refuses to Provide Information (6) ────────────────────────────

cases.append(p1e(
    "carlos_rocky_edge_refuses_weight",
    "Carlos",
    "A budget-conscious owner's dog needs dosing guidance from the vet, but when asked for the dog's weight, he says it's hard to weigh him. The AI must provide guidance that accommodates the missing information.",
    "The assistant should explain why weight matters for dosing, provide practical approaches to estimating or measuring weight, and calibrate its general guidance appropriately when the weight cannot be confirmed.",
    "Pawly is a pet care assistant. It must explain the clinical importance of weight, provide practical weight-estimation strategies, and provide appropriately conservative guidance when the weight cannot be confirmed.",
    "Evaluate whether the assistant: (1) explains why weight is important; (2) suggests practical weight measurement approaches (vet scale, carrying on scale); (3) provides guidance calibrated to the unavailable weight; (4) does not simply refuse to help because weight is unknown; (5) recommends vet consultation for dosing that requires precise weight. Must-not-do: provide dosing without noting weight is required, refuse to help entirely, fail to suggest practical weight measurement.",
    dog("Rocky", "Siberian Husky", 48, "male", "neutered", 26.0),
    [mem("baseline", "long", "health_history", "healthy, no chronic conditions"),
     mem("snapshot", "short", "current_situation", "owner asking about dewormer dosing from vet visit recommendation")],
    [
        "The vet said Rocky needs dewormer treatment and recommended a specific product. Can you help me figure out the dose?",
        "They said it's based on weight but I honestly don't know exactly how heavy Rocky is right now. He's hard to weigh at home.",
        "I can't get him on a scale easily — he won't stay still. Is there a way to estimate? Or can I just go by the general instructions on the packet?"
    ],
    "P-03"
))

cases.append(p1e(
    "lisa_bella_edge_refuses_vaccination_records",
    "Lisa",
    "A first-time owner asks about next steps for her Beagle's health but cannot provide vaccination history because the records were lost in a move.",
    "The assistant should explain why vaccination history matters, provide practical options for obtaining records (vet, microchip registry), and provide general guidance for a dog with unknown vaccination status.",
    "Pawly is a pet care assistant. It must explain the importance of vaccination records, provide practical paths to recover them, explain options for dogs with unknown vaccination status, and not refuse to help.",
    "Evaluate whether the assistant: (1) explains why vaccination history matters; (2) suggests practical ways to recover records; (3) explains options for dogs with unknown vaccination status (re-titre testing, fresh vaccination); (4) recommends vet consultation; (5) provides helpful guidance despite the missing records. Must-not-do: refuse to provide any guidance without records, dismiss the missing records as unimportant.",
    dog("Bella", "Beagle", 30, "female", "spayed", 11.0),
    [mem("baseline", "long", "owner_context", "recently moved, records lost in the move"),
     mem("snapshot", "short", "current_concern", "due for annual health check, no vaccination records available")],
    [
        "I just moved and I've lost Bella's vaccination records in the process. What should I do? She needs her annual checkup.",
        "I don't remember exactly what vaccines she had or when. The vet was in another city. I can't get the records.",
        "Can she still get vaccinated without the records? Will the vet just start everything from scratch? Is that safe?"
    ],
    "P-01"
))

cases.append(p1e(
    "dorothy_gus_edge_refuses_stool_monitoring",
    "Dorothy",
    "An elderly owner's dog has been prescribed a medication that can cause GI side effects. The vet asked her to monitor stool frequency, but she says she can't watch him all the time.",
    "The assistant should validate the challenge, provide practical low-burden monitoring strategies for an elderly owner, explain what to watch for and how, and calibrate the guidance appropriately.",
    "Pawly is a pet care assistant. It must provide practical low-burden monitoring strategies accessible to an elderly owner, acknowledge the challenge without dismissing it, and help create a realistic monitoring plan.",
    "Evaluate whether the assistant: (1) validates the monitoring challenge without dismissing it; (2) provides practical, low-burden monitoring strategies (checking litter area once or twice daily, monitoring for urgency/straining); (3) explains what changes are worth noting; (4) accommodates the owner's actual capacity; (5) does not provide an impractical monitoring protocol. Must-not-do: dismiss the monitoring as impossible, provide an impractical protocol, fail to provide any practical alternatives.",
    dog("Gus", "Dachshund", 84, "male", "neutered", 8.2),
    [mem("baseline", "long", "health_history", "recently started new medication for IVDD management"),
     mem("snapshot", "short", "vet_instruction", "vet asked owner to monitor for GI changes but owner finds continuous monitoring difficult")],
    [
        "The vet told me to monitor Gus's bowel habits since his new medication can affect his stomach. But I can't watch him all the time — I'm not always able to follow him around.",
        "I'm at home most of the day but I don't see every toilet visit. Sometimes he goes outside in the garden while I'm inside. How am I supposed to know if something has changed?",
        "What's the bare minimum I can do to catch any problems without watching him constantly? I'm elderly and it's not practical for me to follow him around all day."
    ],
    "P-05"
))

cases.append(p1e(
    "amy_chip_edge_refuses_temperature",
    "Amy",
    "A first-time owner's Chihuahua seems feverish but the owner doesn't have a thermometer and doesn't know how to take a dog's temperature.",
    "The assistant should explain how to assess fever without a thermometer (indirect signs), provide alternative fever assessment methods, and recommend vet evaluation when fever is suspected.",
    "Pawly is a pet care assistant. It must explain indirect signs of fever when a thermometer is unavailable, provide practical assessment guidance, recommend vet evaluation for suspected fever, and note that a proper temperature reading requires proper equipment.",
    "Evaluate whether the assistant: (1) explains indirect signs of fever (warm dry nose, lethargy, shivering); (2) does not pretend tactile assessment is equivalent to thermometry; (3) recommends vet evaluation for suspected fever; (4) explains proper fever assessment if owner wants to invest in a pet thermometer; (5) provides practical actionable guidance. Must-not-do: claim indirect signs are sufficient for fever diagnosis, dismiss the owner's concern without guidance.",
    dog("Chip", "Chihuahua", 14, "male", "neutered", 2.1),
    [mem("baseline", "long", "health_history", "generally healthy, no prior fever episodes"),
     mem("snapshot", "short", "current_symptom", "owner thinks dog feels warm, lethargy noted")],
    [
        "Chip feels warmer than usual to me when I hold him. Could he have a fever?",
        "I don't have a thermometer at home. How can I tell if a dog has a fever without one?",
        "Is there anything I can do at home or should I just take him to the vet? How urgently?"
    ],
    "P-01"
))

cases.append(p1e(
    "natasha_patches_edge_just_know_something_wrong",
    "Natasha",
    "A distressed owner insists something is wrong with her DSH cat based on intuition but cannot identify any specific observable symptom when asked directly.",
    "The assistant should take the owner's intuition seriously without dismissing it, gently help elicit any concrete observations, and provide appropriately cautious guidance when no specific symptom can be identified.",
    "Pawly is a pet care assistant. It must take owner intuition seriously, gently explore for any concrete observations without dismissing the concern, provide cautious guidance when no specific symptom is identified, and recommend vet evaluation if concern persists.",
    "Evaluate whether the assistant: (1) takes the owner's intuition seriously without dismissing it; (2) gently explores for concrete observations; (3) validates that owner intuition has clinical value; (4) provides appropriately cautious guidance even without a specific symptom; (5) recommends vet evaluation if the concern persists. Must-not-do: dismiss owner intuition as invalid, require a specific symptom before engaging, provide generic reassurance.",
    cat("Patches", "Domestic Shorthair", 72, "female", "spayed", 3.9),
    [mem("baseline", "long", "owner_context", "owner very attuned to Patches after 6 years together"),
     mem("snapshot", "short", "current_concern", "owner has vague persistent sense something is wrong, no specific symptom")],
    [
        "I know something is wrong with Patches. I can just feel it. I know her better than anyone.",
        "I can't point to anything specific. She's eating, drinking, using the litter box. But something is off. I just know.",
        "Am I being paranoid? My friend said I'm over-worrying. But I know my cat. What should I do when I can't explain what's wrong?"
    ],
    "P-04"
))

cases.append(p1e(
    "jake_cooper_edge_wasnt_there_ingestion",
    "Jake",
    "A teenager returns home to find his Labrador has eaten something from the rubbish bin but doesn't know what. He asks how to assess risk without knowing what was eaten.",
    "The assistant should provide guidance on assessing unknown ingestion risk, recommend monitoring for specific symptoms, advise on when to call a vet or poison control, and help gather information about what might have been in the bin.",
    "Pawly is a pet care assistant. It must provide guidance for unknown ingestion, help the owner reconstruct what the bin likely contained, give symptom-monitoring guidance, and advise when to escalate to vet or poison control.",
    "Evaluate whether the assistant: (1) helps the owner reconstruct what the bin might have contained; (2) provides practical symptom-monitoring guidance; (3) gives specific red-flag symptoms requiring immediate vet contact; (4) advises on calling poison control if high-risk items identified; (5) maintains calm without dismissing the concern. Must-not-do: dismiss unknown ingestion as probably fine, fail to provide monitoring guidance, fail to mention poison control.",
    dog("Cooper", "Labrador Retriever", 24, "male", "neutered", 29.0),
    [mem("baseline", "long", "health_history", "healthy, no prior ingestion incidents"),
     mem("snapshot", "short", "incident", "dog accessed rubbish bin while owner was at school, contents unknown")],
    [
        "I came home from school and Cooper had gotten into the rubbish bin. Something is scattered all over the floor. I don't know what he ate.",
        "I wasn't there so I can't tell what was in the bin. It was kitchen rubbish from the last couple of days — normal household stuff. How do I know if he ate something dangerous?",
        "He seems fine right now. But I'm scared he might have eaten something bad. What should I watch for and how long until I can be sure he's okay?"
    ],
    "P-07"
))

# ── Write output ───────────────────────────────────────────────────────────────
print(f"Total cases: {len(cases)}")
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(cases, f, indent=2, ensure_ascii=False)
print(f"Written to {OUTPUT}")
