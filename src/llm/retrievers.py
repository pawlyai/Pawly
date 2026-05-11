"""
Keyword-based retrievers for symptom followup KB and special rules.

PR 3: match_followups()  -> populates <retrieved_followups>
PR 4: match_red_flags()  -> populates <special_scenarios>

Pure keyword match (no embeddings/vector store — decision B.5).
"""

import pathlib
from dataclasses import dataclass, field

import yaml

from src.triage.rules_engine import TOXIN_TRIGGER_KEYWORDS

_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
_FOLLOWUPS_YAML = _PROMPTS_DIR / "followups.yaml"
_SPECIAL_RULES_YAML = _PROMPTS_DIR / "special_rules.yaml"

_followups_loaded: list | None = None
_special_rules_loaded: list | None = None


@dataclass
class Followup:
    id: str
    system: str
    keywords_en: list[str]
    keywords_cn: list[str]
    questions: list[str]
    escalation_hint: str


@dataclass
class RedFlag:
    id: str
    triggers_en: list[str]
    triggers_cn: list[str]
    rule_text: str


def _get_followups() -> list[Followup]:
    global _followups_loaded
    if _followups_loaded is None:
        with _FOLLOWUPS_YAML.open("r", encoding="utf-8") as fh:
            raw: list[dict] = yaml.safe_load(fh)
        _followups_loaded = [
            Followup(
                id=entry["id"],
                system=entry.get("system", ""),
                keywords_en=[str(k) for k in entry.get("keywords_en", [])],
                keywords_cn=[str(k) for k in entry.get("keywords_cn", [])],
                questions=entry.get("questions", []),
                escalation_hint=entry.get("escalation_hint", ""),
            )
            for entry in raw
        ]
    return _followups_loaded


def _get_special_rules() -> list[RedFlag]:
    global _special_rules_loaded
    if _special_rules_loaded is None:
        with _SPECIAL_RULES_YAML.open("r", encoding="utf-8") as fh:
            raw: list[dict] = yaml.safe_load(fh)
        entries: list[RedFlag] = []
        for entry in raw:
            triggers_en = [str(t) for t in entry.get("triggers_en", [])]
            if entry.get("uses_rules_engine_keywords"):
                # Single source of truth: use toxin keywords from rules_engine.py.
                triggers_en = list(TOXIN_TRIGGER_KEYWORDS)
            entries.append(RedFlag(
                id=entry["id"],
                triggers_en=triggers_en,
                triggers_cn=[str(t) for t in entry.get("triggers_cn", [])],
                rule_text=entry.get("rule_text", ""),
            ))
        _special_rules_loaded = entries
    return _special_rules_loaded


def match_followups(user_msg: str, top_k: int = 3) -> list[Followup]:
    """
    Keyword match against followups.yaml. Returns top_k entries sorted by
    keyword-hit count (ties broken by yaml file order). Returns [] when no
    keyword fires — caller removes the entire <retrieved_followups> tag.
    """
    lower = user_msg.lower()
    scored: list[tuple[int, int, Followup]] = []
    for idx, entry in enumerate(_get_followups()):
        hits = sum(1 for kw in entry.keywords_en if kw.lower() in lower)
        hits += sum(1 for kw in entry.keywords_cn if kw in user_msg)
        if hits > 0:
            scored.append((hits, idx, entry))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [e for _, _, e in scored[:top_k]]


def match_red_flags(user_msg: str) -> list[RedFlag]:
    """
    Returns matched rule entries when user_msg contains any trigger keyword
    from special_rules.yaml. Returns [] when no match — caller removes the
    <special_scenarios> tag entirely. Multiple hits -> multiple <rule> blocks
    in yaml order.
    """
    lower = user_msg.lower()
    result: list[RedFlag] = []
    for entry in _get_special_rules():
        if any(t.lower() in lower for t in entry.triggers_en):
            result.append(entry)
            continue
        if any(t in user_msg for t in entry.triggers_cn):
            result.append(entry)
    return result


def format_followups(followups: list[Followup]) -> str:
    """Format matched followup entries for injection into <retrieved_followups>."""
    if not followups:
        return ""
    lines: list[str] = []
    for f in followups:
        headline = f"**{f.id.replace('_', ' ').capitalize()}:**"
        questions_str = " ".join(f.questions)
        line = f"{headline} {questions_str}"
        if f.escalation_hint:
            line += f" **{f.escalation_hint}**"
        lines.append(line)
    return "\n".join(lines)


def format_special_rules(red_flags: list[RedFlag]) -> str:
    """Format matched special rule entries for injection into <special_scenarios>."""
    if not red_flags:
        return ""
    parts: list[str] = []
    for rf in red_flags:
        parts.append(f'<rule id="{rf.id}">\n{rf.rule_text.strip()}\n</rule>')
    return "\n".join(parts)


# ── Intent gating for general KB retrieval ──────────────────────────────────
#
# The general KB (src/memory/kb_retrieval.py) covers husbandry / behaviour /
# life-stage / region-specific questions. Calling retrieve_general_kb() on
# *every* message dilutes attention in memory-driven (longitudinal) or
# safety-critical (RED triage) scenarios. We gate it via this heuristic:
# only invoke when the user message looks like a general question, not a
# symptom report, follow-up on prior memory, or crisis topic.

