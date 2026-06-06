"""
Proactive message quality — interactive runner + history viewer.

Run tab:   pick cases + judge model → generate live → score with GEval
History tab: load proactive_quality_results.jsonl → table + score chart
"""

import asyncio
import concurrent.futures
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent.parent.parent
for _p in (str(REPO_ROOT),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-bot-token")

import streamlit as st

st.set_page_config(page_title="Proactive Quality", page_icon="📨", layout="wide")

CASES_FILE   = REPO_ROOT / "tests" / "blackbox_proactive" / "test_data" / "proactive_quality_cases.json"
RESULTS_FILE = REPO_ROOT / "proactive_quality_results.jsonl"

_DEEPSEEK_BASE_URL  = "https://api.deepseek.com/v1"
_DEEPSEEK_MAX_TOKENS = 4000
_JUDGE_MODELS = ["deepseek-v4-pro", "gemini-2.5-flash"]


# ── Data loading ──────────────────────────────────────────────────────────────

def load_cases() -> list[dict[str, Any]]:
    if not CASES_FILE.exists():
        return []
    with CASES_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def load_results(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


# ── Async generation ──────────────────────────────────────────────────────────

async def _generate(case: dict) -> str:
    t   = case["type"]
    inp = case["input"]

    if t == "triage_followup":
        from src.jobs.followup import _generate_message
        return await _generate_message(
            pet_name=inp["pet_name"],
            pet_species=inp["pet_species"],
            triage_level=inp["triage_level"],
            symptom_tags=inp["symptom_tags"],
            stage=inp["stage"],
            pet_context=inp.get("pet_context", ""),
            locale=inp.get("locale", "en"),
        )

    if t == "episode_checkin":
        from src.jobs.episode_checkin import _generate_episode_checkin
        return await _generate_episode_checkin(
            pet_name=inp["pet_name"],
            pet_species=inp["pet_species"],
            symptom_type=inp["symptom_type"],
            severity=inp["severity"],
            days_ongoing=inp["days_ongoing"],
            interventions=inp.get("interventions"),
            pet_context=inp.get("pet_context", ""),
            locale=inp.get("locale", "en"),
        )

    if t == "reengagement":
        pet_name = inp["pet_name"]
        species = inp.get("species", "pet").lower()
        return (
            f"Hey! It's been a couple of days — how is {pet_name} doing? 🐾\n"
            f"Feel free to share any updates or questions about your {species}!"
        )

    if t == "daily_summary_push":
        from src.proactive.summary_pusher import _generate_push_message
        return await _generate_push_message(
            pet_name=inp["pet_name"],
            species=inp["species"],
            unresolved=inp.get("unresolved", []),
            follow_up_reason=inp.get("follow_up_reason", ""),
        )

    raise ValueError(f"Unknown case type: {t}")


def generate_sync(case: dict) -> str:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _generate(case)).result()


# ── Judge model builder ───────────────────────────────────────────────────────

def make_judge(model_name: str):
    """Return (judge_model, error_str). error_str is None on success."""
    try:
        from deepeval.models import DeepEvalBaseLLM

        if model_name == "deepseek-v4-pro":
            key = os.environ.get("DEEPSEEK_API_KEY", "")
            if not key:
                return None, "DEEPSEEK_API_KEY not set"
            from openai import OpenAI

            class _DeepSeekJudge(DeepEvalBaseLLM):
                def __init__(self):
                    self._client = OpenAI(api_key=key, base_url=_DEEPSEEK_BASE_URL)
                    self.model_name = model_name

                def load_model(self):
                    return self._client

                def generate(self, prompt: str, schema=None) -> str:
                    resp = self._client.chat.completions.create(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=_DEEPSEEK_MAX_TOKENS,
                    )
                    return resp.choices[0].message.content or ""

                async def a_generate(self, prompt: str, schema=None) -> str:
                    return self.generate(prompt, schema)

                def get_model_name(self) -> str:
                    return self.model_name

            return _DeepSeekJudge(), None

        # Gemini judge — use custom wrapper (GeminiModel.generate_raw_response crashes)
        google_key = os.environ.get("GOOGLE_API_KEY", "")
        if not google_key or google_key.startswith("test"):
            return None, "GOOGLE_API_KEY not set"
        import google.genai as genai
        from google.genai import types as _gtypes

        class _GeminiJudge(DeepEvalBaseLLM):
            def __init__(self):
                self._client = genai.Client(api_key=google_key)
                self.model_name = model_name

            def load_model(self):
                return self._client

            def generate(self, prompt: str, schema=None) -> str:
                resp = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=_gtypes.GenerateContentConfig(max_output_tokens=4000, temperature=0.0),
                )
                return resp.text or ""

            async def a_generate(self, prompt: str, schema=None) -> str:
                return self.generate(prompt, schema)

            def get_model_name(self) -> str:
                return self.model_name

        return _GeminiJudge(), None

    except Exception as exc:
        return None, str(exc)


