"""
Generate Robust P1 General Green-light cases (54 cases) — NEW V1 robust test cases.
Different from the original 54 in gen_p1_general.py.

Sub-categories:
  G-01 Diet & Nutrition         10 cases
  G-02 Daily Care               8 cases
  G-03 Behaviour                8 cases
  G-04 Routine Health           10 cases
  G-05 Life Stages              8 cases
  G-06 User Already Googled     5 cases
  G-07 Singapore Localisation   5 cases
"""
import json, pathlib

OUT = pathlib.Path(__file__).parent / "multiturn_pawly_regression_test_robust_p1_general.json"

def p1(name, display, scenario, outcome, role, criteria, pet, prior_turns, user_turns, persona,
       focus="general", category="general_topic"):
    return {
        "name": name,
        "user_display_name": display,
        "scenario": scenario,
        "expected_outcome": outcome,
        "chatbot_role": role,
        "criteria": criteria,
        "threshold": 0.75,
        "pet_profile": pet,
        "memories": [],
        "recent_turns": prior_turns,
        "user_turns": user_turns,
        "metadata": {
            "focus": focus,
            "layer": "handler_blackbox_multiturn",
            "priority": "P1",
            "category": category,
            "persona": persona,
            "multiturn": True,
        },
    }

def prior_turn(role, content):
    return {"role": role, "content": content}

CASES = []

# ─────────────────────────────────────────────
# G-01  Diet & Nutrition  (10 cases)
# ─────────────────────────────────────────────

CASES.append(p1(
    name="rob_hunter_diet_raw_safety",
    display="Rob",
    scenario="Rob wants to switch his 3-year-old Siberian Husky, Hunter, to a raw food diet after watching videos online about BARF (Biologically Appropriate Raw Food).",
    outcome="Pawly explains BARF principles, protein rotation, hygiene risks (Salmonella, E. coli), bone safety (raw vs. cooked), and recommends consulting a vet nutritionist before full transition.",
    role="Provide balanced, evidence-informed guidance on raw diets including hygiene risks and transition protocols.",
    criteria="Must cover BARF concept; must explain hygiene risks (Salmonella); must address bone safety; must recommend vet nutritionist; must not push vet visit for a routine diet enquiry. Suggestions must be specific and actionable; warm persona.",
    pet={"name": "Hunter", "species": "dog", "breed": "Siberian Husky", "age": "3 years", "weight": "27 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Rob has been feeding Hunter a premium dry kibble for 2 years; curious about BARF after YouTube research.")],
    user_turns=[
        "Is raw feeding actually safe for a Husky like Hunter?",
        "What proteins should I rotate and why?",
        "Can I give him cooked bones?",
        "How do I transition him from kibble to raw without upsetting his stomach?",
    ],
    persona="P-02",
))

CASES.append(p1(
    name="chloe_biscuit_diet_grainfree_heart",
    display="Chloe",
    scenario="Chloe's 5-year-old Cocker Spaniel Biscuit has been on a boutique grain-free diet for a year. She heard about the FDA grain-free DCM link and is worried.",
    outcome="Pawly explains the FDA DCM investigation, notes the evidence is associational not causational, explains the role of taurine, and recommends discussing with a vet whether to switch to a grain-inclusive diet.",
    role="Discuss grain-free DCM concern objectively, avoiding catastrophizing or dismissal.",
    criteria="Must mention FDA investigation and DCM link; must not catastrophize or dismiss; must explain taurine context; must recommend vet discussion; must not over-medicalize a routine diet review.",
    pet={"name": "Biscuit", "species": "dog", "breed": "Cocker Spaniel", "age": "5 years", "weight": "12 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Chloe switched Biscuit to grain-free food after reading it was better for sensitive stomachs.")],
    user_turns=[
        "I heard grain-free food causes heart problems in dogs — is Biscuit at risk?",
        "What is DCM and how is it linked to grain-free food?",
        "What does taurine have to do with it?",
        "Should I switch her back to grain-inclusive food?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="priscilla_toby_diet_homecook_balance",
    display="Priscilla",
    scenario="Priscilla wants to home-cook all of Toby's meals. Her 4-year-old Beagle Toby has been on kibble his whole life.",
    outcome="Pawly provides a home-cooked framework (protein, complex carbs, fats, calcium, micronutrients), warns about nutrient deficiencies with home-cooking alone, lists critical supplements, and recommends a board-certified veterinary nutritionist.",
    role="Guide home-cooking for dogs with attention to nutritional completeness and deficiency risks.",
    criteria="Must highlight nutrient deficiency risks; must list critical supplements (calcium, zinc, vitamins B and D); must recommend board-certified vet nutritionist; must not push vet visit for routine dietary enquiry.",
    pet={"name": "Toby", "species": "dog", "breed": "Beagle", "age": "4 years", "weight": "10 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Priscilla is a home cook who prefers knowing exactly what goes into Toby's food.")],
    user_turns=[
        "What do I need to include in Toby's home-cooked meals?",
        "Can I just use chicken and rice every day?",
        "What supplements are non-negotiable?",
        "How do I figure out the right portion size for him?",
    ],
    persona="P-03",
))

CASES.append(p1(
    name="jane_luna_diet_senior_cat_transition",
    display="Jane",
    scenario="Jane's 11-year-old Domestic Shorthair cat Luna has been on the same adult kibble for years. The vet mentioned transitioning to senior food at the last checkup.",
    outcome="Pawly explains senior cat food benefits (lower phosphorus for kidney support, joint nutrients, digestibility), recommends a slow transition schedule (7–10 days), and clarifies that sudden diet changes can cause GI upset.",
    role="Advise on senior cat food transition with attention to health benefits and safe transition protocol.",
    criteria="Must explain senior food benefits; must recommend gradual transition schedule; must not over-medicalize a routine dietary change; suggestions must be specific and actionable.",
    pet={"name": "Luna", "species": "cat", "breed": "Domestic Shorthair", "age": "11 years", "weight": "4.2 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Luna has been eating the same adult dry kibble since age 2; vet suggested senior formula at last visit.")],
    user_turns=[
        "Why should I switch Luna to senior cat food now?",
        "What's actually different about senior cat food?",
        "How do I transition her without causing diarrhoea?",
        "How long does the transition take?",
    ],
    persona="P-05",
))

