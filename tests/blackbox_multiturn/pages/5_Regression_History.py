"""Regression history — PR-aware index of every CI / manual regression run.

Each row corresponds to one cached report under
`/opt/pawly/regression-cache/reports-{light-30,full-223}/<MODEL>/`. Pick
exactly two rows to see:
  - Overall pass-rate delta + verdict (via utils.regression_diff.render)
  - Per-case score matrix (rows = test cases, columns = the two reports)
  - Drill-into-a-case side-by-side reasoning

Reads PR metadata from the `.meta.json` sidecar written by the CI workflow
(or by `make regression-promote-baseline` for manual runs).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import streamlit as st

REPO_ROOT = Path(__file__).parent.parent.parent.parent
BLACKBOX_DIR = Path(__file__).parent.parent
CACHE_DIR = Path("/opt/pawly/regression-cache")

for _p in (str(REPO_ROOT), str(BLACKBOX_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lang import lang_toggle  # noqa: E402
from utils.regression_view import (  # noqa: E402
    humanize_when,
    pass_rate,
    render_diff_section,
    render_single_detail,
)

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


def _row_label(meta: dict[str, Any], report: dict[str, Any]) -> str:
    pr = meta.get("pr_number")
    title = (meta.get("pr_title") or "(no title)").strip()
    rate, passed, total = pass_rate(report)
    pr_disp = f"#{pr}" if pr else (meta.get("pr_branch") or meta.get("trigger") or "manual")
    if len(title) > 60:
        title = title[:60] + "…"
    return f"{pr_disp}  ·  {title}  ·  {rate:.1f}% ({passed}/{total})"


def _render_index_table(items: list[tuple[Path, dict[str, Any], dict[str, Any]]]) -> None:
    rows: list[dict[str, Any]] = []
    for path, report, meta in items:
        rate, passed, total = pass_rate(report)
        pr_num = meta.get("pr_number")
        pr_disp = f"#{pr_num}" if pr_num else (meta.get("trigger") or "—")
        rows.append({
            "PR": pr_disp,
            "Title": (meta.get("pr_title") or "—")[:80],
            "Branch": meta.get("pr_branch") or "—",
            "Model": meta.get("model") or "—",
            "Pass %": round(rate, 1),
            "Cases": f"{passed}/{total}",
            "When": humanize_when(meta, report),
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
        _, report, meta = items[picked[0]]
        render_single_detail(report, meta)
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

    render_diff_section(
        baseline_path, baseline_report,
        candidate_path, candidate_report,
        a_label=a_short, b_label=b_short,
        key_prefix=f"hist_{subdir}",
    )


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
