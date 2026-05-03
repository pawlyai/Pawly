"""Single-report browser — case list + transcripts."""

import json
import sys
from pathlib import Path
from typing import Any

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from lang import lang_toggle, t  # noqa: E402

st.set_page_config(page_title="Reports", page_icon="📋", layout="wide")

RESULTS_DIR = Path(__file__).parent.parent / "results"

_SORT_KEYS = ["sort_name", "sort_score_high", "sort_score_low", "sort_turns"]
_STATUS_KEYS = ["status_all", "status_passed", "status_failed"]


def get_available_reports() -> list[str]:
    if not RESULTS_DIR.exists():
        return []
    return sorted([f.name for f in RESULTS_DIR.glob("*.json")])


def load_report(filename: str) -> dict[str, Any]:
    path = RESULTS_DIR / filename
    if not path.exists():
        st.error(f"Report not found: {path}")
        st.stop()
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def get_status_emoji(status: str) -> str:
    return "✅" if status == "passed_threshold" else "❌"


def render_summary(summary: dict[str, Any], selected: str) -> None:
    col_title, col_selector = st.columns([2, 1])
    with col_title:
        st.title(t("report_title"))
    with col_selector:
        reports = get_available_reports()
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


def main() -> None:
    lang_toggle()

    reports = get_available_reports()
    if not reports:
        st.warning(t("no_reports"))
        return

    if "selected_report" not in st.session_state:
        st.session_state.selected_report = reports[0]

    report = load_report(st.session_state.selected_report)
    summary = report.get("summary", {})
    cases = report.get("cases", [])

    render_summary(summary, st.session_state.selected_report)

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
    with right:
        render_case_details(filtered[st.session_state.selected_case_index])


main()
