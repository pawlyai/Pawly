"""Go-stack multi-turn regression browser.

Page 1 renders these reports already — the schema is the same on purpose — but
it was built for the Python harness and shows only the judged score. Go runs
carry two verdicts, and the one page 1 cannot show is usually the one that
matters: a case can score 1.00 and still fail because `alert` was wrong, and a
reader looking at "Failed, score 1.00 / 0.90" has no way to see why.

So this page leads with the assertions, and adds the thing no single report can
show — the same case across every run. Multi-turn attribution is not
deterministic: one case here names the right pet about eleven times in twelve,
which reads as a solid pass or a clean failure depending on which run you
happen to open.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import streamlit as st

st.set_page_config(page_title="Go Eval", page_icon="🐹", layout="wide")

RESULTS_DIR = Path(__file__).parent.parent / "results"

_LEVEL_ICON = {"red": "🔴", "orange": "🟠", "green": "🟢", "": "⚪"}
_ALERT_ICON = {"red_flag": "🚨", "care": "💊", None: "", "": ""}


# ── Loading ───────────────────────────────────────────────────────────────────


@st.cache_data(show_spinner=False)
def load_go_reports() -> dict[str, dict[str, Any]]:
    """Every report produced by run_go_eval.py, newest name last.

    Identified by a summary key only this harness writes, rather than by
    filename: the topic is a CLI flag, so an A/B run lands under a different
    prefix and would otherwise vanish from the stability view.
    """
    out: dict[str, dict[str, Any]] = {}
    if not RESULTS_DIR.exists():
        return out
    for f in sorted(RESULTS_DIR.glob("*.json")):
        if f.name == "translation_cache.json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and "judge_same_family" in (data.get("summary") or {}):
            out[f.name] = data
    return out


def asserts_of(case: dict[str, Any]) -> list[dict[str, Any]]:
    return (case.get("metadata") or {}).get("assert_results") or []


# ── Rendering ─────────────────────────────────────────────────────────────────


def render_summary(report: dict[str, Any]) -> None:
    s = report["summary"]
    total = s.get("total_cases", 0)
    passed = s.get("passed_threshold", 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cases", total)
    c2.metric("Passed", passed)
    c3.metric("Failed", s.get("below_threshold", 0))
    c4.metric("Pass rate", f"{(passed / total * 100) if total else 0:.0f}%")

    sut = s.get("llm_model", "?")
    judge = s.get("judge_model", "?")
    if s.get("judge_same_family"):
        # Stated on the page, not just in the JSON: a judge from the same family
        # as the system under test shares its blind spots, so the failures most
        # worth catching are the ones least likely to be flagged. Anyone reading
        # a pass rate off this screen should know that before they quote it.
        st.warning(
            f"Judge **{judge}** and system under test **{sut}** are the same "
            f"model family. Scores on subjective criteria are optimistic; the "
            f"assertions below are unaffected."
        )
    else:
        st.caption(f"System under test **{sut}** · judged by **{judge}**")


def render_case_table(report: dict[str, Any]) -> None:
    import pandas as pd

    rows = []
    for c in report["cases"]:
        a = asserts_of(c)
        ok = sum(1 for x in a if x["passed"])
        md = c.get("metadata") or {}
        rows.append({
            "": "✅" if c["status"] == "passed_threshold" else "❌",
            "Case": c["name"],
            "Score": f"{c['score']:.2f} / {c['threshold']:.2f}",
            "Asserts": f"{ok}/{len(a)}" if a else "—",
            "Failed assert": ", ".join(md.get("assert_failures") or []) or "",
            "Mem": md.get("memories_seeded", 0),
            "Turns": c.get("turn_count", 0),
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def render_case_detail(case: dict[str, Any]) -> None:
    md = case.get("metadata") or {}
    passed = case["status"] == "passed_threshold"

    st.subheader(case["name"])
    if md.get("error"):
        st.error(md["error"])

    a = asserts_of(case)
    score_ok = case["score"] >= case["threshold"]
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Assertions** — wire fields, not opinions")
        if not a:
            st.caption("none declared")
        for x in a:
            icon = "✅" if x["passed"] else "❌"
            st.markdown(f"{icon} `{x['name']}` — {x['detail']}")
    with c2:
        st.markdown("**Judged score** — the case's own criteria")
        st.markdown(
            f"{'✅' if score_ok else '❌'} **{case['score']:.2f}** / {case['threshold']:.2f}"
        )
        st.caption(case.get("reason") or "—")

    # Spelling out the conjunction is the point of the page: "Failed" next to a
    # perfect score is otherwise indistinguishable from a broken report.
    if not passed and score_ok:
        st.info(
            "Cleared the rubric but failed an assertion. The judge scored the "
            "prose; the assertion checked what actually went over the wire."
        )
    st.divider()

    pet = case.get("pet_profile") or {}
    mems = case.get("memories") or []
    if pet or mems:
        bits = [
            str(pet.get(k, "")) for k in
            ("name", "species", "breed", "gender", "neutered_status")
        ]
        age = pet.get("age_in_months")
        label = " · ".join([b for b in bits if b] + ([f"{age}mo"] if age else []))
        with st.expander(f"Context — {label} · {md.get('memories_seeded', 0)} memories seeded"):
            for m in mems:
                v = m.get("value", {})
                detail = v.get("detail", v) if isinstance(v, dict) else v
                st.caption(f"`{m.get('field')}` — {detail}")

    st.markdown("**Transcript**")
    for i, turn in enumerate(case.get("turns") or []):
        if turn.get("role") == "user":
            st.markdown(f"**👤 User**")
            st.info(turn.get("content", ""))
            continue
        lvl = ((turn.get("triage_trace") or {}).get("resolved") or {}).get("level", "")
        alert = turn.get("alert")
        badge = f"{_LEVEL_ICON.get(lvl, '⚪')} `{lvl or 'none'}`"
        if alert:
            badge += f" · alert {_ALERT_ICON.get(alert, '')} `{alert}`"
        else:
            badge += " · no alert"
        lat = turn.get("latency_s")
        if lat:
            badge += f" · {lat:.1f}s"
        st.markdown(f"**🤖 Assistant** — {badge}")
        st.success(turn.get("content", ""))


def render_stability(reports: dict[str, dict[str, Any]]) -> None:
    """Pass/fail for every case across every run.

    The single most useful view here. A case that passes 11 runs and fails the
    12th is not a pass and not a regression — it is a flake, and no individual
    report can tell you which one you are looking at.
    """
    import pandas as pd

    # Ordered oldest to newest by the run's own timestamp, not by filename:
    # topics sort alphabetically, so an A/B run under a different --topic would
    # otherwise land in the middle of the history string and invent a flake.
    ordered = sorted(reports.values(), key=lambda d: d["summary"].get("timestamp", ""))

    tally: dict[str, list[bool | None]] = defaultdict(list)
    for data in ordered:
        for c in data["cases"]:
            # A case whose driver never reached the model says nothing about the
            # model. Counting QUOTA_EXCEEDED as a failure is how a broken eval
            # stack gets read as a flaky assistant.
            # `or ""` because the key is present and explicitly null on a case
            # that succeeded — a default only applies to a missing key.
            err = (c.get("metadata") or {}).get("error") or ""
            if err.startswith("drive failed"):
                tally[c["name"]].append(None)
            else:
                tally[c["name"]].append(c["status"] == "passed_threshold")

    rows = []
    for name, runs in sorted(tally.items()):
        scored = [r for r in runs if r is not None]
        errs = len(runs) - len(scored)
        n, ok = len(scored), sum(1 for r in scored if r)

        if n == 0:
            verdict = "never ran"
        elif ok == n:
            verdict = "stable pass"
        elif ok == 0:
            verdict = "stable fail"
        else:
            # A run of failures followed by a run of passes is a fix, not a
            # flake, and calling it flaky buries the most useful thing the
            # history has to say.
            #
            # Both verdicts need TWO consecutive results at the end. One
            # trailing pass after a failure is equally consistent with a flake
            # that happened to land well, and one trailing failure after a
            # streak of passes is the single most common shape a flake takes.
            # Naming either on a sample of one puts a claim on screen that the
            # data does not carry.
            # Length of the trailing run of identical results. The all-same case
            # already returned above, so this run is always shorter than n.
            tail = 1
            while tail < len(scored) and scored[-1 - tail] == scored[-1]:
                tail += 1

            if tail < 2:
                verdict = f"FLAKY ({ok}/{n})"
            elif scored[-1]:
                verdict = f"fixed ({tail} straight)"
            else:
                verdict = f"REGRESSED ({tail} straight)"

        rows.append({
            "Case": name,
            "Scored": n,
            "Passed": ok,
            "Rate": f"{ok / n * 100:.0f}%" if n else "—",
            "Verdict": verdict,
            "History": "".join("." if r else "x" if r is False else "!" for r in runs),
            # Always a string: mixing int and "" in one column makes Arrow fall
            # back to a coerced type and log a serialization error per render.
            "Drive errors": str(errs) if errs else "",
        })

    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.caption(
        "History reads oldest to newest: `.` pass, `x` fail, `!` the driver "
        "never reached the model (excluded from the rate). A genuinely mixed "
        "row means the run you opened decided the verdict, not the code."
    )


# ── Page ──────────────────────────────────────────────────────────────────────

st.title("🐹 Go Eval")

reports = load_go_reports()
if not reports:
    st.info(
        "No Go reports yet. Bring the eval stack up and run:\n\n"
        "```\ndocker compose -f deploy/docker-compose.eval.yml -p pawly-eval up -d --build\n"
        "python tests/blackbox_multiturn/run_go_eval.py\n```"
    )
    st.stop()

# Newest last by run timestamp. Sorting by filename would put a `quota_check`
# probe after a full `multiturn_go_regression` run and default the page to it.
names = [
    n for n, _ in sorted(
        reports.items(), key=lambda kv: kv[1]["summary"].get("timestamp", "")
    )
]
tab_run, tab_stability = st.tabs(["Run", f"Stability across {len(names)} runs"])

with tab_run:
    selected = st.selectbox("Report", names, index=len(names) - 1)
    report = reports[selected]
    render_summary(report)
    st.divider()
    render_case_table(report)
    st.divider()

    case_names = [c["name"] for c in report["cases"]]
    # Default to the first failure: on a red run that is what the reader came
    # for, and on a green run the index falls through to the first case.
    first_bad = next(
        (i for i, c in enumerate(report["cases"]) if c["status"] != "passed_threshold"), 0
    )
    chosen = st.selectbox("Case", case_names, index=first_bad)
    render_case_detail(next(c for c in report["cases"] if c["name"] == chosen))

with tab_stability:
    render_stability(reports)
