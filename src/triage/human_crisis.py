"""
Deterministic human-crisis gate.

Intercepts messages that contain self-harm / suicidal signals *before* the
LLM is called, so a user expressing crisis alongside a pet question is never
routed to vet advice. The gate uses keyword regex (not the LLM) so it is
100% deterministic and carries no latency cost.

Public API:
    detect_human_crisis(text: str) -> bool
    HUMAN_CRISIS_RESPONSE: str  — caring bilingual reply with SG hotlines
"""

import re

# ── Signal patterns ────────────────────────────────────────────────────────────
# Each entry is a regex that matches self-harm / suicidal language.
# Word boundaries (\b) guard against substring matches inside unrelated words.

_CRISIS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in [
        # Chinese — self-harm / suicidal ideation
        r"结束.{0,6}(自己的)?生命",
        r"不想.{0,4}活",
        r"想.{0,4}死",
        r"自\s*杀",
        r"去\s*死",
        r"活\s*不\s*下\s*去",
        r"没\s*有\s*意\s*义",
        r"没\s*有\s*意\s*思\s*活",
        r"活\s*着\s*没\s*意\s*思",
        r"活\s*着\s*太\s*累",
        r"不\s*想\s*撑\s*下\s*去",
        r"放\s*弃\s*生\s*命",
        r"伤\s*害\s*自\s*己",
        r"割\s*腕",
        r"跳\s*楼",
        r"结\s*束\s*一\s*切",
        # English — self-harm / suicidal ideation
        r"\bsuicid",
        r"\bend\s+my\s+(own\s+)?life\b",
        r"\bkill\s+myself\b",
        r"\bwant\s+to\s+die\b",
        r"\bno\s+reason\s+to\s+(live|go\s+on)\b",
        r"\bnothing\s+to\s+live\s+for\b",
        r"\bself[- ]?harm\b",
        r"\bcut\s+(myself|my\s+wrists?)\b",
        r"\btake\s+my\s+(own\s+)?life\b",
        r"\bcan'?t\s+go\s+on\b",
        r"\bgive\s+up\s+on\s+life\b",
        r"\bdon'?t\s+want\s+to\s+be\s+(here|alive)\b",
    ]
]

# ── Suppression patterns ───────────────────────────────────────────────────────
# If any of these match within a 40-char window around a crisis keyword, the
# signal is treated as past-tense, hypothetical, or animal-directed — not a
# human crisis signal.

_SUPPRESSION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(my\s+)?(dog|cat|pet|rabbit|hamster|bird|fish|turtle|reptile|animal)\b",
        r"\b(he|she|it)\s+(wants?|tried|is|was)\b",
        r"\bmy\s+pet\b",
        r"\bveterinar",
        r"\bvet\b",
        r"\beuthanasi",
        r"\byears?\s+ago\b",
        r"\blast\s+(year|month|week)\b",
        r"\bwhat\s+if\b",
        r"\bhypothetical",
        r"\bin\s+(a\s+)?(book|movie|film|story|game|show)\b",
    ]
]


def detect_human_crisis(text: str) -> bool:
    """
    Return True if ``text`` contains a human self-harm or suicidal signal.

    Scans for crisis keywords and suppresses matches that are clearly about a
    pet, a fictional context, or a past/hypothetical event.
    """
    for pattern in _CRISIS_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        start = max(0, m.start() - 40)
        end = min(len(text), m.end() + 40)
        window = text[start:end]
        if any(s.search(window) for s in _SUPPRESSION_PATTERNS):
            continue
        return True
    return False


# ── Hardcoded crisis response ──────────────────────────────────────────────────
# Caring tone — validated in PAW-61 comment thread (2026-05-14).
# Singapore-first numbers per prompts_config.yaml final_reminders.

HUMAN_CRISIS_RESPONSE: str = """\
谢谢你愿意告诉我这些。我想让你知道，你说的话我都听到了，**你现在的感受很重要**。

生命中有些时刻真的很难，但你不必一个人扛着这一切。有人愿意陪伴你、倾听你：

- **新加坡 SOS 热线：1767**（24小时；也可 WhatsApp 9151 1767）
- **新加坡 SOS 热线：1800-221-4444**
- 如果你在中国大陆：北京心理危机研究与干预中心 010-82951332 / 全国心理援助热线 400-161-9995
- 如果你在以上地区以外：国际自杀预防协会 https://www.iasp.info/resources/Crisis_Centres/

你值得被好好照顾。请给自己一个机会，和他们聊聊。💙

---

Thank you for sharing this with me. I want you to know that I hear you, and **what you're feeling matters**.

There are people who care and want to listen — please reach out:

- **Singapore SOS: 1767** (24-hour; WhatsApp 9151 1767)
- **Singapore SOS: 1800-221-4444**
- If you're in mainland China: 010-82951332 / 400-161-9995 / 400-821-1215
- If you're elsewhere: https://www.iasp.info/resources/Crisis_Centres/

You deserve support. You don't have to face this alone. 💙\
"""
