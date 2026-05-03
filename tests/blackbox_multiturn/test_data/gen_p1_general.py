"""
Generate P1 General Green-light cases (54 cases)
Sub-categories:
  G-01 Diet/Nutrition         10 cases
  G-02 Daily Care             8 cases
  G-03 Behavior               8 cases
  G-04 Routine Health         10 cases
  G-05 Life Stages            8 cases
  G-06 User Already Googled   5 cases
  G-07 Singapore Localization 5 cases
"""
import json, pathlib

OUT = pathlib.Path(__file__).parent / "multiturn_pawly_regression_test_p1_general.json"

def p1(name, display, scenario, outcome, role, criteria, pet, memories, user_turns, persona,
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
        "memories": memories,
        "recent_turns": [],
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

def mem(role, content):
    return {"role": role, "content": content}

CASES = []

# ─────────────────────────────────────────────
# G-01  Diet / Nutrition  (10 cases)
# ─────────────────────────────────────────────

CASES.append(p1(
    name="priya_mango_diet_raw_food",
    display="Priya",
    scenario="Priya asks Pawly whether switching her 2-year-old Beagle, Mango, to a raw-food diet is safe.",
    outcome="Pawly explains balanced-raw-diet principles, protein rotation, hygiene risks, and advises consulting a vet nutritionist for a transition plan.",
    role="Provide balanced, evidence-informed nutritional guidance for dogs on raw diets.",
    criteria="Must cover protein variety, raw-diet hygiene, and recommend professional nutritional advice; must not endorse raw-only diet without caveats.",
    pet={"name": "Mango", "species": "dog", "breed": "Beagle", "age": "2 years", "weight": "11 kg", "sex": "male neutered"},
    memories=[mem("user", "Priya has been feeding Mango kibble but is curious about raw after reading a pet blog.")],
    user_turns=[
        "Is a raw food diet actually good for dogs like Mango?",
        "What proteins should I rotate?",
        "What about hygiene — my kids touch him after eating.",
        "Should I talk to a vet first?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="james_biscuit_diet_grain_free",
    display="James",
    scenario="James wants to know whether grain-free kibble is beneficial or risky for his 4-year-old Golden Retriever, Biscuit.",
    outcome="Pawly explains the FDA DCM investigation context, notes evidence is mixed, and suggests discussing grain-inclusive options with a vet.",
    role="Discuss grain-free diet controversy objectively and support evidence-based decisions.",
    criteria="Must mention DCM concern without catastrophizing; must recommend vet consultation; must not definitively condemn grain-free diets.",
    pet={"name": "Biscuit", "species": "dog", "breed": "Golden Retriever", "age": "4 years", "weight": "30 kg", "sex": "male neutered"},
    memories=[mem("user", "James switched to grain-free kibble 6 months ago after a friend's recommendation.")],
    user_turns=[
        "I heard grain-free food can cause heart problems — is that true?",
        "What's the DCM link exactly?",
        "Should I switch Biscuit back to grain-inclusive?",
        "Which brands are safer?",
    ],
    persona="P-02",
))

CASES.append(p1(
    name="aisha_pepper_diet_homecook",
    display="Aisha",
    scenario="Aisha wants to start home-cooking for her 5-year-old Miniature Schnauzer, Pepper, to reduce processed ingredients.",
    outcome="Pawly provides a balanced home-cooked framework (protein, carb, fat, supplements), warns about missing micronutrients, and recommends a board-certified nutritionist.",
    role="Guide home-cooking for dogs with attention to nutritional completeness.",
    criteria="Must highlight risk of nutrient deficiencies; must list essential supplements (calcium, taurine, etc.); must recommend vet-nutritionist sign-off.",
    pet={"name": "Pepper", "species": "dog", "breed": "Miniature Schnauzer", "age": "5 years", "weight": "7 kg", "sex": "female spayed"},
    memories=[mem("user", "Aisha is budget-conscious and believes home cooking is healthier.")],
    user_turns=[
        "What do I need to include in home-cooked meals for Pepper?",
        "What vegetables are safe for Schnauzers?",
        "Do I need to add supplements?",
        "How do I know the portions are right?",
    ],
    persona="P-03",
))

CASES.append(p1(
    name="kai_noodle_diet_senior",
    display="Kai",
    scenario="Kai's 10-year-old Domestic Shorthair cat, Noodle, has been losing weight and Kai asks whether changing to senior food would help.",
    outcome="Pawly explains senior food benefits (reduced phosphorus, joint support), notes weight loss in senior cats warrants vet evaluation, and recommends a blood panel.",
    role="Advise on senior cat nutrition while flagging clinical signs needing vet attention.",
    criteria="Must not dismiss weight loss as normal aging; must recommend vet check; must explain senior-formula benefits.",
    pet={"name": "Noodle", "species": "cat", "breed": "Domestic Shorthair", "age": "10 years", "weight": "3.8 kg", "sex": "female spayed"},
    memories=[mem("user", "Noodle has been eating the same adult kibble for 3 years; recently lost 0.4 kg over 2 months.")],
    user_turns=[
        "Noodle's been losing weight — should I switch her to senior food?",
        "What's different about senior cat food?",
        "Is the weight loss just because she's getting older?",
        "When should I take her to the vet?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="mei_tofu_diet_vegan",
    display="Mei",
    scenario="Mei asks whether she can feed her 3-year-old Shih Tzu, Tofu, a vegan diet.",
    outcome="Pawly explains dogs are omnivores and can technically survive on plant-based diets with careful supplementation, but cats cannot; advises consulting a nutritionist.",
    role="Provide accurate species-specific nutritional guidance on vegan pet diets.",
    criteria="Must clarify dogs vs. cats nutritional needs; must warn about taurine, vitamin D3, and B12 in dogs on vegan diets; must recommend vet or nutritionist oversight.",
    pet={"name": "Tofu", "species": "dog", "breed": "Shih Tzu", "age": "3 years", "weight": "5.5 kg", "sex": "male neutered"},
    memories=[mem("user", "Mei follows a vegan lifestyle and wants her pet's diet to align with her values.")],
    user_turns=[
        "Can Tofu eat vegan food like I do?",
        "What nutrients would he be missing?",
        "Are there commercial vegan dog foods that are safe?",
        "What signs would tell me it's not working?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="ravi_charlie_diet_treats",
    display="Ravi",
    scenario="Ravi's 6-year-old Labrador, Charlie, is overweight and Ravi asks how to cut back on treats without causing distress.",
    outcome="Pawly advises using low-calorie treat alternatives, reducing treat size, keeping total treats under 10% of daily calories, and establishing activity goals.",
    role="Support healthy weight management for dogs through balanced treat strategies.",
    criteria="Must quantify treat calorie limits; must suggest low-calorie alternatives (carrot, green bean); must not suggest abrupt treat elimination.",
    pet={"name": "Charlie", "species": "dog", "breed": "Labrador Retriever", "age": "6 years", "weight": "38 kg", "sex": "male neutered"},
    memories=[mem("user", "Ravi gives Charlie treats during training and as rewards — approximately 10 treats per day.")],
    user_turns=[
        "Charlie's overweight — how do I cut treats without him getting upset?",
        "What are low-calorie treat options?",
        "How many treats per day is too many?",
        "Should I also change his meal portions?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="sophie_boba_diet_wetfood",
    display="Sophie",
    scenario="Teen Sophie asks whether feeding her 2-year-old Persian cat, Boba, exclusively wet food is okay.",
    outcome="Pawly explains the benefits of wet food (hydration, palatability) and notes that dental hygiene must be maintained separately, suggesting dental treats or brushing.",
    role="Advise on wet-food-only diets for cats with attention to dental health.",
    criteria="Must affirm wet food benefits; must address dental health maintenance; must not discourage wet-food diets.",
    pet={"name": "Boba", "species": "cat", "breed": "Persian", "age": "2 years", "weight": "4.2 kg", "sex": "female spayed"},
    memories=[mem("user", "Sophie's family recently switched from dry to wet food because Boba drinks more water now.")],
    user_turns=[
        "Is feeding Boba only wet food okay?",
        "Will her teeth get bad without dry food?",
        "How do I keep her teeth clean on wet food?",
        "Are dental treats enough?",
    ],
    persona="P-07",
))

CASES.append(p1(
    name="thomas_rocky_diet_protein",
    display="Thomas",
    scenario="Thomas asks how much protein his 3-year-old Border Collie, Rocky, needs given his high activity level.",
    outcome="Pawly explains that working/active dogs need 25–30% protein as a percentage of dry matter, recommends high-quality animal-based protein sources, and advises monitoring body condition score.",
    role="Advise on high-protein diets for active working-breed dogs.",
    criteria="Must provide protein percentage ranges; must recommend animal-based protein; must mention BCS monitoring.",
    pet={"name": "Rocky", "species": "dog", "breed": "Border Collie", "age": "3 years", "weight": "18 kg", "sex": "male intact"},
    memories=[mem("user", "Thomas competes in agility trials with Rocky 3 times per week.")],
    user_turns=[
        "How much protein does an active Border Collie really need?",
        "Is plant protein as good as animal protein for dogs?",
        "How do I check if Rocky is at a healthy weight?",
        "What's a BCS and how do I score him?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="linda_marshmallow_diet_kidney",
    display="Linda",
    scenario="Linda's 9-year-old Domestic Shorthair, Marshmallow, was diagnosed with early-stage CKD. Linda asks what dietary changes to make.",
    outcome="Pawly explains CKD diet principles (restricted phosphorus, moderate high-quality protein, increased moisture), recommends prescription renal food, and emphasizes close vet monitoring.",
    role="Guide CKD cat diet management with appropriate medical caution.",
    criteria="Must recommend low-phosphorus diet; must emphasize moisture and prescription food; must advise ongoing vet monitoring.",
    pet={"name": "Marshmallow", "species": "cat", "breed": "Domestic Shorthair", "age": "9 years", "weight": "4.0 kg", "sex": "female spayed"},
    memories=[mem("user", "Marshmallow was diagnosed with stage 2 CKD at the last vet visit; currently eating regular adult food.")],
    user_turns=[
        "Marshmallow has kidney disease — what should she eat now?",
        "Why does the phosphorus level matter so much?",
        "Do I have to use prescription food or can I make home-cooked?",
        "How often should I bring her in for monitoring?",
    ],
    persona="P-05",
))

CASES.append(p1(
    name="oscar_cookie_diet_allergies",
    display="Oscar",
    scenario="Oscar suspects his 4-year-old French Bulldog, Cookie, has a food allergy causing chronic ear infections.",
    outcome="Pawly explains food allergy elimination diet protocol (novel protein or hydrolyzed protein diet for 8–12 weeks), and recommends allergy testing consultation with vet.",
    role="Guide the food allergy investigation process for dogs with chronic ear infections.",
    criteria="Must explain elimination trial protocol and duration; must not name a specific allergen without testing; must recommend vet-directed allergy workup.",
    pet={"name": "Cookie", "species": "dog", "breed": "French Bulldog", "age": "4 years", "weight": "12 kg", "sex": "female spayed"},
    memories=[mem("user", "Cookie has had recurring ear infections for 8 months despite treatment; vet suspects environmental or food allergy.")],
    user_turns=[
        "Could Cookie's ear infections be from her food?",
        "How do I do an elimination diet?",
        "How long does it take to see results?",
        "Which proteins are best for the novel-protein trial?",
    ],
    persona="P-02",
))

# ─────────────────────────────────────────────
# G-02  Daily Care  (8 cases)
# ─────────────────────────────────────────────

CASES.append(p1(
    name="anna_oreo_care_bathing",
    display="Anna",
    scenario="Anna asks how often she should bathe her 3-year-old Poodle mix, Oreo, and what shampoo to use.",
    outcome="Pawly advises every 3–4 weeks for Poodle mixes, recommends pH-balanced dog shampoo, and explains over-bathing strips natural oils.",
    role="Advise on bathing frequency and product selection for Poodle mixes.",
    criteria="Must give specific bathing frequency; must recommend dog-specific shampoo; must warn against human shampoo.",
    pet={"name": "Oreo", "species": "dog", "breed": "Poodle mix", "age": "3 years", "weight": "8 kg", "sex": "male neutered"},
    memories=[mem("user", "Oreo goes to the dog park twice a week and Anna bathes him roughly once a month.")],
    user_turns=[
        "How often should I bathe Oreo?",
        "Is human shampoo okay in a pinch?",
        "What should I look for in a dog shampoo?",
        "Any tips for drying him without matting his fur?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="ben_simba_care_nailclip",
    display="Ben",
    scenario="Ben is nervous about clipping his 2-year-old Maine Coon, Simba's nails and asks for guidance.",
    outcome="Pawly explains the two-person hold technique, how to identify the quick, and recommends styptic powder in case of bleeding.",
    role="Teach safe cat nail trimming technique to an anxious owner.",
    criteria="Must explain the quick; must recommend styptic powder; must describe calm restraint technique.",
    pet={"name": "Simba", "species": "cat", "breed": "Maine Coon", "age": "2 years", "weight": "6.5 kg", "sex": "male neutered"},
    memories=[mem("user", "Ben has never trimmed Simba's nails; Simba scratched the sofa last week.")],
    user_turns=[
        "I'm scared to cut Simba's nails — how do I do it safely?",
        "What is the quick and how do I avoid it?",
        "What happens if I cut too far?",
        "Is it better to do all nails at once or a few at a time?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="grace_luna_care_dental",
    display="Grace",
    scenario="Grace wants to start brushing her 1-year-old Maltese, Luna's, teeth and asks for a beginner guide.",
    outcome="Pawly walks through the desensitization steps: finger rubbing, gauze, then toothbrush, using enzymatic pet toothpaste, and recommends brushing 3× per week minimum.",
    role="Guide new owners through pet dental care desensitization and brushing.",
    criteria="Must describe gradual desensitization; must specify enzymatic toothpaste; must never recommend human toothpaste (xylitol risk).",
    pet={"name": "Luna", "species": "dog", "breed": "Maltese", "age": "1 year", "weight": "3 kg", "sex": "female spayed"},
    memories=[mem("user", "Grace adopted Luna 3 months ago; Luna has never had her teeth brushed.")],
    user_turns=[
        "How do I start brushing Luna's teeth if she's never had it done?",
        "Can I use human toothpaste?",
        "What toothpaste do you recommend for dogs?",
        "How often should I brush?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="tom_archie_care_grooming",
    display="Tom",
    scenario="Tom asks how to manage his 5-year-old Siberian Husky, Archie's, shedding without professional grooming.",
    outcome="Pawly recommends the deshedding brush sequence (undercoat rake → slicker brush → blow-dry), bathing every 6–8 weeks to loosen undercoat, and avoiding shaving.",
    role="Advise on at-home grooming for double-coat breeds.",
    criteria="Must recommend undercoat rake and slicker brush combo; must warn against shaving double coats; must suggest bathing frequency.",
    pet={"name": "Archie", "species": "dog", "breed": "Siberian Husky", "age": "5 years", "weight": "25 kg", "sex": "male neutered"},
    memories=[mem("user", "Archie blows coat twice a year; Tom spends 30 minutes vacuuming daily during shedding season.")],
    user_turns=[
        "How do I manage Archie's shedding at home?",
        "What brushes work best for a Husky's double coat?",
        "Should I shave him in summer to keep him cool?",
        "How often should I bathe him during shedding season?",
    ],
    persona="P-02",
))

CASES.append(p1(
    name="clara_mochi_care_earclean",
    display="Clara",
    scenario="Clara asks how to clean her 3-year-old Basset Hound, Mochi's, droopy ears to prevent infections.",
    outcome="Pawly explains weekly ear cleaning with vet-approved ear cleanser, cotton balls (not swabs), how to spot early infection signs.",
    role="Guide floppy-ear dog owners on safe ear cleaning to prevent otitis.",
    criteria="Must specify vet-approved ear cleanser; must warn against cotton swabs; must list infection warning signs.",
    pet={"name": "Mochi", "species": "dog", "breed": "Basset Hound", "age": "3 years", "weight": "22 kg", "sex": "female spayed"},
    memories=[mem("user", "Clara adopted Mochi 6 months ago; Mochi had one ear infection treated 2 months ago.")],
    user_turns=[
        "How often should I clean Mochi's ears?",
        "What solution should I use?",
        "Should I use cotton swabs?",
        "How do I know if she has an infection starting?",
    ],
    persona="P-03",
))

CASES.append(p1(
    name="yusuf_ziggy_care_paws",
    display="Yusuf",
    scenario="Yusuf's 4-year-old Labrador, Ziggy, walks on hot pavement in Singapore. Yusuf asks how to protect Ziggy's paw pads.",
    outcome="Pawly advises the 5-second pavement test, walking during cooler hours, paw wax application, and checking pads for cracking post-walk.",
    role="Advise on paw pad protection for dogs in hot climates.",
    criteria="Must explain 5-second pavement test; must recommend walking at cooler times; must mention paw wax or protective booties.",
    pet={"name": "Ziggy", "species": "dog", "breed": "Labrador Retriever", "age": "4 years", "weight": "29 kg", "sex": "male neutered"},
    memories=[mem("user", "Yusuf lives in Singapore and walks Ziggy at noon on weekdays due to his work schedule.")],
    user_turns=[
        "Can hot pavement hurt Ziggy's paws?",
        "How do I test if the ground is too hot?",
        "Should I put boots on him?",
        "What else can I do to protect his paws in Singapore's heat?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="nina_cloud_care_litter",
    display="Nina",
    scenario="Nina asks how often to change her 2-year-old Maine Coon, Cloud's, litter and whether crystal litter is safe.",
    outcome="Pawly advises scooping daily, full litter change every 2–4 weeks depending on litter type, explains silica crystal vs. clumping clay differences.",
    role="Advise on litter hygiene and litter-type selection for cats.",
    criteria="Must recommend daily scooping; must distinguish litter types; must not assert one type is universally superior.",
    pet={"name": "Cloud", "species": "cat", "breed": "Maine Coon", "age": "2 years", "weight": "7 kg", "sex": "male neutered"},
    memories=[mem("user", "Nina just adopted Cloud and has never owned a cat before.")],
    user_turns=[
        "How often should I completely change Cloud's litter?",
        "Is crystal litter safer than clumping litter?",
        "How many litter boxes do I need for one cat?",
        "Where should I put the litter box?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="hassan_duke_care_exercise",
    display="Hassan",
    scenario="Hassan asks how much daily exercise his 7-year-old Cocker Spaniel, Duke, needs now that Duke seems less energetic.",
    outcome="Pawly advises 30–45 minutes of moderate daily exercise for a senior Cocker Spaniel, recommends low-impact activities, and suggests a vet check to rule out arthritis or hypothyroidism.",
    role="Advise on exercise adjustment for middle-aged/senior dogs with reduced energy.",
    criteria="Must recommend appropriate exercise duration; must suggest low-impact alternatives; must flag vet check for underlying causes of energy decrease.",
    pet={"name": "Duke", "species": "dog", "breed": "Cocker Spaniel", "age": "7 years", "weight": "13 kg", "sex": "male neutered"},
    memories=[mem("user", "Duke used to run for an hour daily but lately he stops after 20 minutes and pants heavily.")],
    user_turns=[
        "Duke seems less energetic lately — is he just getting old?",
        "How much exercise does a 7-year-old Cocker Spaniel need?",
        "What low-impact activities can we do together?",
        "When should I see a vet about this?",
    ],
    persona="P-05",
))

# ─────────────────────────────────────────────
# G-03  Behavior  (8 cases)
# ─────────────────────────────────────────────

CASES.append(p1(
    name="irene_pepper_behav_barking",
    display="Irene",
    scenario="Irene's 2-year-old Jack Russell, Pepper, barks excessively at strangers. Irene asks how to reduce reactive barking.",
    outcome="Pawly explains desensitization + counter-conditioning approach, teaches the 'watch me' command, and recommends keeping below the threshold distance.",
    role="Guide reactive barking reduction through positive reinforcement techniques.",
    criteria="Must explain desensitization/counter-conditioning; must introduce threshold concept; must not recommend punishment-based tools.",
    pet={"name": "Pepper", "species": "dog", "breed": "Jack Russell Terrier", "age": "2 years", "weight": "6 kg", "sex": "female spayed"},
    memories=[mem("user", "Irene has tried scolding Pepper for barking but it makes the behavior worse.")],
    user_turns=[
        "How do I stop Pepper from barking at every stranger we pass?",
        "What is desensitization — I keep reading about it?",
        "How do I do the 'watch me' command?",
        "How far away from strangers should we start?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="mike_rex_behav_leash",
    display="Mike",
    scenario="Mike's 3-year-old Doberman, Rex, pulls hard on the leash and Mike asks for help teaching loose-leash walking.",
    outcome="Pawly explains the stop-and-wait and direction-change methods, recommends a front-clip harness, and suggests 5-minute daily focused training sessions.",
    role="Teach loose-leash walking techniques appropriate for large-breed dogs.",
    criteria="Must recommend front-clip harness; must explain stop-and-wait method; must advise short focused sessions.",
    pet={"name": "Rex", "species": "dog", "breed": "Doberman Pinscher", "age": "3 years", "weight": "35 kg", "sex": "male neutered"},
    memories=[mem("user", "Mike injured his shoulder last month due to Rex's pulling; currently using a collar.")],
    user_turns=[
        "Rex pulls so hard he almost dislocated my shoulder — how do I fix this?",
        "What gear should I use?",
        "How does the stop-and-wait method work?",
        "How long until I'll see improvement?",
    ],
    persona="P-02",
))

CASES.append(p1(
    name="amy_coco_behav_separation",
    display="Amy",
    scenario="Amy's 1.5-year-old Cavalier King Charles Spaniel, Coco, destroys things when left alone and Amy asks for separation anxiety help.",
    outcome="Pawly explains graduated departure training, recommends a stuffed Kong toy, suggests a pet camera, and advises a vet check if severe.",
    role="Guide owners through separation anxiety management with graduated training.",
    criteria="Must explain graduated departure training; must recommend enrichment toys; must flag severe cases for vet/behaviourist referral.",
    pet={"name": "Coco", "species": "dog", "breed": "Cavalier King Charles Spaniel", "age": "1.5 years", "weight": "7 kg", "sex": "female spayed"},
    memories=[mem("user", "Coco has been left alone 8 hours daily since Amy returned to the office 3 months ago.")],
    user_turns=[
        "Coco tears up cushions whenever I leave — is that separation anxiety?",
        "What is graduated departure training?",
        "Would a Kong toy actually help?",
        "How do I know if she needs professional help?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="delia_whiskers_behav_litter",
    display="Delia",
    scenario="Delia's 4-year-old Domestic Shorthair, Whiskers, started urinating outside the litter box. She asks what to do.",
    outcome="Pawly explains possible causes (medical UTI, litter aversion, stress), advises vet check first to rule out UTI, then reviews litter type/location/cleanliness.",
    role="Triage inappropriate elimination in cats — medical vs. behavioural.",
    criteria="Must recommend vet check before behavioural fix; must list litter-aversion factors; must not attribute issue to behavioral cause without ruling out medical.",
    pet={"name": "Whiskers", "species": "cat", "breed": "Domestic Shorthair", "age": "4 years", "weight": "4.5 kg", "sex": "female spayed"},
    memories=[mem("user", "Delia moved apartments 3 weeks ago; Whiskers started missing the litter box last week.")],
    user_turns=[
        "Whiskers is peeing on the bathroom mat — why?",
        "Could it be a medical problem?",
        "Could the move have caused this?",
        "What changes to the litter box setup should I make?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="kevin_buddy_behav_jumping",
    display="Kevin",
    scenario="Kevin's 1-year-old Golden Retriever, Buddy, jumps on everyone who enters the house. Kevin asks how to train him to stop.",
    outcome="Pawly explains the four-on-floor rule, turn-and-ignore method, and consistent family buy-in for training success.",
    role="Teach jumping-up prevention training to owners of exuberant dogs.",
    criteria="Must explain four-on-floor rule; must emphasize consistency across all household members; must not recommend knee-bump or alpha rolling.",
    pet={"name": "Buddy", "species": "dog", "breed": "Golden Retriever", "age": "1 year", "weight": "28 kg", "sex": "male intact"},
    memories=[mem("user", "Kevin's elderly mother visits weekly and is afraid of being knocked down by Buddy.")],
    user_turns=[
        "Buddy jumps on everyone — how do I train him to stop?",
        "What is the turn-and-ignore method?",
        "My kids keep petting him when he jumps — will that ruin the training?",
        "How long until he stops jumping?",
    ],
    persona="P-02",
))

CASES.append(p1(
    name="rachel_ginger_behav_aggression",
    display="Rachel",
    scenario="Rachel's 5-year-old rescue Terrier mix, Ginger, growls at Rachel's husband. Rachel asks if this is dangerous.",
    outcome="Pawly explains growling as communication, advises not to punish growling, recommends a Certified Applied Animal Behaviourist (CAAB) consult, and interim safety management steps.",
    role="Help owners understand canine growling and safely manage resource/person guarding.",
    criteria="Must not advise punishing growling; must recommend professional behaviourist; must provide interim safety management.",
    pet={"name": "Ginger", "species": "dog", "breed": "Terrier mix", "age": "5 years", "weight": "8 kg", "sex": "female spayed"},
    memories=[mem("user", "Ginger was rescued 1 year ago; she growls at Rachel's husband when he approaches her food bowl.")],
    user_turns=[
        "Ginger growls at my husband near her food bowl — is she dangerous?",
        "Should I punish her for growling?",
        "Why does she only do it to my husband?",
        "What should we do for safety while we work on this?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="andy_mocha_behav_scratching",
    display="Andy",
    scenario="Andy's 2-year-old Siamese, Mocha, scratches the leather sofa. Andy asks how to redirect the behavior.",
    outcome="Pawly recommends sisal scratching posts near the sofa, deterrent sprays on furniture, nail caps (Soft Paws), and positive reinforcement when Mocha uses the post.",
    role="Guide cat scratching redirection using positive reinforcement.",
    criteria="Must recommend appropriate scratch surface (sisal); must advise against declawing; must include positive reinforcement steps.",
    pet={"name": "Mocha", "species": "cat", "breed": "Siamese", "age": "2 years", "weight": "4.5 kg", "sex": "male neutered"},
    memories=[mem("user", "Andy bought a carpeted cat tree but Mocha ignores it and still scratches the sofa.")],
    user_turns=[
        "Mocha destroys my leather sofa — how do I stop it?",
        "Should I declaw him?",
        "How do I get him to use the scratching post?",
        "Would nail caps help?",
    ],
    persona="P-03",
))

CASES.append(p1(
    name="tanya_snow_behav_hiss",
    display="Tanya",
    scenario="Tanya's 3-year-old cat, Snow, started hissing at the family's new puppy. Tanya asks how to help them coexist.",
    outcome="Pawly explains scent swapping introduction, feeding on opposite sides of a door, and slow visual introduction with a baby gate over 2–4 weeks.",
    role="Guide multi-species household introduction using gradual desensitization.",
    criteria="Must recommend scent introduction before visual; must not force contact; must give realistic timeline.",
    pet={"name": "Snow", "species": "cat", "breed": "Domestic Shorthair", "age": "3 years", "weight": "4 kg", "sex": "female spayed"},
    memories=[mem("user", "A 10-week-old Beagle puppy arrived 3 days ago; Snow now hides and hisses.")],
    user_turns=[
        "Snow hisses at the new puppy — is this normal?",
        "How do I introduce them properly?",
        "How long will it take before they get along?",
        "What if Snow never accepts the puppy?",
    ],
    persona="P-04",
))

# ─────────────────────────────────────────────
# G-04  Routine Health  (10 cases)
# ─────────────────────────────────────────────

CASES.append(p1(
    name="liam_peanut_health_vaccine",
    display="Liam",
    scenario="Liam asks about the core vaccine schedule for his newly adopted 8-week-old Labrador puppy, Peanut.",
    outcome="Pawly outlines core vaccines (distemper, parvovirus, hepatitis, rabies), timing schedule (6–8 wks, 10–12 wks, 14–16 wks, 12–16 months), and recommends vet confirmation.",
    role="Educate new puppy owners on core vaccination schedules.",
    criteria="Must list core vaccines by name; must give timing intervals; must recommend vet for local regulatory requirements.",
    pet={"name": "Peanut", "species": "dog", "breed": "Labrador Retriever", "age": "8 weeks", "weight": "4.5 kg", "sex": "male intact"},
    memories=[mem("user", "Liam just adopted Peanut and has never owned a dog before.")],
    user_turns=[
        "What vaccines does an 8-week-old Labrador puppy need?",
        "When do I give each vaccine?",
        "Is the rabies vaccine required in Singapore?",
        "What happens if I miss a vaccine appointment?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="diana_felix_health_flea",
    display="Diana",
    scenario="Diana asks how to handle a flea infestation on her 3-year-old Domestic Shorthair, Felix, and in her apartment.",
    outcome="Pawly explains treating the pet with vet-approved flea treatment, washing bedding at 60°C, vacuuming, and environmental flea spray for carpets; notes flea lifecycle stages.",
    role="Guide comprehensive flea eradication in pet and home environment.",
    criteria="Must address both pet treatment and environmental treatment; must mention flea lifecycle (eggs in environment); must recommend vet-approved products.",
    pet={"name": "Felix", "species": "cat", "breed": "Domestic Shorthair", "age": "3 years", "weight": "4.8 kg", "sex": "male neutered"},
    memories=[mem("user", "Diana noticed Felix scratching and found live fleas; she has a carpeted apartment.")],
    user_turns=[
        "Felix has fleas — what should I do first?",
        "Why do I need to treat the whole apartment?",
        "What temperature do I need to wash his bedding at?",
        "How long until the fleas are completely gone?",
    ],
    persona="P-03",
))

CASES.append(p1(
    name="sam_bella_health_deworming",
    display="Sam",
    scenario="Sam asks how often to deworm his 5-year-old Pomeranian, Bella, who goes to dog parks.",
    outcome="Pawly recommends deworming every 3 months for dogs with outdoor exposure, explains common worm types (roundworm, hookworm, whipworm, tapeworm), and recommends vet-prescribed dewormer.",
    role="Advise on routine deworming frequency and product selection for adult dogs.",
    criteria="Must give deworming frequency; must name common worm types; must recommend vet-prescribed products over OTC.",
    pet={"name": "Bella", "species": "dog", "breed": "Pomeranian", "age": "5 years", "weight": "3 kg", "sex": "female spayed"},
    memories=[mem("user", "Bella goes to the dog park 3 times per week; Sam last dewormed her 8 months ago.")],
    user_turns=[
        "How often should I deworm Bella?",
        "What worms do dogs at the park usually get?",
        "Can I use over-the-counter dewormer from the pet shop?",
        "Are there signs I can look out for at home?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="natalie_cleo_health_spay",
    display="Natalie",
    scenario="Natalie asks when and whether to spay her 5-month-old female Border Collie, Cleo.",
    outcome="Pawly explains the timing debate (early vs. delayed spay, joint health studies in large breeds), and recommends consulting a vet for a personalized decision.",
    role="Discuss pros and cons of spay timing for large-breed dogs without dictating one correct answer.",
    criteria="Must mention joint health considerations; must not give a one-size-fits-all recommendation; must recommend vet consultation.",
    pet={"name": "Cleo", "species": "dog", "breed": "Border Collie", "age": "5 months", "weight": "12 kg", "sex": "female intact"},
    memories=[mem("user", "Natalie's previous dog was spayed at 6 months without issue, but she heard newer research recommends waiting.")],
    user_turns=[
        "Should I spay Cleo now at 5 months or wait?",
        "I heard early spay can hurt joint development — is that true?",
        "What are the risks of waiting?",
        "When is the ideal age to spay a Border Collie?",
    ],
    persona="P-02",
))

CASES.append(p1(
    name="paul_milo_health_tick",
    display="Paul",
    scenario="Paul asks how to safely remove a tick from his 4-year-old Golden Retriever, Milo, and prevent future bites.",
    outcome="Pawly explains fine-tipped tweezers technique (grasp at skin surface, pull straight), warns against twisting/burning, advises monitoring for 30 days, and recommends monthly tick prevention.",
    role="Guide safe tick removal and prevention for dogs in tick-endemic areas.",
    criteria="Must explain correct tweezers technique; must warn against twisting or burning; must recommend monitoring for tick-borne disease signs.",
    pet={"name": "Milo", "species": "dog", "breed": "Golden Retriever", "age": "4 years", "weight": "31 kg", "sex": "male neutered"},
    memories=[mem("user", "Paul found a tick on Milo after a hike in a forested area; Milo is not on tick prevention.")],
    user_turns=[
        "I found a tick on Milo — how do I remove it?",
        "Should I twist or pull straight?",
        "What do I watch for after removing it?",
        "How do I prevent ticks in the future?",
    ],
    persona="P-02",
))

CASES.append(p1(
    name="zoe_daisy_health_dental",
    display="Zoe",
    scenario="Zoe notices her 6-year-old Cocker Spaniel, Daisy, has bad breath and asks if she needs a dental cleaning.",
    outcome="Pawly explains that persistent bad breath (halitosis) in dogs often indicates periodontal disease, recommends a vet dental exam, and explains professional dental cleaning under anaesthesia.",
    role="Advise on dental disease recognition and professional dental care for dogs.",
    criteria="Must link halitosis to periodontal disease; must recommend professional dental exam; must not dismiss it as normal.",
    pet={"name": "Daisy", "species": "dog", "breed": "Cocker Spaniel", "age": "6 years", "weight": "11 kg", "sex": "female spayed"},
    memories=[mem("user", "Daisy has never had a professional dental cleaning; Zoe brushes her teeth once a week.")],
    user_turns=[
        "Daisy has really bad breath — is that normal for dogs?",
        "What causes bad breath in dogs?",
        "Does she need a professional dental cleaning?",
        "What's involved in a dental cleaning under anaesthesia?",
    ],
    persona="P-05",
))

CASES.append(p1(
    name="fred_titan_health_microchip",
    display="Fred",
    scenario="Fred asks about microchipping his 3-month-old Great Dane puppy, Titan, and whether it's painful.",
    outcome="Pawly explains microchipping (ISO 15-digit chip, between shoulder blades, quick procedure), notes it's mandatory in Singapore for dogs, and reassures about minimal pain.",
    role="Educate owners on microchipping procedure and local regulations.",
    criteria="Must mention ISO 15-digit standard; must note Singapore mandatory requirement for dogs; must reassure about minimal pain.",
    pet={"name": "Titan", "species": "dog", "breed": "Great Dane", "age": "3 months", "weight": "18 kg", "sex": "male intact"},
    memories=[mem("user", "Fred is getting Titan his first vet visit next week and wants to know what to expect.")],
    user_turns=[
        "Does microchipping hurt Titan?",
        "Where is the chip implanted?",
        "Is microchipping mandatory in Singapore?",
        "Can I track Titan's location with the microchip?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="helen_princess_health_obesity",
    display="Helen",
    scenario="Helen's 7-year-old Domestic Shorthair, Princess, has been told by the vet she is overweight. Helen asks how to help her lose weight safely.",
    outcome="Pawly advises measured meal portions using a food scale, transitioning to a high-protein lower-calorie food, 15-minute play sessions twice daily, and monthly weight checks.",
    role="Guide safe weight-loss strategies for overweight adult cats.",
    criteria="Must recommend measured portions; must suggest active play; must not recommend rapid weight loss (hepatic lipidosis risk).",
    pet={"name": "Princess", "species": "cat", "breed": "Domestic Shorthair", "age": "7 years", "weight": "6.2 kg", "sex": "female spayed"},
    memories=[mem("user", "Princess weighs 6.2 kg; ideal weight is 4.5 kg according to the vet; she is an indoor cat.")],
    user_turns=[
        "The vet says Princess is obese — how do I help her lose weight safely?",
        "How much should I cut her food by?",
        "She's not very playful — how do I get her to exercise more?",
        "How quickly should she lose the weight?",
    ],
    persona="P-05",
))

CASES.append(p1(
    name="victor_echo_health_neuter",
    display="Victor",
    scenario="Victor asks about neutering his 6-month-old male Bengal cat, Echo, and what the recovery looks like.",
    outcome="Pawly explains the castration procedure (brief GA, small incision), 7-10 day recovery with activity restriction, e-collar use, and benefits (reduced roaming, spraying, aggression).",
    role="Inform cat owners about neutering procedure and post-op care.",
    criteria="Must explain activity restriction post-op; must mention e-collar; must list benefits of neutering without being prescriptive.",
    pet={"name": "Echo", "species": "cat", "breed": "Bengal", "age": "6 months", "weight": "3.5 kg", "sex": "male intact"},
    memories=[mem("user", "Victor noticed Echo has started spraying in the apartment; vet recommended neutering.")],
    user_turns=[
        "What happens during Echo's neutering surgery?",
        "How long is the recovery?",
        "What activity restrictions does he need?",
        "Will neutering definitely stop the spraying?",
    ],
    persona="P-02",
))

CASES.append(p1(
    name="claire_benny_health_heartworm",
    display="Claire",
    scenario="Claire asks whether her 2-year-old Maltese, Benny, needs heartworm prevention in Singapore.",
    outcome="Pawly confirms heartworm is present in Singapore due to mosquito vectors, recommends monthly preventive (e.g. Heartgard) year-round, and advises annual blood test.",
    role="Advise on heartworm prevention in tropical/endemic regions.",
    criteria="Must confirm heartworm risk in Singapore; must recommend monthly preventive; must advise annual testing.",
    pet={"name": "Benny", "species": "dog", "breed": "Maltese", "age": "2 years", "weight": "3.2 kg", "sex": "male neutered"},
    memories=[mem("user", "Claire recently moved to Singapore from a non-endemic country and is unsure if heartworm prevention is needed.")],
    user_turns=[
        "Does Benny need heartworm prevention in Singapore?",
        "How does heartworm spread?",
        "What prevention options are available?",
        "How often should he be tested?",
    ],
    persona="P-01",
))

# ─────────────────────────────────────────────
# G-05  Life Stages  (8 cases)
# ─────────────────────────────────────────────

CASES.append(p1(
    name="matt_spark_stage_puppy",
    display="Matt",
    scenario="Matt asks what the socialization window is for his 7-week-old Husky puppy, Spark, and what experiences to expose him to.",
    outcome="Pawly explains the critical socialization window (3–14 weeks), recommends exposure to sounds, surfaces, people, and gentle handling, and warns against harmful over-exposure.",
    role="Guide new owners through the puppy socialization window.",
    criteria="Must state the 3–14 week window; must give specific exposure categories; must warn against forcing fearful exposures.",
    pet={"name": "Spark", "species": "dog", "breed": "Siberian Husky", "age": "7 weeks", "weight": "3 kg", "sex": "male intact"},
    memories=[mem("user", "Matt just brought Spark home; he works from home and has time to focus on socialization.")],
    user_turns=[
        "When is the best time to socialize a puppy like Spark?",
        "What kinds of things should I expose him to?",
        "Can I take him outside before he's fully vaccinated?",
        "What if he seems scared of something?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="ellen_mittens_stage_senior_cat",
    display="Ellen",
    scenario="Ellen's 12-year-old tabby, Mittens, was declared a 'senior' at the last vet visit. Ellen asks what changes to expect.",
    outcome="Pawly describes senior cat changes (mobility, kidney function, dental, cognitive), recommends biannual vet checks, senior-specific food, and joint supplements if needed.",
    role="Prepare cat owners for the health changes that come with feline aging.",
    criteria="Must list multiple senior-stage changes; must recommend biannual vet checks; must suggest senior-appropriate diet.",
    pet={"name": "Mittens", "species": "cat", "breed": "Tabby", "age": "12 years", "weight": "4.2 kg", "sex": "female spayed"},
    memories=[mem("user", "Ellen has had Mittens since she was a kitten; Mittens is indoor-only and eats adult kibble.")],
    user_turns=[
        "The vet called Mittens a senior — what should I be watching for?",
        "How often should she see the vet now?",
        "Should I switch her to senior cat food?",
        "Are there supplements I should add?",
    ],
    persona="P-05",
))

CASES.append(p1(
    name="jason_bean_stage_adolescent",
    display="Jason",
    scenario="Jason says his 8-month-old Border Collie, Bean, has become stubborn and seems to have forgotten his training. Jason asks what's happening.",
    outcome="Pawly explains canine adolescence (6–18 months), hormonal changes affecting behavior, and recommends consistent positive training and patience.",
    role="Help owners understand and manage canine adolescence.",
    criteria="Must explain adolescence developmental stage; must recommend consistent positive reinforcement; must reassure owner that regression is temporary.",
    pet={"name": "Bean", "species": "dog", "breed": "Border Collie", "age": "8 months", "weight": "15 kg", "sex": "male intact"},
    memories=[mem("user", "Bean graduated puppy class at 4 months; now he ignores recall commands and chews furniture.")],
    user_turns=[
        "Bean was trained but now he acts like he forgot everything — what happened?",
        "Is this just a phase?",
        "How do I handle his stubbornness during training?",
        "Should I enroll him in more classes?",
    ],
    persona="P-02",
))

CASES.append(p1(
    name="petra_cherry_stage_pregnant",
    display="Petra",
    scenario="Petra's 3-year-old Domestic Shorthair, Cherry, may be pregnant. Petra asks how to confirm and what to prepare.",
    outcome="Pawly explains vet ultrasound at day 25 for confirmation, gestation period (~63 days), nutrition increase in final 3 weeks, nesting box preparation, and signs of impending labour.",
    role="Guide owners through feline pregnancy confirmation and preparation.",
    criteria="Must recommend vet confirmation via ultrasound; must mention gestational timeline; must describe nesting preparation.",
    pet={"name": "Cherry", "species": "cat", "breed": "Domestic Shorthair", "age": "3 years", "weight": "3.8 kg", "sex": "female intact"},
    memories=[mem("user", "Cherry is indoor-outdoor and may have encountered a male cat; Petra noticed nipple enlargement.")],
    user_turns=[
        "I think Cherry might be pregnant — how do I confirm?",
        "How long is cat pregnancy?",
        "What do I need to prepare for the birth?",
        "What signs tell me she's about to give birth?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="robin_basil_stage_kitten",
    display="Robin",
    scenario="Robin asks what to feed his 10-week-old kitten, Basil, and how much.",
    outcome="Pawly recommends high-protein kitten-specific wet or dry food, 4 small meals per day at this age, and transitioning to 3 meals by 12 weeks.",
    role="Guide kitten feeding schedule and food selection in early development.",
    criteria="Must recommend kitten-specific food; must give feeding frequency for the age; must not recommend adult food for a kitten.",
    pet={"name": "Basil", "species": "cat", "breed": "Domestic Shorthair", "age": "10 weeks", "weight": "0.85 kg", "sex": "male intact"},
    memories=[mem("user", "Robin adopted Basil from a shelter; shelter was feeding him kitten wet food.")],
    user_turns=[
        "What should I feed Basil at 10 weeks old?",
        "How many times per day does he need to eat?",
        "Can I give him adult cat food since I already have some?",
        "When do I switch to fewer meals?",
    ],
    persona="P-07",
))

CASES.append(p1(
    name="sue_daffy_stage_geriatric",
    display="Sue",
    scenario="Sue's 15-year-old Poodle, Daffy, has become incontinent at night. Sue asks what options are available.",
    outcome="Pawly explains common causes (sphincter incompetence, cognitive dysfunction, kidney disease), recommends vet workup, discusses doggy diapers as short-term aid, and notes medication options.",
    role="Advise on geriatric incontinence with empathy and actionable options.",
    criteria="Must recommend vet workup; must list multiple possible causes; must mention doggy diapers as management aid.",
    pet={"name": "Daffy", "species": "dog", "breed": "Poodle", "age": "15 years", "weight": "6 kg", "sex": "female spayed"},
    memories=[mem("user", "Daffy has been incontinent at night for the past 2 weeks; she seems otherwise bright and alert.")],
    user_turns=[
        "Daffy is wetting the bed at night — is this just old age?",
        "What could be causing it?",
        "What can I do right now while waiting for the vet?",
        "Are there medications that can help?",
    ],
    persona="P-05",
))

CASES.append(p1(
    name="carl_tigger_stage_puppy_teeth",
    display="Carl",
    scenario="Carl's 4-month-old Beagle, Tigger, is teething and biting everything. Carl asks how to manage teething.",
    outcome="Pawly explains the teething timeline (3–6 months), recommends chew toys (rubber or nylon), frozen treats, and redirecting biting to appropriate items.",
    role="Guide owners through puppy teething with appropriate chew options.",
    criteria="Must give teething timeline; must recommend appropriate chew options; must advise redirection over punishment.",
    pet={"name": "Tigger", "species": "dog", "breed": "Beagle", "age": "4 months", "weight": "7 kg", "sex": "male intact"},
    memories=[mem("user", "Carl's furniture and shoes have bite marks; Tigger seems more restless at night.")],
    user_turns=[
        "Tigger is biting everything — is this because he's teething?",
        "When will the teething stop?",
        "What can I give him to chew safely?",
        "Should I freeze the chew toys?",
    ],
    persona="P-03",
))

CASES.append(p1(
    name="jess_nova_stage_spay_recovery",
    display="Jess",
    scenario="Jess's 6-month-old Domestic Shorthair, Nova, just got spayed today. Jess asks what post-op care is needed.",
    outcome="Pawly outlines 24-hour post-GA monitoring, e-collar use for 10 days, activity restriction, incision site check daily, and signs of complications (excessive swelling, discharge).",
    role="Guide owners through immediate post-spay recovery care for cats.",
    criteria="Must mention e-collar; must state activity restriction duration; must list complication warning signs.",
    pet={"name": "Nova", "species": "cat", "breed": "Domestic Shorthair", "age": "6 months", "weight": "2.8 kg", "sex": "female spayed"},
    memories=[mem("user", "Nova just came home from the clinic 2 hours ago; she is groggy from anaesthesia.")],
    user_turns=[
        "Nova just got spayed — what do I do for her tonight?",
        "She keeps trying to lick the wound — what do I do?",
        "When can she eat normally again?",
        "What warning signs should I bring her back to the vet for?",
    ],
    persona="P-07",
))

# ─────────────────────────────────────────────
# G-06  User Already Googled  (5 cases)
# ─────────────────────────────────────────────

CASES.append(p1(
    name="alice_coco_google_vinegar",
    display="Alice",
    scenario="Alice googled 'home remedies for dog ear infection' and found a recommendation to use diluted white vinegar. She asks Pawly if it's safe.",
    outcome="Pawly explains that vinegar may worsen infections caused by yeast vs. bacteria, warns it can cause pain if ear drum is ruptured, and recommends vet diagnosis first.",
    role="Critically evaluate home-remedy information retrieved from the internet.",
    criteria="Must explain why vinegar can be harmful; must recommend vet diagnosis before home treatment; must not dismiss internet searches dismissively.",
    pet={"name": "Coco", "species": "dog", "breed": "Poodle", "age": "4 years", "weight": "7 kg", "sex": "female spayed"},
    memories=[mem("user", "Alice found the vinegar advice on a popular pet blog; Coco has been shaking her head for 2 days.")],
    user_turns=[
        "I read online to use diluted vinegar for dog ear infections — is that safe?",
        "Why would vinegar make things worse?",
        "What if I just try it to see if it helps?",
        "Should I go straight to the vet?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="marcus_fudge_google_coconut",
    display="Marcus",
    scenario="Marcus read that coconut oil is a 'superfood' for dogs and wants to add it to his 3-year-old Dachshund, Fudge's, meals daily.",
    outcome="Pawly explains coconut oil is high-fat (pancreatitis risk for predisposed breeds), has limited evidence for its claimed benefits, and recommends small quantities if at all.",
    role="Evaluate popular pet-health social media claims with evidence-based context.",
    criteria="Must explain pancreatitis risk; must note lack of strong evidence; must not endorse large amounts of coconut oil.",
    pet={"name": "Fudge", "species": "dog", "breed": "Dachshund", "age": "3 years", "weight": "9 kg", "sex": "male neutered"},
    memories=[mem("user", "Marcus follows a wellness Instagram account that promotes coconut oil for dogs daily.")],
    user_turns=[
        "I heard coconut oil is great for dogs — how much should I add to Fudge's food?",
        "It's natural fat, so it should be fine, right?",
        "What's the risk if he eats too much fat?",
        "Is there any real evidence it helps skin or coat?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="ivy_nugget_google_tea_tree",
    display="Ivy",
    scenario="Ivy found an article recommending tea tree oil spray for cat skin conditions and wants to apply it to her 2-year-old cat, Nugget.",
    outcome="Pawly urgently warns that tea tree oil is toxic to cats even in diluted form, can cause ataxia, tremors, and liver failure, and must never be used on cats.",
    role="Urgently advise against toxic home remedies for cats.",
    criteria="Must clearly state tea tree oil is toxic to cats; must list toxicity symptoms; must advise immediate contact with vet if already applied.",
    pet={"name": "Nugget", "species": "cat", "breed": "Domestic Shorthair", "age": "2 years", "weight": "4.1 kg", "sex": "male neutered"},
    memories=[mem("user", "Ivy found the article on a natural-remedies website; Nugget has a small scabby patch on his neck.")],
    user_turns=[
        "Can I use diluted tea tree oil on Nugget's skin patch?",
        "The article says it's fine when diluted — are you sure it's dangerous?",
        "What if I only use a tiny drop?",
        "What symptoms should I watch for if I've already used some?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="owen_shadow_google_probiotic",
    display="Owen",
    scenario="Owen googled dog probiotics after Shadow had loose stools and asks Pawly which human probiotic brand to use.",
    outcome="Pawly explains human probiotics have different strains not optimized for dogs, recommends dog-specific probiotics, and suggests plain pumpkin puree as a short-term dietary fibre aid.",
    role="Advise on evidence-based probiotic options for dogs.",
    criteria="Must distinguish dog vs. human probiotic strains; must recommend species-appropriate products; must suggest vet consultation for persistent diarrhoea.",
    pet={"name": "Shadow", "species": "dog", "breed": "Doberman Pinscher", "age": "4 years", "weight": "34 kg", "sex": "male neutered"},
    memories=[mem("user", "Shadow has had soft stools for 3 days after a change in kibble brand.")],
    user_turns=[
        "Can I give Shadow my Yakult or human probiotic for his loose stools?",
        "Why are dog probiotics different?",
        "What dog probiotics would you recommend?",
        "Is there something natural I can try first?",
    ],
    persona="P-03",
))

CASES.append(p1(
    name="fiona_pumpkin_google_insulin",
    display="Fiona",
    scenario="Fiona's 9-year-old Labrador, Pumpkin, was recently diagnosed with diabetes. Fiona read about natural alternatives to insulin injections online.",
    outcome="Pawly clearly explains that insulin injections are the medical standard for canine diabetes and that dietary supplements cannot replace insulin; reinforces the vet's protocol.",
    role="Reinforce evidence-based diabetes management and correct dangerous misinformation.",
    criteria="Must not endorse natural alternatives to insulin; must explain why insulin is essential; must recommend following the vet's treatment plan.",
    pet={"name": "Pumpkin", "species": "dog", "breed": "Labrador Retriever", "age": "9 years", "weight": "30 kg", "sex": "female spayed"},
    memories=[mem("user", "Pumpkin was diagnosed with diabetes last week; Fiona is worried about giving daily injections.")],
    user_turns=[
        "I read that cinnamon can control dog diabetes naturally — is that true?",
        "The injections scare me — can I try diet changes first?",
        "My vet said she'll go into a coma without insulin — is that really possible?",
        "What helps me get comfortable giving the injections?",
    ],
    persona="P-05",
))

# ─────────────────────────────────────────────
# G-07  Singapore Localization  (5 cases)
# ─────────────────────────────────────────────

CASES.append(p1(
    name="wei_kopi_sg_hdb",
    display="Wei",
    scenario="Wei lives in an HDB flat in Singapore and asks whether he can keep a dog and which breeds are allowed.",
    outcome="Pawly explains the HDB Pet Dog Scheme (one approved small breed, licensing, microchip, sterilisation requirements), lists approved breeds, and directs Wei to check the HDB and AVS websites.",
    role="Advise Singapore HDB residents on pet ownership regulations accurately.",
    criteria="Must mention HDB Pet Dog Scheme by name; must note sterilisation and microchipping requirements; must not give outdated breed list — direct to official source.",
    pet={"name": "Kopi", "species": "dog", "breed": "Unknown (prospective)", "age": "N/A", "weight": "N/A", "sex": "N/A"},
    memories=[mem("user", "Wei is considering adopting a dog for the first time and lives in an HDB flat.")],
    user_turns=[
        "Can I keep a dog in my HDB flat in Singapore?",
        "Which dog breeds are allowed in HDB flats?",
        "Do I need to register or license my dog?",
        "Is sterilisation compulsory for HDB dogs?",
    ],
    persona="P-01",
))

CASES.append(p1(
    name="hui_mimi_sg_vet_cost",
    display="Hui",
    scenario="Hui asks Pawly which government-linked or subsidised vet clinics are available in Singapore for budget-conscious pet owners.",
    outcome="Pawly mentions SPCA clinic, Action for Singapore Dogs (ASD), and government vet clinics under AVS for certain cases; recommends calling ahead and checking for community cat/dog programs.",
    role="Help Singapore residents find affordable veterinary care options.",
    criteria="Must mention SPCA clinic as a low-cost option; must recommend confirming details directly with the clinic; must not provide fabricated prices.",
    pet={"name": "Mimi", "species": "cat", "breed": "Domestic Shorthair", "age": "4 years", "weight": "3.9 kg", "sex": "female spayed"},
    memories=[mem("user", "Hui is a student on a tight budget; Mimi is a stray she adopted informally.")],
    user_turns=[
        "Are there cheaper vet options in Singapore for cats?",
        "What about the SPCA — do they treat pets that aren't adopted from them?",
        "Are there government subsidies for vet fees in Singapore?",
        "Is there a payment plan option at normal vets?",
    ],
    persona="P-03",
))

CASES.append(p1(
    name="jun_astro_sg_avs_import",
    display="Jun",
    scenario="Jun is relocating from Australia to Singapore and asks about the import requirements for his 5-year-old Border Collie, Astro.",
    outcome="Pawly outlines the AVS import permit process, Group 1 country requirements (microchip, vaccination records, health certificate, titer test if applicable), and quarantine details.",
    role="Guide owners through Singapore pet import procedures accurately.",
    criteria="Must mention AVS import permit requirement; must mention microchip and vaccination records; must recommend contacting AVS for the latest requirements.",
    pet={"name": "Astro", "species": "dog", "breed": "Border Collie", "age": "5 years", "weight": "20 kg", "sex": "male neutered"},
    memories=[mem("user", "Jun is relocating in 3 months; Astro has current rabies vaccination and microchip.")],
    user_turns=[
        "What do I need to bring Astro from Australia to Singapore?",
        "Does Australia count as Group 1?",
        "Does Astro need to do quarantine?",
        "How long does the AVS import permit process take?",
    ],
    persona="P-06",
))

CASES.append(p1(
    name="siti_brownie_sg_heat",
    display="Siti",
    scenario="Siti asks how to protect her 3-year-old Corgi, Brownie, from Singapore's heat and humidity during outdoor walks.",
    outcome="Pawly advises walking before 8am or after 7pm, checking pavement temperature, carrying water, watching for heatstroke signs, and avoiding overweight dogs in peak heat.",
    role="Provide tropical climate-specific exercise safety advice for dogs.",
    criteria="Must recommend early morning or evening walks; must list heatstroke warning signs; must advise carrying water.",
    pet={"name": "Brownie", "species": "dog", "breed": "Pembroke Welsh Corgi", "age": "3 years", "weight": "13 kg", "sex": "female spayed"},
    memories=[mem("user", "Siti walks Brownie at lunchtime due to her schedule; Singapore temperature is typically 30–34°C midday.")],
    user_turns=[
        "How do I keep Brownie safe in Singapore's heat when I walk her?",
        "What are the warning signs of heatstroke in dogs?",
        "I can only walk her at lunch — what can I do?",
        "Should I shave her coat to help her stay cool?",
    ],
    persona="P-04",
))

CASES.append(p1(
    name="dav_pepper_sg_catkilling",
    display="Dave",
    scenario="Dave asks Pawly about Singapore laws regarding cruelty to animals after witnessing a neighbour kick a stray cat.",
    outcome="Pawly explains the Animals and Birds Act and the Animal & Veterinary Service (AVS) reporting channel, directs Dave to call the AVS Animal Cruelty Hotline, and briefly explains penalties.",
    role="Inform Singapore residents about animal cruelty laws and reporting channels.",
    criteria="Must name the Animals and Birds Act; must provide the AVS cruelty hotline as the correct reporting channel; must not fabricate penalties or legal outcomes.",
    pet={"name": "N/A", "species": "N/A", "breed": "N/A", "age": "N/A", "weight": "N/A", "sex": "N/A"},
    memories=[mem("user", "Dave witnessed his neighbour kicking a stray cat and wants to report it.")],
    user_turns=[
        "I saw my neighbour kick a stray cat — is that illegal in Singapore?",
        "Which law covers animal cruelty?",
        "Who do I call to report it?",
        "What could happen to my neighbour if they're found guilty?",
    ],
    persona="P-06",
))

# ─────────────────────────────────────────────
# Validate and write
# ─────────────────────────────────────────────

expected = 10 + 8 + 8 + 10 + 8 + 5 + 5  # = 54
assert len(CASES) == expected, f"Expected {expected} cases, got {len(CASES)}"

print(f"Total cases: {len(CASES)}")
OUT.write_text(json.dumps(CASES, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Written to {OUT}")
