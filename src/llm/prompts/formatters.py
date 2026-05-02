"""
Response formatters — apply Figma visual style to LLM output.

The LLM writes plain content (explanation, questions). Python wraps it
with the correct visual chrome based on the resolved triage level.

Output uses Telegram HTML parse mode (<b>, <i>, etc.).

Public API:
    apply_response_format(text, triage) -> str
"""

import html
import re

from src.db.models import TriageLevel

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
