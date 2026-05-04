"""Single-report browser — case list + transcripts."""

import json
import sys
from pathlib import Path
from typing import Any

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from lang import get_lang, lang_toggle, t  # noqa: E402
from utils import parse_filename  # noqa: E402
from utils.export import generate_csv, translate_for_display  # noqa: E402

st.set_page_config(page_title="Reports", page_icon="📋", layout="wide")

RESULTS_DIR = Path(__file__).parent.parent / "results"
CACHE_PATH = RESULTS_DIR / "translation_cache.json"

_SORT_KEYS = ["sort_name", "sort_score_high", "sort_score_low", "sort_turns"]
_STATUS_KEYS = ["status_all", "status_passed", "status_failed"]


def get_available_reports() -> list[str]:
    if not RESULTS_DIR.exists():
        return []
    # dict.fromkeys deduplicates while preserving order (glob can yield the
    # same path twice on some filesystems via symlinks or aliases).
    names = (
        f.name
        for f in RESULTS_DIR.glob("*.json")
        if f.name != "translation_cache.json"
    )
    return sorted(dict.fromkeys(names))


def load_report(filename: str) -> dict[str, Any]:
    path = RESULTS_DIR / filename
    if not path.exists():
        st.error(f"Report not found: {path}")
        st.stop()
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def get_status_emoji(status: str) -> str:
    return "✅" if status == "passed_threshold" else "❌"


def render_summary(summary: dict[str, Any], selected: str, reports: list[str]) -> None:
    col_title, col_selector, col_export = st.columns([2, 1, 1])
    with col_title:
        st.title(t("report_title"))
    with col_selector:
        if reports:
            choice = st.selectbox(
                t("select_report"),
                reports,
                index=reports.index(selected) if selected in reports else 0,
                key="report_selector",
            )
            if choice != selected:
                st.session_state.selected_report = choice
                st.rerun()
    with col_export:
        st.write("")  # align button vertically with selector
        if st.button("📥 Export CSV", use_container_width=True, key="open_export_btn"):
            st.session_state["show_export_panel"] = not st.session_state.get(
                "show_export_panel", False
            )
            st.session_state.pop("export_ready", None)

    total = summary.get("total_cases", 0)
    passed = summary.get("passed_threshold", 0)
    failed = summary.get("below_threshold", 0)
    pass_rate = (passed / total * 100) if total > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("total_cases"), total)
    c2.metric(t("passed"), passed)
    c3.metric(t("failed"), failed)
    c4.metric(t("pass_rate"), f"{pass_rate:.1f}%")
    st.divider()


def render_case_details(case: dict[str, Any]) -> None:
    name = case.get("name", "Unknown")
    status = case.get("status", "unknown")
    score = case.get("score", 0)
    threshold = case.get("threshold", 0.7)
    reason = case.get("reason", "No reason provided")
    turn_count = case.get("turn_count", 0)
    turns = case.get("turns", [])

    st.header(f"{get_status_emoji(status)} {name}")
    c1, c2, c3 = st.columns(3)
    c1.metric(t("score"), f"{score:.2f}")
    c2.metric(t("threshold"), f"{threshold:.2f}")
    c3.metric(t("turn_count"), turn_count)

    color = "green" if status == "passed_threshold" else "red"
    status_label = t("status_passed_label") if status == "passed_threshold" else t("status_failed_label")
    st.markdown(f"**{t('status')}:** :{color}[{status_label}]")
    st.divider()

    if get_lang() == "zh":
        reason = translate_for_display(reason, CACHE_PATH)

    st.subheader(t("eval_reason"))
    st.write(reason)
    st.divider()

    st.subheader(t("transcript"))
    if not turns:
        st.info(t("no_turns"))
        return

    for i, turn in enumerate(turns):
        role = turn.get("role", "unknown")
        content = turn.get("content", "")
        if get_lang() == "zh":
            content = translate_for_display(content, CACHE_PATH)
        if role == "user":
            st.markdown(f"**{t('user_turn', i=i+1)}**")
            st.info(content)
        else:
            st.markdown(f"**{t('assistant_turn', i=i+1)}**")
            clean = content.replace("<i>", "_").replace("</i>", "_")
            clean = clean.replace("<b>", "**").replace("</b>", "**")
            clean = clean.replace("<blockquote>", "").replace("</blockquote>", "")
            st.success(clean)
        if i < len(turns) - 1:
            st.markdown("---")


def _build_report_label(fname: str) -> str:
    """Return a display label for a report file: name + pass rate."""
    try:
        r = load_report(fname)
        s = r.get("summary", {})
        total = s.get("total_cases", 0)
        passed = s.get("passed_threshold", 0)
        rate = (passed / total * 100) if total else 0.0
        return f"{fname}  —  {rate:.1f}% pass ({passed}/{total})"
    except Exception:
        return fname


