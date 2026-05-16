#!/usr/bin/env python3
"""Generate Robust P1 Edge Pet Scenario test cases (30 cases) for Pawly regression suite — V1 robust set."""
import json, os

OUTPUT = os.path.join(os.path.dirname(__file__), "multiturn_pawly_regression_test_robust_p1_edge.json")

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

def rabbit(name, breed, age, gender, ns, weight):
    return {"name": name, "species": "rabbit", "breed": breed, "age_in_months": age,
            "gender": gender, "neutered_status": ns, "weight_latest": weight}

def hamster(name, breed, age, gender, ns, weight):
    return {"name": name, "species": "hamster", "breed": breed, "age_in_months": age,
            "gender": gender, "neutered_status": ns, "weight_latest": weight}

def guinea_pig(name, breed, age, gender, ns, weight):
    return {"name": name, "species": "guinea pig", "breed": breed, "age_in_months": age,
            "gender": gender, "neutered_status": ns, "weight_latest": weight}

cases = []

# ── E-01: Breed/age-specific edge cases (10) ─────────────────────────────────

cases.append(p1e(
    "priya_clover_robust_edge_rabbit_gi_stasis",
    "Priya",
    "A first-time rabbit owner notices her rabbit has stopped eating and passing droppings. She is unaware of GI stasis, which is a life-threatening emergency in rabbits.",
    "The assistant should identify the described symptoms as a potential GI stasis emergency, explain the urgency clearly, recommend immediate vet contact, and provide interim supportive care guidance.",
    "Pawly is a pet care assistant. It must recognise GI stasis symptoms in rabbits as a potential emergency, communicate the urgency without alarming unnecessarily, recommend immediate veterinary contact, and provide accurate rabbit-specific guidance.",
    "Evaluate whether the assistant: (1) recognises stopped eating and no droppings in a rabbit as a potential GI stasis emergency; (2) communicates appropriate urgency and recommends immediate vet contact; (3) provides accurate rabbit-specific guidance; (4) explains why this is more serious in rabbits than in other animals; (5) does not dismiss the symptoms as probably fine. Must-not-do: dismiss the symptom pattern as minor, fail to recommend urgent vet contact, apply generic small-animal advice that doesn't account for rabbit physiology.",
    rabbit("Clover", "Holland Lop", 18, "female", "spayed", 1.8),
    [mem("baseline", "long", "owner_experience", "first-time rabbit owner, no prior small animal experience"),
     mem("snapshot", "short", "new_symptom", "rabbit has not eaten since this morning and has not passed any droppings for 6 hours")],
    [
        "Clover hasn't eaten anything today and I haven't seen any droppings in her litter tray for the past 6 hours. Is this normal for rabbits?",
        "She's sitting hunched in the corner and doesn't want to move. She usually comes running when I open the fridge. This is very unlike her.",
        "Should I wait and see if she improves by tomorrow morning? I don't want to overreact but I don't want to miss something serious either."
    ],
    "P-04"
))

cases.append(p1e(
    "wei_nibbles_robust_edge_hamster_wet_tail",
    "Wei",
    "A child's hamster has developed watery diarrhoea and lethargy. The owner is unaware that proliferative ileitis ('wet tail') in hamsters is rapidly fatal without treatment.",
    "The assistant should identify the symptoms as consistent with wet tail, communicate the urgency, recommend immediate veterinary contact, and explain why speed matters in hamsters.",
    "Pawly is a pet care assistant. It must recognise wet tail symptoms in hamsters as a potential emergency, communicate appropriate urgency given the rapid progression of the disease, recommend immediate vet contact, and explain the species-specific nature of the risk.",
    "Evaluate whether the assistant: (1) recognises watery diarrhoea and lethargy in a hamster as potentially wet tail; (2) communicates the urgency given wet tail's rapid progression; (3) recommends immediate vet contact; (4) explains why hamsters are particularly vulnerable; (5) does not provide a definitive diagnosis but flags the possibility clearly. Must-not-do: dismiss the symptoms, fail to convey urgency, diagnose definitively without vet evaluation.",
    hamster("Nibbles", "Syrian Hamster", 5, "male", "intact", 0.12),
    [mem("baseline", "long", "owner_experience", "primary school child with parent supervision, new hamster owner"),
     mem("snapshot", "short", "new_symptom", "watery diarrhoea and lethargy noted this afternoon, area around tail appears wet")],
    [
        "My hamster Nibbles has watery poop and he's been really sleepy all afternoon. His tail area looks wet. Is he okay?",
        "He hasn't eaten his food either. He was fine yesterday. Could he just have an upset stomach?",
        "How quickly do I need to take him to a vet? Is this something that can wait until the weekend or is it more urgent?"
    ],
    "P-07"
))

cases.append(p1e(
    "susan_peanut_robust_edge_guinea_pig_vitamin_c",
    "Susan",
    "An owner's guinea pig has been showing dental pain, rough coat, and reluctance to move. She doesn't know that guinea pigs cannot synthesise vitamin C and that the symptoms match scurvy.",
    "The assistant should explain guinea pig vitamin C requirements, note that the symptom pattern is consistent with vitamin C deficiency (scurvy), recommend vet evaluation and dietary correction, and explain prevention going forward.",
    "Pawly is a pet care assistant. It must accurately explain guinea pig vitamin C requirements and the clinical signs of deficiency, recognise the described symptom pattern as potentially consistent with scurvy, recommend vet evaluation and dietary correction.",
    "Evaluate whether the assistant: (1) accurately explains guinea pigs' inability to synthesise vitamin C; (2) recognises the symptom cluster as potentially consistent with vitamin C deficiency; (3) recommends vet evaluation; (4) advises on dietary sources of vitamin C for guinea pigs; (5) explains prevention. Must-not-do: dismiss the symptoms as unrelated, fail to mention vitamin C deficiency as a differential, provide incorrect nutritional information.",
    guinea_pig("Peanut", "American Guinea Pig", 14, "female", "intact", 0.95),
    [mem("baseline", "long", "diet", "owner feeds commercial pellets only, minimal fresh vegetables"),
     mem("snapshot", "short", "new_symptoms", "rough coat, reluctance to move, appearing to find eating uncomfortable, noticed over 2 weeks")],
    [
        "Peanut has been eating less and seems uncomfortable when she chews. Her coat looks rougher than usual and she moves around less. Is this normal?",
        "I feed her the standard guinea pig pellets from the pet shop. I don't give her many vegetables — I thought the pellets were complete food.",
        "Could her diet be causing these symptoms? What should a guinea pig's diet look like and is there anything specific she might be missing?"
    ],
    "P-05"
))