CASES.append(p1(
    name="wei_miffy_diet_diabetic_timing",
    display="Wei",
    scenario="Wei's 9-year-old domestic shorthair cat Miffy was recently diagnosed with diabetes and he asks about how to time meals around insulin injections.",
    outcome="Pawly explains the importance of consistent meal timing with insulin injections, recommends feeding at the time of injection, advises against free-feeding for diabetic cats, and recommends close vet monitoring.",
    role="Advise on diabetic cat meal timing in relation to insulin management.",
    criteria="Must address meal-insulin timing clearly; must advise against free-feeding for diabetic cats; must recommend consistent schedule; must recommend vet monitoring for dosing adjustments.",
    pet={"name": "Miffy", "species": "cat", "breed": "Domestic Shorthair", "age": "9 years", "weight": "5.5 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Miffy was diagnosed with diabetes 2 weeks ago; Wei is new to giving insulin injections.")],
    user_turns=[
        "Should I feed Miffy before or after her insulin injection?",
        "Can I leave food out all day for her?",
        "What do I do if she doesn't eat before the injection?",
        "How often should I check in with the vet now that she's diabetic?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="tom_duke_diet_obese_dog",
    display="Tom",
    scenario="Tom's 6-year-old Labrador Duke weighs 42 kg but should weigh closer to 30 kg. The vet has recommended a structured weight-loss diet.",
    outcome="Pawly recommends a measured-portion weight management diet, suggests low-calorie treats (carrot, cucumber), explains body condition scoring, and reinforces consistent family feeding habits.",
    role="Guide structured canine weight-loss plan with measured portions and healthy treat alternatives.",
    criteria="Must recommend measured portions with a food scale; must suggest low-calorie treat alternatives; must address family consistency; must not recommend abrupt calorie elimination; must not over-medicalize routine weight management.",
    pet={"name": "Duke", "species": "dog", "breed": "Labrador Retriever", "age": "6 years", "weight": "42 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Duke has been overweight for 2 years; vet confirmed obesity at last visit; Tom's family gives frequent treats.")],
    user_turns=[
        "What's the best way to help Duke lose weight?",
        "How much should I cut his daily food by?",
        "What treats can he still have while dieting?",
        "My kids keep sneaking him food — how do I handle that?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="amy_pablo_diet_puppy_adult_transition",
    display="Amy",
    scenario="Amy's Miniature Poodle Pablo just turned 12 months old and she asks when and how to switch from puppy food to adult food.",
    outcome="Pawly explains that small breeds like Miniature Poodles can transition to adult food around 12 months, recommends a 7–10 day gradual transition, and advises choosing a high-quality adult food appropriate for small breeds.",
    role="Guide puppy-to-adult food transition for a small-breed dog.",
    criteria="Must specify approximate age for transition in small breeds; must recommend gradual transition schedule; must recommend small-breed appropriate adult food; must not over-medicalize a routine developmental milestone.",
    pet={"name": "Pablo", "species": "dog", "breed": "Miniature Poodle", "age": "12 months", "weight": "5 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Pablo turned 1 year old last week; Amy has been feeding puppy-formula kibble.")],
    user_turns=[
        "Pablo just turned 1 — is it time to switch to adult food?",
        "What's different about adult vs puppy food for small breeds?",
        "How do I switch without upsetting his stomach?",
        "How do I know when the new food agrees with him?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="linda_duchess_diet_hydration_dry_cat",
    display="Linda",
    scenario="Linda's 4-year-old Persian cat Duchess eats only dry food and Linda is worried she doesn't drink enough water.",
    outcome="Pawly explains cats' low thirst drive, recommends wet food supplementation or a cat water fountain, suggests adding water or broth to dry food, and notes the link between chronic low hydration and UTIs/CKD in cats.",
    role="Advise on increasing moisture intake for cats on dry-food diets.",
    criteria="Must explain cats' naturally low thirst drive; must recommend wet food supplement or fountain; must note UTI/kidney disease hydration link; must not over-medicalize routine hydration discussion.",
    pet={"name": "Duchess", "species": "cat", "breed": "Persian", "age": "4 years", "weight": "4.0 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Duchess eats only dry kibble and rarely drinks from her water bowl; vet mentioned hydration at the last visit.")],
    user_turns=[
        "Duchess barely drinks water — is that normal for cats?",
        "What can I do to get her to drink more?",
        "Would a cat water fountain actually help?",
        "Is there a way to add moisture without switching her off dry food entirely?",
    ],
    persona="P-05",
))

CASES.append(p1(
    name="marcus_dalmatian_diet_low_purine",
    display="Marcus",
    scenario="Marcus recently adopted a 2-year-old Dalmatian named Atlas. His breeder told him Dalmatians need a special low-purine diet to avoid urate stones.",
    outcome="Pawly explains Dalmatians' genetic predisposition to hyperuricemia and urate bladder stones, recommends a low-purine diet (avoiding organ meat, fish, high-purine legumes), and stresses the importance of hydration.",
    role="Guide breed-specific low-purine diet advice for Dalmatians.",
    criteria="Must explain Dalmatian urate stone predisposition; must list high-purine foods to avoid (organ meat, sardines, anchovies); must emphasise hydration; must not over-medicalize routine breed-specific dietary guidance.",
    pet={"name": "Atlas", "species": "dog", "breed": "Dalmatian", "age": "2 years", "weight": "24 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Marcus adopted Atlas from a Dalmatian rescue; breeder warned about low-purine diet requirement.")],
    user_turns=[
        "What foods should Atlas avoid as a Dalmatian?",
        "Why are Dalmatians different from other dogs when it comes to diet?",
        "Can I give him the same kibble I gave my previous dog?",
        "How important is hydration for a Dalmatian?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="hana_kona_diet_vegan_pet",
    display="Hana",
    scenario="Hana follows a vegan lifestyle and wants to feed her 3-year-old Bichon Frisé Kona a vegan diet. She also has a cat Yuki and wants to know if both can eat vegan.",
    outcome="Pawly explains dogs are omnivores and can survive on carefully supplemented plant-based diets, but cats are obligate carnivores and cannot safely eat vegan diets; recommends vet nutritionist oversight for the dog.",
    role="Provide accurate species-specific guidance on vegan pet diets distinguishing dogs from cats.",
    criteria="Must clearly distinguish dog (omnivore) from cat (obligate carnivore) nutritional needs; must warn that cats cannot be vegan safely; must recommend vet nutritionist oversight for the dog; must not over-medicalize routine diet discussion.",
    pet={"name": "Kona", "species": "dog", "breed": "Bichon Frisé", "age": "3 years", "weight": "6 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Hana is vegan and has both a dog (Kona) and a cat (Yuki); wants her values reflected in their diet.")],
    user_turns=[
        "Can Kona and Yuki both eat a vegan diet?",
        "Why can't cats eat vegan like dogs can?",
        "What nutrients would Kona be missing on a vegan diet?",
        "Are commercial vegan dog foods actually complete and balanced?",
    ],
    persona="P-04",
))

# ─────────────────────────────────────────────
# G-02  Daily Care  (8 cases)
# ─────────────────────────────────────────────

CASES.append(p1(
    name="peter_rex_care_athome_dental",
    display="Peter",
    scenario="Peter has never brushed his 3-year-old German Shepherd Rex's teeth and asks how to start an at-home dental care routine.",
    outcome="Pawly walks through a gradual desensitization process (finger, gauze, brush), recommends enzymatic dog toothpaste, advises 3–5 brushing sessions per week, and warns against human toothpaste (fluoride and xylitol toxicity).",
    role="Guide at-home dental care desensitization for adult dogs.",
    criteria="Must describe gradual desensitization steps; must specify enzymatic toothpaste; must warn against human toothpaste (fluoride/xylitol toxicity); must not push vet dental clean as the first step for a routine care question.",
    pet={"name": "Rex", "species": "dog", "breed": "German Shepherd", "age": "3 years", "weight": "32 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Peter has never brushed Rex's teeth; Rex has no diagnosed dental disease but bad breath noticed.")],
    user_turns=[
        "I've never brushed Rex's teeth — how do I start?",
        "Can I use human toothpaste?",
        "Rex hates having his face touched — how do I get him to cooperate?",
        "How often do I need to brush his teeth?",
    ],
    persona="P-02",
))

CASES.append(p1(
    name="wei_mochi_care_nail_trim_cat",
    display="Wei",
    scenario="Wei's 2-year-old Maine Coon Mochi has never had his nails trimmed and becomes extremely distressed when Wei tries. Wei asks for a step-by-step approach.",
    outcome="Pawly recommends a desensitization protocol over multiple sessions (touching paws, pressing toes, introducing clippers without cutting), suggests trimming one nail per session, recommends styptic powder, and advises identifying the quick.",
    role="Teach cat nail trimming desensitization to an anxious owner with an uncooperative cat.",
    criteria="Must describe multi-session desensitization; must explain the quick and how to avoid it; must recommend styptic powder; must not suggest sedation or vet visit as the only option for a routine nail trim.",
    pet={"name": "Mochi", "species": "cat", "breed": "Maine Coon", "age": "2 years", "weight": "7.2 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Wei tried trimming Mochi's nails once and Mochi scratched him badly; hasn't tried again since.")],
    user_turns=[
        "Mochi goes crazy when I try to cut his nails — how do I do this without getting scratched?",
        "Do I need to do all the nails at once?",
        "How do I find the quick in dark-coloured nails?",
        "What do I do if I accidentally cut too far?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="julie_bella_care_matted_grooming",
    display="Julie",
    scenario="Julie's 5-year-old Himalayan cat Bella has severe matting from lack of grooming. Julie asks how to manage matted fur at home.",
    outcome="Pawly explains the risks of cutting mats (skin fold injuries), recommends a detangling spray and dematting comb for mild mats, advises professional grooming for severe mats, and provides guidance on ongoing coat maintenance to prevent recurrence.",
    role="Advise on safe at-home mat management for long-haired cats, distinguishing mild from severe cases.",
    criteria="Must explain skin injury risk from cutting mats; must recommend professional grooming for severe mats; must advise detangling spray and comb for mild mats; must provide ongoing prevention advice.",
    pet={"name": "Bella", "species": "cat", "breed": "Himalayan", "age": "5 years", "weight": "4.6 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Bella has not been professionally groomed in 18 months; mats are significant on her flanks and belly.")],
    user_turns=[
        "Bella has really bad matting — can I cut them out myself?",
        "What's the safest way to remove mats at home?",
        "When should I just take her to a professional groomer?",
        "How do I stop the matting from happening again?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="oscar_finn_care_double_coat_bath",
    display="Oscar",
    scenario="Oscar's 4-year-old Alaskan Malamute Finn needs bathing, but Oscar isn't sure how often a double-coated dog should be bathed and how to dry the undercoat properly.",
    outcome="Pawly recommends bathing Finn every 6–8 weeks, explains the importance of fully drying the undercoat to prevent hot spots and skin infection, recommends a high-velocity dryer, and advises against shaving the double coat.",
    role="Advise on bathing frequency and drying technique for double-coated dog breeds.",
    criteria="Must specify appropriate bathing frequency for double-coated breeds; must address undercoat drying and hot spot risk; must warn against shaving double coats; must recommend high-velocity dryer for undercoat.",
    pet={"name": "Finn", "species": "dog", "breed": "Alaskan Malamute", "age": "4 years", "weight": "38 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Oscar bathes Finn roughly every 2 weeks because he smells; Finn's undercoat stays damp for hours after bathing.")],
    user_turns=[
        "How often should I bathe a double-coated dog like Finn?",
        "His undercoat takes forever to dry — does that matter?",
        "What happens if his undercoat stays damp?",
        "Should I shave his coat in summer to help him stay cool?",
    ],
    persona="P-02",
))