def _render_export_panel(all_reports: list[str]) -> None:
    """Multi-select panel for choosing reports and triggering CSV export."""
    with st.container(border=True):
        header_col, close_col = st.columns([5, 1])
        with header_col:
            st.subheader("📥 Export Reports to CSV")
        with close_col:
            if st.button("✕ Close", key="close_export_btn"):
                st.session_state["show_export_panel"] = False
                st.session_state.pop("export_ready", None)
                st.rerun()

        label_map = {f: _build_report_label(f) for f in all_reports}

        selected_exports: list[str] = st.multiselect(
            "Select one or more reports to export:",
            options=all_reports,
            format_func=lambda f: label_map.get(f, f),
            default=[],
            key="export_report_multiselect",
        )

        export_col, _ = st.columns([1, 3])
        with export_col:
            export_clicked = st.button(
                "Export Selected",
                disabled=len(selected_exports) == 0,
                type="primary",
                key="do_export_btn",
            )

        if export_clicked and selected_exports:
            # Deduplicate selection order-preservingly; duplicate entries would
            # produce duplicate rows in the CSV.
            unique_exports = list(dict.fromkeys(selected_exports))
            progress_bar = st.progress(0.0, text="Starting export…")

            def _on_progress(frac: float, msg: str) -> None:
                progress_bar.progress(min(frac, 1.0), text=msg)

            reports_data = [
                (fname.replace(".json", ""), load_report(fname))
                for fname in unique_exports
            ]
            try:
                csv_bytes = generate_csv(reports_data, CACHE_PATH, on_progress=_on_progress)
                out_name = (
                    f"{unique_exports[0].replace('.json', '')}.csv"
                    if len(unique_exports) == 1
                    else f"export_{len(unique_exports)}_reports.csv"
                )
                st.session_state["export_ready"] = {
                    "data": csv_bytes,
                    "filename": out_name,
                }
            except Exception as exc:
                st.error(f"Export failed: {exc}")

        if "export_ready" in st.session_state:
            ready = st.session_state["export_ready"]
            size_kb = len(ready["data"]) // 1024
            st.success(f"Ready — {size_kb} KB  •  {ready['filename']}")
            st.download_button(
                label="⬇️ Download CSV",
                data=ready["data"],
                file_name=ready["filename"],
                mime="text/csv",
                key="download_csv_btn",
            )


def main() -> None:
    lang_toggle()

    all_reports = get_available_reports()
    if not all_reports:
        st.warning(t("no_reports"))
        return

    # Parse filenames to extract unique models and categories for filtering
    parsed = {fname: parse_filename(fname) for fname in all_reports}
    models = sorted({p["model"] for p in parsed.values() if p["model"]})
    categories = sorted({p["topic"] for p in parsed.values() if p["topic"]})

    # Report-level filters in sidebar
    st.sidebar.subheader(t("report_filters"))
    sel_category = st.sidebar.selectbox(
        t("filter_by_category"),
        options=[""] + categories,
        format_func=lambda x: t("all_categories") if x == "" else x,
        key="filter_category",
    )
    sel_model = st.sidebar.selectbox(
        t("filter_by_model"),
        options=[""] + models,
        format_func=lambda x: t("all_models") if x == "" else x,
        key="filter_model",
    )
    st.sidebar.divider()

    reports = [
        fname for fname in all_reports
        if (not sel_category or parsed[fname]["topic"] == sel_category)
        and (not sel_model or parsed[fname]["model"] == sel_model)
    ]

    if not reports:
        st.warning(t("no_reports"))
        return

    if "selected_report" not in st.session_state or st.session_state.selected_report not in reports:
        st.session_state.selected_report = reports[0]

    report = load_report(st.session_state.selected_report)
    summary = report.get("summary", {})
    cases = report.get("cases", [])

    render_summary(summary, st.session_state.selected_report, reports)

    if st.session_state.get("show_export_panel"):
        _render_export_panel(reports)

    st.sidebar.title(t("filters"))
    status_idx = st.sidebar.radio(
        t("status"),
        options=range(len(_STATUS_KEYS)),
        format_func=lambda i: t(_STATUS_KEYS[i]),
        index=0,
        key="status_filter",
    )
    status_key = _STATUS_KEYS[status_idx]

    min_score = st.sidebar.slider(t("minimum_score"), 0.0, 1.0, 0.0, 0.1)

    sort_idx = st.sidebar.selectbox(
        t("sort_by"),
        options=range(len(_SORT_KEYS)),
        format_func=lambda i: t(_SORT_KEYS[i]),
        key="sort_by_select",
    )
    sort_key = _SORT_KEYS[sort_idx]

    filtered = cases
    if status_key == "status_passed":
        filtered = [c for c in filtered if c.get("status") == "passed_threshold"]
    elif status_key == "status_failed":
        filtered = [c for c in filtered if c.get("status") == "below_threshold"]
    filtered = [c for c in filtered if c.get("score", 0) >= min_score]

    if sort_key == "sort_score_high":
        filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
    elif sort_key == "sort_score_low":
        filtered.sort(key=lambda x: x.get("score", 0))
    elif sort_key == "sort_turns":
        filtered.sort(key=lambda x: x.get("turn_count", 0), reverse=True)
    else:
        filtered.sort(key=lambda x: x.get("name", ""))

    st.markdown(f"### {t('showing_cases', n=len(filtered), total=len(cases))}")

    if "selected_case_index" not in st.session_state:
        st.session_state.selected_case_index = 0
    if st.session_state.selected_case_index >= len(filtered):
        st.session_state.selected_case_index = 0

    if not filtered:
        st.warning(t("no_cases_match"))
        return

    left, right = st.columns([1, 2])
    with left:
        st.markdown(f"#### {t('test_cases')}")
        for i, case in enumerate(filtered):
            is_selected = i == st.session_state.selected_case_index
            label = (
                f"{get_status_emoji(case.get('status', ''))} {case.get('name', '?')}\n"
                f"📊 {case.get('score', 0):.2f} / {case.get('threshold', 0.7):.2f}"
            )
            if st.button(
                label,
                key=f"case_{i}",
                type=("primary" if is_selected else "secondary"),
                use_container_width=True,
            ):
                st.session_state.selected_case_index = i
                st.rerun()
    with right:
        render_case_details(filtered[st.session_state.selected_case_index])


main()
