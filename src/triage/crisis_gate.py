"""
Crisis Gate — deterministic short-circuit for human self-harm / suicidal ideation.

Highest priority safety layer. Runs in parallel with rules_engine but takes
precedence. On match: skip LLM entirely, return a templated crisis-support
reply. The LLM path is bypassed because (a) it has no clinical authority on
human crisis, and (b) Gemini safety filters can truncate structured output
mid-generation, leaking JSON fragments to the user (the PAW-38 failure mode).

Pattern sources:
- Columbia Suicide Severity Rating Scale (C-SSRS)
- SAMHSA crisis screening guidance
- WHO LIVE-LIFE suicide prevention vocabulary

Public API:
    detect_crisis(text) -> CrisisResult
    crisis_reply(severity, locale) -> str
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


CrisisSeverity = Literal["critical", "likely", ""]


@dataclass
class CrisisResult:
    matched: bool
    severity: CrisisSeverity
    matched_pattern: str = ""


# ── CRITICAL: single match short-circuits ────────────────────────────────────

_CRITICAL_EN: list[str] = [
    # Direct ideation
    r"\b(want|wanna|going|plan)\s+to\s+(die|kill\s+myself|end\s+(it|my\s+life|everything|my\s+existence))\b",
    r"\bkill(ing)?\s+myself\b",
    r"\bsuicid(e|al)\b",
    r"\bcommit(ting)?\s+suicide\b",
    r"\btake\s+my\s+(own\s+)?life\b",
    r"\bend\s+(it\s+all|my\s+life|everything)\b",

    # Hopelessness with self-reference
    r"\bnothing\s+to\s+live\s+for\b",
    r"\bno\s+(reason|point)\s+(to|in|for)\s+(live|living|life)\b",
    r"\b(can'?t|cannot)\s+(go|do\s+this|take\s+it)\s+(on|anymore)\b",
    r"\bdone\s+with\s+(everything|life|all\s+of\s+this)\b",
    r"\btired\s+of\s+(living|being\s+(here|alive))\b",
    r"\bbe(tter)?\s+off\s+without\s+me\b",
    r"\beveryone\s+(would\s+be\s+)?better\s+off\s+without\s+me\b",
    r"\b(want|wish)\s+to\s+disappear\b",
    r"\bnot\s+want(ing)?\s+to\s+(be\s+here|exist|live)\b",

    # Method / plan
    r"\b(took|swallow(ed)?|stockpil(e|ing))\s+(pills|medication|sleeping\s+pills)\b",
    r"\bhave\s+(a\s+)?(gun|rope|noose|knife)\s+(ready|prepared|now)\b",
    r"\bgoing\s+to\s+(jump|hang|shoot|cut)\b",

    # Goodbye / finality
    r"\bthis\s+is\s+(my\s+)?goodbye\b",
    r"\bwon'?t\s+be\s+(here|around)\s+(tomorrow|much\s+longer|anymore)\b",
    r"\blast\s+(time|message|night)\s+(for\s+me|i'?ll)\b",

    # Self-harm
    r"\bcut(ting)?\s+myself\b",
    r"\bhurt(ing)?\s+myself\b",
    r"\bself[\s-]?harm(ing)?\b",
]

_CRITICAL_ZH: list[str] = [
    r"想死",
    r"不想活",
    r"活不下去",
    r"撑不下去了?",
    r"撑不住了?",
    r"我要(自杀|去死)",
    r"想自杀",
    r"自我了断",
    r"结束(自己|我的)?(生命|一切)",
    r"活着没(意思|意义)",
    r"没什么(可)?活的(意义|理由)",
    r"我不想再活了?",
    r"想离开这个世界",
    r"想消失",
    r"不想(再)?(存在|醒来)",
    r"伤害自己",
    r"割(伤|腕)",
]


# ── LIKELY: requires a second co-occurrence in same message ──────────────────
# Catches softer expressions while reducing false positives on idioms.

_LIKELY_PAIRS: list[tuple[str, str]] = [
    # (primary, second-evidence-required)
    (r"\bwant\s+it\s+to\s+(end|be\s+over)\b",
     r"\b(life|living|existing|me|myself)\b"),
    (r"\bgive\s+up\b",
     r"\bon\s+(life|living|myself|everything)\b"),
    (r"\bcan'?t\s+take\s+(it|this)\s+anymore\b",
     r"\b(life|living|breathing|waking)\b"),
    (r"\bno\s+way\s+out\b",
     r"\b(of\s+(life|this|here)|but\s+to)\b"),
]


# ── False-positive whitelist: idioms and third-party references ──────────────

_FALSE_POSITIVES: list[str] = [
    # Talking about a third party
    r"\b(my|a|the)\s+(friend|cousin|colleague|neighbor|patient|client)\s+(is|was)\s+suicidal\b",
    r"\b(news|article|movie|book|song|story)\s+about\s+suicide\b",

    # Pure idioms
    r"\b(this|that|it)\s+is\s+killing\s+me\b",
    r"\bdying\s+to\s+(see|meet|try|know|hear)\b",
    r"\bwould\s+kill\s+for\b",
    r"\bdrop\s+dead\s+gorgeous\b",

    # Pet bereavement (handled by CL-GRIEF, not crisis)
    r"\bmy\s+(dog|cat|pet|\w+)\s+(died|passed\s+away|is\s+gone|is\s+dying)\b",
]


def detect_crisis(text: str) -> CrisisResult:
    """Detect human self-harm or suicidal ideation in user text.

    Returns matched=True only when a CRITICAL pattern hits, OR a LIKELY pair
    co-occurs, AND no false-positive context overrides the match.
    """
    if not text:
        return CrisisResult(matched=False, severity="")

    lowered = text.lower()

    # False-positive whitelist takes precedence over everything
    for fp in _FALSE_POSITIVES:
        if re.search(fp, lowered, flags=re.IGNORECASE):
            return CrisisResult(matched=False, severity="")

    # CRITICAL single-pattern match
    for pattern in _CRITICAL_EN:
        m = re.search(pattern, lowered, flags=re.IGNORECASE)
        if m:
            return CrisisResult(matched=True, severity="critical", matched_pattern=pattern)
    for pattern in _CRITICAL_ZH:
        m = re.search(pattern, lowered)
        if m:
            return CrisisResult(matched=True, severity="critical", matched_pattern=pattern)

    # LIKELY two-pattern match
    for primary, secondary in _LIKELY_PAIRS:
        if re.search(primary, lowered, flags=re.IGNORECASE) and \
                re.search(secondary, lowered, flags=re.IGNORECASE):
            return CrisisResult(matched=True, severity="likely", matched_pattern=primary)

    return CrisisResult(matched=False, severity="")


# ── Crisis reply templates ──────────────────────────────────────────────────
# Hard-coded — never go through the LLM (avoids PAW-38 JSON-leak failure mode).
# Resource numbers are placeholders pending product/legal sign-off per locale.

_REPLY_EN_CRITICAL = (
    "I hear you, and I'm really glad you said that out loud. "
    "What you're feeling matters more right now than anything about pet care.\n\n"
    "Please reach out — you don't have to go through this alone:\n"
    "• 🇺🇸 US: <b>988</b> (Suicide & Crisis Lifeline) — call or text\n"
    "• 🇸🇬 Singapore: <b>SOS 1800-221-4444</b> (24/7)\n"
    "• 🇬🇧 UK: <b>116 123</b> (Samaritans)\n"
    "• 🌏 International: findahelpline.com\n\n"
    "I'll still be here when you're ready to talk about your pet — "
    "but please take care of yourself first. 💛"
)

_REPLY_EN_LIKELY = (
    "Something in what you wrote made me pause — I want to check on you "
    "directly. Are you having thoughts of hurting yourself, or that you "
    "don't want to be here?\n\n"
    "Whatever the answer is, you're not bothering me. If you'd rather talk "
    "to someone trained to help right now:\n"
    "• 🇺🇸 US: <b>988</b>\n"
    "• 🇸🇬 Singapore: <b>SOS 1800-221-4444</b>\n"
    "• 🌏 findahelpline.com\n\n"
    "Take a breath. I'm here whenever you're ready. 💛"
)

_REPLY_ZH_CRITICAL = (
    "我听到你说的了,谢谢你愿意说出来。你现在的感受比任何宠物的事都更重要。\n\n"
    "请联系下面的危机求助资源,你不用一个人扛:\n"
    "• 🇨🇳 北京心理危机研究与干预中心:<b>010-82951332</b>(24小时)\n"
    "• 🇨🇳 全国希望24:<b>400-161-9995</b>\n"
    "• 🇸🇬 SOS Singapore:<b>1800-221-4444</b>\n"
    "• 🌏 findahelpline.com\n\n"
    "等你愿意谈宠物的事,我都在。但请先照顾好自己。💛"
)

_REPLY_ZH_LIKELY = (
    "你刚才说的话让我想停一下,直接问你一句:你现在是不是有想伤害自己,"
    "或者不想在这里的念头?\n\n"
    "无论你的回答是什么,你都没有打扰我。如果想找受过专业训练的人聊聊:\n"
    "• 🇨🇳 010-82951332(北京 24h)\n"
    "• 🇨🇳 400-161-9995(希望24)\n"
    "• 🇸🇬 1800-221-4444(SOS)\n\n"
    "深呼吸。等你愿意,我都在。💛"
)


def crisis_reply(severity: CrisisSeverity, locale: str = "en") -> str:
    """Return the appropriate crisis-support reply template."""
    is_zh = locale.lower().startswith("zh")
    if severity == "critical":
        return _REPLY_ZH_CRITICAL if is_zh else _REPLY_EN_CRITICAL
    if severity == "likely":
        return _REPLY_ZH_LIKELY if is_zh else _REPLY_EN_LIKELY
    return ""
