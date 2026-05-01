"""Single-report browser — case list + transcripts."""

import json
from pathlib import Path
from typing import Any

import streamlit as st

st.set_page_config(page_title="Reports", page_icon="📋", layout="wide")

RESULTS_DIR = Path(__file__).parent.parent / "results"


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
        st.title("📋 Report Detail")
    with col_selector:
        reports = get_available_reports()
        if reports:
            choice = st.selectbox(
                "Select Report",
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
    c1.metric("Total Cases", total)
    c2.metric("Passed", passed)
    c3.metric("Failed", failed)
    c4.metric("Pass Rate", f"{pass_rate:.1f}%")
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
    c1.metric("Score", f"{score:.2f}")
    c2.metric("Threshold", f"{threshold:.2f}")
    c3.metric("Turn Count", turn_count)

    color = "green" if status == "passed_threshold" else "red"
    st.markdown(f"**Status:** :{color}[{status.replace('_', ' ').title()}]")
    st.divider()

    st.subheader("📝 Evaluation Reason")
    st.write(reason)
    st.divider()

    st.subheader("💬 Conversation Transcript")
    if not turns:
        st.info("No conversation turns available")
        return

    for i, turn in enumerate(turns):
        role = turn.get("role", "unknown")
        content = turn.get("content", "")
        if role == "user":
            st.markdown(f"**👤 User (Turn {i+1}):**")
            st.info(content)
        else:
            st.markdown(f"**🤖 Assistant (Turn {i+1}):**")
            clean = content.replace("<i>", "_").replace("</i>", "_")
            clean = clean.replace("<b>", "**").replace("</b>", "**")
            clean = clean.replace("<blockquote>", "").replace("</blockquote>", "")
            st.success(clean)
        if i < len(turns) - 1:
            st.markdown("---")


def main() -> None:
    reports = get_available_reports()
    if not reports:
        st.warning("No reports yet. Run tests first.")
        return

    if "selected_report" not in st.session_state:
        st.session_state.selected_report = reports[0]

    report = load_report(st.session_state.selected_report)
    summary = report.get("summary", {})
    cases = report.get("cases", [])

    render_summary(summary, st.session_state.selected_report)

    st.sidebar.title("🔍 Filters")
    status_filter = st.sidebar.radio("Status", ["All", "Passed", "Failed"], index=0)
    min_score = st.sidebar.slider("Minimum Score", 0.0, 1.0, 0.0, 0.1)
    sort_by = st.sidebar.selectbox(
        "Sort By", ["Name", "Score (High to Low)", "Score (Low to High)", "Turn Count"]
    )

    filtered = cases
    if status_filter == "Passed":
        filtered = [c for c in filtered if c.get("status") == "passed_threshold"]
    elif status_filter == "Failed":
        filtered = [c for c in filtered if c.get("status") == "below_threshold"]
    filtered = [c for c in filtered if c.get("score", 0) >= min_score]

    if sort_by == "Score (High to Low)":
        filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
    elif sort_by == "Score (Low to High)":
        filtered.sort(key=lambda x: x.get("score", 0))
    elif sort_by == "Turn Count":
        filtered.sort(key=lambda x: x.get("turn_count", 0), reverse=True)
    else:
        filtered.sort(key=lambda x: x.get("name", ""))

    st.markdown(f"### Showing {len(filtered)} of {len(cases)} test cases")

    if "selected_case_index" not in st.session_state:
        st.session_state.selected_case_index = 0
    if st.session_state.selected_case_index >= len(filtered):
        st.session_state.selected_case_index = 0

    if not filtered:
        st.warning("No test cases match the current filters.")
        return

    left, right = st.columns([1, 2])
    with left:
        st.markdown("#### Test Cases")
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