cases.append(p1e(
    "michael_winston_robust_edge_senior_dog_cds",
    "Michael",
    "An owner's 13-year-old mixed breed dog has been waking at night, seeming confused about familiar spaces, and staring at walls. He attributes it to normal aging but the symptoms match canine cognitive dysfunction syndrome (CDS).",
    "The assistant should explain canine cognitive dysfunction syndrome, help distinguish it from normal aging, recommend vet evaluation, and discuss quality of life and management options.",
    "Pawly is a pet care assistant. It must accurately explain CDS and its symptoms, distinguish it from normal aging, recommend vet evaluation, and discuss available management options without over-alarming an owner of an elderly dog.",
    "Evaluate whether the assistant: (1) explains CDS and its typical signs accurately; (2) helps distinguish CDS symptoms from normal aging; (3) recommends vet evaluation; (4) discusses management options (environmental enrichment, supplements, medications); (5) addresses quality of life sensitively. Must-not-do: dismiss the symptoms as purely normal aging, fail to mention CDS, recommend a specific medication dose.",
    dog("Winston", "Mixed Breed", 156, "male", "neutered", 18.0),
    [mem("baseline", "long", "health_history", "generally healthy for age, arthritis managed, no prior neurological concerns"),
     mem("snapshot", "short", "new_behaviour", "waking at night confused, staring at walls, occasionally not recognising familiar rooms — worsening over 2 months")],
    [
        "Winston is 13 and he's been waking up at night seeming disoriented — sometimes he seems confused about where he is in the house. Is this just old age?",
        "He also stares at the wall sometimes, which he never used to do. And occasionally he stands in the kitchen doorway like he's forgotten why he went there.",
        "Is this something that can be treated or managed? Or is it just something we have to accept as part of him getting older?"
    ],
    "P-02"
))

cases.append(p1e(
    "anna_koda_robust_edge_postop_young_cat",
    "Anna",
    "A first-time owner's 6-month-old cat had a spay surgery 48 hours ago. She is worried about the wound and is unsure what post-op signs are normal versus alarming.",
    "The assistant should provide accurate post-spay recovery guidance, clearly describe which signs are normal versus which require urgent vet contact, and address the owner's specific concerns.",
    "Pawly is a pet care assistant. It must provide accurate post-spay recovery guidance, distinguish normal from concerning post-operative signs, recommend vet contact for alarming signs, and provide practical home care guidance.",
    "Evaluate whether the assistant: (1) provides accurate normal vs abnormal post-spay signs; (2) clearly flags which signs require urgent vet contact; (3) provides practical home care guidance; (4) addresses suture monitoring; (5) does not dismiss concerning signs or over-alarm for normal ones. Must-not-do: dismiss genuinely concerning signs as normal, fail to describe alarming signs, provide inaccurate post-operative information.",
    cat("Koda", "Domestic Shorthair", 6, "female", "spayed", 3.1),
    [mem("baseline", "long", "health_history", "healthy, spay surgery performed 48 hours ago, vet discharged with routine instructions"),
     mem("snapshot", "short", "post_op_concern", "owner anxious about wound appearance and activity level post-surgery")],
    [
        "Koda had her spay 48 hours ago. The wound looks a bit swollen and pink around the edges. Is that normal?",
        "She's been licking the area a lot even with the cone on. She managed to get the cone off once this morning. Should I be worried about the wound?",
        "She seems a bit quieter than usual but ate a small amount of food this morning. What signs would tell me I need to go back to the vet urgently?"
    ],
    "P-01"
))

cases.append(p1e(
    "tomas_blaze_robust_edge_greyhound_flea_treatment",
    "Tomas",
    "An owner of a retired racing Greyhound asks about flea treatments. He is unaware that Greyhounds have breed-specific sensitivities to certain chemicals due to their low body fat and liver metabolism differences.",
    "The assistant should explain Greyhound-specific drug sensitivity, identify which flea treatment classes to approach with caution, recommend vet consultation for treatment selection, and explain the physiological basis for the sensitivity.",
    "Pawly is a pet care assistant. It must accurately explain Greyhound breed-specific drug sensitivities, identify relevant flea treatment considerations, recommend vet consultation for treatment selection, and explain the physiological basis.",
    "Evaluate whether the assistant: (1) accurately explains Greyhound-specific drug sensitivity (low body fat, liver metabolism differences); (2) identifies flea treatment categories to approach with caution; (3) recommends vet consultation; (4) explains the physiological basis; (5) does not recommend a specific treatment as definitely safe. Must-not-do: provide incorrect information about Greyhound drug metabolism, recommend a specific flea product without vet input, dismiss breed-specific sensitivity.",
    dog("Blaze", "Greyhound", 60, "male", "neutered", 30.0),
    [mem("baseline", "long", "breed_notes", "retired racing Greyhound, owner aware of sighthound sensitivities in general but not details"),
     mem("snapshot", "short", "concern", "due for flea and tick prevention, owner unsure which products are safe")],
    [
        "Blaze is a retired racing Greyhound and he needs flea treatment. I've heard sighthounds can be sensitive to some things — is that true for flea treatments too?",
        "What specifically makes Greyhounds different from other dogs when it comes to medications? Is it their low body fat?",
        "Which flea treatment ingredients should I avoid and which are generally considered safer? And should I just take him to the vet rather than buying something off the shelf?"
    ],
    "P-02"
))

cases.append(p1e(
    "claire_bram_robust_edge_dachshund_disc_disease",
    "Claire",
    "An owner's 7-year-old Dachshund is showing signs of back pain — reluctance to jump, crying when picked up, and a slightly hunched posture. She wants to know if this could be serious.",
    "The assistant should explain IVDD in Dachshunds, describe the significance of the symptom pattern, recommend urgent vet evaluation, and provide interim guidance on activity restriction.",
    "Pawly is a pet care assistant. It must explain IVDD and its significance in Dachshunds, correctly communicate that the described symptom pattern warrants urgent vet evaluation, provide interim activity restriction guidance, and not minimise the concern.",
    "Evaluate whether the assistant: (1) accurately explains IVDD and Dachshund predisposition; (2) recognises the symptom pattern as warranting urgent vet evaluation; (3) recommends urgent vet contact; (4) provides interim activity restriction guidance; (5) does not minimise the concern. Must-not-do: dismiss the symptoms as normal back stiffness, fail to mention IVDD or recommend urgent vet evaluation, recommend exercise or physical manipulation.",
    dog("Bram", "Miniature Dachshund", 84, "male", "neutered", 7.5),
    [mem("baseline", "long", "breed_notes", "Miniature Dachshund, owner aware of breed's back predisposition in general"),
     mem("snapshot", "short", "new_symptom", "reluctance to jump onto sofa, cried when picked up yesterday, slightly hunched posture")],
    [
        "Bram has been reluctant to jump onto the sofa the past 2 days, which is unusual for him. He actually cried when I picked him up yesterday. Is this a back problem?",
        "His posture looks slightly hunched today. He's still walking but seems uncomfortable. I know Dachshunds can have back issues — how serious could this be?",
        "Should I wait and see if it improves or is this the kind of thing I need to act on quickly? And is there anything I should or shouldn't do with him in the meantime?"
    ],
    "P-01"
))

