"""Compare regression runs — Lite-30 / Full-223 tabs.

Unified view of every regression report we have:
  - `tests/blackbox_multiturn/results/*.json`  (Streamlit Run Tests page)
  - `/opt/pawly/regression-cache/reports-{light-30,full-223}/<MODEL>/*.json`
    (historical CI runs; this dir doesn't grow anymore now that CI is gone,
    but the past data stays visible.)

Per tab:
  - 1 row picked → single-report case-by-case detail
  - 2 rows picked → diff (overall verdict + per-case Δ matrix + drill-in)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

import streamlit as st

REPO_ROOT = Path(__file__).parent.parent.parent.parent
BLACKBOX_DIR = Path(__file__).parent.parent
RESULTS_DIR = BLACKBOX_DIR / "results"
CACHE_DIR = Path("/opt/pawly/regression-cache")

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

# (display label, filename filter for results/, cache subdir name)
TOPICS: dict[str, tuple[str, Callable[[str], bool], str]] = {
    "lite": (
        "Lite-30",
        lambda name: name.startswith("multiturn_pawly_regression_light_30_report_"),
        "reports-light-30",
    ),
    "full": (
        "Full-223",
        lambda name: (
            name.startswith("multiturn_pawly_regression_report_")
            and "light_30" not in name
        ),
        "reports-full-223",
    ),
}


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _local_meta(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_filename(path.name)
    return {
        "_source": "local",
        "topic": parsed["topic"],
        "model": parsed["model"],
        "timestamp": parsed["timestamp"],
        "title": path.name,
        "created_at": (
            report.get("summary", {}).get("timestamp", "") or parsed["timestamp"]
        ),
    }


def _ci_meta(path: Path, report: dict[str, Any], model_dir: str) -> dict[str, Any]:
    """Read CI-cached report's `.meta.json` sidecar for PR/Actor metadata."""
    sidecar = path.with_name(path.stem + ".meta.json")
    meta: dict[str, Any] = {}
    if sidecar.exists():
        loaded = _load_json(sidecar) or {}
        meta.update(loaded)
    meta.setdefault("model", model_dir)
    meta["_source"] = "ci"
    if not meta.get("created_at"):
        meta["created_at"] = report.get("summary", {}).get("timestamp", "")
    return meta


def _list_reports(
    filter_fn: Callable[[str], bool],
    cache_subdir: str,
) -> list[tuple[Path, dict[str, Any], dict[str, Any]]]:
    """Return [(path, report, meta)] from both sources, sorted newest first.

    Sources:
      - `results/` filtered by filename pattern (Streamlit-triggered runs)
      - `<CACHE_DIR>/<cache_subdir>/<model>/*.json`        (CI history)

    Items aren't deduped: a report present in both shows twice. The
    `_source` field on meta lets the UI tell them apart.
    """
    items: list[tuple[Path, dict[str, Any], dict[str, Any]]] = []

    if RESULTS_DIR.exists():
        for path in RESULTS_DIR.glob("multiturn_pawly_regression*_report_*.json"):
            if not filter_fn(path.name):
                continue
            report = _load_json(path)
            if report is None:
                continue
            items.append((path, report, _local_meta(path, report)))

    cache_root = CACHE_DIR / cache_subdir
    if cache_root.exists():
        for model_dir in sorted(cache_root.iterdir()):
            if not model_dir.is_dir():
                continue
            for path in model_dir.glob("*.json"):
                if path.name.endswith(".meta.json"):
                    continue
                report = _load_json(path)
                if report is None:
                    continue
                items.append((path, report, _ci_meta(path, report, model_dir.name)))

    items.sort(key=lambda it: it[2].get("created_at") or "", reverse=True)
    return items


def _source_disp(meta: dict[str, Any]) -> str:
    """One-cell label: 'local', 'PR #41', 'main', etc."""
    if meta.get("_source") == "local":
        return "local"
    pr = meta.get("pr_number")
    if pr:
        return f"PR #{pr}"
    return meta.get("pr_branch") or meta.get("trigger") or "ci"


def _row_label(meta: dict[str, Any], report: dict[str, Any]) -> str:
    rate, passed, total = pass_rate(report)
    src = _source_disp(meta)
    model = meta.get("model") or "?"
    when = humanize_when(meta, report)
    return f"{src}  ·  {model}  ·  {when}  ·  {rate:.1f}% ({passed}/{total})"


def _render_index_table(items: list[tuple[Path, dict[str, Any], dict[str, Any]]]) -> None:
    rows: list[dict[str, Any]] = []
    for _, report, meta in items:
        rate, passed, total = pass_rate(report)
        rows.append({
            "Source": _source_disp(meta),
            "Model": meta.get("model") or "—",
            "Pass %": round(rate, 1),
            "Cases": f"{passed}/{total}",
            "When": humanize_when(meta, report),
            "Actor": meta.get("actor") or "—",
            "PR link": meta.get("pr_url") or "",
        })
    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pass %": st.column_config.NumberColumn("Pass %", format="%.1f%%"),
            "PR link": st.column_config.LinkColumn(
                "PR link",
                display_text="open",
                help="Opens the GitHub PR (CI rows only).",
            ),
        },
    )


def _render_topic_tab(label: str, filter_fn: Callable[[str], bool], cache_subdir: str) -> None:
    items = _list_reports(filter_fn, cache_subdir)
    if not items:
        st.info(
            f"No {label} reports yet — neither in `{RESULTS_DIR}/` "
            f"nor `{CACHE_DIR / cache_subdir}/`. Trigger a run from the "
            f"**Run Tests** page."
        )
        return

    n_local = sum(1 for _, _, m in items if m.get("_source") == "local")
    n_ci = len(items) - n_local
    st.markdown(f"**{len(items)} {label} runs** ({n_local} local, {n_ci} from CI cache).")
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

    a_short = (
        f"baseline · {_source_disp(baseline_meta)} · "
        f"{baseline_meta.get('model') or '?'} {humanize_when(baseline_meta, baseline_report)}"
    )
    b_short = (
        f"candidate · {_source_disp(candidate_meta)} · "
        f"{candidate_meta.get('model') or '?'} {humanize_when(candidate_meta, candidate_report)}"
    )

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
        "case-by-case drill-in. Sources: Streamlit-triggered runs in `results/` "
        "+ historical CI cache."
    )

    tab_lite, tab_full = st.tabs([TOPICS["lite"][0], TOPICS["full"][0]])
    with tab_lite:
        _render_topic_tab(*TOPICS["lite"])
    with tab_full:
        _render_topic_tab(*TOPICS["full"])


main()
