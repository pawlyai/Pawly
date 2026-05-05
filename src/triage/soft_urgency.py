"""
Soft Urgency Score — embedding-style match against vet-curated phrase bank.

For messages that don't hit the hard rules_engine keyword list but still
"sound" potentially urgent in soft language ("something is wrong", "他不太对劲",
"please help"). Produces a score in [0, 1] used by the merge layer to decide
whether to trigger the ABC Quick Screen.

V0 implementation: keyword-bag scoring (no embedding model dependency).
V1: replace with sentence-transformer embedding + cosine similarity once a
vet has populated the phrase bank with paraphrases.

The phrase bank itself is medical content — it must be curated by a
veterinarian before V1 ships. The placeholders below are seeded from
general distress vocabulary, NOT from any held-out eval data.

Public API:
    soft_urgency_score(text) -> float  # [0, 1]
"""

from __future__ import annotations

import re


# ── Generic distress markers (not condition-specific) ───────────────────────
# These are markers of user concern, NOT clinical signs. Vet review pending.

_DISTRESS_MARKERS_EN: list[str] = [
    r"\bsomething('s|\s+is)\s+(wrong|off|weird)\b",
    r"\bnot\s+(right|himself|herself|themselves|normal)\b",
    r"\bdoesn'?t\s+(look|seem|feel)\s+(right|okay|good|normal)\b",
    r"\bworried\s+about\b",
    r"\bplease\s+help\b",
    r"\bwhat\s+(do\s+i\s+do|should\s+i\s+do)\b",
    r"\bis\s+this\s+(serious|bad|emergency|urgent)\b",
    r"\bi'?m\s+(scared|worried|panicking|freaking\s+out)\b",
    r"\bsuddenly\b",
    r"\bjust\s+(collapsed|fell|stopped|gave\s+out)\b",
    r"\bhe('s|\s+is|\s+was)\s+(weird|funny|off|not\s+okay)\b",
    r"\bshe('s|\s+is|\s+was)\s+(weird|funny|off|not\s+okay)\b",
    r"\bcan\s+you\s+help\b",
    r"\bshould\s+i\s+(go|take|bring)\b.*\bvet\b",
    r"\bemergency\b",
    r"\basap\b",
    r"\bright\s+now\b",
]

_DISTRESS_MARKERS_ZH: list[str] = [
    r"不(太)?对劲",
    r"不(太)?正常",
    r"怪怪的",
    r"出事了",
    r"很担心",
    r"特别担心",
    r"非常担心",
    r"该怎么办",
    r"怎么办",
    r"严重吗",
    r"是不是急诊",
    r"要紧吗",
    r"我有点慌",
    r"我很慌",
    r"突然",
    r"刚才",
    r"刚刚",
    r"快帮帮",
    r"救救",
    r"赶紧",
    r"急",
]

# ── Body-state words that combine with distress to raise score ──────────────

_BODY_STATE_EN: list[str] = [
    r"\b(breathing|breathe|breath)\b",
    r"\b(blood|bleeding)\b",
    r"\b(can'?t|cannot)\s+(stand|walk|move|get\s+up)\b",
    r"\b(unconscious|passed\s+out|fainted|collapsed)\b",
    r"\b(seizure|fit|convulsion|shaking)\b",
    r"\b(swollen|swelling)\b",
    r"\bbelly\s+(big|huge|swollen|hard)\b",
    r"\b(throwing\s+up|vomiting|threw\s+up)\b",
    r"\b(diarrhea|loose\s+stool)\b",
    r"\bate\s+\w+\b",  # "ate something" — toxin signal
]

_BODY_STATE_ZH: list[str] = [
    r"呼吸",
    r"出血",
    r"血",
    r"站不起",
    r"走不动",
    r"动不了",
    r"昏倒",
    r"晕倒",
    r"抽搐",
    r"颤抖",
    r"肿",
    r"肚子(大|胀|硬)",
    r"吐",
    r"拉肚子",
    r"误食",
    r"吃了",
]


def soft_urgency_score(text: str) -> float:
    """Heuristic urgency score in [0, 1] from text alone.

    Score interpretation (used by merge layer):
        < 0.3  → confidently non-urgent, skip ABC
        0.3–0.7 → ambiguous, trigger ABC Quick Screen
        > 0.7  → confidently urgent, trigger ABC immediately

    V0: keyword-bag with weighted combinations.
    V1 (TODO): embedding similarity against vet-curated phrase bank.
    """
    if not text:
        return 0.0

    lowered = text.lower()
    distress_hits = 0
    body_hits = 0

    for pattern in _DISTRESS_MARKERS_EN:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            distress_hits += 1
    for pattern in _DISTRESS_MARKERS_ZH:
        if re.search(pattern, lowered):
            distress_hits += 1
    for pattern in _BODY_STATE_EN:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            body_hits += 1
    for pattern in _BODY_STATE_ZH:
        if re.search(pattern, lowered):
            body_hits += 1

    # Combination boosts: distress + body-state is more urgent than either alone
    base = min(distress_hits * 0.2, 0.5)         # cap distress alone at 0.5
    body_score = min(body_hits * 0.15, 0.4)
    combo_bonus = 0.2 if (distress_hits >= 1 and body_hits >= 1) else 0.0

    return min(base + body_score + combo_bonus, 1.0)


# ── Memory-aware threshold adjustment ───────────────────────────────────────

def adjusted_threshold(
    base_threshold: float,
    pet_has_chronic_condition: bool = False,
    pet_is_juvenile: bool = False,
) -> float:
    """Lower the urgency threshold for vulnerable pets.

    A pet with cardiac disease, diabetes, or seizure history shouldn't need
    to clear the same bar as a healthy pet to trigger ABC. Same for juveniles
    where decompensation is faster.
    """
    threshold = base_threshold
    if pet_has_chronic_condition:
        threshold -= 0.15
    if pet_is_juvenile:
        threshold -= 0.10
    return max(threshold, 0.10)