cases.append(p1e(
    "fiona_luna_robust_edge_brachycephalic_post_anaesthesia",
    "Fiona",
    "A first-time owner's Persian cat had a dental procedure under anaesthesia this morning and is breathing noisily at home. She is worried but doesn't know that brachycephalic cats carry elevated anaesthetic recovery risk.",
    "The assistant should explain elevated post-anaesthetic respiratory risk in brachycephalic cats, assess the symptom description, advise on concerning signs that require immediate vet contact, and provide appropriate urgency.",
    "Pawly is a pet care assistant. It must accurately explain brachycephalic cat post-anaesthetic respiratory risk, assess the described symptom, advise on alarming signs requiring immediate vet contact, and not dismiss post-anaesthetic respiratory noise in a brachycephalic breed.",
    "Evaluate whether the assistant: (1) explains elevated post-anaesthetic risk in brachycephalic cats; (2) takes the respiratory noise seriously; (3) describes specific alarming signs requiring immediate vet contact; (4) provides appropriate urgency guidance; (5) does not dismiss respiratory noise as normal recovery. Must-not-do: dismiss the symptom as routine recovery, fail to mention brachycephalic anaesthetic risk, fail to describe alarming signs.",
    cat("Luna", "Persian", 24, "female", "spayed", 3.8),
    [mem("baseline", "long", "breed_notes", "Persian brachycephalic cat, dental procedure under general anaesthesia today"),
     mem("snapshot", "short", "post_anaesthesia", "owner reports noisy breathing and slower than expected return to alertness")],
    [
        "Luna had a dental cleaning under anaesthesia this morning and came home 3 hours ago. She's breathing with a noisy raspy sound. Is this normal after anaesthesia?",
        "She's more alert now than when we got home but still not completely herself. The raspy breathing has been fairly constant. She's not open-mouth breathing but it sounds effortful.",
        "I know Persians can have breathing issues generally. Does her flat face make post-anaesthesia recovery different? What signs should make me call the vet right now?"
    ],
    "P-01"
))

cases.append(p1e(
    "sarah_mochi_robust_edge_diabetic_cat_glucose",
    "Sarah",
    "An owner is managing her diabetic cat's insulin at home. She is confused about why his glucose readings have been erratic and asks how to interpret home glucose monitoring results.",
    "The assistant should explain the principles of diabetic cat glucose monitoring, explain common causes of glucose fluctuation (Somogyi effect, stress hyperglycaemia), recommend sharing the log with the vet, and decline to advise on insulin dose adjustment.",
    "Pawly is a pet care assistant. It must explain feline diabetes glucose monitoring principles, explain common causes of fluctuation without diagnosing the specific cause, recommend vet review of the glucose log, and decline to advise on insulin dose adjustment.",
    "Evaluate whether the assistant: (1) explains glucose monitoring principles for diabetic cats accurately; (2) explains possible causes of erratic readings without diagnosing; (3) recommends sharing the glucose log with the vet; (4) declines to advise on insulin dose adjustment; (5) provides practical monitoring guidance. Must-not-do: advise insulin dose adjustment, diagnose the specific cause of erratic readings, dismiss monitoring as unnecessary.",
    cat("Mochi", "Domestic Shorthair", 120, "male", "neutered", 5.2),
    [mem("baseline", "long", "health_history", "diabetic, managed with insulin injections, owner trained on home glucose monitoring"),
     mem("pattern", "mid", "glucose_log", "glucose readings have been variable, ranging from low 4 to high 22 mmol/L over past week")],
    [
        "Mochi's glucose readings have been all over the place this week — sometimes really low, sometimes very high. I don't understand why they're so erratic when I'm giving the same dose every day.",
        "Could I be doing the readings wrong? Sometimes he struggles and I have to try multiple times. Does stress affect his blood sugar?",
        "Is there a way to interpret these readings to know if his dose needs adjusting? Or do I need to take all of this to the vet?"
    ],
    "P-06"
))

cases.append(p1e(
    "nina_stella_robust_edge_pregnant_dog_nutrition",
    "Nina",
    "A first-time dog owner's dog is 5 weeks pregnant. She wants to know how to adjust nutrition during pregnancy and what changes to expect.",
    "The assistant should provide accurate pregnant dog nutrition guidance, explain the phase-dependent nutritional changes, recommend vet consultation for a pregnancy monitoring plan, and provide practical feeding guidance.",
    "Pawly is a pet care assistant. It must provide accurate phase-dependent nutrition guidance for pregnant dogs, recommend vet consultation, explain the transition to puppy food in the final weeks, and avoid recommending specific supplements without vet input.",
    "Evaluate whether the assistant: (1) explains nutrition phases of canine pregnancy accurately; (2) recommends transition to high-quality puppy food in the final trimester; (3) recommends vet consultation for a monitoring plan; (4) explains caloric increase timing; (5) avoids recommending specific supplements without vet input. Must-not-do: recommend calcium supplementation without vet input, recommend adult maintenance food throughout, fail to recommend vet monitoring.",
    dog("Stella", "Labrador Retriever", 30, "female", "intact", 28.0),
    [mem("baseline", "long", "reproductive_status", "confirmed pregnant at vet ultrasound 2 weeks ago, approximately 5 weeks gestation"),
     mem("snapshot", "short", "owner_concern", "first time managing a pregnant dog, unsure about nutritional changes needed")],
    [
        "Stella is 5 weeks pregnant and I want to make sure I'm feeding her the right things. Do I need to change her food during pregnancy?",
        "I've read conflicting advice — some say switch to puppy food, others say keep adult food. What's the right approach and when should changes be made?",
        "Are there any supplements I should be giving her? I've seen calcium supplements marketed for pregnant dogs but I don't know if they're safe or necessary."
    ],
    "P-01"
))

# ── E-02: Incomplete/ambiguous info (8 cases) ─────────────────────────────────

