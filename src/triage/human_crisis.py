"""
Human crisis and medical emergency detection.

Two separate detectors, called by classify_by_rules() and the orchestrator:

  detect_human_crisis(text) -> bool
      Suicidal / self-harm signals, explicit and implicit.
      Covers English and Chinese; suppressed when the signal is clearly about a pet.

  detect_human_medical_emergency(text) -> bool
      Owner describes their own acute medical emergency: chest pain, heart attack,
      stroke, inability to breathe. Suppressed when the symptom is attributed to a pet.

Both functions are false-positive-conservative: they only fire on first-person signals
that clearly belong to the owner, not the pet.

Hardcoded responses (returned by the orchestrator gate, never go through the LLM):
  HUMAN_CRISIS_RESPONSE             — warm, bilingual, SOS 1767 (SG default)
  HUMAN_MEDICAL_EMERGENCY_RESPONSE  — concise, bilingual, 995 / A&E
"""

import re

# ── Pet-subject suppressor ────────────────────────────────────────────────────
# The detectors only fire when the speaker is describing THEIR OWN symptoms.
# Suppress when the message makes it clear the symptom belongs to a pet.
_PET_SUBJECT_RE = re.compile(
    r"\b(?:my|the)\s+(?:dog|cat|puppy|kitten|rabbit|bird|hamster|turtle|snake|"
    r"bunny|chinchilla|ferret|guinea\s*pig|parrot|reptile|pet|"
    r"doggy|kitty|pup|fur\s*baby)\b",
    re.IGNORECASE,
)
# "He/she/it is/has/was" — pet pronouns in third person
_PET_PRONOUN_RE = re.compile(
    r"\b(?:he|she|it)\s+(?:is|has|was|have|had)\s+",
    re.IGNORECASE,
)


def _is_about_pet(text: str) -> bool:
    """Return True when the message clearly attributes symptoms to a pet, not the owner."""
    return bool(_PET_SUBJECT_RE.search(text) or _PET_PRONOUN_RE.search(text))


# ── Human crisis (suicidal / self-harm) ───────────────────────────────────────

# Explicit Chinese patterns
_CRISIS_ZH: tuple[re.Pattern[str], ...] = (
    re.compile(r"结束自己的生命"),
    re.compile(r"自杀"),
    re.compile(r"不想(活|活着)了"),
    re.compile(r"想死"),
    re.compile(r"活不下去"),
    re.compile(r"没有意义了"),
    re.compile(r"(想|要)(跳楼|割腕)"),
    re.compile(r"以死谢罪"),
    re.compile(r"不想见到明天"),
    re.compile(r"如果我(就)?不在了"),
    re.compile(r"如果我消失了"),
)