CASES.append(p1(
    name="sara_boo_care_ear_technique",
    display="Sara",
    scenario="Sara's 3-year-old Labrador Boo has floppy ears and the vet recommended regular ear cleaning. Sara asks for a step-by-step technique.",
    outcome="Pawly describes the correct ear cleaning technique (hold pinna, apply cleanser, massage base, allow head shake, wipe outer canal with cotton ball), warns against inserting cotton swabs, and lists infection warning signs.",
    role="Teach correct ear cleaning technique for floppy-eared dogs.",
    criteria="Must describe the correct technique step-by-step; must warn against inserting cotton swabs; must list infection warning signs (redness, odour, discharge); must not push vet visit for routine ear cleaning instruction.",
    pet={"name": "Boo", "species": "dog", "breed": "Labrador Retriever", "age": "3 years", "weight": "28 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Vet recommended monthly ear cleaning for Boo; Sara has never done it and is unsure of the technique.")],
    user_turns=[
        "How do I clean Boo's ears properly?",
        "Can I use cotton swabs inside the ear canal?",
        "How much cleanser do I use?",
        "What should I watch for to know if she has an infection?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="eric_peanut_care_anal_glands",
    display="Eric",
    scenario="Eric's 4-year-old Cavalier King Charles Spaniel Peanut scoots on the carpet frequently. Eric asks whether he can express Peanut's anal glands at home.",
    outcome="Pawly explains anal gland scooting as a signal of full or impacted glands, explains external expression technique for mild cases, warns that internal expression requires a vet, and notes signs of anal gland infection requiring a vet visit.",
    role="Advise on at-home anal gland management and limits of owner intervention.",
    criteria="Must explain external expression as appropriate for mild cases; must state that internal expression requires vet; must list signs of infection (swelling, bleeding, abscess); must not push vet visit for a routine first-time enquiry.",
    pet={"name": "Peanut", "species": "dog", "breed": "Cavalier King Charles Spaniel", "age": "4 years", "weight": "8 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Peanut scoots on the carpet regularly; vet expressed glands 3 months ago and showed Eric the external technique.")],
    user_turns=[
        "Peanut is scooting again — do his anal glands need expressing?",
        "Can I do it at home or does it always need to be at the vet?",
        "How do I do the external expression?",
        "What signs mean I need to go to the vet rather than doing it myself?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="mei_cloud_care_paw_hot_weather",
    display="Mei",
    scenario="Mei lives in Singapore and walks her 2-year-old Corgi Cloud on hot pavement during her lunch break. She asks how to protect Cloud's paw pads.",
    outcome="Pawly explains the 7-second pavement test, recommends walking before 8am or after 7pm, suggests paw wax for mild protection, describes boot acclimatization for full protection, and explains signs of burnt paw pads.",
    role="Advise on paw pad protection for dogs walked on hot pavement in a tropical climate.",
    criteria="Must explain the pavement temperature test; must recommend cooler walking times; must describe paw wax and/or boots; must list signs of paw pad burns; must not over-medicalize routine paw care.",
    pet={"name": "Cloud", "species": "dog", "breed": "Pembroke Welsh Corgi", "age": "2 years", "weight": "12 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Mei walks Cloud at noon in Singapore; pavement temperature can exceed 60°C on sunny days.")],
    user_turns=[
        "How do I know if the pavement is too hot for Cloud's paws?",
        "What can I do to protect her paws if I can only walk at midday?",
        "Are dog boots actually effective?",
        "What does a burnt paw pad look like and what do I do?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="nat_cleo_care_eye_discharge",
    display="Nat",
    scenario="Nat's 3-year-old Persian cat Cleo has daily eye discharge (brown-red staining near the inner corners). Nat asks how to manage it at home.",
    outcome="Pawly explains that epiphora (tear overflow) is common in flat-faced breeds, describes gentle daily cleaning with damp cotton pads, recommends eye cleaning solution made for cats, and notes signs that indicate a vet visit is needed (increased discharge, cloudiness, squinting).",
    role="Advise on routine eye discharge management for brachycephalic cats, distinguishing routine maintenance from clinical signs.",
    criteria="Must explain epiphora in flat-faced breeds; must recommend gentle daily cleaning technique; must specify when vet visit is needed; must not over-medicalize routine eye care for a known breed-specific trait.",
    pet={"name": "Cleo", "species": "cat", "breed": "Persian", "age": "3 years", "weight": "4.1 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Cleo has had brown staining near her eye corners since kittenhood; vet said it's breed-related at her last visit.")],
    user_turns=[
        "Cleo gets brown gunk around her eyes every day — how do I clean it?",
        "What should I use to clean around her eyes safely?",
        "How often do I need to do this?",
        "When does eye discharge mean I should take her to the vet?",
    ],
    persona="P-04",
))

# ─────────────────────────────────────────────
# G-03  Behaviour  (8 cases)
# ─────────────────────────────────────────────

CASES.append(p1(
    name="kim_zeus_behav_resource_guarding",
    display="Kim",
    scenario="Kim's 3-year-old Rottweiler Zeus growls at her other dog (a Poodle mix) when they approach his food bowl. Kim asks how to manage resource guarding in a multi-dog household.",
    outcome="Pawly explains resource guarding as normal canine behaviour, recommends separate feeding stations, parallel feeding at a distance, and the 'trade' technique, and cautions against punishment-based corrections.",
    role="Guide multi-dog resource guarding management with positive reinforcement techniques.",
    criteria="Must recommend separate feeding stations; must explain 'trade' technique; must advise against punishment-based corrections; must not recommend alpha-rolling or dominance techniques; must not push behaviourist referral as the first response for a moderate case.",
    pet={"name": "Zeus", "species": "dog", "breed": "Rottweiler", "age": "3 years", "weight": "42 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Zeus guards his food bowl; the Poodle mix, Toffee, was recently added to the household 4 months ago.")],
    user_turns=[
        "Zeus growls at Toffee when she gets near his bowl — how do I handle this?",
        "Should I feed them together or separately?",
        "What is the 'trade' technique?",
        "What should I do if the growling gets worse?",
    ],
    persona="P-02",
))

