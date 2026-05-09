"""Compare regression runs — Lite-30 / Full-223 tabs.

Same UX as the Regression History page, but sourced from the local
`results/` directory (where the Run Tests page writes new reports), so
this is the right page for "compare two of my recent runs".

Rows in each tab:
  - 1 picked → single-report case-by-case detail
  - 2 picked → diff (overall verdict + per-case matrix + drill-in)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import streamlit as st

REPO_ROOT = Path(__file__).parent.parent.parent.parent
BLACKBOX_DIR = Path(__file__).parent.parent
RESULTS_DIR = BLACKBOX_DIR / "results"

for _p in (str(REPO_ROOT), str(BLACKBOX_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lang import lang_toggle, t  # noqa: E402
from utils import parse_filename  # noqa: E402
from utils.regression_view import (  # noqa: E402
    humanize_when,
    pass_rate,
    render_diff_section,
    render_single_detail,
)

st.set_page_config(page_title="Compare", page_icon="⚖️", layout="wide")

# (display label, filter predicate over filename)
TOPICS: dict[str, tuple[str, callable]] = {
    "lite": (
        "Lite-30",
        lambda name: name.startswith("multiturn_pawly_regression_light_30_report_"),
    ),
    "full": (
        "Full-223",
        lambda name: (
            name.startswith("multiturn_pawly_regression_report_")
            and "light_30" not in name
        ),
    ),
}


def _load_report(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _list_reports(filter_fn) -> list[tuple[Path, dict[str, Any], dict[str, Any]]]:
    """Return [(path, report_dict, derived_meta)] for matching reports in
    `results/`, sorted newest first by parsed timestamp.

    Meta is derived from the filename: {topic, model, timestamp}. No PR/Actor
    info — those columns just stay blank for local runs.
    """
    if not RESULTS_DIR.exists():
        return []

    items: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []
    for path in RESULTS_DIR.glob("multiturn_pawly_regression*_report_*.json"):
        if not filter_fn(path.name):
            continue
        report = _load_report(path)
        if report is None:
            continue
        parsed = parse_filename(path.name)
        meta: dict[str, Any] = {
            "topic": parsed["topic"],
            "model": parsed["model"],
            "timestamp": parsed["timestamp"],
            "title": path.name,
            # Treat the locally-detected timestamp as `created_at` so
            # humanize_when picks it up.
            "created_at": (
                report.get("summary", {}).get("timestamp", "") or parsed["timestamp"]
            ),
        }
        items.append((path, report, meta))

    def _key(item: tuple[Path, dict[str, Any], dict[str, Any]]) -> str:
        _, report, meta = item
        return meta.get("created_at") or ""

    items.sort(key=_key, reverse=True)
    return items


def _row_label(meta: dict[str, Any], report: dict[str, Any]) -> str:
    rate, passed, total = pass_rate(report)
    model = meta.get("model") or "?"
    when = humanize_when(meta, report)
    return f"{model}  ·  {when}  ·  {rate:.1f}% ({passed}/{total})"


def _render_index_table(items: list[tuple[Path, dict[str, Any], dict[str, Any]]]) -> None:
    rows: list[dict[str, Any]] = []
    for _, report, meta in items:
        rate, passed, total = pass_rate(report)
        rows.append({
            "Model": meta.get("model") or "—",
            "Pass %": round(rate, 1),
            "Cases": f"{passed}/{total}",
            "When": humanize_when(meta, report),
            "File": meta.get("title") or "—",
        })
    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pass %": st.column_config.NumberColumn("Pass %", format="%.1f%%"),
        },
    )


def _render_topic_tab(label: str, filter_fn) -> None:
    items = _list_reports(filter_fn)
    if not items:
        st.info(
            f"No {label} reports under `{RESULTS_DIR}/` yet. "
            f"Trigger a run from the **Run Tests** page."
        )
        return

    st.markdown(f"**{len(items)} {label} runs.**")
    _render_index_table(items)
    st.divider()

    labels = [_row_label(meta, report) for _, report, meta in items]
    picked = st.multiselect(
        f"Pick a {label} run (1 = single-report detail, 2 = diff):",
        options=list(range(len(items))),
        format_func=lambda i: labels[i],
        max_selections=2,
        key=f"compare_pick_{label}",
    )

    if not picked:
        st.info("Pick 1 row to see its case-by-case detail, or 2 rows to see the diff.")
        return

    if len(picked) == 1:
        _, report, meta = items[picked[0]]
        render_single_detail(report, meta)
        return

    # len(picked) == 2 — diff. Older = baseline, newer = candidate.
    a_idx, b_idx = sorted(
        picked,
        key=lambda i: items[i][2].get("created_at") or "",
    )
    baseline_path, baseline_report, baseline_meta = items[a_idx]
    candidate_path, candidate_report, candidate_meta = items[b_idx]

    a_short = f"baseline · {baseline_meta.get('model') or '?'} {humanize_when(baseline_meta, baseline_report)}"
    b_short = f"candidate · {candidate_meta.get('model') or '?'} {humanize_when(candidate_meta, candidate_report)}"

    render_diff_section(
        baseline_path, baseline_report,
        candidate_path, candidate_report,
        a_label=a_short, b_label=b_short,
        key_prefix=f"compare_{label}",
    )


def main() -> None:
    lang_toggle()
    st.title(t("compare_title"))
    st.caption(
        "Compare two regression runs — overall verdict, per-case Δ matrix, "
        "case-by-case drill-in."
    )

    tab_lite, tab_full = st.tabs([TOPICS["lite"][0], TOPICS["full"][0]])
    with tab_lite:
        _render_topic_tab(*TOPICS["lite"])
    with tab_full:
        _render_topic_tab(*TOPICS["full"])


main()
