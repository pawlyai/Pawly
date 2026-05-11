"""Annotate failed cases in a multiturn report with DeepSeek-generated root causes.

For every case whose ``status`` is not ``passed_threshold``, calls DeepSeek with the
case's transcript + evaluator reason and stores ``{category, explanation}`` under
``case["root_cause"]``. The per-category count is written to
``summary["root_cause_breakdown"]`` so the Streamlit Reports page can render a
breakdown without re-reading every case.

Usage:
    DEEPSEEK_API_KEY=... python scripts/annotate_root_causes.py \
        'tests/blackbox_multiturn/results/multiturn_pawly_regression_light30_report_*.json'

Best-effort: if ``DEEPSEEK_API_KEY`` is unset or the SDK is missing, the script
prints a notice and exits 0 so it never blocks CI.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path
from typing import Any

CATEGORIES = [
    "missed_urgency",
    "false_alarm",
    "vague_refusal",
    "out_of_scope_drift",
    "hallucinated_facts",
    "tone_mismatch",
    "memory_inconsistency",
    "incomplete_followup",
    "other",
]

CATEGORY_LIST = ", ".join(CATEGORIES)

SYSTEM_PROMPT = (
    "You are reviewing failed test cases for Pawly, a pet-care chatbot. "
    "Given the evaluator's reason for failure and the conversation transcript, "
    "classify the root cause into exactly one of these categories: "
    f"{CATEGORY_LIST}. "
    "Return strict JSON with two fields:\n"
    '  "category": one of the categories above (use "other" if nothing fits),\n'
    '  "explanation": one short sentence (<= 25 words) describing the specific failure.\n'
    "Do not invent new categories. Do not add commentary."
)

USER_PROMPT_TEMPLATE = (
    "Case: {name}\n"
    "Scenario: {scenario}\n"
    "Score: {score} (threshold {threshold})\n\n"
    "Evaluator reason:\n{reason}\n\n"
    "Transcript (last {turn_count} turns):\n{transcript}\n"
)

MAX_TRANSCRIPT_TURNS = 20
MAX_REASON_CHARS = 1500


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _build_transcript(turns: list[dict[str, Any]]) -> str:
    tail = turns[-MAX_TRANSCRIPT_TURNS:]
    lines = []
    for t in tail:
        role = t.get("role", "?")
        content = _truncate(str(t.get("content", "")).replace("\n", " "), 400)
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _classify(client: Any, model: str, case: dict[str, Any]) -> dict[str, str]:
    reason = _truncate(str(case.get("reason", "")), MAX_REASON_CHARS)
    transcript = _build_transcript(case.get("turns", []))
    user_prompt = USER_PROMPT_TEMPLATE.format(
        name=case.get("name", "?"),
        scenario=_truncate(str(case.get("scenario", "") or case.get("metadata", {}).get("focus", "")), 400),
        score=case.get("score", 0),
        threshold=case.get("threshold", 0.7),
        reason=reason,
        turn_count=min(case.get("turn_count", 0), MAX_TRANSCRIPT_TURNS),
        transcript=transcript,
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=200,
    )
    text = resp.choices[0].message.content or "{}"
    payload = json.loads(text)
    category = str(payload.get("category", "other")).strip()
    if category not in CATEGORIES:
        category = "other"
    explanation = str(payload.get("explanation", "")).strip()
    return {"category": category, "explanation": explanation}


def annotate_report(path: Path, client: Any, model: str) -> tuple[int, dict[str, int]]:
    with path.open("r", encoding="utf-8") as fh:
        report = json.load(fh)

    cases = report.get("cases", [])
    failed = [c for c in cases if c.get("status") != "passed_threshold"]
    counts: dict[str, int] = {}

    for case in failed:
        try:
            rc = _classify(client, model, case)
        except Exception as exc:  # noqa: BLE001
            rc = {"category": "annotation_failed", "explanation": _truncate(str(exc), 200)}
        case["root_cause"] = rc
        cat = rc["category"]
        counts[cat] = counts.get(cat, 0) + 1

    report.setdefault("summary", {})["root_cause_breakdown"] = counts
    with path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=True)

    return len(failed), counts


def _resolve_client() -> tuple[Any, str] | None:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        print("DEEPSEEK_API_KEY not set — skipping root-cause annotation.")
        return None
    try:
        from openai import OpenAI
    except ImportError:
        print("openai SDK not installed — skipping root-cause annotation.")
        return None
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
    model = os.environ.get("PAWLY_MODEL", "deepseek-chat")
    return client, model


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "patterns",
        nargs="+",
        help="One or more glob patterns matching report JSON files",
    )
    args = parser.parse_args()

    paths: list[Path] = []
    for pattern in args.patterns:
        paths.extend(Path(p) for p in sorted(glob.glob(pattern)))
    if not paths:
        print(f"No report files matched: {args.patterns}")
        return 0

    resolved = _resolve_client()
    if resolved is None:
        return 0
    client, model = resolved

    for path in paths:
        failed_count, counts = annotate_report(path, client, model)
        breakdown = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "(no failures)"
        print(f"{path}: annotated {failed_count} failed cases — {breakdown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