CASES.append(p1(
    name="leo_rocky_behav_leash_reactivity",
    display="Leo",
    scenario="Leo's 2-year-old Border Terrier Rocky lunges and barks at other dogs on leash. Leo asks how to manage leash reactivity.",
    outcome="Pawly explains threshold concept, counter-conditioning (look/click/treat), recommends maintaining sub-threshold distance, describes LAT (Look at That) game, and recommends front-clip harness.",
    role="Guide leash reactivity management using positive reinforcement and threshold management.",
    criteria="Must explain threshold concept; must recommend counter-conditioning; must recommend front-clip harness; must not recommend prong collar or shock collar; suggestions must be specific and actionable.",
    pet={"name": "Rocky", "species": "dog", "breed": "Border Terrier", "age": "2 years", "weight": "7 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Rocky lunges and barks intensely at other dogs; Leo has tried verbal correction but it doesn't help.")],
    user_turns=[
        "Rocky loses his mind at other dogs on leash — where do I start?",
        "What is 'threshold' and why does it matter?",
        "How do I do counter-conditioning with him?",
        "What gear should I use to manage him on walks?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="anna_biscuit_behav_counter_surfing",
    display="Anna",
    scenario="Anna's 1.5-year-old Beagle Biscuit steals food off the kitchen counter constantly. Anna asks how to stop counter-surfing.",
    outcome="Pawly explains that counter-surfing is self-reinforcing (finding food reinforces the behaviour), recommends management (keeping counters clear), and teaches the 'leave it' and 'off' commands with positive reinforcement.",
    role="Guide counter-surfing prevention with management and positive reinforcement training.",
    criteria="Must explain the self-reinforcing nature of counter-surfing; must recommend management (counters clear); must describe 'leave it' command training; must not recommend punishment-based corrections; must not push trainer referral for a routine training question.",
    pet={"name": "Biscuit", "species": "dog", "breed": "Beagle", "age": "1.5 years", "weight": "10 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Biscuit has stolen food off the counter 5 times in the past week; Anna's kitchen is always busy.")],
    user_turns=[
        "Biscuit keeps stealing food off the counter — how do I stop it?",
        "Why does telling her 'no' not seem to work?",
        "How do I teach 'leave it'?",
        "Is there anything I can put on the counter to deter her?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="tomas_luna_behav_separation_anxiety",
    display="Tomas",
    scenario="Tomas's 2-year-old Cockapoo Luna destroys furniture and howls when left alone. Tomas returned to the office after working from home for 2 years.",
    outcome="Pawly explains separation anxiety vs. boredom destruction, recommends graduated departure training starting with very short absences, a Kong-stuffed toy, a calming diffuser, and notes when a vet or behaviourist referral is warranted.",
    role="Guide separation anxiety management with graduated departure training and enrichment.",
    criteria="Must distinguish separation anxiety from boredom; must explain graduated departure training; must recommend enrichment (Kong); must note vet/behaviourist referral threshold for severe cases; must not push referral immediately for a moderate case.",
    pet={"name": "Luna", "species": "dog", "breed": "Cockapoo", "age": "2 years", "weight": "9 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Tomas worked from home for 2 years with Luna; returned to office 4 weeks ago; Luna's behaviour started immediately.")],
    user_turns=[
        "Luna is destroying the flat when I leave — is this separation anxiety or boredom?",
        "What is graduated departure training?",
        "What enrichment can I give her when I leave?",
        "When should I consider medication for her anxiety?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="rachel_tigger_behav_sudden_aggression",
    display="Rachel",
    scenario="Rachel's 5-year-old Domestic Shorthair cat Tigger has started hissing and swatting at Rachel without warning over the past 3 weeks. The aggression is new and out of character.",
    outcome="Pawly explains that sudden onset aggression in a cat with no history is a medical red flag (pain, hyperthyroidism, neurological), recommends a vet visit to rule out medical causes before pursuing behavioural approaches, and offers interim safety tips.",
    role="Triage sudden-onset aggression in cats, prioritising medical investigation before behavioural solutions.",
    criteria="Must flag sudden-onset aggression as a potential medical red flag; must recommend vet visit to rule out medical causes; must not focus primarily on behavioural solutions without medical investigation; must offer interim safety advice.",
    pet={"name": "Tigger", "species": "cat", "breed": "Domestic Shorthair", "age": "5 years", "weight": "5.2 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Tigger has been friendly and gentle his whole life; new aggression started 3 weeks ago with no clear trigger.")],
    user_turns=[
        "Tigger has started hissing and swiping at me out of nowhere — what's changed?",
        "Could this be a behavioural problem?",
        "Should I see a vet or try to work on this behaviourally first?",
        "How do I safely handle him in the meantime?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="nadia_snow_behav_litter_box_avoidance",
    display="Nadia",
    scenario="Nadia's 4-year-old Ragdoll cat Snow has started going outside the litter box. The problem started after Nadia changed litter brands 2 weeks ago.",
    outcome="Pawly explains litter aversion as a common cause of inappropriate elimination, recommends reverting to the previous litter, offers litter box setup tips (coverage, location, quantity), and notes when a vet check is needed to rule out UTI.",
    role="Triage litter box avoidance in cats, addressing both litter aversion and medical causes.",
    criteria="Must identify litter aversion as a likely cause given the timeline; must recommend reverting to the previous litter; must offer litter box setup guidance; must advise vet check if avoidance persists beyond 1 week of reverting.",
    pet={"name": "Snow", "species": "cat", "breed": "Ragdoll", "age": "4 years", "weight": "5.8 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Snow used the litter box perfectly until Nadia changed to a new pine-based litter 2 weeks ago.")],
    user_turns=[
        "Snow is peeing outside the litter box — could it be the new litter?",
        "How do I figure out what litter she prefers?",
        "Should I get more litter boxes?",
        "When should I take her to the vet about this?",
    ],
    persona="P-03",
))

CASES.append(p1(
    name="henry_max_behav_excessive_night_barking",
    display="Henry",
    scenario="Henry's 3-year-old Samoyed Max has started barking excessively at night, waking the household. The barking started about a month ago.",
    outcome="Pawly explores possible causes (hearing a noise or animal outside, separation anxiety, medical discomfort), recommends ruling out medical causes, suggests a white noise machine, and advises not rewarding the barking with attention.",
    role="Triage excessive night barking, distinguishing environmental, behavioural, and medical causes.",
    criteria="Must explore multiple potential causes; must recommend ruling out medical causes for sudden onset; must provide practical management suggestions (white noise, ignoring behaviour); must not push a vet visit as the sole response for a routine training enquiry.",
    pet={"name": "Max", "species": "dog", "breed": "Samoyed", "age": "3 years", "weight": "23 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Max never barked at night before; it started about a month ago around the same time Henry moved Max's crate location.")],
    user_turns=[
        "Max is barking every night and waking everyone up — why is he doing this?",
        "Could moving his crate have caused this?",
        "Is there a medical reason for sudden night barking?",
        "What can I do tonight to reduce the barking?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="yuki_kira_behav_tail_chasing",
    display="Yuki",
    scenario="Yuki's 1.5-year-old Bull Terrier Kira chases her own tail obsessively, sometimes for 20 minutes at a time. Yuki asks if this is normal.",
    outcome="Pawly explains that tail chasing in Bull Terriers can be a breed-specific compulsive behaviour (canine compulsive disorder / CCD), explains contributing factors (frustration, boredom, anxiety), recommends increasing enrichment and exercise, and flags severe cases for veterinary or behaviourist assessment.",
    role="Advise on compulsive tail chasing in Bull Terriers, distinguishing normal play from compulsive behaviour.",
    criteria="Must identify tail chasing in Bull Terriers as a potential CCD; must explain contributing factors; must recommend enrichment and exercise; must flag severe or escalating cases for vet/behaviourist; must not dismiss it as purely normal play.",
    pet={"name": "Kira", "species": "dog", "breed": "Bull Terrier", "age": "1.5 years", "weight": "18 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Kira has been tail chasing since 8 months old; Yuki thought it was cute at first but it's getting longer and more frequent.")],
    user_turns=[
        "Kira chases her tail for ages — is this normal for a Bull Terrier?",
        "When does tail chasing become a problem?",
        "What can I do to reduce it?",
        "Should I see a vet about it?",
    ],
    persona="P-01",
))

# ─────────────────────────────────────────────
# G-04  Routine Health  (10 cases)
# ─────────────────────────────────────────────

CASES.append(p1(
    name="alice_rosie_health_microchip",
    display="Alice",
    scenario="Alice is planning to microchip her 10-week-old kitten Rosie and asks what the process involves and whether it's painful.",
    outcome="Pawly explains the ISO 15-digit microchip, implantation site (scruff of neck/between shoulder blades), brief needle insertion, registration with a pet database, and reassures about minimal discomfort similar to a vaccine injection.",
    role="Educate cat owners on the microchipping procedure, including pain level and registration steps.",
    criteria="Must explain ISO 15-digit standard; must describe implantation process; must reassure about minimal pain; must mention registration database requirement; must not over-medicalize a routine procedure explanation.",
    pet={"name": "Rosie", "species": "cat", "breed": "Domestic Shorthair", "age": "10 weeks", "weight": "0.9 kg", "sex": "female intact"},
    prior_turns=[prior_turn("user", "Alice adopted Rosie last week; first vet appointment is next week.")],
    user_turns=[
        "What happens during a microchip procedure for a kitten?",
        "Will it hurt Rosie?",
        "Where is the chip placed?",
        "What do I need to do after the chip is implanted?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="bob_charlie_health_annual_bloodwork",
    display="Bob",
    scenario="Bob's 8-year-old Domestic Shorthair cat Charlie has never had bloodwork done. Bob asks whether annual bloodwork is really necessary for a seemingly healthy cat.",
    outcome="Pawly explains that cats are notorious for masking illness, that bloodwork at age 8+ can catch CKD, hyperthyroidism, diabetes, and anaemia before clinical signs appear, and recommends biannual tests for senior cats.",
    role="Explain the value of proactive annual bloodwork for senior cats who appear healthy.",
    criteria="Must explain cats' tendency to mask illness; must list conditions detectable with early bloodwork; must recommend biannual testing for cats 8+; must not dismiss routine screening as unnecessary.",
    pet={"name": "Charlie", "species": "cat", "breed": "Domestic Shorthair", "age": "8 years", "weight": "4.5 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Charlie has never had bloodwork; Bob's vet recently recommended annual senior screening.")],
    user_turns=[
        "Charlie seems perfectly healthy — is annual bloodwork really worth it at his age?",
        "What does bloodwork actually show for cats?",
        "What conditions can be caught early with bloodwork?",
        "How often should he have it done at age 8?",
    ],
    persona="P-05",
))

