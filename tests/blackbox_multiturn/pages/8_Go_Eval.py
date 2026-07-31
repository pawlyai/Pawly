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
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from lang import lang_toggle, t  # noqa: E402

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
    c1.metric(t("total_cases"), total)
    c2.metric(t("passed"), passed)
    c3.metric(t("failed"), s.get("below_threshold", 0))
    c4.metric(t("pass_rate"), f"{(passed / total * 100) if total else 0:.0f}%")

    sut = s.get("llm_model", "?")
    judge = s.get("judge_model", "?")
    if s.get("judge_same_family"):
        # Stated on the page, not just in the JSON: a judge from the same family
        # as the system under test shares its blind spots, so the failures most
        # worth catching are the ones least likely to be flagged. Anyone reading
        # a pass rate off this screen should know that before they quote it.
        st.warning(t("go_same_family", judge=judge, sut=sut))
    else:
        st.caption(t("go_judged_by", sut=sut, judge=judge))


def render_case_table(report: dict[str, Any]) -> None:
    import pandas as pd

    rows = []
    for c in report["cases"]:
        a = asserts_of(c)
        ok = sum(1 for x in a if x["passed"])
        md = c.get("metadata") or {}
        rows.append({
            "": "✅" if c["status"] == "passed_threshold" else "❌",
            t("case"): c["name"],
            t("score"): f"{c['score']:.2f} / {c['threshold']:.2f}",
            t("go_col_asserts"): f"{ok}/{len(a)}" if a else "—",
            t("go_col_failed_assert"): ", ".join(md.get("assert_failures") or []) or "",
            t("go_col_mem"): md.get("memories_seeded", 0),
            t("go_col_turns"): c.get("turn_count", 0),
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
        st.markdown(t("go_assertions"))
        if not a:
            st.caption(t("go_no_asserts"))
        for x in a:
            icon = "✅" if x["passed"] else "❌"
            st.markdown(f"{icon} `{x['name']}` — {x['detail']}")
    with c2:
        st.markdown(t("go_judged_score"))
        st.markdown(
            f"{'✅' if score_ok else '❌'} **{case['score']:.2f}** / {case['threshold']:.2f}"
        )
        st.caption(case.get("reason") or "—")

    # Spelling out the conjunction is the point of the page: "Failed" next to a
    # perfect score is otherwise indistinguishable from a broken report.
    if not passed and score_ok:
        st.info(t("go_rubric_but_assert"))
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
        with st.expander(t("go_context", label=label, n=md.get("memories_seeded", 0))):
            for m in mems:
                v = m.get("value", {})
                detail = v.get("detail", v) if isinstance(v, dict) else v
                st.caption(f"`{m.get('field')}` — {detail}")

    st.markdown(f"**{t('transcript')}**")
    for i, turn in enumerate(case.get("turns") or []):
        if turn.get("role") == "user":
            st.markdown(f"**👤 {t('go_user')}**")
            st.info(turn.get("content", ""))
            continue
        lvl = ((turn.get("triage_trace") or {}).get("resolved") or {}).get("level", "")
        alert = turn.get("alert")
        badge = f"{_LEVEL_ICON.get(lvl, '⚪')} `{lvl or 'none'}`"
        if alert:
            badge += f" · alert {_ALERT_ICON.get(alert, '')} `{alert}`"
        else:
            badge += " · " + t("go_no_alert")
        lat = turn.get("latency_s")
        if lat:
            badge += f" · {lat:.1f}s"
        st.markdown(f"**🤖 {t('go_assistant')}** — {badge}")
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
            # Scoring failures belong here too, for the same reason: a judge
            # that ran out of credit says nothing about the system. One run had
            # 48 cases unscored that way, and counting them as failures would
            # have written a 48-case regression into this table.
            if err.startswith(("drive failed", "scoring failed")):
                tally[c["name"]].append(None)
            else:
                tally[c["name"]].append(c["status"] == "passed_threshold")

    rows = []
    for name, runs in sorted(tally.items()):
        scored = [r for r in runs if r is not None]
        errs = len(runs) - len(scored)
        n, ok = len(scored), sum(1 for r in scored if r)

        if n == 0:
            verdict = t("go_v_never_ran")
        elif ok == n:
            verdict = t("go_v_stable_pass")
        elif ok == 0:
            verdict = t("go_v_stable_fail")
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
                verdict = t("go_v_flaky", ok=ok, n=n)
            elif scored[-1]:
                verdict = t("go_v_fixed", n=tail)
            else:
                verdict = t("go_v_regressed", n=tail)

        rows.append({
            t("case"): name,
            t("go_col_scored"): n,
            t("passed"): ok,
            t("go_col_rate"): f"{ok / n * 100:.0f}%" if n else "—",
            t("go_col_verdict"): verdict,
            t("go_col_history"): "".join("." if r else "x" if r is False else "!" for r in runs),
            # Always a string: mixing int and "" in one column makes Arrow fall
            # back to a coerced type and log a serialization error per render.
            t("go_col_drive_errors"): str(errs) if errs else "",
        })

    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.caption(t("go_history_caption"))


# ── Page ──────────────────────────────────────────────────────────────────────

lang_toggle()
st.title(f"🐹 {t('go_title')}")

reports = load_go_reports()
if not reports:
    st.info(
        t("go_no_reports") + "\n\n"
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
tab_run, tab_stability = st.tabs([t("go_tab_run"), t("go_tab_stability", n=len(names))])


def _label(name: str) -> str:
    """Report name with its size, so a 5-case probe cannot pass for a full run."""
    s = reports[name]["summary"]
    return f"{name}  —  {s.get('total_cases', 0)} cases"


with tab_run:
    # Newest FULL run, not newest run. Sorting by timestamp alone meant every
    # small debugging probe displaced the thing a reader came to see: the page
    # was opening an 8-case fixup report while two 120-case runs sat below it.
    biggest = max(r["summary"].get("total_cases", 0) for r in reports.values())
    default_i = max(
        (i for i, n in enumerate(names)
         if reports[n]["summary"].get("total_cases", 0) == biggest),
        default=len(names) - 1,
    )
    selected = st.selectbox(t("go_report"), names, index=default_i, format_func=_label)
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
    chosen = st.selectbox(t("case"), case_names, index=first_bad)
    render_case_detail(next(c for c in report["cases"] if c["name"] == chosen))

with tab_stability:
    render_stability(reports)
