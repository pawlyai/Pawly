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