CASES.append(p1(
    name="diana_max_health_dental_anesthesia",
    display="Diana",
    scenario="Diana's 7-year-old Dachshund Max needs a professional dental cleaning. She is worried about the risks of general anaesthesia.",
    outcome="Pawly explains that modern anaesthesia in healthy dogs is very safe, describes pre-anaesthetic bloodwork as a risk-reduction measure, explains the monitoring protocols, and notes that untreated dental disease poses greater long-term health risks.",
    role="Reassure an anxious dog owner about anaesthetic risk for routine dental cleaning while being factually accurate.",
    criteria="Must explain modern anaesthetic safety; must mention pre-anaesthetic bloodwork; must explain monitoring protocols; must note the greater risk of untreated dental disease; must not dismiss the concern but must not catastrophize.",
    pet={"name": "Max", "species": "dog", "breed": "Dachshund", "age": "7 years", "weight": "9 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Max has Grade 3 periodontal disease; vet recommended dental cleaning; Diana heard stories about dogs not waking up from anaesthetic.")],
    user_turns=[
        "Is anaesthesia really safe for a 7-year-old dog?",
        "What can the vet do to make it safer?",
        "How would I know if Max is high risk for anaesthesia?",
        "What happens if I just skip the dental cleaning?",
    ],
    persona="P-05",
))