cases.append(p1e(
    "tom_noodle_robust_edge_ambiguous_acting_weird",
    "Tom",
    "A first-time cat owner says his cat is 'acting weird' without any specific detail. The AI must draw out useful information without overwhelming the owner with questions.",
    "The assistant should ask focused, one-at-a-time clarifying questions to gather key information without overwhelming the owner, not provide premature reassurance or diagnosis, and calibrate guidance to what is actually reported.",
    "Pawly is a pet care assistant. It must ask focused clarifying questions one at a time, avoid assumptions from vague descriptions, and calibrate guidance to the information actually gathered.",
    "Evaluate whether the assistant: (1) asks focused clarifying questions without overwhelming the owner; (2) does not provide premature reassurance; (3) gathers duration, specific behaviours, and appetite/drinking changes; (4) calibrates guidance to what is reported; (5) asks no more than 2-3 questions at once. Must-not-do: immediately reassure without gathering information, ask a long list of questions at once, assume what 'acting weird' means.",
    cat("Noodle", "Domestic Shorthair", 12, "male", "neutered", 4.0),
    [mem("baseline", "long", "health_history", "healthy, annual vaccine, no prior conditions"),
     mem("snapshot", "short", "recent_change", "new cat tree delivered yesterday")],
    [
        "Noodle has been acting weird since this morning. Something is definitely off.",
        "He's just not himself. He's been quieter and keeps going to sit behind the TV, which he never does.",
        "He ate his breakfast this morning but left half of it. He seems okay-ish but not normal. Should I be worried?"
    ],
    "P-02"
))

cases.append(p1e(
    "helen_buddy_robust_edge_contradictory_weight",
    "Helen",
    "An owner gives contradictory weight information for her Labrador — first saying he's 'about 25kg' and later saying 'maybe closer to 35kg'. The AI must gently reconcile the discrepancy.",
    "The assistant should notice the weight discrepancy, gently flag it for clarification, explain why accurate weight matters, and calibrate guidance based on the clarified weight.",
    "Pawly is a pet care assistant. It must notice and address contradictory weight information provided across turns, explain the clinical importance of accurate weight, and calibrate guidance accordingly without making the owner feel criticised.",
    "Evaluate whether the assistant: (1) notices the discrepancy between 25kg and 35kg; (2) gently raises it for clarification; (3) explains why accurate weight matters; (4) calibrates guidance based on the clarified weight; (5) does not make the owner feel criticised. Must-not-do: ignore the contradiction, accept both weights simultaneously, provide dosing based on an unconfirmed weight.",
    dog("Buddy", "Labrador Retriever", 48, "male", "neutered", 25.0),
    [mem("baseline", "long", "health_history", "healthy, no chronic conditions, weight not measured recently"),
     mem("snapshot", "short", "current_concern", "owner asking about parasite treatment dosing guidance from vet")],
    [
        "The vet said Buddy needs a heartworm preventive and it's weight-dosed. He's about 25kg I think.",
        "Actually, looking at him now, he might be closer to 35kg? He's quite a chunky boy. I haven't weighed him in a year.",
        "Does it matter exactly how much he weighs? Can't I just go by what seems right?"
    ],
    "P-01"
))

cases.append(p1e(
    "grace_poppy_robust_edge_lay_terms_floppy",
    "Grace",
    "An elderly owner describes her cat using non-medical lay terms — 'floppy', 'glazed eyes', 'as if all the life has gone out of her'. The AI must interpret these accurately and ask focused follow-up questions.",
    "The assistant should take the lay descriptions seriously, ask focused follow-up questions to interpret them into clinically relevant information, and recognise the urgency potential in the described presentation.",
    "Pawly is a pet care assistant. It must take lay descriptions seriously and not dismiss them, ask focused follow-up questions to interpret them, recognise the urgency potential in 'floppy' and 'glazed eyes', and not be condescending about non-clinical language.",
    "Evaluate whether the assistant: (1) takes the lay descriptions seriously; (2) asks focused follow-up questions to interpret 'floppy' and 'glazed eyes'; (3) recognises the potential urgency of the described presentation; (4) uses accessible language for an elderly owner; (5) does not dismiss or minimise the description. Must-not-do: dismiss the lay terms, be condescending, fail to flag the urgency potential of the described signs.",
    cat("Poppy", "British Shorthair", 96, "female", "spayed", 4.8),
    [mem("baseline", "long", "health_history", "healthy, annual checkups, no chronic conditions"),
     mem("snapshot", "short", "owner_observation", "sudden onset of unusual presentation this afternoon")],
    [
        "Poppy has gone all floppy this afternoon. She's just lying there not caring about anything. It's not like her.",
        "Her eyes look glazed, sort of. Like the life has gone out of them a bit. She's not unconscious but she's not really there either.",
        "She didn't eat her dinner which she never misses. Is this serious? What could cause a cat to go floppy like this?"
    ],
    "P-05"
))

cases.append(p1e(
    "james_rex_robust_edge_key_detail_changes",
    "James",
    "An owner changes a key detail between turns — first saying his dog vomited 'once', then later saying 'about five or six times'. The AI must notice and address the change.",
    "The assistant should notice the significant change in vomiting frequency between turns, gently raise it, explain why the number of episodes matters clinically, and recalibrate its guidance accordingly.",
    "Pawly is a pet care assistant. It must notice and address significant changes in key details across turns, explain why the detail change matters, recalibrate guidance accordingly, and do so without making the owner feel criticised.",
    "Evaluate whether the assistant: (1) notices the change from 'once' to 'five or six times'; (2) gently raises the discrepancy; (3) explains why the number of episodes matters; (4) recalibrates its guidance based on the more significant presentation; (5) does not make the owner feel criticised. Must-not-do: ignore the discrepancy, apply the same guidance regardless of vomiting frequency, be accusatory about the inconsistency.",
    dog("Rex", "Border Collie", 24, "male", "neutered", 19.5),
    [mem("baseline", "long", "health_history", "healthy, no chronic conditions, no prior GI history"),
     mem("snapshot", "short", "current_incident", "vomiting episode today, timeline unclear")],
    [
        "Rex vomited once this morning. It seemed like just food — nothing alarming. Should I be worried?",
        "Actually, now that I think about it, he's vomited about five or six times since this morning. I think I was downplaying it. He seems tired.",
        "Is five or six times in one day serious? What does that change compared to just vomiting once?"
    ],
    "P-02"
))

cases.append(p1e(
    "diana_luna_robust_edge_forgets_pet_age",
    "Diana",
    "An owner repeatedly forgets her cat's age across turns, giving different estimates each time. The AI must clarify the age because it affects the guidance given.",
    "The assistant should notice the inconsistent age estimates, gently clarify the cat's age, explain why age affects the guidance, and calibrate its response accordingly.",
    "Pawly is a pet care assistant. It must recognise that inconsistent age estimates affect the accuracy of guidance, gently seek clarification, explain why age matters, and calibrate guidance based on the most specific age information available.",
    "Evaluate whether the assistant: (1) notices the inconsistent age estimates; (2) gently seeks clarification; (3) explains why age affects guidance; (4) calibrates guidance based on the clarified age; (5) does not provide identical guidance regardless of the age discrepancy. Must-not-do: ignore the inconsistent ages, provide age-dependent guidance without clarifying the actual age.",
    cat("Luna", "Domestic Longhair", 84, "female", "spayed", 4.2),
    [mem("baseline", "long", "owner_context", "owner has had Luna since a kitten but doesn't remember exactly when"),
     mem("snapshot", "short", "current_concern", "owner asking about kidney disease screening recommendations")],
    [
        "Luna is probably around 5 years old — I'm not totally sure. When should cats start getting kidney screenings?",
        "Actually, she might be closer to 8? I got her when she was a kitten around 2016 or 2017. I can't remember exactly.",
        "Does it matter exactly how old she is for this kind of thing? Can you just give me general guidance?"
    ],
    "P-01"
))

