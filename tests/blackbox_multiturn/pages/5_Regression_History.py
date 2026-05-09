"""Regression history — PR-aware index of every CI / manual regression run.

Each row corresponds to one cached report under
`/opt/pawly/regression-cache/reports-{light-30,full-223}/<MODEL>/`. Pick
exactly two rows to see:
  - Overall pass-rate delta + verdict (via scripts/regression_diff.render)
  - Per-case score matrix (rows = test cases, columns = the two reports)
  - Drill-into-a-case side-by-side reasoning

Reads PR metadata from the `.meta.json` sidecar written by the CI workflow
(or by `make regression-promote-baseline` for manual runs).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import streamlit as st

REPO_ROOT = Path(__file__).parent.parent.parent.parent
BLACKBOX_DIR = Path(__file__).parent.parent
CACHE_DIR = Path("/opt/pawly/regression-cache")

for _p in (str(REPO_ROOT), str(BLACKBOX_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lang import get_lang, lang_toggle, t  # noqa: E402
from utils.export import translate_for_display  # noqa: E402


def _load_regression_diff() -> ModuleType:
    """Load `scripts/regression_diff.py` by file path.

    Streamlit can run from different cwds depending on how it's started
    (host /opt/pawly vs docker /app vs other), so relying on sys.path
    finding `scripts/` is fragile. We try a handful of likely locations
    and use importlib to load the module regardless of sys.path state.
    """
    candidates = [
        REPO_ROOT / "scripts" / "regression_diff.py",
        Path("/opt/pawly/scripts/regression_diff.py"),
        Path("/app/scripts/regression_diff.py"),
    ]
    for path in candidates:
        if path.exists():
            spec = importlib.util.spec_from_file_location("regression_diff", path)
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise ImportError(
        "regression_diff.py not found in any of: "
        + ", ".join(str(c) for c in candidates)
    )


_regression_diff = _load_regression_diff()
render_diff_md = _regression_diff.render

CACHE_PATH = BLACKBOX_DIR / "results" / "translation_cache.json"

st.set_page_config(page_title="Regression History", page_icon="📈", layout="wide")

# (display label, cache subdir, report-filename glob for fallback discovery)
TOPICS: dict[str, tuple[str, str]] = {
    "lite": ("Lite-30", "reports-light-30"),
    "full": ("Full-223", "reports-full-223"),
}


def _list_cached(subdir: str) -> list[tuple[Path, dict[str, Any], dict[str, Any]]]:
    """Return [(report_path, report_dict, meta_dict)] for every report under
    `<CACHE_DIR>/<subdir>/<MODEL>/*.json`, sorted newest first.

    Missing meta sidecars degrade gracefully — meta_dict is `{}` and the UI
    renders "—" placeholders instead of erroring.
    """
    base = CACHE_DIR / subdir
    if not base.exists():
        return []

    rows: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    for model_dir in sorted(base.iterdir()):
        if not model_dir.is_dir():
            continue
        for report_path in model_dir.glob("*.json"):
            if report_path.name.endswith(".meta.json"):
                continue
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            meta_path = report_path.with_name(report_path.stem + ".meta.json")
            meta: dict[str, Any] = {}
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            meta.setdefault("model", model_dir.name)
            rows.append((report_path, report, meta))

    def _key(item: tuple[Path, dict[str, Any], dict[str, Any]]) -> str:
        _, report, meta = item
        return (
            (meta.get("created_at") or "")
            or (report.get("summary", {}).get("timestamp", "") or "")
        )

    rows.sort(key=_key, reverse=True)
    return rows


def _humanize(meta: dict[str, Any], report: dict[str, Any]) -> str:
    """Render created_at / report timestamp as a relative phrase."""
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


def _pass_rate(report: dict[str, Any]) -> tuple[float, int, int]:
    s = report.get("summary", {})
    total = int(s.get("total_cases", 0))
    passed = int(s.get("passed_threshold", 0))
    rate = (passed / total * 100) if total else 0.0
    return rate, passed, total


def _row_label(meta: dict[str, Any], report: dict[str, Any]) -> str:
    pr = meta.get("pr_number")
    title = (meta.get("pr_title") or "(no title)").strip()
    rate, passed, total = _pass_rate(report)
    pr_disp = f"#{pr}" if pr else (meta.get("pr_branch") or meta.get("trigger") or "manual")
    if len(title) > 60:
        title = title[:60] + "…"
    return f"{pr_disp}  ·  {title}  ·  {rate:.1f}% ({passed}/{total})"


def _render_index_table(items: list[tuple[Path, dict[str, Any], dict[str, Any]]]) -> None:
    rows: list[dict[str, Any]] = []
    for path, report, meta in items:
        rate, passed, total = _pass_rate(report)
        pr_num = meta.get("pr_number")
        pr_disp = f"#{pr_num}" if pr_num else (meta.get("trigger") or "—")
        rows.append({
            "PR": pr_disp,
            "Title": (meta.get("pr_title") or "—")[:80],
            "Branch": meta.get("pr_branch") or "—",
            "Model": meta.get("model") or "—",
            "Pass %": round(rate, 1),
            "Cases": f"{passed}/{total}",
            "When": _humanize(meta, report),
            "Actor": meta.get("actor") or "—",
            "PR link": meta.get("pr_url") or "",
            "Run / detail": meta.get("run_url") or "",
        })
    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "PR link": st.column_config.LinkColumn(
                "PR link",
                display_text="open PR",
                help="Opens the GitHub PR (if this run was PR-triggered).",
            ),
            "Run / detail": st.column_config.LinkColumn(
                "Run / detail",
                display_text="logs + artifacts",
                help=(
                    "Opens the GitHub Actions run page — full pytest logs, "
                    "judge reasoning, downloadable report artifact. "
                    "For inline case-by-case detail, pick exactly one row "
                    "in the multiselect below."
                ),
            ),
            "Pass %": st.column_config.NumberColumn("Pass %", format="%.1f%%"),
        },
    )


def _case_index(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c.get("name", ""): c for c in report.get("cases", [])}


def _render_per_case_matrix(
    a_label: str,
    a_report: dict[str, Any],
    b_label: str,
    b_report: dict[str, Any],
) -> None:
    """Two-column score matrix with delta — rows = case names sorted by |delta|."""
    a_idx = _case_index(a_report)
    b_idx = _case_index(b_report)
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


def _render_drill_in(
    a_label: str,
    a_report: dict[str, Any],
    b_label: str,
    b_report: dict[str, Any],
) -> None:
    a_idx = _case_index(a_report)
    b_idx = _case_index(b_report)
    names = sorted(set(a_idx) | set(b_idx))
    if not names:
        return
    pick = st.selectbox(t("case"), names, key="hist_drill_case")
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


def _render_single_detail(
    report_path: Path,
    report: dict[str, Any],
    meta: dict[str, Any],
) -> None:
    """Inline case-by-case view for a single run — same content as 1_Reports.

    Cases sort by score ascending so the worst (most-likely-to-investigate)
    cases land at the top.
    """
    pr_num = meta.get("pr_number")
    title = meta.get("pr_title") or "(no title)"
    rate, passed, total = _pass_rate(report)

    head_cols = st.columns([3, 1, 1, 1])
    with head_cols[0]:
        if pr_num:
            st.markdown(f"### #{pr_num} — {title}")
        else:
            st.markdown(f"### {meta.get('trigger') or 'manual'} — {title}")
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

    # Quick links row
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
    cases.sort(key=lambda c: c.get("score", 1.0))  # worst first

    failed = [c for c in cases if c.get("status") != "passed_threshold"]
    passed_cases = [c for c in cases if c.get("status") == "passed_threshold"]

    if failed:
        st.markdown(f"#### ❌ {len(failed)} below threshold")
        for case in failed:
            _render_case_expander(case)
    if passed_cases:
        st.markdown(f"#### ✅ {len(passed_cases)} passed")
        for case in passed_cases:
            _render_case_expander(case)


def _render_case_expander(case: dict[str, Any]) -> None:
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


def _render_topic_tab(label: str, subdir: str) -> None:
    items = _list_cached(subdir)
    if not items:
        st.info(
            f"No cached {label} reports yet under `{CACHE_DIR / subdir}/`.\n\n"
            f"This populates the first time CI runs the corresponding label "
            f"on a PR (or on the VPS via `make regression-promote-baseline` "
            f"for lite-30)."
        )
        return

    st.markdown(f"**{len(items)} {label} runs cached.**")
    _render_index_table(items)
    st.divider()

    labels = [_row_label(meta, report) for _, report, meta in items]
    picked = st.multiselect(
        f"Pick a {label} run (1 = single-report detail, 2 = diff):",
        options=list(range(len(items))),
        format_func=lambda i: labels[i],
        max_selections=2,
        key=f"hist_pick_{subdir}",
    )

    if not picked:
        st.info("Pick 1 row to see its case-by-case detail, or 2 rows to see the diff.")
        return

    if len(picked) == 1:
        path, report, meta = items[picked[0]]
        _render_single_detail(path, report, meta)
        return

    # len(picked) == 2 — diff path

    # Order by created_at: older = baseline, newer = candidate.
    a_idx, b_idx = sorted(
        picked,
        key=lambda i: items[i][2].get("created_at") or items[i][1].get("summary", {}).get("timestamp", ""),
    )
    baseline_path, baseline_report, baseline_meta = items[a_idx]
    candidate_path, candidate_report, candidate_meta = items[b_idx]

    a_short = f"baseline · {_short_label(baseline_meta)}"
    b_short = f"candidate · {_short_label(candidate_meta)}"

    st.subheader("Diff (overall)")
    try:
        md = render_diff_md(baseline_path, candidate_path, baseline_report, candidate_report)
        st.markdown(md)
    except Exception as exc:
        st.error(f"regression_diff.render failed: {exc}")

    st.divider()
    st.subheader("Per-case scores")
    _render_per_case_matrix(a_short, baseline_report, b_short, candidate_report)

    st.divider()
    st.subheader("Drill into a case")
    _render_drill_in(a_short, baseline_report, b_short, candidate_report)


def _short_label(meta: dict[str, Any]) -> str:
    pr = meta.get("pr_number")
    if pr:
        return f"#{pr}"
    return (meta.get("pr_branch") or meta.get("trigger") or "manual")


def main() -> None:
    lang_toggle()
    st.title("📈 Regression History")
    st.caption(
        "Every cached regression run, with PR / branch / actor metadata. "
        "Pick exactly two from a tab to see overall + per-case diff."
    )

    if not CACHE_DIR.exists():
        st.error(
            f"Cache dir not found at `{CACHE_DIR}`. "
            f"This page only renders meaningful data on the VPS where CI runs. "
            f"See `docs/self-hosted-runner-setup.md` step 7."
        )
        return

    tab_lite, tab_full = st.tabs([TOPICS["lite"][0], TOPICS["full"][0]])
    with tab_lite:
        _render_topic_tab(*TOPICS["lite"])
    with tab_full:
        _render_topic_tab(*TOPICS["full"])


main()