CASES.append(p1(
    name="grace_buddy_health_flea_tick_sg",
    display="Grace",
    scenario="Grace just moved to Singapore from the UK with her 4-year-old Labrador Buddy. She asks what flea and tick prevention is needed in Singapore's climate.",
    outcome="Pawly confirms that Singapore's tropical climate supports year-round flea and tick activity, recommends monthly preventive treatments (topical or oral), mentions the risk of tick paralysis (Rhipicephalus tick), and advises year-round prevention without interruption.",
    role="Advise on year-round flea and tick prevention appropriate for Singapore's tropical climate.",
    criteria="Must confirm year-round prevention required in Singapore; must mention tick paralysis risk; must recommend monthly preventive; must address product types (topical vs oral); must note vet consultation for product selection.",
    pet={"name": "Buddy", "species": "dog", "breed": "Labrador Retriever", "age": "4 years", "weight": "30 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Buddy was on seasonal flea/tick prevention in the UK; Grace is unsure if Singapore's requirements differ.")],
    user_turns=[
        "Do I need to give Buddy flea and tick prevention in Singapore year-round?",
        "What ticks are common in Singapore?",
        "What's the difference between topical and oral tick prevention?",
        "How often should he get the treatment?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="ivan_ruby_health_cavalier_heart",
    display="Ivan",
    scenario="Ivan's 3-year-old Cavalier King Charles Spaniel Ruby has not been screened for heart disease. Ivan reads that Cavaliers are prone to MVD and asks what screening he should do.",
    outcome="Pawly explains the breed's predisposition to mitral valve disease (MVD), recommends the CKCS MVD Breeding Protocol screening (cardiac auscultation by vet + specialist echocardiogram at 2.5 years), and notes early detection allows monitoring and treatment planning.",
    role="Guide a Cavalier owner on breed-specific heart disease screening.",
    criteria="Must explain CKCS predisposition to MVD; must recommend annual cardiac auscultation; must mention specialist echocardiogram screening; must explain value of early detection; must not dismiss screening as unnecessary.",
    pet={"name": "Ruby", "species": "dog", "breed": "Cavalier King Charles Spaniel", "age": "3 years", "weight": "7.5 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Ruby has never been cardiac screened; Ivan read Cavaliers are prone to heart disease at a young age.")],
    user_turns=[
        "How likely is Ruby to develop heart problems as a Cavalier?",
        "What screening does she need and when?",
        "What does the heart screening involve?",
        "What happens if she's diagnosed with early MVD?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="fatima_oscar_health_titer_test",
    display="Fatima",
    scenario="Fatima asks whether her 5-year-old cat Oscar needs annual booster vaccines or whether titer testing can replace them.",
    outcome="Pawly explains titer testing as a measure of existing antibody levels, notes that some vets and guidelines support triennial core vaccine schedules (WSAVA guidelines), and recommends discussing with the vet whether titer testing or standard boosters are appropriate.",
    role="Explain titer testing vs booster vaccination trade-offs for cats.",
    criteria="Must explain titer testing accurately; must mention WSAVA triennial guidelines; must recommend vet discussion for individualised schedule; must not dismiss titer testing as worthless or endorse it uncritically.",
    pet={"name": "Oscar", "species": "cat", "breed": "British Shorthair", "age": "5 years", "weight": "6 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Fatima's vet has always recommended annual boosters; she read about titer testing as an alternative.")],
    user_turns=[
        "What is a titer test and can it replace Oscar's annual vaccines?",
        "Are annual boosters really necessary for an adult indoor cat?",
        "What do the WSAVA guidelines say about vaccine frequency?",
        "How do I have this conversation with my vet?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="kai_mochi_health_senior_wellness",
    display="Kai",
    scenario="Kai's 9-year-old Shih Tzu Mochi is now a senior. Kai asks how often senior dogs need vet checkups and what a senior wellness exam includes.",
    outcome="Pawly recommends biannual vet visits for dogs 9+, explains what senior wellness exams cover (physical exam, bloodwork, urinalysis, blood pressure, dental assessment), and advises on common senior health changes to monitor at home.",
    role="Educate owners on senior dog wellness exam frequency and content.",
    criteria="Must recommend biannual visits for senior dogs; must list senior wellness exam components; must advise on at-home monitoring between exams; must not push annual-only or quarterly schedules without context.",
    pet={"name": "Mochi", "species": "dog", "breed": "Shih Tzu", "age": "9 years", "weight": "6 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Mochi has been healthy her whole life; Kai has taken her to the vet once a year; she was just classified as senior.")],
    user_turns=[
        "Now that Mochi is a senior, how often should I take her to the vet?",
        "What does a senior wellness exam involve?",
        "What should I be watching for at home between vet visits?",
        "At what age are dogs considered senior?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="nina_bella_health_spay_recovery",
    display="Nina",
    scenario="Nina's 5-month-old Domestic Shorthair kitten Bella was spayed this morning. Nina asks about the post-operative recovery timeline.",
    outcome="Pawly describes the 24-hour post-GA monitoring period, recommends e-collar use for 10–14 days, explains activity restriction, daily incision site checks, expected healing signs, and lists warning signs that require a vet call.",
    role="Guide a cat owner through post-spay recovery care with a clear timeline.",
    criteria="Must describe 24-hour monitoring; must mention e-collar; must state activity restriction duration; must list incision healing signs and complication warning signs; must not alarm unnecessarily over normal recovery.",
    pet={"name": "Bella", "species": "cat", "breed": "Domestic Shorthair", "age": "5 months", "weight": "2.5 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Bella just came home from the clinic 2 hours after spay surgery; she is groggy from anaesthesia.")],
    user_turns=[
        "What do I need to watch for tonight after Bella's spay?",
        "She keeps trying to lick the wound — what do I do?",
        "When can she go back to jumping and running?",
        "What are the signs I should call the vet about?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="jay_atlas_health_cryptorchid_neuter",
    display="Jay",
    scenario="Jay's 7-month-old French Bulldog Atlas has been diagnosed as cryptorchid (one retained testicle). Jay's vet recommends neutering. Jay asks why cryptorchid neutering is more complicated and urgent.",
    outcome="Pawly explains cryptorchidism (retained testicle in abdomen or inguinal canal), the elevated risk of testicular torsion and cancer in retained testicles, and why surgical removal is recommended with some urgency.",
    role="Explain cryptorchidism and urgency of neutering to an anxious first-time dog owner.",
    criteria="Must explain what cryptorchidism is; must explain cancer and torsion risk in retained testicle; must explain why surgical removal is recommended; must not minimise the medical significance; must not catastrophize.",
    pet={"name": "Atlas", "species": "dog", "breed": "French Bulldog", "age": "7 months", "weight": "9 kg", "sex": "male intact cryptorchid"},
    prior_turns=[prior_turn("user", "Jay's vet said Atlas has one retained testicle and recommended surgery; Jay doesn't understand why this is urgent.")],
    user_turns=[
        "What does it mean that Atlas is cryptorchid?",
        "Why does the retained testicle need to come out?",
        "Is this surgery more complicated than regular neutering?",
        "What happens if I don't do the surgery?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="sue_luna_health_kitten_first_visit",
    display="Sue",
    scenario="Sue just adopted an 8-week-old kitten Luna and asks what to expect at the first vet visit.",
    outcome="Pawly outlines the first vet visit checklist: physical exam, weight, parasite check, first vaccine (FVRCP), deworming, FIV/FeLV test discussion, microchipping, and spay/neuter timing discussion.",
    role="Prepare a new kitten owner for the first vet visit with a structured checklist.",
    criteria="Must list core components of a first kitten vet visit; must mention FVRCP vaccine; must mention deworming; must mention FIV/FeLV test discussion; must mention microchipping; must not overwhelm with non-essential advice.",
    pet={"name": "Luna", "species": "cat", "breed": "Domestic Shorthair", "age": "8 weeks", "weight": "0.8 kg", "sex": "female intact"},
    prior_turns=[prior_turn("user", "Sue adopted Luna from a neighbour's litter 3 days ago; Luna has had no vet care yet.")],
    user_turns=[
        "What should I expect at Luna's first vet visit?",
        "What vaccines does she need at 8 weeks?",
        "Will they check her for parasites?",
        "When should I think about spaying her?",
    ],
    persona="P-01",
))

# ─────────────────────────────────────────────
# G-05  Life Stages  (8 cases)
# ─────────────────────────────────────────────

CASES.append(p1(
    name="tina_daisy_stage_puppy_socialisation",
    display="Tina",
    scenario="Tina just brought home a 7-week-old Golden Retriever puppy, Daisy. She asks about the socialisation window and what to expose Daisy to.",
    outcome="Pawly explains the critical socialisation window (3–14 weeks), lists exposure categories (sounds, surfaces, children, strangers, other animals), explains how to introduce experiences positively, and notes the importance of not waiting until full vaccination.",
    role="Guide a new puppy owner through the critical socialisation window with specific, actionable advice.",
    criteria="Must state the 3–14 week socialisation window; must list multiple exposure categories; must address vaccination window concern; must warn against forcing fearful exposures; suggestions must be specific and actionable.",
    pet={"name": "Daisy", "species": "dog", "breed": "Golden Retriever", "age": "7 weeks", "weight": "2.8 kg", "sex": "female intact"},
    prior_turns=[prior_turn("user", "Tina just brought Daisy home at 7 weeks; first vet visit is scheduled for next week.")],
    user_turns=[
        "When is the critical window for socialising a puppy like Daisy?",
        "What exactly should I expose her to?",
        "She's not fully vaccinated yet — can she still meet other dogs?",
        "What if she seems scared of something new?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="wei_peanut_stage_kitten_proofing",
    display="Wei",
    scenario="Wei is about to bring home a 10-week-old kitten Peanut. He asks how to kitten-proof his apartment before the kitten arrives.",
    outcome="Pawly provides a room-by-room kitten-proofing checklist: secure loose cables, cover toxic plants, secure balcony/windows, hide small swallowable objects, secure washing machines and dryers, store cleaning chemicals out of reach.",
    role="Provide a comprehensive kitten-proofing checklist for an apartment environment.",
    criteria="Must cover multiple hazard categories (cables, toxic plants, balcony, small objects, chemicals); must mention washing machine/dryer safety; must include a note on toxic household plants; must be practical and apartment-specific.",
    pet={"name": "Peanut", "species": "cat", "breed": "Domestic Shorthair", "age": "10 weeks", "weight": "0.85 kg", "sex": "male intact"},
    prior_turns=[prior_turn("user", "Wei has never owned a cat before; he lives in a high-rise apartment.")],
    user_turns=[
        "How do I kitten-proof my apartment before Peanut comes home?",
        "Are there any plants I should remove?",
        "What should I do about the balcony?",
        "What common household items are most dangerous for kittens?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="sam_bella_stage_senior_arthritis",
    display="Sam",
    scenario="Sam's 9-year-old Golden Retriever Bella has been diagnosed with osteoarthritis. Sam asks what life-stage management changes to make.",
    outcome="Pawly advises on arthritis management: low-impact exercise (swimming, short walks), orthopaedic bed, joint supplements (glucosamine/chondroitin/omega-3), ramps instead of stairs, maintaining lean weight, and recommends regular vet reassessment for pain management.",
    role="Guide senior dog arthritis management through life-stage adjustments and appropriate supplementation.",
    criteria="Must recommend low-impact exercise; must recommend orthopaedic bed; must list joint supplements; must recommend weight management; must recommend vet reassessment for pain management medication; must not over-medicalize a routine management question.",
    pet={"name": "Bella", "species": "dog", "breed": "Golden Retriever", "age": "9 years", "weight": "29 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Bella was diagnosed with osteoarthritis 2 months ago; vet started her on NSAIDs short-term; Sam wants to know what else he can do.")],
    user_turns=[
        "What changes should I make to Bella's daily life now that she has arthritis?",
        "What supplements actually help with joint disease in dogs?",
        "How much exercise should she still get?",
        "How do I know if she's in pain if she can't tell me?",
    ],
    persona="P-02",
))

CASES.append(p1(
    name="irene_noodle_stage_geriatric_cognitive",
    display="Irene",
    scenario="Irene's 14-year-old Domestic Shorthair cat Noodle has been seeming confused at night — yowling, getting stuck in corners, staring at walls. Irene asks if this is dementia.",
    outcome="Pawly explains feline cognitive dysfunction syndrome (CDS), describes typical signs (night yowling, disorientation, changed sleep-wake cycle), notes it is analogous to Alzheimer's in humans, recommends a vet visit to confirm and rule out pain/hyperthyroidism, and suggests environmental enrichment and night lights.",
    role="Educate owners on feline cognitive dysfunction syndrome and distinguish it from other geriatric conditions.",
    criteria="Must name and explain CDS; must list common symptoms; must recommend vet visit to rule out other causes; must suggest practical management (night light, enrichment); must not dismiss night yowling as normal aging without investigation.",
    pet={"name": "Noodle", "species": "cat", "breed": "Domestic Shorthair", "age": "14 years", "weight": "3.8 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Noodle has been yowling at 3am and getting confused in familiar spaces for 2 months.")],
    user_turns=[
        "Noodle is acting confused at night — could he have dementia?",
        "What is feline cognitive dysfunction?",
        "Is there anything that causes the same symptoms I should rule out first?",
        "What can I do to help him at home?",
    ],
    persona="P-05",
))

CASES.append(p1(
    name="karen_muffin_stage_postspay_weight",
    display="Karen",
    scenario="Karen's 7-month-old Domestic Shorthair Muffin was spayed 2 months ago and has been gaining weight steadily. Karen asks if this is normal post-spay.",
    outcome="Pawly explains that spaying reduces metabolic rate (lower oestrogen and progesterone), recommends transitioning to a portion-controlled post-spay diet, reducing caloric intake by 20–25%, and increasing play exercise to compensate.",
    role="Advise on post-spay weight management for cats.",
    criteria="Must explain metabolic rate reduction post-spay; must recommend portion control; must recommend activity increase; must not suggest vet visit as the first step for routine post-spay weight gain management.",
    pet={"name": "Muffin", "species": "cat", "breed": "Domestic Shorthair", "age": "7 months", "weight": "3.8 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Muffin was spayed 2 months ago; Karen noticed weight gain of approximately 0.5kg in 6 weeks.")],
    user_turns=[
        "Muffin has been gaining weight since her spay — is that normal?",
        "Why does spaying cause weight gain?",
        "How much should I reduce her food?",
        "What can I do to help her stay at a healthy weight?",
    ],
    persona="P-03",
))