def judge_sync(generated: str, case: dict, judge_model) -> tuple[float, str, bool]:
    """Run GEval scoring in a thread (avoids event-loop conflicts)."""
    def _run():
        from deepeval.metrics import GEval
        from deepeval.test_case import LLMTestCase, SingleTurnParams

        metric = GEval(
            name="ProactiveMessageQuality",
            criteria=case["criteria"],
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            model=judge_model,
            threshold=case.get("threshold", 0.7),
            async_mode=False,
            verbose_mode=False,
        )
        metric.measure(LLMTestCase(
            input=f"Generate proactive message for: {case['name']}",
            actual_output=generated,
        ))
        return metric.score, metric.reason or "", metric.is_successful()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run).result()


# ── UI helpers ────────────────────────────────────────────────────────────────

_SCORE_COLOR = {True: "#21c354", False: "#ff4b4b"}
_LEVEL_COLORS = {"RED": "#ff4b4b", "ORANGE": "#ff8c00", "GREEN": "#21c354"}


def _score_badge(score: float, passed: bool) -> str:
    color = _SCORE_COLOR[passed]
    icon  = "✅" if passed else "❌"
    return (
        f"<span style='background:{color};color:white;padding:2px 10px;"
        f"border-radius:4px;font-weight:700;font-size:0.9em'>"
        f"{icon} {score:.2f}</span>"
    )


def _type_tag(t: str) -> str:
    colors = {
        "triage_followup":   "#6366f1",
        "episode_checkin":   "#0ea5e9",
        "reengagement":      "#8b5cf6",
        "daily_summary_push": "#f59e0b",
    }
    color = colors.get(t, "#888")
    return (
        f"<span style='background:{color};color:white;padding:1px 7px;"
        f"border-radius:3px;font-size:0.78em'>{t}</span>"
    )


def _render_run_result(case: dict, generated: str, score: float, reason: str, passed: bool) -> None:
    color = _SCORE_COLOR[passed]
    with st.container(border=True):
        top_left, top_right = st.columns([5, 1])
        with top_left:
            st.markdown(
                f"{_type_tag(case['type'])} &nbsp; **{case['id']}**",
                unsafe_allow_html=True,
            )
        with top_right:
            st.markdown(_score_badge(score, passed), unsafe_allow_html=True)

        msg_col, reason_col = st.columns([1, 1])
        with msg_col:
            st.markdown("**Generated message**")
            st.markdown(
                f"<div style='background:#1e1e2e;padding:10px 14px;border-radius:6px;"
                f"border-left:4px solid {color};font-style:italic'>{generated}</div>",
                unsafe_allow_html=True,
            )
        with reason_col:
            st.markdown("**Judge reason**")
            st.markdown(
                f"<div style='background:#1e1e2e;padding:10px 14px;border-radius:6px;"
                f"color:#ccc;font-size:0.9em'>{reason}</div>",
                unsafe_allow_html=True,
            )

        with st.expander("Criteria", expanded=False):
            st.markdown(
                f"threshold `{case.get('threshold', 0.7)}` — {case['criteria']}"
            )


# ── Run tab ───────────���───────────────────────────────────────────────────────

def _tab_run(cases: list[dict]) -> None:
    if not cases:
        st.error(f"No cases found at {CASES_FILE}")
        return

    col_cases, col_judge = st.columns([3, 1])
    with col_cases:
        all_ids = [c["id"] for c in cases]
        selected_ids = st.multiselect(
            "Cases to evaluate",
            all_ids,
            default=all_ids,
            key="pq_selected",
        )
    with col_judge:
        judge_name = st.selectbox("Judge model", _JUDGE_MODELS, key="pq_judge")

    google_key = os.environ.get("GOOGLE_API_KEY", "")
    if not google_key or google_key.startswith("test"):
        st.warning("GOOGLE_API_KEY not set — generation will fail for Gemini-based cases.")

    run_btn = st.button(
        f"▶ Run {len(selected_ids)} case{'s' if len(selected_ids) != 1 else ''}",
        type="primary",
        disabled=not selected_ids,
    )

    if not run_btn:
        return

    judge_model, err = make_judge(judge_name)
    if err:
        st.error(f"Judge setup failed: {err}")
        return

    selected_cases = [c for c in cases if c["id"] in selected_ids]
    results: list[dict] = []
    progress = st.progress(0.0, text="Starting…")
    result_area = st.container()

    for i, case in enumerate(selected_cases):
        progress.progress(i / len(selected_cases), text=f"Running `{case['id']}`…")

        with result_area:
            with st.spinner(f"Generating `{case['id']}`…"):
                try:
                    generated = generate_sync(case)
                except Exception as exc:
                    st.error(f"`{case['id']}` generation failed: {exc}")
                    continue

            with st.spinner(f"Judging `{case['id']}`…"):
                try:
                    score, reason, passed = judge_sync(generated, case, judge_model)
                except Exception as exc:
                    st.error(f"`{case['id']}` judging failed: {exc}")
                    continue

            _render_run_result(case, generated, score, reason, passed)
            results.append({
                "case_id": case["id"],
                "score": round(score, 3),
                "reason": reason,
                "passed": passed,
                "generated": generated[:300],
            })

    progress.progress(1.0, text="Done")

    if results:
        passed_count = sum(1 for r in results if r["passed"])
        total = len(results)
        if passed_count == total:
            st.success(f"All {total} cases passed ✅")
        else:
            st.warning(f"{passed_count}/{total} passed — {total - passed_count} failed")

        # Offer download of this run's results
        jsonl_text = "\n".join(json.dumps(r, ensure_ascii=False) for r in results)
        st.download_button(
            "⬇ Download results (.jsonl)",
            data=jsonl_text,
            file_name="proactive_quality_results.jsonl",
            mime="application/jsonl",
        )