_GENERAL_QUESTION_TOKENS_EN = (
    # explicit question markers
    "how do i", "how can i", "how should i", "how often", "how much",
    "what is", "what's the", "what should", "what kind", "what type",
    "when should", "when can", "when to",
    "why does", "why do", "why is",
    "can i", "can my", "can dogs", "can cats", "is it safe",
    "should i", "should we",
    "best way", "best food", "best time", "best age",
    # care topics
    "litter box", "grooming", "brushing", "bathing", "nail",
    "training", "socialization", "crate", "leash",
    "spay", "neuter", "vaccinat", "deworm", "microchip",
    "exercise", "diet", "feeding", "treat", "kibble",
    # life-stage / breed
    "puppy", "kitten", "senior", "adolescent", "elderly",
    "indoor cat", "outdoor cat", "apartment dog",
    # region / housing
    "hdb", "singapore", "tropical", "humid", "monsoon",
)
_GENERAL_QUESTION_TOKENS_CN = (
    "怎么", "如何", "什么", "为什么", "能不能", "可以吗", "应该", "应不应该",
    "几岁", "几个月", "多大", "多久", "多少",
    "刷牙", "梳毛", "剪甲", "洗澡",
    "训练", "社会化", "笼训",
    "绝育", "节育", "疫苗", "驱虫", "芯片",
    "运动", "饮食", "零食", "粮", "干粮", "湿粮",
    "幼犬", "幼猫", "老年", "高龄",
    "室内猫", "公寓",
    "新加坡", "组屋", "湿热",
)

import re as _re

# Symptom indicators that should EXCLUDE a message from "general husbandry"
# category, regardless of question-word presence. Use word-boundary regex
# to avoid false positives like "ate" matching "watermelon".
_SYMPTOM_RE_EN = _re.compile(
    r"\b(?:"
    r"vomit|vomiting|vomited|"
    r"diarrhea|diarrhoea|"
    r"limp|limping|"
    r"swollen|swelling|"
    r"fever|febrile|"
    r"lethargic|lethargy|"
    r"seizure|seizing|"
    r"collapse|collapsed|unconscious|"
    r"labored|labored breathing|"
    r"poisoned|poisoning"
    r")\b",
    _re.IGNORECASE,
)
_SYMPTOM_PHRASES_EN = (
    _re.compile(r"\bnot\s+eating\b", _re.IGNORECASE),
    _re.compile(r"\bnot\s+drinking\b", _re.IGNORECASE),
    _re.compile(r"\bwon'?t\s+eat\b", _re.IGNORECASE),
    _re.compile(r"\b(?:blue|pale)\s+gum", _re.IGNORECASE),
    _re.compile(r"\bgot\s+into\b", _re.IGNORECASE),
    # "ate X" indicates pet ingested X — only when followed by a likely item
    _re.compile(r"\bate\s+(?:something|some|a|the|my|his|her|chocolate|grape|raisin|onion|garlic|xylitol|gum|the\s+\w+)\b", _re.IGNORECASE),
    _re.compile(r"\bswallowed\b", _re.IGNORECASE),
    # "blood" matters as symptom only with bodily-fluid context, not "bloodhound" etc
    _re.compile(r"\b(?:blood|bleeding)\s+(?:in|from|on|coming)\b", _re.IGNORECASE),
    # "pain" matters as pet symptom, not e.g. "a pain to deal with"
    _re.compile(r"\b(?:in\s+pain|seems?\s+to\s+be\s+in\s+pain|painful)\b", _re.IGNORECASE),
    # "hurt" + leg/paw/etc.
    _re.compile(r"\bhurt\s+(?:his|her|its|their|the)\b", _re.IGNORECASE),
    # toxic/urgent/emergency clearly symptom-zone in pet context
    _re.compile(r"\b(?:toxic|emergency|urgent)\b", _re.IGNORECASE),
)
_SYMPTOM_TOKENS_CN = (
    "呕吐", "拉肚", "便血", "瘸", "腿疼", "脚疼",
    "肿", "发烧", "高烧",
    "没精神", "不吃饭", "不喝水", "癫痫", "倒下", "昏迷",
    "呼吸困难", "误食", "中毒", "出血",
)


def looks_like_general_husbandry_question(user_msg: str) -> bool:
    """True when the message looks like a general husbandry / care / behaviour
    question (the kind general_kb_entry covers), False otherwise.

    Conservative: returns False on symptom reports, crisis topics, or
    memory-driven follow-ups — those should use memory + followups.yaml,
    not get distracted by general husbandry content.
    """
    if not user_msg or not user_msg.strip():
        return False
    lower = user_msg.lower()

    # If any symptom indicator fires, treat as symptom report (not general).
    if _SYMPTOM_RE_EN.search(user_msg):
        return False
    if any(pat.search(user_msg) for pat in _SYMPTOM_PHRASES_EN):
        return False
    if any(tok in user_msg for tok in _SYMPTOM_TOKENS_CN):
        return False

    # Positive match on general-question tokens.
    if any(tok in lower for tok in _GENERAL_QUESTION_TOKENS_EN):
        return True
    if any(tok in user_msg for tok in _GENERAL_QUESTION_TOKENS_CN):
        return True

    # Default: not a general question. (Long-tail conservative — better to
    # miss a few real general questions than dilute every message.)
    return False
