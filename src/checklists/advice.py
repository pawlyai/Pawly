"""
Advice template renderer (Section 10).

Fills the checklist's advice template with the slot values collected during
the clarification loop. The LLM is invoked only to natural-ize the prose
within tight constraints — Section 9 hard limits are injected as a do-not
list.

Public API:
    render_advice(spec, collected, locale, llm_client=None) -> str
    build_hard_limits_prompt(spec) -> str
"""

from __future__ import annotations

from typing import Any, Optional

from src.checklists.schema import ChecklistSpec


def build_hard_limits_prompt(spec: ChecklistSpec) -> str:
    """Format Section 9 hard limits for system-prompt injection."""
    if not spec.hard_limits.forbidden and not spec.hard_limits.required:
        return ""

    parts = [
        f"# Hard Limits for scenario {spec.checklist_id} ({spec.title_en})",
    ]
    if spec.hard_limits.forbidden:
        parts.append("\nYou MUST NOT:")
        for item in spec.hard_limits.forbidden:
            parts.append(f"  - {item}")
    if spec.hard_limits.required:
        parts.append("\nYou MUST:")
        for item in spec.hard_limits.required:
            parts.append(f"  - {item}")
    return "\n".join(parts)


def render_escalation(spec: ChecklistSpec, locale: str = "en") -> str:
    """Return the Section 5 escalation message (when urgency trigger fires)."""
    if spec.escalation_template is None:
        # Fallback to a generic immediate-emergency template
        if locale.lower().startswith("zh"):
            return (
                "🚨 这种情况需要立刻去急诊。\n\n"
                "路上保持冷静,不要喂食喂水,提前打电话给急诊告诉他们你正在来。"
            )
        return (
            "🚨 What you're describing needs emergency veterinary attention now.\n\n"
            "On the way: keep them calm, no food or water, and call ahead so the "
            "ER knows you're coming."
        )
    return (
        spec.escalation_template.zh
        if locale.lower().startswith("zh")
        else spec.escalation_template.en
    )


def render_advice(
    spec: ChecklistSpec,
    collected: dict[str, Any],
    locale: str = "en",
    llm_client: Optional[Any] = None,
) -> str:
    """Render Section 10 advice, optionally polishing prose with LLM.

    V0: deterministic template fill, no LLM polishing. The template prose is
    written by the vet during checklist authoring and used verbatim with slot
    interpolation.

    V1 (TODO): pass the filled template + Section 9 hard limits to LLM with
    instruction "rewrite in user's natural register without adding new
    information or violating any hard limit."
    """
    is_zh = locale.lower().startswith("zh")
    a = spec.advice

    sections = []

    if is_zh:
        if a.signal_recap_zh:
            sections.append(_format_template(a.signal_recap_zh, collected))
        if a.home_observation_zh:
            sections.append(_format_template(a.home_observation_zh, collected))
        if a.return_for_vet_triggers_zh:
            sections.append(_format_template(a.return_for_vet_triggers_zh, collected))
        if a.disclaimer_zh:
            sections.append(a.disclaimer_zh)
    else:
        if a.signal_recap_en:
            sections.append(_format_template(a.signal_recap_en, collected))
        if a.home_observation_en:
            sections.append(_format_template(a.home_observation_en, collected))
        if a.return_for_vet_triggers_en:
            sections.append(_format_template(a.return_for_vet_triggers_en, collected))
        if a.disclaimer_en:
            sections.append(a.disclaimer_en)

    return "\n\n".join(s for s in sections if s).strip()


def _format_template(template: str, collected: dict[str, Any]) -> str:
    """Replace {slot_id} placeholders with collected values.

    Falls back to a neutral placeholder rather than raising on missing keys.
    """
    out = template
    for slot_id, value in collected.items():
        placeholder = "{" + slot_id + "}"
        if placeholder in out:
            if isinstance(value, list):
                rendered = ", ".join(str(v) for v in value)
            else:
                rendered = str(value)
            out = out.replace(placeholder, rendered)

    # Strip any remaining unfilled placeholders
    import re
    out = re.sub(r"\{[A-Za-z0-9_]+\}", "", out)
    return out.strip()