# ── History tab ───────────────────────────────────────────────────────────────

def _tab_history() -> None:
    st.markdown("Load a `proactive_quality_results.jsonl` file to view scores.")

    col_src, col_upload = st.columns([1, 1])
    with col_src:
        use_local = st.checkbox(
            f"Load local file (`proactive_quality_results.jsonl`)",
            value=RESULTS_FILE.exists(),
            disabled=not RESULTS_FILE.exists(),
        )
    with col_upload:
        uploaded = st.file_uploader(
            "Or upload a CI artifact",
            type=["jsonl", "json"],
            key="pq_upload",
        )

    rows: list[dict] = []
    if uploaded is not None:
        content = uploaded.read().decode("utf-8")
        for line in content.splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        st.caption(f"Loaded {len(rows)} results from uploaded file.")
    elif use_local and RESULTS_FILE.exists():
        rows = load_results(RESULTS_FILE)
        st.caption(f"Loaded {len(rows)} results from `{RESULTS_FILE.name}`.")

    if not rows:
        st.info("No results to display. Run cases in the **▶ Run** tab or upload a CI artifact.")
        return

    # Summary metrics
    passed = sum(1 for r in rows if r.get("passed"))
    total  = len(rows)
    avg    = sum(r.get("score", 0) for r in rows) / total if total else 0

    m1, m2, m3 = st.columns(3)
    m1.metric("Total cases", total)
    m2.metric("Passed", f"{passed}/{total}")
    m3.metric("Avg score", f"{avg:.2f}")

    st.markdown("---")

    # Score table
    st.markdown("### Scores")
    for r in rows:
        col_id, col_score, col_reason = st.columns([2, 1, 4])
        with col_id:
            st.markdown(f"`{r.get('case_id','?')}`")
        with col_score:
            score = r.get("score", 0.0)
            passed_r = r.get("passed", False)
            st.markdown(_score_badge(score, passed_r), unsafe_allow_html=True)
        with col_reason:
            st.caption((r.get("reason") or "")[:150])

    st.markdown("---")

    # Bar chart
    try:
        import altair as alt
        import pandas as pd

        df = pd.DataFrame([
            {"case": r.get("case_id", "?"), "score": r.get("score", 0.0), "passed": r.get("passed", False)}
            for r in rows
        ])
        df["color"] = df["passed"].map({True: "#21c354", False: "#ff4b4b"})

        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("case:N", sort=None, axis=alt.Axis(labelAngle=-30)),
                y=alt.Y("score:Q", scale=alt.Scale(domain=[0, 1])),
                color=alt.Color("color:N", scale=None),
                tooltip=["case", "score", "passed"],
            )
            .properties(height=300, title="GEval scores by case")
        )
        st.altair_chart(chart, use_container_width=True)
    except ImportError:
        st.info("Install `altair` and `pandas` for the score chart.")

    # Expandable detail per case
    st.markdown("### Generated messages")
    for r in rows:
        label = f"{r.get('case_id','?')}  —  {r.get('score', 0):.2f}"
        with st.expander(label, expanded=not r.get("passed")):
            st.markdown(f"**Generated:** {r.get('generated','')}")
            st.caption(f"Reason: {r.get('reason','')}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    st.title("📨 Proactive Quality")
    st.caption("Evaluate proactive message quality using LLM-as-judge (GEval).")

    cases = load_cases()

    tab_run, tab_history = st.tabs(["▶ Run", "📊 History"])

    with tab_run:
        _tab_run(cases)

    with tab_history:
        _tab_history()


main()
