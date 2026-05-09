"""
Pawly multi-turn test results UI — landing page.

Streamlit auto-discovers pages under ./pages/ as the multi-page navigation
entries. This file is the home page (overview of latest reports).
"""

import json
from datetime import datetime, timedelta
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
LOGS_DIR = Path(__file__).parent / "logs"

# A run is "active" if its log was last appended to within this window
# AND it hasn't emitted `test_finished`. Wider than the slowest expected
# case (~3min) so we don't flicker into "stale" during a long case.
ACTIVE_WINDOW = timedelta(minutes=30)

# Friendly names for the topics that show up most. Anything not in this
# map falls back to a stripped + title-cased version of the topic id.
TOPIC_DISPLAY = {
    "multiturn_pawly_regression_light_30": "Lite-30",
    "multiturn_pawly_regression": "Full-223",
}


def list_reports() -> list[Path]:
    if not RESULTS_DIR.exists():
        return []
    return sorted(RESULTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def load_report(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ── Active runs (live progress) ─────────────────────────────────────────────


def _topic_display(topic: str) -> str:
    if topic in TOPIC_DISPLAY:
        return TOPIC_DISPLAY[topic]
    short = (
        topic
        .removeprefix("multiturn_pawly_regression_test_")
        .removeprefix("multiturn_pawly_regression_")
        .removeprefix("multiturn_")
    )
    return short.replace("_", "-").title() or topic


def _parse_run_log(log_path: Path) -> dict[str, Any] | None:
    """Read a `<topic>_run_<model>_v<ts>.jsonl` and summarize its state.

    Returns None if the log is unreadable or doesn't carry a `test_started`
    event (i.e. it isn't one of our regression run logs).
    """
    try:
        text = log_path.read_text(encoding="utf-8")
    except Exception:
        return None

    started: dict[str, Any] | None = None
    case_starteds: list[dict[str, Any]] = []
    finished = False

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        kind = event.get("event")
        if kind == "test_started" and started is None:
            started = event
        elif kind == "case_started":
            case_starteds.append(event)
        elif kind == "test_finished":
            finished = True

    if started is None:
        return None

    return {
        "log_path": log_path,
        "topic": started.get("topic", "?"),
        "model": started.get("llm_model", "?"),
        "total_cases": started.get("case_count", 0),
        "cases_done": len(case_starteds),
        "last_case_name": case_starteds[-1].get("case_name") if case_starteds else None,
        "started_at": started.get("logged_at"),
        "last_event_at": (case_starteds[-1] if case_starteds else started).get("logged_at"),
        "finished": finished,
    }


def _humanize_ago(iso_ts: str | None) -> str:
    if not iso_ts:
        return "?"
    try:
        when = datetime.fromisoformat(iso_ts)
    except Exception:
        return iso_ts
    # Treat naive timestamps as host-local; comparison stays internally
    # consistent because both ends come from the same VPS clock.
    now = datetime.now() if when.tzinfo is None else datetime.now(when.tzinfo)
    delta = now - when
    total_sec = int(delta.total_seconds())
    if total_sec < 0:
        return "just now"
    if total_sec < 60:
        return f"{total_sec}s ago"
    if total_sec < 3600:
        return f"{total_sec // 60}m ago"
    if total_sec < 86400:
        return f"{total_sec // 3600}h{(total_sec % 3600) // 60}m ago"
    return f"{total_sec // 86400}d ago"


def _is_active(run: dict[str, Any]) -> bool:
    if run["finished"]:
        return False
    last = run.get("last_event_at")
    if not last:
        return False
    try:
        when = datetime.fromisoformat(last)
    except Exception:
        return False
    now = datetime.now() if when.tzinfo is None else datetime.now(when.tzinfo)
    return (now - when) <= ACTIVE_WINDOW


def list_active_runs() -> list[dict[str, Any]]:
    if not LOGS_DIR.exists():
        return []
    runs: list[dict[str, Any]] = []
    # mtime-sorted so the most recently appended-to log comes first.
    for log_path in sorted(LOGS_DIR.glob("*_run_*_v*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        parsed = _parse_run_log(log_path)
        if parsed and _is_active(parsed):
            runs.append(parsed)
    return runs


def render_active_runs() -> None:
    runs = list_active_runs()
    if not runs:
        return

    st.subheader(f"🟢 Active runs ({len(runs)})")
    for run in runs:
        topic = _topic_display(run["topic"])
        total = run["total_cases"] or 0
        done = run["cases_done"]
        bounded_done = min(done, total) if total else done
        progress = (bounded_done / total) if total else 0.0
        last_case = run["last_case_name"] or "(starting)"

        st.markdown(
            f"**{topic}**  ·  `{run['model']}`  ·  "
            f"started {_humanize_ago(run['started_at'])}  ·  "
            f"last update {_humanize_ago(run['last_event_at'])}"
        )
        st.progress(
            progress,
            text=(
                f"{done}/{total}  "
                f"·  currently: {last_case}"
                if total
                else f"{done} cases  ·  currently: {last_case}"
            ),
        )
        st.caption(f"Log: `{run['log_path'].name}`")

    if st.button("🔄 Refresh", help="Re-read the run logs to update progress."):
        st.rerun()
    st.divider()


# ── Page ────────────────────────────────────────────────────────────────────


def main() -> None:
    st.title("🐾 Pawly Multi-Turn Tests")
    st.caption("Multi-model evaluation of the conversation pipeline against blackbox cases.")

    render_active_runs()

    st.markdown(
        """
        **Pages**

        - **Reports** — browse a single report's case-by-case results
        - **Run Tests** — pick a model + topic and trigger a new evaluation run
        - **Compare** — side-by-side comparison of multiple reports
        - **Test Cases** — view, edit, add, or LLM-generate new test cases
        - **Regression History** — PR-aware index of every CI / manual regression run; pick two to diff

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
        rows.append(
            {
                "Topic": meta["topic"],
                "Model": meta["model"],
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