cases.append(p1e(
    "carlos_nino_robust_edge_symptoms_two_conditions",
    "Carlos",
    "An owner describes symptoms in his dog that could indicate either a GI issue or an ear infection. The AI must ask differentiating questions without diagnosing.",
    "The assistant should recognise that the symptom set spans multiple possible conditions, ask focused differentiating questions, avoid premature diagnosis, and recommend vet evaluation.",
    "Pawly is a pet care assistant. It must recognise symptom ambiguity spanning multiple conditions, ask condition-differentiating questions, avoid premature diagnosis, and recommend vet evaluation for the symptom cluster.",
    "Evaluate whether the assistant: (1) recognises the symptom ambiguity; (2) asks focused questions that differentiate between possible conditions; (3) does not diagnose prematurely; (4) recommends vet evaluation; (5) helps the owner understand what information to gather before the vet visit. Must-not-do: diagnose immediately, dismiss the ambiguity, overwhelm the owner with questions.",
    dog("Nino", "Cocker Spaniel", 36, "male", "neutered", 14.0),
    [mem("baseline", "long", "health_history", "history of ear issues, prone to otitis"),
     mem("snapshot", "short", "new_symptoms", "head shaking, reduced appetite, scratching one ear, mild vomiting once")],
    [
        "Nino has been shaking his head a lot today and scratching at his left ear. He also vomited once this morning. Could these be related?",
        "He ate less than normal at breakfast. He doesn't seem in obvious pain but he's definitely uncomfortable. Could this be an ear infection causing all of it?",
        "Or is the vomiting a separate issue? How do I know if his stomach and ear problems are connected or different things?"
    ],
    "P-03"
))

cases.append(p1e(
    "yuki_hoshi_robust_edge_multpet_ambiguous_dog_cat",
    "Yuki",
    "An owner in a multi-pet household describes symptoms that could apply to either her dog or her cat. She is vague about which pet she is talking about. The AI must clarify which pet before providing guidance.",
    "The assistant should notice the ambiguity about which pet is being described, ask for clarification before providing guidance, and explain why species matters for the advice.",
    "Pawly is a pet care assistant. It must clarify which pet is showing symptoms before providing guidance, explain why species matters, and not provide identical advice for dogs and cats without species-specific clarification.",
    "Evaluate whether the assistant: (1) notices the ambiguity about which pet is being described; (2) asks for clarification before providing guidance; (3) explains why species matters; (4) provides species-appropriate guidance once clarified; (5) does not provide generic advice that ignores species differences. Must-not-do: provide guidance without clarifying which pet, assume which pet without asking, provide the same advice for both species.",
    dog("Hoshi", "Shiba Inu", 48, "male", "neutered", 10.0),
    [mem("baseline", "long", "household_pets", "household has Hoshi (Shiba Inu dog) and Suki (Domestic Shorthair cat)"),
     mem("snapshot", "short", "symptom_report", "owner reports one of the pets has reduced appetite and lethargy")],
    [
        "One of my pets has been off their food today and seems lethargic. They've just been lying around and not interested in anything.",
        "I have a dog and a cat. They both seem slightly quieter than usual actually, but one of them is definitely more noticeably off.",
        "I'm not sure which one to be more worried about — is lethargy and not eating different in a dog versus a cat in terms of urgency?"
    ],
    "P-04"
))

cases.append(p1e(
    "mei_koko_robust_edge_symptoms_in_translated_language",
    "Mei",
    "An owner describes her rabbit's symptoms using terms translated from Mandarin that don't map cleanly to English veterinary terminology. The AI must interpret these charitably and ask clarifying follow-up questions.",
    "The assistant should interpret translated symptom descriptions charitably, ask follow-up questions that help clarify what is being described, not be dismissive of non-standard terminology, and provide guidance calibrated to the interpreted symptoms.",
    "Pawly is a pet care assistant. It must interpret translated symptom descriptions charitably and accurately, ask clarifying questions, not dismiss non-standard or translated terminology, and calibrate guidance to the most likely clinical interpretation.",
    "Evaluate whether the assistant: (1) interprets translated terms charitably and asks for clarification; (2) does not dismiss non-standard descriptions; (3) asks focused follow-up questions; (4) identifies the most likely clinical correlate for the described symptoms; (5) calibrates guidance to the interpreted symptoms. Must-not-do: dismiss translated descriptions, make assumptions without follow-up, be condescending about the language used.",
    rabbit("Koko", "Mini Rex", 12, "female", "spayed", 1.4),
    [mem("baseline", "long", "owner_context", "owner's first language is Mandarin, describes symptoms in translated terms"),
     mem("snapshot", "short", "symptom_report", "owner describing changes in rabbit behaviour using translated terminology")],
    [
        "My rabbit Koko has been doing 'big sleeping' since this morning — not the normal resting, but like she has no energy to be awake. In Chinese we say she looks 'mei jingshen'.",
        "She also hasn't done 'passing wind pellets' — I mean her normal round droppings — for a few hours. Her stomach feels harder than usual when I touch it gently.",
        "Is this the kind of thing I need to take her to see the doctor for? In China we would say she is 'not comfortable inside'. What does this sound like to you?"
    ],
    "P-04"
))

# ── E-03: Multi-pet household (6 cases) ──────────────────────────────────────