# Explicit and implicit English patterns
_CRISIS_EN: tuple[re.Pattern[str], ...] = (
    # Explicit self-harm / suicidal
    re.compile(r"\bsuicid(?:al|e)\b", re.IGNORECASE),
    re.compile(r"\bwant(?:s)?\s+to\s+(?:die|kill\s+myself?|end\s+(?:my|their)\s+life)\b", re.IGNORECASE),
    re.compile(r"\bend(?:ing)?\s+my\s+life\b", re.IGNORECASE),
    re.compile(r"\bkill(?:ing)?\s+myself?\b", re.IGNORECASE),
    re.compile(r"\bnothing\s+to\s+live\s+for\b", re.IGNORECASE),
    re.compile(r"\bdon'?t\s+want\s+to\s+(?:be\s+here|live|exist)\s*(?:anymore)?\b", re.IGNORECASE),
    re.compile(r"\bbetter\s+off\s+dead\b", re.IGNORECASE),
    re.compile(r"\bself[- ]?harm\b", re.IGNORECASE),
    re.compile(r"\bcut(?:ting)?\s+myself?\b", re.IGNORECASE),
    # Implicit — "if I weren't here / wasn't around"
    re.compile(r"\bif\s+i\s+(?:just\s+)?weren'?t\s+here\b", re.IGNORECASE),
    re.compile(r"\bif\s+i\s+(?:just\s+)?wasn'?t\s+(?:here|around|alive)\b", re.IGNORECASE),
    re.compile(r"\bif\s+i\s+(?:just\s+)?(?:disappeared|was\s+gone|wasn'?t\s+around)\b", re.IGNORECASE),
    re.compile(r"\b(?:wonder|think\s+about)\s+what\s+it\s+(?:would|'?d)\s+be\s+like\s+(?:if\s+i\s+(?:just\s+)?(?:weren'?t|wasn'?t)\s+here)\b", re.IGNORECASE),
    re.compile(r"\bcan'?t\s+imagine\s+(?:a\s+)?(?:life|living)\s+(?:without|after)\b", re.IGNORECASE),
    # "I don't see the point anymore" — implicit
    re.compile(r"\bdon'?t\s+see\s+(?:the\s+)?point\s+(?:anymore|in\s+(?:anything|living|going\s+on))\b", re.IGNORECASE),
    # Passive ideation — wishing not to wake up / wishing to be dead
    re.compile(r"\bwouldn'?t\s+(?:mind\s+)?(?:just\s+)?not\s+waking\s+up\b", re.IGNORECASE),
    re.compile(r"\bwish\s+(?:i\s+)?(?:just\s+)?wouldn'?t\s+wake\s+up\b", re.IGNORECASE),
    re.compile(r"\bdon'?t\s+want\s+to\s+wake\s+up\b", re.IGNORECASE),
    re.compile(r"\bwish\s+(?:i\s+)?(?:was|were)\s+dead\b", re.IGNORECASE),
    re.compile(r"\bwish\s+(?:i\s+)?(?:could\s+)?just\s+disappear\b", re.IGNORECASE),
    re.compile(r"\bno\s+reason\s+to\s+(?:go\s+on|keep\s+going|be\s+here|stay)\b", re.IGNORECASE),
    re.compile(r"\bso\s+tired\s+of\s+(?:living|being\s+alive|this\s+life|everything)\b", re.IGNORECASE),
    re.compile(r"\bwish\s+i\s+(?:wasn'?t|weren'?t)\s+(?:here|alive|around)\b", re.IGNORECASE),
)


def detect_human_crisis(text: str) -> bool:
    """Return True when the message contains suicidal or self-harm signals from the owner."""
    if _is_about_pet(text):
        return False
    return (
        any(p.search(text) for p in _CRISIS_ZH)
        or any(p.search(text) for p in _CRISIS_EN)
    )


# ── Human medical emergency (chest pain, heart attack, stroke) ────────────────

# Chinese: require explicit "I / myself" subject for broad terms;
#          heart-attack / stroke terms are human-specific regardless of subject.
_MEDICAL_ZH: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:我|自己).{0,20}胸痛"),
    re.compile(r"胸口.{0,10}(?:痛|疼|不舒服|压迫)"),
    re.compile(r"(?:我|自己).{0,20}心脏.{0,10}(?:痛|疼|不舒服)"),
    re.compile(r"心脏病发|心肌梗塞|心梗"),
    re.compile(r"中风|脑梗"),
    re.compile(r"(?:我|自己).{0,20}(?:呼吸困难|喘不过气|无法呼吸)"),
    # Broad "chest pain" (胸痛) without explicit subject: fire unless pet-context
    re.compile(r"胸痛"),
)

