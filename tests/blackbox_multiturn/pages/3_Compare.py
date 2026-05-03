"""Side-by-side comparison of multiple reports."""

import json
import sys
from pathlib import Path
from typing import Any

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from lang import lang_toggle, t  # noqa: E402

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
    lang_toggle()

    st.title(t("compare_title"))
    st.caption(t("compare_caption"))

    reports = list_reports()
    if not reports:
        st.warning(t("no_reports_compare"))
        return

    selected = st.multiselect(
        t("reports_to_compare"),
        reports,
        default=reports[:2],
        max_selections=6,
    )

    if len(selected) < 2:
        st.info(t("pick_two"))
        return

    loaded = [(name, load(name)) for name in selected]

    # ── Summary table ────────────────────────────────────────────────────────
    st.subheader(t("summary"))
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
            t("col_report"): name,
            t("col_topic"): meta["topic"],
            t("col_model"): meta["model"],
            t("col_cases"): total,
            t("col_passed"): passed,
            t("col_pass_rate"): round(rate, 1),
            t("col_avg_score"): round(avg_score, 3),
        })
    st.dataframe(summary_rows, use_container_width=True, hide_index=True)

    # ── Pass rate bar chart ──────────────────────────────────────────────────
    st.subheader(t("pass_rate_chart"))
    pass_rate_col = t("col_pass_rate")
    chart_data = [
        {"Run": f"{parse_filename(name)['model']}\n({parse_filename(name)['timestamp']})",
         pass_rate_col: row[pass_rate_col]}
        for name, row in zip(selected, summary_rows)
    ]
    try:
        import altair as alt
        chart = alt.Chart(alt.Data(values=chart_data)).mark_bar().encode(
            x=alt.X("Run:N", sort=None),
            y=alt.Y(f"{pass_rate_col}:Q", scale=alt.Scale(domain=[0, 100])),
            color="Run:N",
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)
    except ImportError:
        st.bar_chart({r["Run"]: r[pass_rate_col] for r in chart_data})

    # ── Per-case score matrix ────────────────────────────────────────────────
    st.subheader(t("per_case_scores"))
    case_names: set[str] = set()
    for _, report in loaded:
        for case in report.get("cases", []):
            case_names.add(case.get("name", ""))

    matrix_rows: list[dict[str, Any]] = []
    for case_name in sorted(case_names):
        row: dict[str, Any] = {t("case"): case_name}
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
    st.subheader(t("drill_into"))
    case_pick = st.selectbox(t("case"), sorted(case_names))
    cols = st.columns(len(loaded))
    for col, (filename, report) in zip(cols, loaded):
        meta = parse_filename(filename)
        case = next((c for c in report.get("cases", []) if c.get("name") == case_pick), None)
        with col:
            st.markdown(f"**{meta['model']}**  \n_{meta['timestamp']}_")
            if not case:
                st.caption(t("not_in_report"))
                continue
            score = case.get("score", 0)
            threshold = case.get("threshold", 0.7)
            emoji = "✅" if score >= threshold else "❌"
            st.metric(t("score"), f"{emoji} {score:.2f}", delta=f"th: {threshold:.2f}")
            st.markdown(f"**{t('reason')}**")
            st.write(case.get("reason", "—"))


main()