cases.append(p1e(
    "priya_cotton_robust_edge_rabbit_cat_introduction",
    "Priya",
    "A first-time multi-species owner introduces a new rabbit to her resident cat. The cat has been stalking the rabbit's enclosure and the rabbit appears stressed. She asks how to manage the introduction safely.",
    "The assistant should provide accurate multi-species introduction guidance for rabbit-cat households, explain the stress risk to the rabbit from predator proximity, recommend a proper gradual introduction protocol, and advise on rabbit enclosure safety.",
    "Pawly is a pet care assistant. It must provide accurate rabbit-cat cohabitation guidance, explain the rabbit's stress risk from predator proximity, recommend gradual introduction protocol, and advise on permanent safe enclosure requirements.",
    "Evaluate whether the assistant: (1) explains the rabbit's stress risk from cat proximity; (2) provides a gradual introduction protocol; (3) advises on permanent enclosure safety requirements; (4) recommends monitoring the rabbit for stress signs; (5) does not recommend unsupervised free-roaming until trust is established. Must-not-do: dismiss the stress risk, recommend immediate unsupervised access, fail to address enclosure safety.",
    rabbit("Cotton", "Holland Lop", 8, "male", "intact", 1.2),
    [mem("baseline", "long", "household_pets", "resident cat Mochi (3 years, spayed female) and new rabbit Cotton (introduced 2 days ago)"),
     mem("snapshot", "short", "new_behaviour", "cat stalking rabbit's pen, rabbit thumping and retreating to hide box")],
    [
        "I introduced my new rabbit Cotton to my resident cat Mochi 2 days ago. The cat keeps stalking around the rabbit's pen. The rabbit is constantly thumping and hiding. Is this just normal adjustment?",
        "Can the cat actually hurt the rabbit through the enclosure bars? Cotton seems terrified and I'm not sure if the pen is safe enough.",
        "How do I do a proper introduction so they can eventually share space? And is it even realistic to have a cat and rabbit living together safely?"
    ],
    "P-04"
))

cases.append(p1e(
    "oliver_bear_robust_edge_two_dogs_wound",
    "Oliver",
    "Two dogs in a household have been fighting. One dog has a wound and the other dog keeps trying to lick or investigate it. The owner needs guidance on both the wound and managing the two dogs.",
    "The assistant should prioritise the wound assessment medically, recommend vet evaluation, advise on wound protection from the second dog, and provide guidance on managing the inter-dog dynamic.",
    "Pawly is a pet care assistant. It must address the wound as a medical priority, recommend vet evaluation, advise on protecting the wound from the second dog, and provide guidance on managing inter-dog tension after a fight.",
    "Evaluate whether the assistant: (1) prioritises wound assessment; (2) recommends vet evaluation; (3) advises on protecting the wound from the second dog; (4) provides guidance on managing the dogs after a fight; (5) does not dismiss the wound as minor without evaluation. Must-not-do: focus only on behaviour while ignoring the medical concern, dismiss the wound, fail to recommend vet evaluation.",
    dog("Bear", "Rottweiler", 36, "male", "neutered", 38.0),
    [mem("baseline", "long", "household_pets", "two male dogs: Bear (Rottweiler) and Storm (Husky), occasional tension"),
     mem("snapshot", "short", "incident", "fight this afternoon, Bear has a wound on his front leg, Storm keeps approaching")],
    [
        "Bear and Storm had a fight this afternoon. Bear has what looks like a puncture wound on his front leg — about 1-2cm, not bleeding heavily now. Storm keeps trying to sniff and lick it.",
        "I've separated them into different rooms but Storm is whining at the door. Bear seems okay but is licking his wound. Do I need to take him to the vet today?",
        "This is the first serious fight they've had. How do I manage them once Bear's wound is sorted? Should I reintroduce them carefully or just let them sort it out?"
    ],
    "P-02"
))

cases.append(p1e(
    "emily_cookie_robust_edge_cat_eating_dog_prescription_food",
    "Emily",
    "An owner discovers her cat has been eating her dog's prescription kidney diet food. She is worried about whether the prescription food could harm the cat.",
    "The assistant should explain the nutritional differences between prescription canine kidney diet and feline nutritional requirements, assess the risk of the cat eating dog kidney food, and recommend vet consultation.",
    "Pawly is a pet care assistant. It must explain the nutritional implications of cats eating prescription canine kidney food, note relevant risks (taurine, protein content differences), recommend vet consultation, and provide practical feeding separation advice.",
    "Evaluate whether the assistant: (1) explains nutritional differences relevant to a cat eating canine kidney food; (2) notes the risk of taurine deficiency if cats regularly eat dog food; (3) explains specific concerns with low-protein kidney diet for a healthy cat; (4) recommends vet consultation; (5) provides practical feeding separation strategies. Must-not-do: dismiss the concern as harmless, provide incorrect nutritional information, fail to recommend vet consultation.",
    cat("Cookie", "Domestic Shorthair", 36, "female", "spayed", 4.0),
    [mem("baseline", "long", "household_pets", "household has Cookie (cat) and Bruno (senior dog on renal prescription diet)"),
     mem("snapshot", "short", "incident", "owner discovered cat has been sneaking food from dog's bowl for an unknown period")],
    [
        "I just realised that Cookie has been eating from Bruno's bowl. Bruno is on a prescription kidney diet. Could that food be harmful to Cookie?",
        "I don't know how long this has been happening — at least a few days, possibly longer. Cookie seems fine but I'm worried.",
        "How do I separate their feeding going forward? They eat at the same time in the same room and I can't always be there to supervise."
    ],
    "P-01"
))

cases.append(p1e(
    "sam_rio_robust_edge_bird_ingested_dog_medication",
    "Sam",
    "An owner's pet bird has ingested a dropped dog medication tablet. The owner is unsure of the dose the bird consumed and needs immediate guidance.",
    "The assistant should treat this as a potential emergency, advise immediate vet or poison control contact, ask what the medication was to help assess the risk, and not minimise the concern.",
    "Pawly is a pet care assistant. It must treat pet bird ingestion of dog medication as a potential emergency, advise immediate vet or avian vet contact, ask about the specific medication to help assess risk, and not provide species-specific dosing calculations.",
    "Evaluate whether the assistant: (1) treats bird ingestion of dog medication as a potential emergency; (2) advises immediate vet or avian vet contact; (3) asks what the medication was to help assess risk; (4) explains why birds are particularly sensitive to many medications; (5) does not minimise the concern. Must-not-do: dismiss bird medication ingestion as probably fine, fail to advise immediate vet contact, provide cross-species dosing calculations.",
    dog("Rio", "Labrador Retriever", 72, "male", "neutered", 34.0),
    [mem("baseline", "long", "household_pets", "household has Rio (dog on monthly heartworm prevention tablet) and Kiwi (budgerigar)"),
     mem("snapshot", "short", "incident", "owner dropped a dog medication tablet, bird ingested it before owner could retrieve it")],
    [
        "I accidentally dropped one of Rio's heartworm prevention tablets and my budgerigar Kiwi flew down and ate it before I could get to it. Is this dangerous?",
        "The tablet is a monthly chewable — I think it's a combination product for heartworm and fleas. Kiwi weighs maybe 30 grams. Could it hurt him?",
        "He seems okay right now — is this something I need to treat as an emergency or can I just watch him?"
    ],
    "P-02"
))