CASES.append(p1(
    name="james_coco_stage_adolescent_behaviour",
    display="James",
    scenario="James's 9-month-old Border Collie Coco was making great progress in obedience training but has become rebellious and is ignoring commands she previously knew.",
    outcome="Pawly explains canine adolescence (6–18 months), hormonal changes, the secondary fear period, recommends consistent positive reinforcement, short engaging training sessions, and patience.",
    role="Help owners understand and manage canine adolescent regression in training.",
    criteria="Must explain adolescence as a developmental stage; must mention secondary fear period; must recommend consistent positive reinforcement; must reassure the regression is temporary; must not suggest punitive correction.",
    pet={"name": "Coco", "species": "dog", "breed": "Border Collie", "age": "9 months", "weight": "14 kg", "sex": "female intact"},
    prior_turns=[prior_turn("user", "Coco graduated puppy classes at 4 months with distinction; now ignores recall and sits commands entirely.")],
    user_turns=[
        "Coco was brilliant in puppy class but now she ignores everything — what happened?",
        "Is this a phase or did I do something wrong?",
        "How do I keep training when she just refuses?",
        "Will she go back to being responsive?",
    ],
    persona="P-02",
))

CASES.append(p1(
    name="helen_pip_stage_orphaned_kittens",
    display="Helen",
    scenario="Helen found a litter of 3-day-old orphaned kittens. She asks how to care for them without a mother cat.",
    outcome="Pawly explains feeding schedule (every 2 hours with KMR kitten milk replacer, never cow's milk), stimulation for elimination, warmth (incubator at 29–32°C), and refers to a local rescue for specialist support.",
    role="Provide emergency orphaned kitten care guidance with appropriate feeding and warmth protocols.",
    criteria="Must specify KMR formula and feeding frequency; must warn against cow's milk; must explain stimulation for elimination; must address warmth requirements; must recommend local rescue/vet for ongoing support.",
    pet={"name": "N/A (orphaned litter)", "species": "cat", "breed": "Unknown", "age": "3 days", "weight": "~100g each", "sex": "unknown"},
    prior_turns=[prior_turn("user", "Helen found 4 kittens approximately 3 days old under a bush; no mother cat present.")],
    user_turns=[
        "I found newborn kittens with no mum — what do I do?",
        "What do I feed them and how often?",
        "How do I keep them warm enough?",
        "What else do I need to do for them to survive?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="david_rocky_stage_new_baby",
    display="David",
    scenario="David has a 3-year-old German Shepherd Rocky. David's wife is 7 months pregnant and they want to know how to prepare Rocky for the new baby.",
    outcome="Pawly recommends gradual preparation (baby sounds, smells from blankets, changing routines early, establishing boundaries before the baby arrives), and supervised introduction protocol when the baby comes home.",
    role="Guide owners on preparing a dog for a new baby with a proactive preparation plan.",
    criteria="Must recommend gradual exposure to baby sounds and smells; must recommend establishing boundaries and routines before arrival; must describe supervised introduction protocol; must not over-alarm about dog safety with babies.",
    pet={"name": "Rocky", "species": "dog", "breed": "German Shepherd", "age": "3 years", "weight": "34 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Rocky has always been the centre of attention; no children in the household yet; baby due in 2 months.")],
    user_turns=[
        "How do I prepare Rocky for our new baby?",
        "Should I start changing his routine now?",
        "How do I introduce Rocky to the baby when we come home from hospital?",
        "What boundaries should I set before the baby arrives?",
    ],
    persona="P-06",
))

# ─────────────────────────────────────────────
# G-06  User Already Googled  (5 cases)
# ─────────────────────────────────────────────

CASES.append(p1(
    name="lisa_mittens_google_milk_cats",
    display="Lisa",
    scenario="Lisa read that cats should not have cow's milk and asks Pawly to confirm whether this is true.",
    outcome="Pawly confirms that most adult cats are lactose intolerant, that cow's milk can cause diarrhoea and GI upset, and clarifies that occasional small amounts may not cause obvious harm in some cats but is still not recommended.",
    role="Confirm accurate internet information while adding useful nuance.",
    criteria="Must confirm cats are typically lactose intolerant; must explain diarrhoea risk; must note that severity varies; must not dismiss the concern or overcorrect toward 'cow's milk is fine'; warm persona.",
    pet={"name": "Mittens", "species": "cat", "breed": "Tabby", "age": "4 years", "weight": "4.1 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Lisa read that cow's milk is bad for cats and wants to confirm before giving it to Mittens as a treat.")],
    user_turns=[
        "Is it true that cats can't have cow's milk?",
        "Mittens seems to like it though — does that mean she's okay with it?",
        "Are there any dairy products that are safe for cats?",
        "What happens if she has a small amount occasionally?",
    ],
    persona="P-03",
))

CASES.append(p1(
    name="dan_rex_google_raw_forum",
    display="Dan",
    scenario="Dan read on a Facebook pet group that raw feeding is always superior to kibble and eliminates all disease. He asks Pawly if this is true.",
    outcome="Pawly acknowledges that raw feeding has some benefits but corrects the overclaim ('eliminates all disease'), explains hygiene risks (Salmonella, pathogen shedding), notes that kibble can also be high quality, and recommends a balanced evidence-informed perspective.",
    role="Correct overclaims from social media about raw feeding while remaining balanced.",
    criteria="Must acknowledge some benefits of raw feeding without endorsing the overclaim; must explain hygiene risks; must note that quality kibble is a legitimate option; must not dismiss raw feeding entirely; warm and non-preachy tone.",
    pet={"name": "Rex", "species": "dog", "breed": "German Shepherd", "age": "5 years", "weight": "35 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Dan read on Facebook that raw feeding cures everything and kibble causes cancer; he's considering switching Rex immediately.")],
    user_turns=[
        "I read that raw feeding eliminates disease and kibble causes cancer — is that true?",
        "Why do so many pet owners swear by raw then?",
        "What are the actual risks of raw feeding?",
        "Is there a middle ground between raw and kibble?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="hong_charlie_google_garlic_immunity",
    display="Hong",
    scenario="Hong read that garlic boosts dog immunity and wants to add it to his 4-year-old Dachshund Charlie's food daily.",
    outcome="Pawly clearly explains that garlic (like onion) is toxic to dogs even in small amounts (Heinz body anaemia, oxidative damage to red blood cells), warns that the toxicity is cumulative, and advises against it entirely.",
    role="Clearly correct a dangerous pet health myth while being warm and non-condescending.",
    criteria="Must clearly state garlic is toxic to dogs; must explain Heinz body anaemia; must note cumulative toxicity; must not hedge or soften the danger; must not be preachy or condescending.",
    pet={"name": "Charlie", "species": "dog", "breed": "Dachshund", "age": "4 years", "weight": "9 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Hong read a natural pet health website recommending garlic as an immunity booster for dogs.")],
    user_turns=[
        "I read garlic boosts dog immunity — can I add it to Charlie's food?",
        "The article said just a small amount is fine — is that true?",
        "What does garlic actually do to dogs?",
        "Are there safe alternatives that actually boost immunity?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="yuki_snow_google_ice_cubes_bloat",
    display="Yuki",
    scenario="Yuki read online that giving ice cubes to dogs causes bloat (GDV) and is dangerous. She asks Pawly whether this is true.",
    outcome="Pawly explains that the ice cube–bloat myth is not supported by evidence, clarifies the actual risk factors for GDV (large breed, eating large meals, exercise after eating), and notes that ice cubes in moderation are generally safe for dogs.",
    role="Debunk a pet health myth while providing accurate information about actual GDV risk factors.",
    criteria="Must debunk the ice-cube/bloat myth clearly; must explain actual GDV risk factors; must affirm ice cubes in moderation are generally safe; must not hedge excessively or leave the user unsure whether ice is dangerous.",
    pet={"name": "Snow", "species": "dog", "breed": "Husky", "age": "3 years", "weight": "24 kg", "sex": "female spayed"},
    prior_turns=[prior_turn("user", "Yuki stopped giving Snow ice cubes after reading an article claiming they cause bloat.")],
    user_turns=[
        "Is it true that ice cubes cause bloat in dogs?",
        "Where did this myth come from?",
        "What actually causes bloat then?",
        "Is it safe to give Snow ice cubes on a hot day?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="peter_biscuit_google_essential_oils",
    display="Peter",
    scenario="Peter read that lavender essential oil calms anxious dogs and wants to diffuse it around his 2-year-old Pomeranian Biscuit.",
    outcome="Pawly explains that dogs' olfactory sensitivity makes essential oil diffusers potentially overwhelming and that some oils (tea tree, pennyroyal, eucalyptus) are outright toxic; notes that lavender has limited evidence for calming in dogs and recommends veterinary-approved calming options instead.",
    role="Evaluate essential oil safety for pets and recommend evidence-based alternatives.",
    criteria="Must explain dogs' olfactory sensitivity; must name clearly toxic oils (tea tree, pennyroyal); must note limited evidence for lavender calming; must recommend vet-approved calming alternatives; must not endorse diffusing essential oils around pets.",
    pet={"name": "Biscuit", "species": "dog", "breed": "Pomeranian", "age": "2 years", "weight": "3.5 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Peter's Pomeranian Biscuit is anxious during thunderstorms; Peter read lavender oil diffusers are a safe calming method.")],
    user_turns=[
        "Can I diffuse lavender oil to calm Biscuit during thunderstorms?",
        "Are essential oils safe around dogs?",
        "Which oils are actually dangerous for dogs?",
        "What are safer options for calming an anxious dog during storms?",
    ],
    persona="P-06",
))

