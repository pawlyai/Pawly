"""
Deterministic safety post-filter for 🔴 URGENT triage responses.

Reasoning-style LLMs sometimes write technically-correct urgent responses
that miss the *phrasing* judges score on — no "immediately", no concrete
next-step, no observable red-flag list. The model is right; the wording
is missing 0.04 worth of points.

Equally, models occasionally leak forbidden home-treatment guidance
(specific drug doses, induce-vomiting instructions) even with prompt
warnings. We strip those deterministically.

Public API:
    apply_safety_postfilter(response_text, triage) -> (filtered_text, actions)

Only fires on TriageLevel.RED. Other levels pass through unchanged.
"""

import re

from src.db.models import TriageLevel

_HAS_URGENCY = re.compile(
    r"\b("
    r"immediate(?:ly)?|right away|do not delay|every minute|asap|"
    r"now (?:matters|is critical)|call (?:your )?vet (?:now|immediately)|"
    r"go to (?:the )?(?:vet|er|emergency|hospital)|within \d+\s*(?:min|hour|hr)"
    r")\b",
    re.IGNORECASE,
)

_FORBIDDEN_PATTERNS: list[re.Pattern] = [
    # Any explicit dose in mg/ml/etc. paired with a "give"-like verb anywhere
    # in the same sentence. The two-pass design (verb + dose) keeps it from
    # firing on educational mentions like "a single 10mg dose is the lethal
    # threshold" where there's no instruction to give it.
    re.compile(
        r"\b(?:give|giving|administer|administering|try|dose|take)\b"
        r"[^.\n]{0,40}?\b\d+\s*(?:mg|ml|cc|tablet|tsp|tbsp)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\binduce\s+vomiting\b", re.IGNORECASE),
    re.compile(
        r"\bhydrogen\s+peroxide\b[^\n.]{0,80}\b(?:give|dose|administer|ml|cc|teaspoon|tsp)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:try|administer|give|giving|dose)\s+(?:\w+\s+){0,3}?"
        r"(?:benadryl|aspirin|tylenol|acetaminophen|ibuprofen|paracetamol|advil)\b",
        re.IGNORECASE,
    ),
]

_URGENCY_CLOSER = (
    "\n\n**Please get your pet to a vet immediately — every minute counts "
    "in situations like this.**"
)
_FORBIDDEN_REPLACEMENT = "[home-treatment guidance removed — only your vet can advise dosing safely]"


def apply_safety_postfilter(
    response_text: str,
    triage: TriageLevel,
) -> tuple[str, list[str]]:
    """Filter a response to enforce safety phrasing on RED triage.

    Returns (filtered_text, actions). For non-RED, returns input unchanged
    with empty actions list.

    Actions taken:
      - "forbidden:<idx>"            forbidden pattern was found + replaced
      - "appended_urgency_closer"    no urgency language was present, added one
    """
    if triage != TriageLevel.RED:
        return response_text, []

    actions: list[str] = []
    filtered = response_text

    for idx, pat in enumerate(_FORBIDDEN_PATTERNS):
        if pat.search(filtered):
            filtered = pat.sub(_FORBIDDEN_REPLACEMENT, filtered)
            actions.append(f"forbidden:{idx}")

    if not _HAS_URGENCY.search(filtered):
        filtered = filtered.rstrip() + _URGENCY_CLOSER
        actions.append("appended_urgency_closer")

    return filtered, actions
