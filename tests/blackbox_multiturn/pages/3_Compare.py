"""Side-by-side comparison of multiple reports."""

import json
from pathlib import Path
from typing import Any

import streamlit as st

st.set_page_config(page_title="Compare", page_icon="⚖️", layout="wide")

RESULTS_DIR = Path(__file__).parent.parent / "results"


def list_reports() -> list[str]:
    if not RESULTS_DIR.exists():
        return []
    return sorted(
        (f.name for f in RESULTS_DIR.glob("*.json")),
        reverse=True,
    )


def load(filename: str) -> dict[str, Any]:
    with (RESULTS_DIR / filename).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_filename(name: str) -> dict[str, str]:
    stem = name.replace(".json", "")
    parts = stem.split("_report_")
    topic = parts[0] if parts else ""
    rest = parts[1] if len(parts) > 1 else ""
    if "_v" in rest:
        model, ts = rest.rsplit("_v", 1)
    else:
        model, ts = rest, ""
    return {"topic": topic, "model": model, "timestamp": ts}


def main() -> None:
    st.title("⚖️ Compare Runs")
    st.caption("Pick 2–6 reports to compare pass rates and per-case scores.")

    reports = list_reports()
    if not reports:
        st.warning("No reports yet — run tests first.")
        return

    selected = st.multiselect(
        "Reports to compare",
        reports,
        default=reports[:2],
        max_selections=6,
    )

    if len(selected) < 2:
        st.info("Pick at least two reports.")
        return

    loaded = [(name, load(name)) for name in selected]

    # ── Summary table ────────────────────────────────────────────────────────
    st.subheader("Summary")
    summary_rows: list[dict[str, Any]] = []
    for name, report in loaded:
        meta = parse_filename(name)
        s = report.get("summary", {})
        total = s.get("total_cases", 0)
        passed = s.get("passed_threshold", 0)
        rate = (passed / total * 100) if total else 0
        avg_score = (
            sum(c.get("score", 0) for c in report.get("cases", [])) / len(report["cases"])
            if report.get("cases") else 0
        )
        summary_rows.append({
            "Report": name,
            "Topic": meta["topic"],
            "Model": meta["model"],
            "Cases": total,
            "Passed": passed,
            "Pass Rate (%)": round(rate, 1),
            "Avg Score": round(avg_score, 3),
        })
    st.dataframe(summary_rows, use_container_width=True, hide_index=True)

    # ── Pass rate bar chart ──────────────────────────────────────────────────
    st.subheader("Pass rate")
    chart_data = [
        {"Run": f"{parse_filename(name)['model']}\n({parse_filename(name)['timestamp']})",
         "Pass Rate (%)": row["Pass Rate (%)"]}
        for name, row in zip(selected, summary_rows)
    ]
    try:
        import altair as alt
        chart_df = chart_data
        chart = alt.Chart(alt.Data(values=chart_df)).mark_bar().encode(
            x=alt.X("Run:N", sort=None),
            y=alt.Y("Pass Rate (%):Q", scale=alt.Scale(domain=[0, 100])),
            color="Run:N",
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)
    except ImportError:
        st.bar_chart({r["Run"]: r["Pass Rate (%)"] for r in chart_data})

    # ── Per-case score matrix ────────────────────────────────────────────────
    st.subheader("Per-case scores")
    case_names: set[str] = set()
    for _, report in loaded:
        for case in report.get("cases", []):
            case_names.add(case.get("name", ""))

    matrix_rows: list[dict[str, Any]] = []
    for case_name in sorted(case_names):
        row: dict[str, Any] = {"Case": case_name}
        for filename, report in loaded:
            meta = parse_filename(filename)
            label = f"{meta['model']}"
            match = next((c for c in report.get("cases", []) if c.get("name") == case_name), None)
            if match:
                row[label] = round(match.get("score", 0), 3)
            else:
                row[label] = None
        matrix_rows.append(row)
    st.dataframe(matrix_rows, use_container_width=True, hide_index=True)

    # ── Side-by-side reasoning per case ──────────────────────────────────────
    st.subheader("Drill into a case")
    case_pick = st.selectbox("Case", sorted(case_names))
    cols = st.columns(len(loaded))
    for col, (filename, report) in zip(cols, loaded):
        meta = parse_filename(filename)
        case = next((c for c in report.get("cases", []) if c.get("name") == case_pick), None)
        with col:
            st.markdown(f"**{meta['model']}**  \n_{meta['timestamp']}_")
            if not case:
                st.caption("Not in this report.")
                continue
            score = case.get("score", 0)
            threshold = case.get("threshold", 0.7)
            emoji = "✅" if score >= threshold else "❌"
            st.metric("Score", f"{emoji} {score:.2f}", delta=f"th: {threshold:.2f}")
            st.markdown("**Reason**")
            st.write(case.get("reason", "—"))


main()
