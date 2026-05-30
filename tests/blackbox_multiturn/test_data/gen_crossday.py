"""
Generate cross-day multi-turn test cases for testing memory continuity between days.

Each case spans two simulated days. The `days` list encodes per-day user turns and
flags for extraction / daily-summary jobs. The judge evaluates whether the bot
carries forward context from Day 1 into Day 2 without re-asking already-covered
questions and with advice informed by the prior day's episode.
"""
import json
import pathlib

OUT = pathlib.Path(__file__).parent / "multiturn_crossday_cases.json"


def crossday(name, scenario, expected_outcome, chatbot_role, criteria, threshold, pet_profile, days):
    return {
        "name": name,
        "scenario": scenario,
        "expected_outcome": expected_outcome,
        "chatbot_role": chatbot_role,
        "criteria": criteria,
        "threshold": threshold,
        "pet_profile": pet_profile,
        "metadata": {
            "category": "cross_day",
            "layer": "handler_blackbox_multiturn",
            "priority": "P1",
            "multiturn": True,
        },
        "days": days,
    }


def day(label, user_turns, run_extraction=True, run_daily_summary=False):
    return {
        "label": label,
        "user_turns": user_turns,
        "run_extraction": run_extraction,
        "run_daily_summary": run_daily_summary,
    }


def cat(name, breed, age_in_months, gender, neutered_status, weight_latest):
    return {
        "name": name,
        "species": "cat",
        "breed": breed,
        "age_in_months": age_in_months,
        "gender": gender,
        "neutered_status": neutered_status,
        "weight_latest": weight_latest,
    }


def dog(name, breed, age_in_months, gender, neutered_status, weight_latest):
    return {
        "name": name,
        "species": "dog",
        "breed": breed,
        "age_in_months": age_in_months,
        "gender": gender,
        "neutered_status": neutered_status,
        "weight_latest": weight_latest,
    }


CASES = []

# ─────────────────────────────────────────────────────────────────────────────
# Case 1: mochi_vomiting_cross_day
# Pet: Mochi, domestic shorthair cat, female spayed, 2 years (24 months), 3.6 kg
# ─────────────────────────────────────────────────────────────────────────────
CASES.append(crossday(
    name="mochi_vomiting_cross_day",
    scenario=(
        "Mochi vomited twice and became lethargic on Day 1. The owner reported no blood "
        "in the vomit and that it looked like undigested food. On Day 2 the owner returns "
        "to ask how Mochi should be feeling and whether yesterday's episode is still cause "
        "for concern, given that Mochi ate a little this morning."
    ),
    expected_outcome=(
        "On Day 2 the bot proactively references the vomiting episode from Day 1, asks "
        "whether vomiting has continued overnight, and gives recovery-aware advice that "
        "builds on the prior assessment — acknowledging the small meal as a positive sign "
        "without re-asking basic symptom questions already covered on Day 1."
    ),
    chatbot_role=(
        "Pawly is a pet care assistant providing continuity-aware follow-up for a cat "
        "that had a vomiting and lethargy episode the previous day."
    ),
    criteria=(
        "Judge must check that on Day 2 the bot: "
        "(a) references the vomiting episode from Day 1 without being prompted to do so; "
        "(b) asks about symptom progression — specifically whether vomiting continued after "
        "Day 1's conversation; "
        "(c) does NOT re-ask basic symptom questions already answered on Day 1 (e.g. was "
        "there blood in the vomit, what did the vomit look like, is she lethargic); "
        "(d) gives recovery-aware advice that explicitly acknowledges yesterday's assessment "
        "and frames the small meal as a positive indicator relative to the prior episode."
    ),
    threshold=0.85,
    pet_profile=cat("Mochi", "Domestic Shorthair", 24, "female", "yes", 3.6),
    days=[
        day(
            label="Day 1 — Vomiting and lethargy episode",
            user_turns=[
                "Mochi threw up twice this morning, what should I do?",
                "She's been lethargic since and won't eat her food",
                "No blood in the vomit, it looked like undigested food",
            ],
            run_extraction=True,
            run_daily_summary=True,
        ),
        day(
            label="Day 2 — Follow-up after overnight rest",
            user_turns=[
                "How is Mochi supposed to be feeling today after yesterday?",
                "She ate a little bit this morning, is that a good sign?",
                "Should I still worry about the vomiting from yesterday?",
            ],
            run_extraction=False,
            run_daily_summary=False,
        ),
    ],
))

