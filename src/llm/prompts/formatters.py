"""
Response formatters — apply Figma visual style to LLM output.

The LLM writes plain content (explanation, questions). Python wraps it
with the correct visual chrome based on the resolved triage level.

Output uses Telegram HTML parse mode (<b>, <i>, etc.).

Public API:
    apply_response_format(text, triage) -> str
    build_safety_banner(matched_rules) -> str
    prepend_safety_banner(text, matched_rules) -> str
"""

import html
import re

from src.db.models import TriageLevel


# Human-readable labels for rule-engine matches. The banner concatenates
# the labels of the rules that fired so the user understands which signal
# escalated the conversation to RED. Anything not in this map is rendered
# as the raw rule name with prefixes stripped (a graceful fallback rather
# than a hard error — new rules just need their entry added here).
_RULE_LABELS: dict[str, str] = {
    "red:toxin_ingestion": "suspected toxin ingestion",
    "red:toxin_poisoned": "possible poisoning",
    "red:respiratory_distress": "difficulty breathing",
    "red:gasping": "gasping for breath",
    "red:labored_breathing": "labored breathing",
    "red:cyanosis": "blue or pale gums",
    "red:seizure_active": "active seizure",
    "red:seizure_now": "seizure happening now",
    "red:convulsion": "convulsion",
    "red:collapsed": "collapse",
    "red:unconscious": "unresponsive",
    "red:heavy_bleeding": "heavy bleeding",
    "red:bleeding_wont_stop": "bleeding that won't stop",
    "red:hematemesis": "vomiting blood",
    "red:blood_in_urine": "blood in urine",
    "red:hemoptysis_coughing_blood": "coughing blood",
    "red:hit_by_car": "vehicle trauma",
    "red:vehicle_strike": "vehicle trauma",
    "red:bloat_pacing": "possible bloat / GDV",
    "red:non_productive_retching": "non-productive retching (possible GDV)",
    "red:urinary_obstruction": "possible urinary obstruction",
    "red:straining_litter_box": "straining in the litter box",
    "red:paralysis_acute": "acute paralysis",
    "red:dragging_legs": "leg dragging / hind-end weakness",
    "red:cant_stand": "unable to stand or walk",
    "red:heatstroke": "heatstroke",
    "red:overheating_severe": "severe overheating",
    "red:eye_prolapse": "eye prolapse",
    "combo:bloody_diarrhea_lethargy": "bloody diarrhea with lethargy",
    "combo:breathing_plus_other": "breathing difficulty with systemic signs",
    "pet:male_cat_urinary_blockage": "male cat urinary blockage risk",
    "pet:young_animal_anorexia": "young animal not eating",
    "pet:young_animal_acute_gi": "young animal with acute GI signs",
    "pet:brachycephalic_respiratory": "brachycephalic breed with breathing concern",
    "human:crisis": "human crisis / suicidal ideation",
    "human:medical_emergency": "human medical emergency",
}


def _label_for_rule(rule_name: str) -> str:
    if rule_name in _RULE_LABELS:
        return _RULE_LABELS[rule_name]
    # Fallback: strip category prefix, swap underscores for spaces.
    bare = rule_name.split(":", 1)[-1] if ":" in rule_name else rule_name
    return bare.replace("_", " ")


def build_safety_banner(matched_rules: list[str]) -> str:
    """Construct the deterministic safety banner shown when the rule engine
    forces a RED escalation. Returns plain text (no HTML); the visual chrome
    is added later by `apply_response_format`.
    """
    # Skip pure "context:" / "orange:" / "pet:age_escalation" entries — they
    # carry no clinical signal worth surfacing.
    skip_prefixes = ("context:", "orange:")
    skip_exact = {"pet:age_escalation"}
    surfaced = [
        r for r in matched_rules
        if not r.startswith(skip_prefixes) and r not in skip_exact
    ]
    if not surfaced:
        return (
            "Based on what you described, the safety check flagged this as "
            "needing immediate vet attention — please contact an emergency "
            "vet now."
        )
    labels = [_label_for_rule(r) for r in surfaced]
    # Dedupe while preserving order (multiple rules can map to the same label)
    seen: set[str] = set()
    unique_labels = [lbl for lbl in labels if not (lbl in seen or seen.add(lbl))]
    joined = ", ".join(unique_labels)
    return (
        f"Based on what you described ({joined}), this needs immediate "
        f"emergency vet attention — please call ahead and go now."
    )


def prepend_safety_banner(response_text: str, matched_rules: list[str]) -> str:
    """Prepend the deterministic safety banner to an LLM response. Used by
    the orchestrator when the rule engine forces a RED escalation but the
    LLM under-triaged — preserves the LLM's contextual reasoning instead of
    regenerating with a 'CRITICAL OVERRIDE' system prompt."""
    banner = build_safety_banner(matched_rules)
    return f"{banner}\n\n{response_text}".strip()

# Lines the LLM sometimes generates despite being told not to.
# Matched case-insensitively; the whole line is removed before we apply
# our own Python-side formatting chrome.
_LLM_CHROME_PATTERNS: list[re.Pattern] = [
    re.compile(r"^[🚨\*\s]*red\s+flag\s+alert[^\n]*$", re.I | re.M),
    re.compile(r"^[⚠️🏥\*\s]*recommend\s+immediate\s+vet\s+visit[^\n]*$", re.I | re.M),
    re.compile(r"^[🏥\*\s]*please\s+seek\s+immediate\s+vet\s+care[^\n]*$", re.I | re.M),
    re.compile(r"^[🔄🟠\*\s]*care\s+mode[^\n]*$", re.I | re.M),
    re.compile(r"^[🔄\*\s]*switching\s+to[^\n]*$", re.I | re.M),
]


def _strip_llm_chrome(text: str) -> str:
    """Remove header/footer lines the LLM added that Python will re-add."""
    for pattern in _LLM_CHROME_PATTERNS:
        text = pattern.sub("", text)
    # Collapse runs of 3+ newlines left by removed lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _md_bold_to_html(text: str) -> str:
    # Run AFTER html.escape so the inserted tags survive escaping. The LLM
    # often emits Markdown **bold** even though replies render with HTML
    # parse mode; without this users see literal `**` in chat.
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)


def apply_response_format(response_text: str, triage: TriageLevel) -> str:
    """Wrap *response_text* with the visual format matching *triage* level."""
    if triage == TriageLevel.RED:
        return _format_red_flag(response_text)
    if triage == TriageLevel.ORANGE:
        return _format_care_mode(response_text)
    return response_text  # GREEN: pass through as-is


def _format_red_flag(text: str) -> str:
    body = _md_bold_to_html(html.escape(_strip_llm_chrome(text)))
    return (
        # Header row — mimics the red card title bar
        "🚨 <b>RED FLAG ALERT</b>  ·  🔴 <b>URGENT</b>\n\n"
        # Dark inner card — Telegram blockquote renders with a dark accent block
        "<blockquote>"
        "⚠️ <b>Recommend Immediate Vet Visit</b>\n\n"
        f"{body}"
        "</blockquote>\n\n"
        # Footer bar — mimics the bottom pill in Figma
        "⚠️ <i>Please seek immediate vet care first</i>"
    )


def _format_care_mode(text: str) -> str:
    # Care mode replies render as plain content — no transition indicator
    # and no CARE MODE badge. We don't surface the active mode to users.
    return _md_bold_to_html(html.escape(_strip_llm_chrome(text)))