# ─────────────────────────────────────────────
# G-07  Singapore Localisation  (5 cases)
# ─────────────────────────────────────────────

CASES.append(p1(
    name="wei_gogo_sg_hdb_limits",
    display="Wei",
    scenario="Wei lives in an HDB flat and wants to know how many dogs he is allowed to keep and whether his Shih Tzu and a prospective Maltese both qualify.",
    outcome="Pawly explains the HDB limit of one dog per flat under the HDB Pet Dog Scheme, that both Shih Tzu and Maltese are on the approved breed list, but that keeping two dogs would violate HDB rules, and directs Wei to check HDB's official website for the current approved breed list.",
    role="Advise Singapore HDB residents on multi-dog ownership limits and the approved breed list.",
    criteria="Must state the one-dog-per-HDB-flat limit; must confirm both breeds are typically on the approved list; must note that two dogs would violate the rules; must direct to HDB official website for the current list.",
    pet={"name": "GoGo", "species": "dog", "breed": "Shih Tzu", "age": "2 years", "weight": "5 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Wei has a Shih Tzu and is considering adding a Maltese; he lives in a 4-room HDB flat.")],
    user_turns=[
        "How many dogs am I allowed to keep in my HDB flat?",
        "Are Shih Tzus and Malteses both approved HDB breeds?",
        "Can I keep two approved breeds at the same time?",
        "Where do I find the official list of HDB-approved dogs?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="lin_tortoise_sg_avs_exotic",
    display="Lin",
    scenario="Lin wants to keep a red-eared slider tortoise in Singapore and asks if this is legal and what AVS regulations apply.",
    outcome="Pawly explains that red-eared sliders are legal to keep in Singapore under AVS regulations, explains the licence is not required for sliders under 30cm, mentions that sliders cannot be released into the wild (invasive species), and recommends verifying current regulations on the AVS website.",
    role="Advise on Singapore exotic pet regulations for red-eared slider turtles.",
    criteria="Must confirm red-eared sliders are generally legal to keep in Singapore; must note the invasive species prohibition on release; must recommend AVS website for current regulations; must not fabricate licensing requirements.",
    pet={"name": "N/A (prospective tortoise)", "species": "reptile", "breed": "Red-eared Slider", "age": "N/A", "weight": "N/A", "sex": "N/A"},
    prior_turns=[prior_turn("user", "Lin is considering buying a red-eared slider from a pet shop in Singapore.")],
    user_turns=[
        "Can I legally keep a red-eared slider in Singapore?",
        "Do I need a licence for it?",
        "What are the rules about releasing it if I can't care for it anymore?",
        "Where can I check the latest AVS rules on exotic pets?",
    ],
    persona="P-03",
))

CASES.append(p1(
    name="sam_brownie_sg_heatstroke",
    display="Sam",
    scenario="Sam walks his 4-year-old Pug Brownie in Singapore midday. He asks what to do if Brownie shows signs of heatstroke.",
    outcome="Pawly explains that Pugs are high-risk for heatstroke due to brachycephalic anatomy, describes early signs (excessive panting, drooling, lethargy), explains the emergency cooling protocol (cool wet towels, move to shade/aircon, cool water), and directs Sam to a 24-hour vet immediately.",
    role="Advise on heatstroke recognition and emergency response for a high-risk brachycephalic dog in Singapore.",
    criteria="Must note Pug's elevated brachycephalic risk for heatstroke; must list early signs; must describe emergency cooling steps; must direct to 24-hour vet as an emergency; must recommend prevention (walk timing, hydration).",
    pet={"name": "Brownie", "species": "dog", "breed": "Pug", "age": "4 years", "weight": "8 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Sam walks Brownie at noon due to his schedule; Singapore temperature is typically 31–34°C midday.")],
    user_turns=[
        "How do I know if Brownie is getting heatstroke on our walks?",
        "What's my first step if I think he's overheating?",
        "Should I use ice or cold water to cool him down?",
        "Is Brownie more at risk than other dogs because he's a Pug?",
    ],
    persona="P-02",
))

CASES.append(p1(
    name="jun_kopi_sg_24h_vet",
    display="Jun",
    scenario="Jun's dog Kopi has been vomiting blood at 11pm. Jun asks how to find a 24-hour vet in Singapore urgently.",
    outcome="Pawly acknowledges the urgency, confirms this is an emergency warranting immediate veterinary attention, provides the names of known 24-hour vet hospitals in Singapore (Veterinary Emergency & Specialty Hospital, Animal Emergency & Referral Centre, Mount Pleasant vet), and advises Jun to call ahead while heading to the clinic.",
    role="Provide urgent Singapore-specific 24-hour veterinary resources with appropriate emergency framing.",
    criteria="Must acknowledge urgency; must name known 24-hour vets in Singapore; must advise calling ahead; must not downplay bloody vomiting as non-urgent; must not fabricate clinic details — name known facilities only.",
    pet={"name": "Kopi", "species": "dog", "breed": "Singapore Special", "age": "5 years", "weight": "15 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Kopi started vomiting bright red blood 30 minutes ago; Jun's usual vet clinic is closed.")],
    user_turns=[
        "Kopi is vomiting blood at night — where can I take him in Singapore right now?",
        "Is this really an emergency or can I wait until morning?",
        "Which 24-hour vets in Singapore are the most equipped?",
        "Should I call before going in?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="ah_wei_dog_sg_singlish",
    display="Ah Wei",
    scenario="Ah Wei asks in Singlish about what to do during Chinese New Year fireworks season when his dog Koko is very scared.",
    outcome="Pawly responds warmly and clearly (not mocking the Singlish), explains noise phobia management strategies (safe den, white noise, calming wrap, pheromone diffuser), notes that the fear is common during festive season in Singapore, and recommends discussing anti-anxiety medication with a vet for severe cases.",
    role="Respond warmly and helpfully to a Singlish-phrased pet care question about noise phobia during Singapore festive season.",
    criteria="Must respond to the Singlish input without mocking or correcting the language; must address firework/festive noise phobia strategies; must recommend vet for severe cases; must use a warm approachable tone; must be Singapore-context aware (CNY fireworks).",
    pet={"name": "Koko", "species": "dog", "breed": "Mixed Breed", "age": "3 years", "weight": "10 kg", "sex": "male neutered"},
    prior_turns=[prior_turn("user", "Ah Wei is a Singaporean owner who communicates naturally in Singlish.")],
    user_turns=[
        "eh my dog Koko sibei scared of firework season leh, CNY coming already he start shaking. what to do ah?",
        "last year he hide under the bed the whole night, very kesian",
        "can give him something to calm down or not?",
        "my neighbour say can give panadol, that one safe or not?",
    ],
    persona="P-03",
))

# ─────────────────────────────────────────────
# Validate and write
# ─────────────────────────────────────────────

expected = 10 + 8 + 8 + 10 + 8 + 5 + 5  # = 54
assert len(CASES) == expected, f"Expected {expected} cases, got {len(CASES)}"

print(f"Total cases: {len(CASES)}")
OUT.write_text(json.dumps(CASES, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Written to {OUT}")
