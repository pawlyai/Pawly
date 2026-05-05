"""
ABC Quick Screen — vital-signs-first triage clarification.

Clinical pattern: every ER nurse asks Airway / Breathing / Circulation before
specialty assessment. The answers route reliably regardless of underlying
disease, because life-threatening emergencies almost always perturb at least
one of the three.

This module provides:
    1. The standardized ABC question text (EN + ZH)
    2. A deterministic answer parser (no LLM in the loop)
    3. Result interpretation (any-abnormal → escalate; all-normal → continue;
       ambiguous → escalate by asymmetric default)

Triggered by the merge layer when:
    - hard rules / crisis / per-checklist U-triggers all miss
    - LLM scenario classifier is mid-confidence
    - urgency_soft_score is in the ambiguous band (0.3-0.7)

Public API:
    abc_question(locale)                  -> str
    parse_abc_answer(text, locale)        -> ABCResult
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


ABCStatus = Literal["normal", "abnormal", "ambiguous"]


@dataclass
class ABCResult:
    consciousness: ABCStatus
    breathing: ABCStatus
    perfusion: ABCStatus
    overall: Literal["all_normal", "any_abnormal", "ambiguous"]

    @property
    def escalate(self) -> bool:
        return self.overall in ("any_abnormal", "ambiguous")


_QUESTION_EN = (
    "Before anything else — three quick checks:\n"
    "① Are they conscious and responsive (head turns, eyes track)?\n"
    "② Is breathing normal, or rapid / labored / open-mouthed?\n"
    "③ Lift the lip — what color are the gums: pink, pale, blue/purple, or gray?"
)

_QUESTION_ZH = (
    "先确认 3 件事:\n"
    "① 他现在意识清醒、能反应吗(回头、眼睛会跟着动)?\n"
    "② 呼吸正常,还是急促 / 费力 / 张嘴喘?\n"
    "③ 翻一下嘴唇,牙龈是粉色,还是苍白 / 青紫 / 灰?"
)


def abc_question(locale: str = "en") -> str:
    return _QUESTION_ZH if locale.lower().startswith("zh") else _QUESTION_EN


# ── Answer parser ────────────────────────────────────────────────────────────
# Asymmetric default: any uncertain or unparseable answer → "ambiguous" → escalate.
# Cost of false escalation < cost of missed emergency.

_NORMAL_CONSCIOUS = (
    r"\b(yes|yeah|yep|conscious|responsive|alert|aware|fine|normal|okay|ok)\b",
    r"(清醒|有反应|能回应|正常|没事|意识好)",
)
_ABNORMAL_CONSCIOUS = (
    r"\b(no|unconscious|unresponsive|won'?t\s+(wake|respond|move)|out\s+cold|knocked\s+out|limp)\b",
    r"\b(can'?t|cannot)\s+(wake|rouse)\b",
    r"(不动|不反应|叫不醒|昏迷|没意识|失去意识|意识不清)",
)

_NORMAL_BREATHING = (
    r"\b(normal|fine|okay|ok|regular|steady|calm)\s*(breathing)?\b",
    r"\bbreathing\s+(normally|fine|okay|ok|well)\b",
    r"(呼吸正常|呼吸平稳|正常|没问题)",
)
_ABNORMAL_BREATHING = (
    r"\b(rapid|fast|labored|laboured|heavy|struggling|gasping|panting)\b",
    r"\bopen[\s-]mouth\b",
    r"\b(can'?t|cannot)\s+breathe\b",
    r"\bbelly\s+(heaving|moving)\b",
    r"(急促|费力|喘|张嘴呼吸|呼吸困难|呼吸不正常|喘不上)",
)

_NORMAL_GUMS = (
    r"\bpink\b",
    r"(粉|粉色|粉红)",
)
_ABNORMAL_GUMS = (
    r"\b(pale|white|blue|purple|gray|grey|cyanotic)\b",
    r"(苍白|白|青|紫|灰|发蓝|发紫)",
)


def _classify(text: str, normal: tuple[str, ...], abnormal: tuple[str, ...]) -> ABCStatus:
    if not text:
        return "ambiguous"
    lowered = text.lower()

    # Abnormal takes precedence — if user mentions any abnormal sign, that's the signal
    for pattern in abnormal:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            return "abnormal"
    for pattern in normal:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            return "normal"
    return "ambiguous"


def parse_abc_answer(text: str, locale: str = "en") -> ABCResult:
    """Parse the user's reply to the ABC question into structured signals.

    The parser is conservative: anything that isn't clearly "normal" maps to
    "ambiguous" and triggers escalation. Refusals, "I don't know", and
    short replies all escalate by default — that's the asymmetric cost model
    (better to over-escalate than miss a real emergency).
    """
    consciousness = _classify(text, _NORMAL_CONSCIOUS, _ABNORMAL_CONSCIOUS)
    breathing = _classify(text, _NORMAL_BREATHING, _ABNORMAL_BREATHING)
    perfusion = _classify(text, _NORMAL_GUMS, _ABNORMAL_GUMS)

    parts = (consciousness, breathing, perfusion)

    if any(p == "abnormal" for p in parts):
        overall = "any_abnormal"
    elif all(p == "normal" for p in parts):
        overall = "all_normal"
    else:
        overall = "ambiguous"

    return ABCResult(
        consciousness=consciousness,
        breathing=breathing,
        perfusion=perfusion,
        overall=overall,
    )


# ── Templated escalation reply (used when ABC fires abnormal) ────────────────

_ESCALATION_EN = (
    "🚨 What you're describing needs an emergency vet right now — please don't wait.\n\n"
    "On the way:\n"
    "• Keep them as still and calm as you can\n"
    "• If breathing is hard, prop the chest up slightly; do NOT force them flat\n"
    "• No food, no water\n"
    "• Have a phone ready and call ahead so the ER knows you're coming"
)

_ESCALATION_ZH = (
    "🚨 这种情况需要立刻去急诊,不要再等。\n\n"
    "路上:\n"
    "• 让他保持安静、尽量不要乱动\n"
    "• 如果呼吸费力,稍微把前胸垫高,不要强迫他平躺\n"
    "• 不要喂食、不要喂水\n"
    "• 提前打电话给急诊,告诉他们你正在来"
)


def abc_escalation_reply(locale: str = "en") -> str:
    return _ESCALATION_ZH if locale.lower().startswith("zh") else _ESCALATION_EN