# English: patterns are written to require first-person subject
_MEDICAL_EN: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bi'?(?:ve|m)\s+(?:had|been\s+having|having)\s+.{0,30}chest\s+pain\b", re.IGNORECASE),
    re.compile(r"\bi\s+have\s+.{0,30}chest\s+pain\b", re.IGNORECASE),
    re.compile(r"\bmy\s+chest\s+(?:hurts|is\s+hurting|is\s+(?:in\s+)?pain|feels?\s+tight)\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:think\s+)?i'?m\s+having\s+.{0,30}heart\s+attack\b", re.IGNORECASE),
    re.compile(r"\bi'?m\s+having\s+.{0,30}heart\s+attack\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:had|have)\s+.{0,30}heart\s+attack\b", re.IGNORECASE),
    re.compile(r"\bmy\s+heart\s+(?:hurts|is\s+(?:racing|pounding|stopping))\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:think\s+)?i'?m\s+having\s+.{0,30}stroke\b", re.IGNORECASE),
    re.compile(r"\bi\s+can'?t\s+breathe\b", re.IGNORECASE),
    re.compile(r"\bi'?m\s+(?:having\s+trouble|unable\s+to)\s+breath(?:e|ing)\b", re.IGNORECASE),
    # "chest pain" anywhere when "I / me / my chest / my pain" is also in the message
    re.compile(r"chest\s+pain.{0,100}\b(?:i|me|myself)\b", re.IGNORECASE),
    re.compile(r"\b(?:i|me|myself)\b.{0,100}chest\s+pain", re.IGNORECASE),
)


def detect_human_medical_emergency(text: str) -> bool:
    """Return True when the owner describes their own acute medical emergency."""
    if _is_about_pet(text):
        return False
    return (
        any(p.search(text) for p in _MEDICAL_ZH)
        or any(p.search(text) for p in _MEDICAL_EN)
    )


# ── Hardcoded responses ───────────────────────────────────────────────────────
# These are returned by the orchestrator gate without calling the LLM.
# Plain text (no HTML) — Telegram renders them fine; the orchestrator must NOT
# wrap them in apply_response_format() with the pet-emergency RED template.

HUMAN_CRISIS_RESPONSE = (
    "Thank you for sharing this with me. I want you to know that I hear you, "
    "and what you're feeling matters.\n\n"
    "There are people who care and want to listen — please reach out:\n\n"
    "• Samaritans of Singapore / SOS (24 hrs): 1767 (call or WhatsApp 9151 1767)\n"
    "• Singapore IMH Mental Health Helpline: 6389-2222\n\n"
    "If you're outside Singapore, please contact your local crisis line or go "
    "to your nearest emergency room.\n\n"
    "You deserve support. You don't have to face this alone. 💙\n\n"
    "---\n\n"
    "谢谢你愿意告诉我这些。你说的话我都听到了，你现在的感受很重要。\n\n"
    "有人愿意陪伴你、倾听你：\n\n"
    "• 新加坡 SOS 热线（24小时）：1767（也可 WhatsApp 9151 1767）\n"
    "• 新加坡 IMH 心理援助：6389-2222\n"
    "• 如在中国大陆：北京 010-82951332 / 全国 400-161-9995\n\n"
    "你值得被好好照顾。请给自己一个机会，和他们聊聊。💙"
)

HUMAN_MEDICAL_EMERGENCY_RESPONSE = (
    "I noticed you may be describing your own medical emergency. "
    "Please call emergency services immediately — do not wait:\n\n"
    "🚨 Singapore: 995 (ambulance / A&E)\n"
    "🚨 Or go to the nearest Accident & Emergency department now.\n\n"
    "Chest pain can be a sign of a heart attack. This needs urgent attention "
    "from a doctor, not a pet care assistant.\n\n"
    "Pawly is here for pet care questions. Once you're safe, I'm happy to help "
    "with anything your pet needs. 🐾\n\n"
    "---\n\n"
    "我注意到你可能在描述自己的身体不适。请立即拨打急救电话，不要等待：\n\n"
    "🚨 新加坡急救：995（救护车）\n"
    "🚨 或立刻前往最近的急诊室（A&E）\n"
    "🚨 如在中国大陆：拨打 120\n\n"
    "胸痛可能是心脏病发作的信号，需要立即就医。\n\n"
    "Pawly 是宠物助手，无法提供人类医疗建议。待您安全后，我随时可以帮您解答宠物问题。🐾"
)
