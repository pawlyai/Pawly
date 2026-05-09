"""Shared rendering helpers for regression-style report views.

Used by `pages/3_Compare.py` and `pages/5_Regression_History.py` so both pages
present the same diff / per-case matrix / drill-in / single-detail UI.

`meta` is a free-form dict — pages provide whatever they have (PR metadata
from CI sidecars, or just {topic, model, timestamp} parsed from the filename).
The renderers degrade gracefully when fields are missing.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st

_BLACKBOX_DIR = Path(__file__).resolve().parent.parent
if str(_BLACKBOX_DIR) not in sys.path:
    sys.path.insert(0, str(_BLACKBOX_DIR))

from lang import get_lang, t  # noqa: E402
from utils.export import translate_for_display  # noqa: E402
from utils.regression_diff import render as render_diff_md  # noqa: E402

CACHE_PATH = _BLACKBOX_DIR / "results" / "translation_cache.json"


def pass_rate(report: dict[str, Any]) -> tuple[float, int, int]:
    s = report.get("summary", {})
    total = int(s.get("total_cases", 0))
    passed = int(s.get("passed_threshold", 0))
    rate = (passed / total * 100) if total else 0.0
    return rate, passed, total


def case_index(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c.get("name", ""): c for c in report.get("cases", [])}


def humanize_when(meta: dict[str, Any], report: dict[str, Any]) -> str:
    """Render `meta.created_at` (CI sidecar) or `summary.timestamp` (local run)
    as a relative phrase like '2h ago' / '3d ago'."""
    created = meta.get("created_at") or ""
    when: datetime | None = None
    if created:
        try:
            when = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:
            when = None
    if when is None:
        ts = report.get("summary", {}).get("timestamp", "")
        if ts:
            try:
                when = datetime.strptime(ts, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
            except Exception:
                when = None
    if when is None:
        return "—"

    delta = datetime.now(timezone.utc) - when
    if delta.days > 30:
        return when.strftime("%Y-%m-%d")
    if delta.days >= 1:
        return f"{delta.days}d ago"
    if delta.seconds >= 3600:
        return f"{delta.seconds // 3600}h ago"
    if delta.seconds >= 60:
        return f"{delta.seconds // 60}m ago"
    return "just now"


def render_per_case_matrix(
    a_label: str,
    a_report: dict[str, Any],
    b_label: str,
    b_report: dict[str, Any],
) -> None:
    """Two-column score matrix sorted by |Δ| desc, with flip flag."""
    a_idx = case_index(a_report)
    b_idx = case_index(b_report)
    names = sorted(set(a_idx) | set(b_idx))

    def _row(name: str) -> dict[str, Any]:
        a = a_idx.get(name)
        b = b_idx.get(name)
        a_score = float(a["score"]) if a and "score" in a else None
        b_score = float(b["score"]) if b and "score" in b else None
        delta = (b_score - a_score) if (a_score is not None and b_score is not None) else None
        a_pass = bool(a and a.get("status") == "passed_threshold")
        b_pass = bool(b and b.get("status") == "passed_threshold")
        flag = ""
        if a is not None and b is not None:
            if a_pass and not b_pass:
                flag = "❌ regression"
            elif not a_pass and b_pass:
                flag = "✅ improvement"
            elif delta is not None and abs(delta) >= 0.1:
                flag = "⚠️ score moved"
        return {
            "Case": name,
            a_label: round(a_score, 3) if a_score is not None else None,
            b_label: round(b_score, 3) if b_score is not None else None,
            "Δ": round(delta, 3) if delta is not None else None,
            "Flag": flag,
        }

    rows = [_row(n) for n in names]
    rows.sort(
        key=lambda r: (abs(r["Δ"]) if r["Δ"] is not None else 0, r["Flag"] != ""),
        reverse=True,
    )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_drill_in(
    a_label: str,
    a_report: dict[str, Any],
    b_label: str,
    b_report: dict[str, Any],
    *,
    key_prefix: str,
) -> None:
    """Side-by-side drill into one case's score + judge reason.

    `key_prefix` namespaces the selectbox so multiple drill-ins on one page
    (e.g. one per tab) don't collide.
    """
    a_idx = case_index(a_report)
    b_idx = case_index(b_report)
    names = sorted(set(a_idx) | set(b_idx))
    if not names:
        return
    pick = st.selectbox(t("case"), names, key=f"{key_prefix}_drill_case")
    cols = st.columns(2)
    for col, label, idx in zip(cols, [a_label, b_label], [a_idx, b_idx]):
        case = idx.get(pick)
        with col:
            st.markdown(f"**{label}**")
            if not case:
                st.caption(t("not_in_report"))
                continue
            score = case.get("score", 0)
            threshold = case.get("threshold", 0.7)
            emoji = "✅" if score >= threshold else "❌"
            st.metric(t("score"), f"{emoji} {score:.2f}", delta=f"th: {threshold:.2f}")
            st.markdown(f"**{t('reason')}**")
            reason = case.get("reason", "—")
            if get_lang() == "zh" and reason != "—":
                reason = translate_for_display(reason, CACHE_PATH)
            st.write(reason)


def render_diff_section(
    baseline_path: Path,
    baseline_report: dict[str, Any],
    candidate_path: Path,
    candidate_report: dict[str, Any],
    *,
    a_label: str = "baseline",
    b_label: str = "candidate",
    key_prefix: str,
) -> None:
    """Full diff view: overall verdict + per-case matrix + drill-in."""
    st.subheader("Diff (overall)")
    try:
        md = render_diff_md(baseline_path, candidate_path, baseline_report, candidate_report)
        st.markdown(md)
    except Exception as exc:
        st.error(f"regression_diff.render failed: {exc}")

    st.divider()
    st.subheader("Per-case scores")
    render_per_case_matrix(a_label, baseline_report, b_label, candidate_report)

    st.divider()
    st.subheader("Drill into a case")
    render_drill_in(a_label, baseline_report, b_label, candidate_report, key_prefix=key_prefix)


def render_case_expander(case: dict[str, Any]) -> None:
    name = case.get("name", "?")
    score = case.get("score", 0.0)
    threshold = case.get("threshold", 0.7)
    emoji = "✅" if case.get("status") == "passed_threshold" else "❌"
    label = f"{emoji} {name}  ·  {score:.2f} / {threshold:.2f}"
    with st.expander(label):
        reason = case.get("reason", "—")
        if get_lang() == "zh" and reason != "—":
            reason = translate_for_display(reason, CACHE_PATH)
        st.markdown(f"**{t('eval_reason')}**")
        st.write(reason)
        turns = case.get("turns", [])
        if turns:
            st.markdown(f"**{t('transcript')}**")
            for i, turn in enumerate(turns):
                role = turn.get("role", "unknown")
                content = turn.get("content", "")
                if get_lang() == "zh":
                    content = translate_for_display(content, CACHE_PATH)
                if role == "user":
                    st.markdown(f"_{t('user_turn', i=i+1)}_")
                    st.info(content)
                else:
                    st.markdown(f"_{t('assistant_turn', i=i+1)}_")
                    clean = content.replace("<i>", "_").replace("</i>", "_")
                    clean = clean.replace("<b>", "**").replace("</b>", "**")
                    clean = clean.replace("<blockquote>", "").replace("</blockquote>", "")
                    st.success(clean)


def render_single_detail(
    report: dict[str, Any],
    meta: dict[str, Any],
) -> None:
    """Inline case-by-case view for one run. Worst (lowest score) first."""
    pr_num = meta.get("pr_number")
    title = meta.get("pr_title") or meta.get("title") or "(no title)"
    rate, passed, total = pass_rate(report)

    head_cols = st.columns([3, 1, 1, 1])
    with head_cols[0]:
        if pr_num:
            st.markdown(f"### #{pr_num} — {title}")
        else:
            heading = meta.get("trigger") or meta.get("model") or "manual"
            st.markdown(f"### {heading} — {title}")
        sub_bits: list[str] = []
        if meta.get("pr_branch"):
            sub_bits.append(f"branch `{meta['pr_branch']}`")
        if meta.get("model"):
            sub_bits.append(f"model `{meta['model']}`")
        if meta.get("actor"):
            sub_bits.append(f"by {meta['actor']}")
        if sub_bits:
            st.caption(" · ".join(sub_bits))
    head_cols[1].metric(t("total_cases"), total)
    head_cols[2].metric(t("passed"), passed)
    head_cols[3].metric(t("pass_rate"), f"{rate:.1f}%")

    link_bits: list[str] = []
    if meta.get("pr_url"):
        link_bits.append(f"[PR]({meta['pr_url']})")
    if meta.get("run_url"):
        link_bits.append(f"[Actions run]({meta['run_url']})")
    if meta.get("commit_sha"):
        link_bits.append(f"`{meta['commit_sha'][:8]}`")
    if link_bits:
        st.markdown(" · ".join(link_bits))

    st.divider()

    cases = list(report.get("cases", []))
    cases.sort(key=lambda c: c.get("score", 1.0))

    failed = [c for c in cases if c.get("status") != "passed_threshold"]
    passed_cases = [c for c in cases if c.get("status") == "passed_threshold"]

    if failed:
        st.markdown(f"#### ❌ {len(failed)} below threshold")
        for case in failed:
            render_case_expander(case)
    if passed_cases:
        st.markdown(f"#### ✅ {len(passed_cases)} passed")
        for case in passed_cases:
            render_case_expander(case)
