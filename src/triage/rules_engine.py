"""
Pattern-based triage rules engine (v2).

Replaces the v1 substring-keyword engine. Key changes:

* Patterns are regex with word boundaries — `blood\\b` no longer matches
  `bloodwork`. Active-event markers required for toxin / trauma rules so
  educational questions ("is xylitol toxic?") don't escalate.
* Negation / past-tense / hypothetical / owner-self cues suppress signals
  that would otherwise fire — "no blood in stool", "had a seizure 3 years
  ago", "what if my dog has a seizure", "I had a panic attack".
* Each signal carries a weight; the final classification comes from a
  scored sum, not the first matching keyword. RED requires a high-weight
  signal or a deliberate combination.
* Pet-specific bumps live alongside text patterns — male cat + urinary
  signal, brachycephalic breed + respiratory, young animal + acute GI.

Public API (unchanged so callers keep working):
    classify_by_rules(pet, description)        -> TriageRuleResult
    detect_triage_from_response(text)          -> TriageLevel | None  (audit-only)
    compare_and_resolve(llm, rule)             -> CompareResult
    classify_triage(text)                      -> "RED" | "ORANGE" | "GREEN"
    get_matched_symptoms(text)                 -> list[str]
    TOXIN_TRIGGER_KEYWORDS                     -> list[str]  (consumed by retrievers.py)

Backward-compat aliases:
    RuleClassificationResult = TriageRuleResult
    ResolveResult            = CompareResult

Adding a new pattern is one line in the relevant section below. Adding a new
false-positive class is one line in tests/triage/test_golden_cases.py.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from src.db.models import Gender, LifeStage, Pet, Species, TriageLevel

# ══════════════════════════════════════════════════════════════════════════════
# Result types (kept stable for callers)
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class TriageRuleResult:
    """Result of classify_by_rules()."""

    classification: TriageLevel
    matched_rules: list[str] = field(default_factory=list)
    confidence: float = 0.5
    score: float = 0.0  # sum of signal weights after suppression

    @property
    def matched_patterns(self) -> list[str]:
        return self.matched_rules


@dataclass
class CompareResult:
    """Result of compare_and_resolve()."""

    final_classification: TriageLevel
    overridden: bool
    override_direction: str = ""  # "" | "rules_stricter" | "llm_stricter"


# Backward-compat aliases
RuleClassificationResult = TriageRuleResult
ResolveResult = CompareResult


# ══════════════════════════════════════════════════════════════════════════════
# Suppression cues — these zero out otherwise-matching signals
# ══════════════════════════════════════════════════════════════════════════════

# A signal is suppressed if any suppression pattern matches the description.
# Past-tense and hypothetical apply globally; owner-self is for cases where
# the owner is describing their own state ("I had a panic attack") rather
# than the pet's.

_PAST_TENSE_CUES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d+\s+(year|month|week|day)s?\s+ago\b"),
    re.compile(r"\b(used to|in the past|previously|years? back|months? back)\b"),
    # "seizure-free since 2020", "symptom-free since the surgery" — only fires
    # when an explicit *X-free since* phrasing is present, otherwise
    # "has been vomiting since morning" would be suppressed too.
    re.compile(r"\b\w+-free since\b", re.IGNORECASE),
    re.compile(r"\bsince (then|last|that)\b"),
    re.compile(r"\b(history of (a |an )?(seizure|surgery|illness|condition))\b"),
)

_HYPOTHETICAL_CUES: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*what if\b", re.IGNORECASE),
    re.compile(r"\bif (my|the) .{0,30}\b(ever|one day|someday|in the future)\b"),
    re.compile(r"\bhypothetical(ly)?\b"),
    re.compile(r"\bsuppose(d)? (he|she|my|the)\b"),
    re.compile(r"\bjust curious\b"),
    re.compile(r"\bin case\b"),
)

_OWNER_SELF_CUES: tuple[re.Pattern[str], ...] = (
    # Pet description rarely starts with "I had/have/am" — those are about the owner.
    re.compile(r"^\s*i\s+(had|have|'?ve had|am|was|feel)\b", re.IGNORECASE),
    re.compile(r"\bmy (own|therapist|doctor|psychiatrist)\b", re.IGNORECASE),
    re.compile(r"\bi'?m (anxious|grieving|depressed|stressed|panicking|sad)\b", re.IGNORECASE),
    re.compile(r"\bi had (a |an )?(panic|anxiety) attack\b", re.IGNORECASE),
    re.compile(r"\bi'?ve been (struggling|grieving|crying|depressed)\b", re.IGNORECASE),
)

# Negation cues that suppress a matching signal when they appear within
# NEGATION_WINDOW characters before the match. Tighter than a sentence-wide
# scan so "she didn't have a seizure, just twitched" suppresses the seizure
# signal but "had no symptoms today, but yesterday she had a seizure" does not.
NEGATION_WINDOW = 25
_NEGATION_PATTERN = re.compile(
    r"\b(no|not|never|didn'?t|hasn'?t|isn'?t|wasn'?t|haven'?t|doesn'?t|don'?t|without)\b",
    re.IGNORECASE,
)


def _is_past_tense(text: str) -> bool:
    return any(p.search(text) for p in _PAST_TENSE_CUES)


def _is_hypothetical(text: str) -> bool:
    return any(p.search(text) for p in _HYPOTHETICAL_CUES)


def _is_about_owner_not_pet(text: str) -> bool:
    return any(p.search(text) for p in _OWNER_SELF_CUES)


def _is_negated(text: str, match: re.Match[str]) -> bool:
    """Return True iff a negation cue appears within NEGATION_WINDOW chars
    before *match*."""
    window_start = max(0, match.start() - NEGATION_WINDOW)
    window = text[window_start : match.start()]
    return bool(_NEGATION_PATTERN.search(window))


# ══════════════════════════════════════════════════════════════════════════════
# Signal definitions
# ══════════════════════════════════════════════════════════════════════════════
#
# Each signal is (name, regex, weight). The classifier scans every signal,
# applies the suppression cues, sums weights, and maps to a triage level.
#
# Weight scale:
#   0.8+   → single match is enough for RED
#   0.5    → ORANGE on its own, combos may push to RED
#   0.3    → ORANGE contributor (needs companion to RED)


# Toxin / poisoning — require an active ingestion verb to avoid matching
# educational phrasings like "is xylitol toxic?".
_TOXIC_SUBSTANCES = (
    r"(?:chocolate|xylitol|grape[s]?|raisin[s]?|onion[s]?|garlic|lily|lilies|"
    r"antifreeze|rat poison|rodenticide|ibuprofen|tylenol|acetaminophen|"
    r"adhd (?:medication|pill)s?|antidepressants?|marijuana|cannabis|thc|"
    r"mouse bait|slug bait|snail bait)"
)
_INGESTION_VERBS = r"(?:ate|swallowed|consumed|ingested|got into|just had|"
_INGESTION_VERBS += r"chewed (?:up |on )?|licked up|drank)"

RED_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    # Toxin ingestion (must be active event)
    ("toxin_ingestion",
     re.compile(rf"\b{_INGESTION_VERBS}\b[\s\S]{{0,40}}?\b{_TOXIC_SUBSTANCES}\b", re.IGNORECASE),
     0.8),
    ("toxin_poisoned",
     re.compile(r"\b(?:got |is |may be |might be )?poisoned\b", re.IGNORECASE),
     0.7),

    # Acute respiratory
    ("respiratory_distress",
     re.compile(r"\b(?:can'?t|cannot|unable to|stopped) (?:breathe|breathing)\b", re.IGNORECASE),
     0.8),
    ("gasping",
     re.compile(r"\bgasping(?: for (?:air|breath))?\b", re.IGNORECASE),
     0.8),
    ("labored_breathing",
     re.compile(r"\b(?:labored|laboured|struggling) (?:to )?breath(?:e|ing)\b", re.IGNORECASE),
     0.7),
    ("cyanosis",
     re.compile(r"\b(?:blue|pale|white|grey|gray) (?:gums?|tongue)\b", re.IGNORECASE),
     0.8),

    # Seizure (active) — past/hypothetical/negation handled by suppression layer
    ("seizure_active",
     re.compile(r"\b(?:having|is having|just had) (?:a |an )?seizure\b", re.IGNORECASE),
     0.8),
    ("seizure_now",
     re.compile(r"\bseizure (?:right now|currently|happening)\b", re.IGNORECASE),
     0.8),
    ("convulsion",
     re.compile(r"\b(?:convulsing|convulsion[s]?|fitting|shaking uncontrollably)\b", re.IGNORECASE),
     0.7),

    # Collapse / unresponsive
    ("collapsed",
     re.compile(r"\b(?:just |suddenly |has )?collapsed\b", re.IGNORECASE),
     0.7),
    ("unconscious",
     re.compile(r"\b(?:unconscious|not responding|won'?t wake|wont wake|"
                r"unresponsive)\b(?! to (?:training|recall|name|treats|commands))",
                re.IGNORECASE),
     0.7),

    # Hemorrhage
    ("heavy_bleeding",
     re.compile(r"\bheavy bleeding\b", re.IGNORECASE),
     0.8),
    ("bleeding_wont_stop",
     re.compile(r"\b(?:won'?t|wont|can'?t) stop bleeding\b", re.IGNORECASE),
     0.8),
    ("hematemesis",
     re.compile(r"\b(?:vomiting|throwing up|coughing up) blood\b", re.IGNORECASE),
     0.8),
    ("blood_in_urine",
     re.compile(r"\bblood in (?:the )?(?:urine|pee)\b", re.IGNORECASE),
     0.7),
    ("hemoptysis_coughing_blood",
     re.compile(r"\bcoughing (?:up )?blood\b", re.IGNORECASE),
     0.8),

    # Trauma
    ("hit_by_car",
     re.compile(r"\bhit by (?:a )?car\b", re.IGNORECASE),
     0.8),
    ("vehicle_strike",
     re.compile(r"\b(?:struck|run over) by (?:a )?(?:car|vehicle|bike|truck)\b", re.IGNORECASE),
     0.8),

    # GDV / bloat (dog emergency)
    ("bloat_pacing",
     re.compile(r"\b(?:bloated|distended|swollen) (?:stomach|abdomen|belly)\b", re.IGNORECASE),
     0.7),
    ("non_productive_retching",
     re.compile(r"\b(?:retching|trying to vomit)\b.{0,40}\bnothing(?:'s| is)? coming(?: up)?\b",
                re.IGNORECASE),
     0.8),

    # Urinary blockage (often paired with pet-specific bump for male cats)
    ("urinary_obstruction",
     re.compile(r"\b(?:can'?t|cannot|unable to|hasn'?t|hasnt) (?:pee|urinate|"
                r"go|empty(?:ing)? (?:his|her|the) bladder)\b",
                re.IGNORECASE),
     0.6),
    ("straining_litter_box",
     re.compile(r"\bstraining (?:in the )?(?:litter box|to (?:pee|urinate))\b", re.IGNORECASE),
     0.5),

    # Acute neurological — paralysis with body part
    ("paralysis_acute",
     re.compile(r"\bparalyz(?:ed|ation) (?:in|on|with)?\s*(?:the |his |her )?"
                r"(?:back|hind|front|all four|both)\s*(?:legs?|paws?|limbs?)\b",
                re.IGNORECASE),
     0.7),
    ("dragging_legs",
     re.compile(r"\b(?:dragging (?:his|her|the) (?:legs?|hind quarters)|"
                r"hind legs? not working)\b",
                re.IGNORECASE),
     0.7),
    ("cant_stand",
     re.compile(r"\b(?:can'?t|cannot|unable to) (?:stand|walk|get up)\b", re.IGNORECASE),
     0.6),

    # Heatstroke
    ("heatstroke",
     re.compile(r"\bheat ?(?:stroke|exhaustion)\b", re.IGNORECASE),
     0.8),
    ("overheating_severe",
     re.compile(r"\boverheat(?:ed|ing) (?:and|with) (?:panting|drooling|collapsed|weak)\b",
                re.IGNORECASE),
     0.7),

    # Severe eye trauma
    ("eye_prolapse",
     re.compile(r"\b(?:eye (?:popping|popped) out|prolapse(?:d eye)?)\b", re.IGNORECASE),
     0.8),
]


# ORANGE signals — concerning but not life-threatening. Combinations can push
# the total score over the RED threshold.
ORANGE_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    ("vomiting",
     re.compile(r"\b(?:vomiting|threw up|throwing up|emesis|puked|puking)\b", re.IGNORECASE),
     0.5),
    ("diarrhea",
     re.compile(r"\b(?:diarrhea|diarrhoea|loose stool|watery stool|soft stool)\b", re.IGNORECASE),
     0.5),
    ("anorexia",
     re.compile(r"\b(?:won'?t eat|wont eat|not eating|off (?:his|her|the) food|"
                r"refusing food|anorexic|anorexia|no appetite)\b",
                re.IGNORECASE),
     0.5),
    ("lethargy",
     re.compile(r"\b(?:lethargic|lethargy|sleeping all day|no energy|very tired|"
                r"unusually tired|not (?:himself|herself)|lying around)\b",
                re.IGNORECASE),
     0.5),
    ("limping",
     re.compile(r"\b(?:limping|limps|favouring|favoring (?:a |his |her )?(?:leg|paw))\b",
                re.IGNORECASE),
     0.4),
    ("rapid_breathing",
     # ORANGE on its own; pet-specific brachycephalic combo will push to RED
     # when the breed is on the brachy list.
     re.compile(r"\b(?:panting hard|panting heavily|breathing fast|rapid breathing|"
                r"breathing rapidly|heavy panting)\b",
                re.IGNORECASE),
     0.4),
    ("scratching_excessive",
     re.compile(r"\bscratching (?:a lot|excessively|constantly|all the time|"
                r"at (?:her|his|the) (?:ears?|face|skin))\b",
                re.IGNORECASE),
     0.4),
    ("hair_loss",
     re.compile(r"\b(?:hair loss|bald (?:patch|spot)|losing hair|patchy fur)\b", re.IGNORECASE),
     0.4),
    ("lump",
     re.compile(r"\bnew (?:lump|mass|growth|bump)\b", re.IGNORECASE),
     0.4),
    ("sneezing_persistent",
     re.compile(r"\b(?:sneezing (?:a lot|for|constant|repeatedly)|"
                r"constant sneezing|persistent sneezing)\b",
                re.IGNORECASE),
     0.4),
    ("cough",
     re.compile(r"\b(?:coughing|persistent cough|honking cough)\b", re.IGNORECASE),
     0.4),
    ("eye_discharge",
     re.compile(r"\b(?:eye discharge|runny eyes|gunky eyes|discharge from (?:the )?eyes?)\b",
                re.IGNORECASE),
     0.4),
    ("nose_discharge",
     re.compile(r"\b(?:runny nose|nasal discharge)\b", re.IGNORECASE),
     0.3),
    ("polydipsia",
     re.compile(r"\b(?:drinking (?:way )?more|increased thirst|excessive (?:drinking|thirst))\b",
                re.IGNORECASE),
     0.4),
    ("polyuria",
     re.compile(r"\b(?:peeing (?:way )?more|urinating more|frequent urination)\b", re.IGNORECASE),
     0.4),
    ("weight_change",
     re.compile(r"\b(?:weight loss|weight gain|losing weight|gaining weight)\b", re.IGNORECASE),
     0.4),
]


# Composite triggers — boolean flags from the orange/red signals plus
# additional cues used in combination rules below. Each flag is True when
# its pattern matches AND no suppression cue (negation/past/hypothetical)
# applies at that match site.
def _flag(text: str, pattern: re.Pattern[str]) -> bool:
    for m in pattern.finditer(text):
        if not _is_negated(text, m):
            return True
    return False


_HAS_VOMIT = re.compile(r"\b(?:vomit(?:ing)?|threw up|throwing up|puked)\b", re.IGNORECASE)
_HAS_DIARRHEA = re.compile(r"\b(?:diarrhea|diarrhoea|loose stool|watery stool)\b", re.IGNORECASE)
_HAS_BLOOD = re.compile(
    # blood/bloody/bleeding but NOT "blood test", "bloodwork", "blood line"
    r"\b(?:blood|bloody|bleeding)\b(?!\s*(?:test|work|line|panel|draw|result))",
    re.IGNORECASE,
)
_HAS_LETHARGY = re.compile(
    r"\b(?:lethargic|lethargy|sleeping all day|no energy|very tired|"
    r"unusually tired|not (?:himself|herself))\b",
    re.IGNORECASE,
)
_HAS_BREATHING_DIFFICULTY = re.compile(
    r"\b(?:can'?t breathe|gasping|labored breathing|laboured breathing|"
    r"struggling to breathe|panting hard|breathing fast|rapid breathing)\b",
    re.IGNORECASE,
)
_HAS_NOT_EATING = re.compile(
    r"\b(?:won'?t eat|wont eat|not eating|off (?:his|her|the) food|"
    r"refusing food|anorexic|anorexia|no appetite)\b",
    re.IGNORECASE,
)
_HAS_URINARY_DIFFICULTY = re.compile(
    r"\b(?:straining (?:in (?:the )?litter|to (?:pee|urinate))|"
    r"can'?t pee|hasn'?t peed|hasnt peed|"
    r"litter box (?:more|trips)|in (?:the )?litter box (?:more often|all (?:the )?time))\b",
    re.IGNORECASE,
)


# Brachycephalic breeds — known to deteriorate fast with respiratory signs.
_BRACHYCEPHALIC_BREEDS = {
    "french bulldog", "frenchie", "english bulldog", "bulldog",
    "pug", "boston terrier", "boxer", "shih tzu", "pekingese",
    "cavalier king charles spaniel", "cavalier", "persian", "himalayan",
    "exotic shorthair", "british shorthair", "scottish fold",
}


def _is_brachycephalic(pet: Optional[Pet]) -> bool:
    if pet is None or not getattr(pet, "breed", None):
        return False
    return pet.breed.lower() in _BRACHYCEPHALIC_BREEDS


def _post_exercise_context(text: str) -> bool:
    return bool(re.search(
        r"\b(?:after (?:a |the )?(?:walk|run|hike|playtime|fetch|exercise)|"
        r"post[- ]exercise|when (?:he|she|they) plays?)\b",
        text,
        re.IGNORECASE,
    ))


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════
#
# Thresholds:
#   score >= 0.70 → RED
#   0.30 <= score < 0.70 → ORANGE
#   score < 0.30 → GREEN
#
# Tuned so a single high-weight signal (RED pattern, 0.7+) → RED, while two
# ORANGE signals (0.4 + 0.5 = 0.9) → RED only after a deliberate combo bump.

RED_THRESHOLD = 0.70
ORANGE_THRESHOLD = 0.30
# Cap on stacked ORANGE-pattern contribution. Without this, three ORANGE
# signals (vomit 0.5 + lethargy 0.5 + anorexia 0.5 = 1.5) would push the
# total past the RED threshold even though each one is individually
# ORANGE-grade. RED requires either a dedicated RED pattern, a documented
# combination trigger, or a pet-specific bump — never just an accumulation
# of routine ORANGE signals.
ORANGE_CONTRIBUTION_CAP = 0.50


def classify_by_rules(pet: Optional[Pet], description: str) -> TriageRuleResult:
    """Classify *description* with pattern matching + multi-signal scoring.

    Suppression cues (past tense, hypothetical, owner-self) zero the score
    early so educational and reflective phrasings don't escalate. Pet-aware
    rules add weight when the species / breed / life stage materially changes
    the urgency of an otherwise ORANGE pattern.

    Returns the same TriageRuleResult shape as v1 (with the addition of a
    `score` field) so callers don't need to change.
    """
    text = description.strip()

    # Global suppression: descriptions that aren't really about the pet's
    # current state shouldn't produce any signal.
    if _is_about_owner_not_pet(text):
        return TriageRuleResult(TriageLevel.GREEN, [], confidence=0.6, score=0.0)
    if _is_hypothetical(text):
        return TriageRuleResult(TriageLevel.GREEN, [], confidence=0.6, score=0.0)
    if _is_past_tense(text):
        return TriageRuleResult(TriageLevel.GREEN, [], confidence=0.6, score=0.0)

    red_score = 0.0
    orange_score = 0.0
    matched: list[str] = []

    # ── Red signal scan ───────────────────────────────────────────────────────
    for name, pattern, weight in RED_PATTERNS:
        for match in pattern.finditer(text):
            if _is_negated(text, match):
                continue
            red_score += weight
            matched.append(f"red:{name}")
            break  # one hit per signal is enough

    # ── Orange signal scan (capped) ───────────────────────────────────────────
    has_vomit = _flag(text, _HAS_VOMIT)
    has_diarrhea = _flag(text, _HAS_DIARRHEA)
    has_blood = _flag(text, _HAS_BLOOD)
    has_lethargy = _flag(text, _HAS_LETHARGY)
    has_breathing = _flag(text, _HAS_BREATHING_DIFFICULTY)
    has_not_eating = _flag(text, _HAS_NOT_EATING)
    has_urinary = _flag(text, _HAS_URINARY_DIFFICULTY)

    for name, pattern, weight in ORANGE_PATTERNS:
        for match in pattern.finditer(text):
            if _is_negated(text, match):
                continue
            orange_score = min(orange_score + weight, ORANGE_CONTRIBUTION_CAP)
            matched.append(f"orange:{name}")
            break

    score = red_score + orange_score

    # ── Composite RED triggers ────────────────────────────────────────────────
    # Bloody diarrhea + lethargy → likely HGE / parvo → RED
    if has_blood and has_diarrhea and has_lethargy:
        score += 0.6
        matched.append("combo:bloody_diarrhea_lethargy")

    # Breathing difficulty + any GI / lethargy sign → likely systemic → RED
    if has_breathing and (has_vomit or has_diarrhea or has_lethargy or has_not_eating):
        score += 0.4
        matched.append("combo:breathing_plus_other")

    # ── Pet-specific RED triggers ────────────────────────────────────────────
    if pet is not None:
        species = getattr(pet, "species", None)
        gender = getattr(pet, "gender", None)
        stage = getattr(pet, "stage", None)

        # Male cat + urinary signal → emergency blockage risk
        if species == Species.CAT and gender == Gender.MALE and has_urinary:
            score += 0.7
            matched.append("pet:male_cat_urinary_blockage")

        # Puppy / kitten + acute GI → parvo / panleukopenia risk
        # `young_animal_anorexia` is the original name kept for the historical
        # test, applied to the not-eating case; vomit/diarrhea get the
        # broader `young_animal_acute_gi` label.
        if stage in (LifeStage.PUPPY, LifeStage.KITTEN):
            if has_not_eating:
                score += 0.5
                matched.append("pet:young_animal_anorexia")
            elif has_diarrhea or has_vomit:
                score += 0.5
                matched.append("pet:young_animal_acute_gi")

        # Brachycephalic + respiratory → deteriorates fast
        if _is_brachycephalic(pet) and has_breathing:
            # post-exercise panting in a brachy is still urgent, but if the
            # description explicitly anchors it to recent exercise AND there
            # are no other signals, it stays orange-leaning; we still
            # contribute weight here because the body type itself is the risk.
            score += 0.5
            matched.append("pet:brachycephalic_respiratory")

    # ── Non-brachy + benign post-exercise panting → cap at ORANGE ────────────
    # "Labrador panting after a walk" by itself shouldn't escalate.
    if (
        has_breathing
        and _post_exercise_context(text)
        and not _is_brachycephalic(pet)
        and not has_vomit
        and not has_diarrhea
        and not has_lethargy
        and not has_blood
    ):
        # Strip out the breathing signal weight added by ORANGE_PATTERNS
        # ("panting hard" → caught by neither RED nor ORANGE here actually,
        # but the breathing combo could still add). We don't subtract; we
        # explicitly cap by lowering score to ORANGE band.
        if score >= RED_THRESHOLD:
            score = min(score, RED_THRESHOLD - 0.05)
            matched.append("context:post_exercise_panting_cap")

    # ── Map score → triage level ──────────────────────────────────────────────
    if score >= RED_THRESHOLD:
        return TriageRuleResult(TriageLevel.RED, matched, confidence=0.95, score=round(score, 2))
    if score >= ORANGE_THRESHOLD:
        # Vulnerable life stage bumps confidence (not classification)
        is_vulnerable = pet is not None and getattr(pet, "stage", None) in (
            LifeStage.PUPPY, LifeStage.KITTEN, LifeStage.SENIOR,
        )
        if is_vulnerable:
            matched.append("pet:age_escalation")
        return TriageRuleResult(
            TriageLevel.ORANGE,
            matched,
            confidence=0.8 if is_vulnerable else 0.7,
            score=round(score, 2),
        )

    return TriageRuleResult(TriageLevel.GREEN, matched, confidence=0.5, score=round(score, 2))


# ══════════════════════════════════════════════════════════════════════════════
# Audit-only: response-side triage detection (DEPRECATED for decisions)
# ══════════════════════════════════════════════════════════════════════════════
#
# Substring-scans the assistant's reply for urgency keywords. Has no
# negation handling, no past-tense detection, no context awareness, so it
# classifies "this is not urgent" as RED. It must NOT participate in any
# decision (override gating, resolver, visual format) — those callers were
# migrated off this function in the v2 redesign (see git log for the
# fix(triage): commits). The function is preserved purely for telemetry:
# the orchestrator records its output in `triage_result["llm_response_keywords"]`
# so offline analytics can spot the rare cases where the LLM emitted RED-
# coded language in its prose while its structured `triage_level` field
# was something else. That kind of inconsistency is a useful signal for
# prompt tuning, but it must not gate user-visible behaviour.

_RED_RESPONSE_SIGNALS: tuple[str, ...] = (
    "urgent", "emergency", "immediately", "emergency vet", "do not wait",
    "life-threatening", "critical", "rush", "go now", "call the vet now",
)
_ORANGE_RESPONSE_SIGNALS: tuple[str, ...] = (
    "watch closely", "monitor", "keep an eye", "concerning", "see your vet",
    "worth checking", "may want to", "could be", "watch for",
)


def detect_triage_from_response(text: str) -> Optional[TriageLevel]:
    """DEPRECATED for decisions. Audit-only response-side triage classifier.

    Returns the triage level implied by the assistant's wording, based on
    substring matching of urgency keywords. NO negation handling, NO past-
    tense detection, NO context awareness. Do not call this from any code
    path that gates user-visible behaviour — use the LLM's structured
    `triage_level` field (orchestrator / graph) or `classify_by_rules`
    against the user message instead.

    Kept callable so telemetry can record the audit signal for offline
    review. New code should not depend on this function.
    """
    lower = text.lower()
    if any(sig in lower for sig in _RED_RESPONSE_SIGNALS):
        return TriageLevel.RED
    if any(sig in lower for sig in _ORANGE_RESPONSE_SIGNALS):
        return TriageLevel.ORANGE
    return TriageLevel.GREEN


def audit_log_triage_divergence(
    *,
    pet_id: Optional[str],
    structured_triage: Optional[TriageLevel],
    rule_classification: TriageLevel,
    response_keyword_triage: Optional[TriageLevel],
    matched_rules: list[str],
    logger_: Any,
) -> None:
    """Emit a single structured log line when the three triage sources
    disagree in a way that's worth reviewing offline.

    The interesting cases are:
      * structured (LLM JSON) != response_keyword (LLM prose) — the LLM
        said one thing in its triage_level field and wrote prose at a
        different urgency level. Usually a prompt-tuning opportunity.
      * structured == GREEN, response_keyword == RED, rule == GREEN —
        false-positive territory; useful to see which response wording
        flips the audit signal.
      * structured == GREEN, rule == RED — the safety-floor case, banner
        prepended; log to confirm escalation chose the right rules.

    The orchestrator calls this once per turn; the LangGraph variant does
    not currently emit audit logs (kept simple). Pass the `logger`
    instance so the line lands in the right module's namespace.
    """
    def _v(t: Optional[TriageLevel]) -> Optional[str]:
        return t.value if t is not None else None

    structured_val = _v(structured_triage)
    rule_val = _v(rule_classification)
    response_val = _v(response_keyword_triage)

    diverges = (
        (structured_val and response_val and structured_val != response_val)
        or (structured_val and structured_val != rule_val)
    )
    if not diverges:
        return

    logger_.info(
        "triage signals diverge",
        pet_id=pet_id,
        structured=structured_val,
        rule=rule_val,
        response_keywords=response_val,
        matched_rules=matched_rules,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Compare / resolve
# ══════════════════════════════════════════════════════════════════════════════

_SEVERITY: dict[TriageLevel, int] = {
    TriageLevel.GREEN: 0,
    TriageLevel.ORANGE: 1,
    TriageLevel.RED: 2,
}


def compare_and_resolve(
    llm_triage: Optional[TriageLevel],
    rule_classification: TriageLevel,
) -> CompareResult:
    """Combine LLM-inferred triage with the rule-engine result, taking the
    stricter of the two. Annotates the override direction for telemetry."""
    if llm_triage is None:
        return CompareResult(rule_classification, overridden=False, override_direction="")

    llm_sev = _SEVERITY[llm_triage]
    rule_sev = _SEVERITY[rule_classification]

    if llm_sev == rule_sev:
        return CompareResult(llm_triage, overridden=False, override_direction="")
    if rule_sev > llm_sev:
        return CompareResult(rule_classification, overridden=True, override_direction="rules_stricter")
    return CompareResult(llm_triage, overridden=True, override_direction="llm_stricter")


# ══════════════════════════════════════════════════════════════════════════════
# Legacy helpers (kept for callers that haven't migrated)
# ══════════════════════════════════════════════════════════════════════════════

TriageResult = Literal["RED", "ORANGE", "GREEN"]


def classify_triage(text: str) -> TriageResult:
    """Classify text → 'RED' | 'ORANGE' | 'GREEN' (legacy string form)."""
    result = classify_by_rules(None, text)
    return result.classification.value.upper()  # type: ignore[return-value]


def get_matched_symptoms(text: str) -> list[str]:
    """Return matched rule names for *text* (legacy helper)."""
    return classify_by_rules(None, text).matched_rules


# ══════════════════════════════════════════════════════════════════════════════
# Toxin trigger keywords (consumed by retrievers.py for the special-rule
# router). Kept as flat substrings for backward compat — they're used for
# trigger matching only, not for triage classification.
# ══════════════════════════════════════════════════════════════════════════════

TOXIN_TRIGGER_KEYWORDS: list[str] = [
    "ate chocolate", "ate xylitol", "ate lily", "ate antifreeze",
    "ate grape", "ate raisin", "ate onion", "ate garlic",
    "swallowed chocolate", "swallowed xylitol", "got into the chocolate",
    "rat poison", "rodenticide",
    "poisoned", "toxic to dogs", "toxic to cats",
]
