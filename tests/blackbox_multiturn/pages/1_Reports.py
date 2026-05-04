"""Single-report browser — case list + transcripts."""

import json
import os
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from lang import get_lang, lang_toggle, t  # noqa: E402
from utils import parse_filename  # noqa: E402
from utils.export import generate_csv, pre_translate_report, translate_for_display  # noqa: E402

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
    # ── Auto pre-translate all reports when panel first opens ─────────────────
    # Kick off a background thread the first time this panel is shown per session.
    # By the time the user selects reports and clicks Export, translations are
    # already cached and the export completes instantly.
    _PT_STATE = "_pretrans_bg"
    _api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if _api_key and _PT_STATE not in st.session_state and not st.session_state.get("_pretrans_complete"):
        _ptq: queue.Queue = queue.Queue()

        def _pretrans_all(_reports: list[str] = all_reports, _q: queue.Queue = _ptq, _ak: str = _api_key) -> None:
            for i, fname in enumerate(_reports):
                try:
                    pre_translate_report(RESULTS_DIR / fname, CACHE_PATH, _ak)
                except Exception:
                    pass
                _q.put(i + 1)
            _q.put("done")

        _ptt = threading.Thread(target=_pretrans_all, daemon=True)
        st.session_state[_PT_STATE] = {"q": _ptq, "total": len(all_reports), "done_count": 0}
        _ptt.start()

    with st.container(border=True):
        header_col, close_col = st.columns([5, 1])
        with header_col:
            st.subheader("📥 Export Reports to CSV")
        with close_col:
            if st.button("✕ Close", key="close_export_btn"):
                st.session_state["show_export_panel"] = False
                for _k in ("export_ready", "_export_thread", "_export_queue", "_export_progress",
                           _PT_STATE, "_pretrans_complete"):
                    st.session_state.pop(_k, None)
                st.rerun()

        # Show pre-translation status when it's running
        if _PT_STATE in st.session_state:
            _pts = st.session_state[_PT_STATE]
            _n, _tot = _pts["done_count"], _pts["total"]
            st.caption(f"⏳ Caching translations in background: {_n}/{_tot} reports — export will be instant once complete.")

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
            _is_running = "_export_thread" in st.session_state
            export_clicked = st.button(
                "Export Selected",
                disabled=len(selected_exports) == 0 or _is_running,
                type="primary",
                key="do_export_btn",
            )

        if export_clicked and selected_exports and not _is_running:
            # Deduplicate selection order-preservingly; duplicate entries would
            # produce duplicate rows in the CSV.
            unique_exports = list(dict.fromkeys(selected_exports))
            out_name = (
                f"{unique_exports[0].replace('.json', '')}.csv"
                if len(unique_exports) == 1
                else f"export_{len(unique_exports)}_reports.csv"
            )
            reports_data = [
                (fname.replace(".json", ""), load_report(fname))
                for fname in unique_exports
            ]
            st.session_state.pop("export_ready", None)
            _progress_q: queue.Queue = queue.Queue()

            def _run_export(
                _rd: list = reports_data,
                _name: str = out_name,
                _q: queue.Queue = _progress_q,
            ) -> None:
                def _on_prog(frac: float, msg: str) -> None:
                    _q.put(("progress", frac, msg))
                try:
                    result = generate_csv(_rd, CACHE_PATH, on_progress=_on_prog)
                    _q.put(("done", result, _name))
                except Exception as exc:
                    _q.put(("error", str(exc)))

            _t = threading.Thread(target=_run_export, daemon=True)
            st.session_state["_export_thread"] = _t
            st.session_state["_export_queue"] = _progress_q
            st.session_state["_export_progress"] = (0.0, "Starting export…")
            _t.start()
            st.rerun()

        # Poll the background export thread on every rerun
        if "_export_thread" in st.session_state:
            _q: queue.Queue = st.session_state["_export_queue"]
            _last_frac, _last_msg = st.session_state.get("_export_progress", (0.0, "Running…"))
            _result = None
            _error = None
            _done_name = None

            while True:
                try:
                    _item = _q.get_nowait()
                    if _item[0] == "done":
                        _result, _done_name = _item[1], _item[2]
                    elif _item[0] == "error":
                        _error = _item[1]
                    else:
                        _last_frac, _last_msg = _item[1], _item[2]
                        st.session_state["_export_progress"] = (_last_frac, _last_msg)
                except queue.Empty:
                    break

            if _result is not None:
                st.session_state["export_ready"] = {"data": _result, "filename": _done_name}
                for _k in ("_export_thread", "_export_queue", "_export_progress"):
                    st.session_state.pop(_k, None)
                st.rerun()
            elif _error is not None:
                st.error(f"Export failed: {_error}")
                for _k in ("_export_thread", "_export_queue", "_export_progress"):
                    st.session_state.pop(_k, None)
            else:
                st.progress(_last_frac, text=_last_msg)
                st.info("⏳ Export running in background — page refreshes automatically, you can keep browsing.")
                time.sleep(0.5)
                st.rerun()

        # Poll the pre-translation background thread (drives caption updates +
        # triggers a rerun every 0.5 s while pre-translation is in progress and
        # no export thread is competing for the rerun cycle).
        if _PT_STATE in st.session_state and "_export_thread" not in st.session_state:
            _pts2 = st.session_state[_PT_STATE]
            _ptq2: queue.Queue = _pts2["q"]
            while True:
                try:
                    _ptmsg = _ptq2.get_nowait()
                    if _ptmsg == "done":
                        del st.session_state[_PT_STATE]
                        st.session_state["_pretrans_complete"] = True
                        break
                    else:
                        _pts2["done_count"] = _ptmsg
                        st.session_state[_PT_STATE] = _pts2
                except queue.Empty:
                    break
            time.sleep(0.5)
            st.rerun()

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