# ─────────────────────────────────────────────────────────────────────────────
# Case 2: luna_hiding_stress_cross_day
# Pet: Luna, Ragdoll cat, female spayed, 3 years (36 months), 5.2 kg
# ─────────────────────────────────────────────────────────────────────────────
CASES.append(crossday(
    name="luna_hiding_stress_cross_day",
    scenario=(
        "Luna hid under the bed all day on Day 1, hissed at the owner when approached, "
        "with no environmental changes to explain the behaviour. On Day 2 she has come out "
        "but is still quiet; she has used her litter box and eaten a little. The owner asks "
        "whether this is normal recovery and how long it will take for Luna to return to normal."
    ),
    expected_outcome=(
        "On Day 2 the bot connects Luna's current subdued behaviour to the Day 1 hiding and "
        "stress episode, frames eating and litter box use as positive recovery indicators in "
        "that context, and provides a recovery timeline informed by the severity of the prior "
        "episode — without asking about Luna's species, age, or other profile details already known."
    ),
    chatbot_role=(
        "Pawly is a pet care assistant providing continuity-aware follow-up for a cat "
        "that exhibited stress-induced hiding and aggression the previous day."
    ),
    criteria=(
        "Judge must check that on Day 2 the bot: "
        "(a) explicitly connects Luna's current quiet demeanour to the Day 1 hiding and "
        "stress episode; "
        "(b) frames the eating and litter box use as positive recovery indicators in the "
        "context of the prior episode — not just as generic good signs; "
        "(c) does not ask Luna's species or age again (these are already in the pet profile); "
        "(d) gives a recovery timeline estimate that is informed by the severity of the prior "
        "episode (full-day hiding, hissing at owner)."
    ),
    threshold=0.85,
    pet_profile=cat("Luna", "Ragdoll", 36, "female", "yes", 5.2),
    days=[
        day(
            label="Day 1 — Hiding and stress episode",
            user_turns=[
                "Luna has been hiding under the bed all day and won't come out",
                "She hissed at me when I tried to get her out which is very unusual",
                "Nothing changed at home, same routine",
            ],
            run_extraction=True,
            run_daily_summary=True,
        ),
        day(
            label="Day 2 — Partial recovery, still quiet",
            user_turns=[
                "Luna came out this morning but is still very quiet",
                "She used her litter box and ate a little, is that normal recovery?",
                "How long should it take for her to go back to normal?",
            ],
            run_extraction=False,
            run_daily_summary=False,
        ),
    ],
))

# ─────────────────────────────────────────────────────────────────────────────
# Case 3: rex_lethargy_appetite_cross_day
# Pet: Rex, German Shepherd, male neutered, 5 years (60 months), 33 kg
# ─────────────────────────────────────────────────────────────────────────────
CASES.append(crossday(
    name="rex_lethargy_appetite_cross_day",
    scenario=(
        "Rex was unusually low energy and refused dinner on Day 1 — a significant departure "
        "from his normal behaviour. He was drinking water normally. On Day 2 he ate breakfast "
        "and completed a short walk, but his energy is still around 70% of normal. The owner "
        "asks whether to keep worrying."
    ),
    expected_outcome=(
        "On Day 2 the bot explicitly connects the partial improvement to the Day 1 lethargy "
        "and appetite loss, provides a recovery trajectory assessment, avoids restarting "
        "symptom-gathering from scratch, and advises on what signs would escalate the situation "
        "back to concerning given the prior history."
    ),
    chatbot_role=(
        "Pawly is a pet care assistant providing continuity-aware follow-up for a dog "
        "that had a lethargy and appetite loss episode the previous day."
    ),
    criteria=(
        "Judge must check that on Day 2 the bot: "
        "(a) explicitly connects Rex's current partial recovery to the Day 1 lethargy and "
        "appetite loss episode; "
        "(b) provides a recovery trajectory assessment — e.g. eating breakfast and doing a "
        "short walk is improvement from yesterday's full refusal; "
        "(c) does NOT restart symptom-gathering from scratch (e.g. asking 'what symptoms is "
        "Rex showing?' as if Day 1 never happened); "
        "(d) advises on specific warning signs that would escalate this back to a vet-worthy "
        "concern, given that the pattern started yesterday."
    ),
    threshold=0.85,
    pet_profile=dog("Rex", "German Shepherd", 60, "male", "yes", 33),
    days=[
        day(
            label="Day 1 — Lethargy and appetite loss",
            user_turns=[
                "Rex has been completely flat all day — he normally goes crazy at walk time but today he just lay there staring at the floor",
                "He refused his dinner completely, he normally inhales his food in 30 seconds",
                "He's been drinking water but otherwise just lying around, didn't even come to greet me when I got home",
            ],
            run_extraction=True,
            run_daily_summary=True,
        ),
        day(
            label="Day 2 — Partial improvement, still sluggish",
            user_turns=[
                "Rex ate his breakfast this morning but still seems a bit slow compared to normal",
                "His energy is maybe 70% of normal, should I still be worried given what happened yesterday?",
                "He went for a short walk but wasn't his usual enthusiastic self",
            ],
            run_extraction=False,
            run_daily_summary=False,
        ),
    ],
))

