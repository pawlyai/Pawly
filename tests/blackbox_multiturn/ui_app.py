"""
Pawly multi-turn test results UI — landing page.

Streamlit auto-discovers pages under ./pages/ as the multi-page navigation
entries. This file is the home page (overview of latest reports).
"""

import json
from pathlib import Path
from typing import Any

import streamlit as st
from utils import parse_filename

st.set_page_config(
    page_title="Pawly Multi-Turn Tests",
    page_icon="🐾",
    layout="wide",
)

RESULTS_DIR = Path(__file__).parent / "results"


def list_reports() -> list[Path]:
    if not RESULTS_DIR.exists():
        return []
    return sorted(RESULTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def load_report(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)



def main() -> None:
    st.title("🐾 Pawly Multi-Turn Tests")
    st.caption("Multi-model evaluation of the conversation pipeline against blackbox cases.")

    st.markdown(
        """
        **Pages**

        - **Reports** — browse a single report's case-by-case results
        - **Run Tests** — pick a model + topic and trigger a new evaluation run
        - **Compare** — side-by-side comparison of multiple reports
        - **Test Cases** — view, edit, add, or LLM-generate new test cases

        Use the left sidebar to navigate.
        """
    )

    reports = list_reports()
    st.subheader(f"📊 Recent runs ({len(reports)} total)")

    if not reports:
        st.info("No reports yet. Use **Run Tests** to start.")
        return

    rows: list[dict[str, Any]] = []
    for path in reports[:25]:
        meta = parse_filename(path.name)
        try:
            report = load_report(path)
            summary = report.get("summary", {})
            total = summary.get("total_cases", 0)
            passed = summary.get("passed_threshold", 0)
            pass_rate = (passed / total * 100) if total else 0.0
        except Exception:
            total = passed = 0
            pass_rate = 0.0
        # Prefer git_ref from report content (authoritative) but fall back to
        # the parsed filename so legacy reports still display something.
        try:
            git_ref = report.get("summary", {}).get("git_ref", "") or meta.get("git_ref", "")
        except Exception:
            git_ref = meta.get("git_ref", "")
        rows.append(
            {
                "Topic": meta["topic"],
                "Model": meta["model"],
                "Branch/Tag": git_ref or "—",
                "Timestamp": meta["timestamp"],
                "Cases": total,
                "Passed": passed,
                "Pass Rate (%)": round(pass_rate, 1),
                "File": path.name,
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