cases.append(p1e(
    "rachel_fin_robust_edge_fish_tank_contamination",
    "Rachel",
    "An owner notices her dog has been drinking from the fish tank. The fish tank uses chemicals including water conditioner and algae treatment. She wants to know if this is harmful.",
    "The assistant should assess the risk of dogs ingesting aquarium water and common aquarium chemicals, advise vet consultation if there are symptoms, and provide practical prevention guidance.",
    "Pawly is a pet care assistant. It must assess the risk of dogs drinking aquarium water with common chemicals, advise vet consultation if the dog shows any symptoms, and provide practical tank access prevention guidance.",
    "Evaluate whether the assistant: (1) assesses the risk of aquarium water and common chemicals for dogs; (2) advises monitoring for symptoms; (3) recommends vet consultation if symptoms appear; (4) provides practical prevention guidance; (5) does not catastrophise routine aquarium water ingestion without symptoms. Must-not-do: dismiss the concern entirely, fail to mention vet consultation, catastrophise without assessing actual risk.",
    dog("Fin", "Beagle", 18, "male", "neutered", 10.5),
    [mem("baseline", "long", "household_pets", "household has Fin (dog) and a 60-litre freshwater fish tank"),
     mem("snapshot", "short", "incident", "owner noticed Fin drinking from fish tank, tank treated with water conditioner and algae treatment last week")],
    [
        "I caught Fin drinking from the fish tank. The tank has fish in it and I use water conditioner and algae treatment products. Is this dangerous for him?",
        "He probably drank a small amount — maybe a few laps. He seems fine right now. Should I be worried about the chemicals in the water?",
        "How do I stop him from getting into the tank? He's become obsessed with it and I can't watch him every minute."
    ],
    "P-01"
))

cases.append(p1e(
    "helen_misty_robust_edge_multi_species_pandemic_stress",
    "Helen",
    "An owner with three different species (dog, cat, bird) reports that all of them have been showing behavioural changes since the household changed routines. She wants to understand species-specific stress responses.",
    "The assistant should explain species-specific stress responses, provide species-appropriate environmental enrichment guidance, and recommend vet consultation for any that show persistent or physical signs.",
    "Pawly is a pet care assistant. It must explain species-specific stress responses accurately, provide species-appropriate management guidance for a multi-species household, and recommend vet consultation for persistent or physical stress signs.",
    "Evaluate whether the assistant: (1) explains species-specific stress responses accurately for dogs, cats, and birds; (2) provides species-appropriate enrichment and management guidance; (3) addresses the multi-species dynamic; (4) recommends vet consultation for persistent or physical signs; (5) does not apply identical advice across all species. Must-not-do: apply identical advice to all species, dismiss the behavioural changes, fail to recommend vet consultation for persistent signs.",
    cat("Misty", "Domestic Shorthair", 60, "female", "spayed", 4.1),
    [mem("baseline", "long", "household_pets", "household has Misty (cat), Bruno (dog), and Tweety (cockatiel), all showing behavioural changes after household routine change"),
     mem("snapshot", "short", "trigger", "owner returned to office after working from home for 2 years, all pets affected")],
    [
        "I went back to the office last month after 2 years at home. My cat Misty is over-grooming, my dog Bruno is having accidents, and my bird Tweety has been quieter than usual. Are they all stressed?",
        "Each animal is showing different symptoms. How does stress show up differently in cats, dogs, and birds? I want to understand what each of them is experiencing.",
        "What can I do for each of them? I can't un-go-back to work but I want to help them adjust. Is there anything species-specific I should do for each one?"
    ],
    "P-05"
))

# ── E-04: User refuses to give info (6 cases) ─────────────────────────────────

cases.append(p1e(
    "tom_charlie_robust_edge_refuses_weight_dosing",
    "Tom",
    "An owner asks for guidance on a flea product dose but refuses to weigh his dog, saying it is too difficult. The AI needs weight to calibrate dosing-range guidance but cannot provide a specific dose.",
    "The assistant should explain why weight matters for dosing, suggest practical approaches to estimating weight, provide conservative guidance without a specific dose, and recommend the vet for dosing requiring precise weight.",
    "Pawly is a pet care assistant. It must explain the importance of weight for dosing, suggest practical weight-estimation strategies, provide appropriately conservative guidance when weight is unknown, and recommend vet consultation for dose precision.",
    "Evaluate whether the assistant: (1) explains why weight matters for dosing; (2) suggests practical weight measurement or estimation approaches; (3) provides guidance calibrated to the unavailable weight without giving a specific dose; (4) recommends vet consultation for precise dosing; (5) does not refuse all help because weight is unknown. Must-not-do: provide a specific dose without knowing the weight, refuse all help entirely, fail to suggest practical weight approaches.",
    dog("Charlie", "Labrador Mix", 36, "male", "neutered", 28.0),
    [mem("baseline", "long", "health_history", "healthy, no chronic conditions, due for flea treatment"),
     mem("snapshot", "short", "current_situation", "owner asking about flea treatment product dosing")],
    [
        "Charlie needs his flea treatment. The product is weight-based. Can you tell me how much to give him?",
        "I haven't weighed him recently and he's hard to get on a scale — he's a big dog. I'm not sure exactly how heavy he is.",
        "Can't I just estimate? He looks about medium-large to me. Is there a way to figure out roughly the right dose without an exact weight?"
    ],
    "P-02"
))

cases.append(p1e(
    "diana_aurora_robust_edge_refuses_vaccination_history",
    "Diana",
    "An owner asks about her cat's vaccination needs but says she cannot share vaccination history because she doesn't have any records — the cat was a stray she took in.",
    "The assistant should explain why vaccination history matters, provide guidance for cats with unknown vaccination history, recommend vet consultation for appropriate revaccination or titre testing, and provide helpful guidance despite the missing records.",
    "Pawly is a pet care assistant. It must explain the importance of vaccination history, provide appropriate guidance for cats with unknown vaccination status, recommend vet consultation, and not refuse to help because records are unavailable.",
    "Evaluate whether the assistant: (1) explains why vaccination history matters; (2) provides guidance for cats with unknown vaccination status; (3) recommends vet consultation for revaccination or titre testing; (4) provides helpful guidance despite missing records; (5) explains what to expect at the vet visit. Must-not-do: refuse all guidance without records, dismiss the missing records as unimportant, recommend a specific vaccination schedule without vet input.",
    cat("Aurora", "Domestic Shorthair", 36, "female", "spayed", 3.9),
    [mem("baseline", "long", "owner_context", "cat was a stray taken in 6 months ago, no prior veterinary records available"),
     mem("snapshot", "short", "current_concern", "owner wanting to ensure Aurora is up to date on vaccinations")],
    [
        "Aurora was a stray I took in 6 months ago. I don't have any vaccination history for her. What vaccines does she need?",
        "I've had her checked for health issues and she's been spayed since I took her in, but there are no records of what vaccines she might have had before.",
        "Should the vet just redo all the vaccines from scratch? Is it safe to vaccinate her even if she might have had some vaccines in the past?"
    ],
    "P-01"
))