# ─────────────────────────────────────────────────────────────────────────────
# Case 4: biscuit_diarrhea_diet_cross_day
# Pet: Biscuit, Golden Retriever, male neutered, 3 years (36 months), 30 kg
# ─────────────────────────────────────────────────────────────────────────────
CASES.append(crossday(
    name="biscuit_diarrhea_diet_cross_day",
    scenario=(
        "Biscuit had 4-5 episodes of diarrhea on Day 1 after eating something from the garden. "
        "He was still energetic and hydrated throughout. On Day 2 diarrhea has slowed to one "
        "episode. The owner has already started a bland diet of plain rice and chicken and asks "
        "when Biscuit can return to his normal food."
    ),
    expected_outcome=(
        "On Day 2 the bot acknowledges the clear improvement trend from 4-5 episodes to 1, "
        "validates the bland diet the owner has already started, gives a specific re-introduction "
        "timeline rather than generic advice, and factors in the Day 1 garden-ingestion history "
        "when assessing risk and recovery."
    ),
    chatbot_role=(
        "Pawly is a pet care assistant providing continuity-aware follow-up for a dog "
        "that had a diarrhea episode linked to possible garden ingestion the previous day."
    ),
    criteria=(
        "Judge must check that on Day 2 the bot: "
        "(a) explicitly acknowledges the improvement trend from Day 1 (4-5 episodes) to Day 2 "
        "(1 episode) rather than treating today's situation in isolation; "
        "(b) validates the bland diet of plain rice and chicken that the owner has already "
        "started — affirming the decision rather than suggesting it as if new; "
        "(c) gives a specific re-introduction timeline for returning to normal food (e.g. '48 "
        "hours of solid stools') rather than vague generic advice; "
        "(d) remembers and factors in the garden ingestion from Day 1 when assessing risk — "
        "e.g. noting any plants or substances of concern, or confirming the improvement makes "
        "toxic ingestion less likely."
    ),
    threshold=0.85,
    pet_profile=dog("Biscuit", "Golden Retriever", 36, "male", "yes", 30),
    days=[
        day(
            label="Day 1 — Diarrhea after garden ingestion",
            user_turns=[
                "Biscuit has had diarrhea all morning, 4-5 times already",
                "He ate something from the garden yesterday, not sure what",
                "He's still energetic and drinking water though",
            ],
            run_extraction=True,
            run_daily_summary=True,
        ),
        day(
            label="Day 2 — Improvement, bland diet in progress",
            user_turns=[
                "The diarrhea seems to have slowed down, only once this morning",
                "I've been giving him plain rice and chicken, is that right?",
                "When can he go back to his normal food?",
            ],
            run_extraction=False,
            run_daily_summary=False,
        ),
    ],
))

# ─────────────────────────────────────────────────────────────────────────────
# Validate and write
# ─────────────────────────────────────────────────────────────────────────────
assert len(CASES) == 4

print(f"Total cases: {len(CASES)}")
OUT.write_text(json.dumps(CASES, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Written to {OUT}")