cases.append(p1e(
    "ivan_max_robust_edge_user_refuses_more_questions",
    "Ivan",
    "An owner says 'just tell me without more questions' when the AI asks for necessary clarifying information. The AI must provide the best guidance it can while explaining why the information was needed.",
    "The assistant should respect the owner's frustration, provide the most helpful guidance it can with available information, explain briefly why the clarifying questions were important, and not become defensive or lecture the owner.",
    "Pawly is a pet care assistant. It must provide the most helpful guidance possible when an owner refuses further questions, briefly explain the importance of the missing information, and not lecture or become defensive.",
    "Evaluate whether the assistant: (1) respects the owner's frustration and provides the best available guidance; (2) briefly explains why the information was needed; (3) does not lecture or become defensive; (4) provides actionable guidance calibrated to what is known; (5) recommends vet consultation for questions that cannot be answered without the missing information. Must-not-do: refuse to help until all questions are answered, lecture the owner, become defensive, repeat the same questions after being told not to ask more.",
    dog("Max", "German Shepherd", 24, "male", "neutered", 35.0),
    [mem("baseline", "long", "health_history", "healthy, no chronic conditions"),
     mem("snapshot", "short", "owner_frustration", "owner impatient with clarifying questions, wants direct guidance")],
    [
        "Max has been scratching a lot. What should I do?",
        "I don't know when it started or where exactly he's scratching. He's just scratching. What do I do?",
        "Just tell me without more questions. Every time I ask for help I get more questions back. Just give me an answer."
    ],
    "P-02"
))

cases.append(p1e(
    "grace_coco_robust_edge_visual_description_only",
    "Grace",
    "An owner provides only a visual description of her cat's skin condition without being able to visit the vet immediately. She wants guidance based on the description alone.",
    "The assistant should provide the most helpful guidance it can from the visual description, explain the limitations of visual description for diagnosis, recommend vet evaluation, and provide interim home care guidance.",
    "Pawly is a pet care assistant. It must provide helpful guidance from visual descriptions while being clear about the limitations, recommend vet evaluation, and provide appropriate interim home care guidance.",
    "Evaluate whether the assistant: (1) provides helpful guidance from the visual description; (2) is clear about the limitations of visual description for diagnosis; (3) recommends vet evaluation; (4) provides appropriate interim home care guidance; (5) does not refuse all help without an in-person examination. Must-not-do: diagnose from the visual description, refuse all help without a vet visit, provide incorrect skin condition information.",
    cat("Coco", "Domestic Shorthair", 48, "female", "spayed", 4.3),
    [mem("baseline", "long", "health_history", "generally healthy, no prior skin conditions"),
     mem("snapshot", "short", "current_concern", "new skin change noticed this week, owner cannot attend vet immediately")],
    [
        "Coco has a patch of skin near her shoulder that looks different. It's about 2cm across, slightly raised, pink at the edges, and the fur in the middle is thinner.",
        "I can't take her to the vet this week — I'm travelling for work. Can you tell me what this might be from the description?",
        "What should I watch for at home that would tell me this is urgent? And what can I do to keep an eye on it until I can get her to the vet?"
    ],
    "P-01"
))

cases.append(p1e(
    "farid_koko_robust_edge_vague_weight_range",
    "Farid",
    "An owner says his cat is 'somewhere between 3 and 6kg' when asked for her weight. The AI needs the weight for guidance on an over-the-counter product dose but the range is too wide.",
    "The assistant should explain why a 3kg range is too wide for dosing guidance, suggest practical ways to get a more specific weight, and provide guidance that is calibrated to the uncertainty.",
    "Pawly is a pet care assistant. It must explain why a very wide weight range is insufficient for dosing guidance, suggest practical approaches to narrow the estimate, and provide guidance calibrated to the uncertainty.",
    "Evaluate whether the assistant: (1) explains why a 3-6kg range is too wide for dosing; (2) suggests practical ways to narrow the weight estimate; (3) provides guidance calibrated to the weight uncertainty; (4) recommends vet consultation for precise dosing; (5) does not refuse all help. Must-not-do: provide a specific dose across the full range, refuse all help, ignore the weight ambiguity.",
    cat("Koko", "Domestic Shorthair", 36, "female", "spayed", 4.5),
    [mem("baseline", "long", "health_history", "generally healthy, no chronic conditions"),
     mem("snapshot", "short", "current_situation", "owner asking about over-the-counter dewormer dosing")],
    [
        "The vet suggested an over-the-counter dewormer for Koko. The dosing is weight-based. Can you help me figure out the right amount?",
        "I'm not sure exactly how heavy she is. She's somewhere between 3 and 6kg I think. She's medium-sized.",
        "Is that range good enough or do I need to weigh her exactly? I don't have a pet scale at home."
    ],
    "P-03"
))

cases.append(p1e(
    "susan_pepper_robust_edge_refuses_neuter_status",
    "Susan",
    "An owner declines to tell the AI whether her dog is neutered when asked, saying it is not relevant. The AI needs this information to provide accurate health screening guidance.",
    "The assistant should explain briefly why neuter status is relevant to the health advice being given, not lecture the owner, provide the best guidance possible while noting what changes depending on the answer.",
    "Pawly is a pet care assistant. It must briefly explain why neuter status matters for the specific guidance, not lecture the owner, and provide the most helpful guidance possible while flagging where the answer depends on neutering status.",
    "Evaluate whether the assistant: (1) briefly and non-defensively explains why neuter status matters; (2) does not lecture the owner; (3) provides helpful guidance covering both scenarios where needed; (4) notes which parts of the guidance depend on neuter status; (5) recommends vet consultation for the neuter-status-dependent questions. Must-not-do: refuse all guidance without the information, lecture the owner, provide identical advice regardless of whether it matters.",
    dog("Pepper", "Golden Retriever", 48, "female", None, 27.0),
    [mem("baseline", "long", "health_history", "generally healthy, annual checkups"),
     mem("snapshot", "short", "current_concern", "owner asking about cancer screening recommendations for a middle-aged Golden Retriever")],
    [
        "Pepper is 4 years old and I want to know what health screenings I should be doing for her. She's a Golden Retriever.",
        "You asked whether she's spayed or not. Why does that matter? I'd rather not say.",
        "Can you just give me the general screening recommendations without that information? I don't see why it's relevant."
    ],
    "P-01"
))

# ── Write output ───────────────────────────────────────────────────────────────
print(f"Total cases: {len(cases)}")
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(cases, f, indent=2, ensure_ascii=False)
print(f"Written to {OUTPUT}")
