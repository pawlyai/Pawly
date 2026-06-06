"""
Proactive message quality — interactive runner + history viewer.

Run tab:     pick cases + judge model → generate live → score with GEval
             → saves report JSON to results/ so it appears in 1_Reports.py
History tab: list & browse proactive_quality_report_*.json files in results/
"""

import asyncio
import concurrent.futures
import json
import os
import sys
from datetime import datetime, timezone
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
RESULTS_DIR  = REPO_ROOT / "tests" / "blackbox_multiturn" / "results"

_DEEPSEEK_BASE_URL  = "https://api.deepseek.com/v1"
_DEEPSEEK_MAX_TOKENS = 4000
_JUDGE_MODELS = ["deepseek-v4-pro", "gemini-2.5-flash"]


# ── Data loading ──────────────────────────────────────────────────────────────

def load_cases() -> list[dict[str, Any]]:
    if not CASES_FILE.exists():
        return []
    with CASES_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def _write_report_json(results: list[dict], judge_name: str) -> Path:
    """Save run results as a report JSON in results/ and return the path."""
    slug = judge_name.replace("/", "-").replace(":", "-")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fname = f"proactive_quality_report_{slug}_v{ts}.json"
    passed = sum(1 for r in results if r["passed"])
    report = {
        "summary": {
            "total_cases": len(results),
            "passed_threshold": passed,
            "below_threshold": len(results) - passed,
        },
        "cases": [_to_report_case(r) for r in results],
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / fname
    with out.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return out


def _to_report_case(r: dict) -> dict:
    case = r["case"]
    inp = case.get("input", {})
    input_lines = [f"**Type:** {case['type']}"] + [f"**{k}:** {v}" for k, v in inp.items()]
    input_lines.append(f"\n**Criteria:** {case.get('criteria', '')}")
    return {
        "name": case["name"],
        "status": "passed_threshold" if r["passed"] else "below_threshold",
        "score": round(r["score"], 3),
        "threshold": case.get("threshold", 0.7),
        "reason": r["reason"],
        "turn_count": 1,
        "turns": [
            {"role": "user", "content": "\n".join(input_lines)},
            {"role": "assistant", "content": r["generated"]},
        ],
    }


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
                "case": case,
                "score": score,
                "reason": reason,
                "passed": passed,
                "generated": generated,
            })

    progress.progress(1.0, text="Done")

    if results:
        passed_count = sum(1 for r in results if r["passed"])
        total = len(results)
        if passed_count == total:
            st.success(f"All {total} cases passed ✅")
        else:
            st.warning(f"{passed_count}/{total} passed — {total - passed_count} failed")

        out_path = _write_report_json(results, judge_name)
        st.info(f"Report saved → `{out_path.name}` — open **📋 Reports** to browse it.")


# ── History tab ───────────────────────────────────────────────────────────────

def _load_report(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _tab_history() -> None:
    report_files = sorted(RESULTS_DIR.glob("proactive_quality_report_*.json"), reverse=True)
    if not report_files:
        st.info("No reports yet. Run cases in **▶ Run** tab or run `pytest tests/blackbox_proactive/`.")
        return

    # Report selector
    options = [f.name for f in report_files]
    selected_name = st.selectbox("Select report", options, key="pq_hist_report")
    report = _load_report(RESULTS_DIR / selected_name)
    summary = report.get("summary", {})
    cases = report.get("cases", [])

    # Summary metrics
    total  = summary.get("total_cases", 0)
    passed = summary.get("passed_threshold", 0)
    avg    = sum(c.get("score", 0) for c in cases) / total if total else 0

    m1, m2, m3 = st.columns(3)
    m1.metric("Total cases", total)
    m2.metric("Passed", f"{passed}/{total}")
    m3.metric("Avg score", f"{avg:.2f}")

    st.divider()

    # Case list (left) + detail (right)
    if not cases:
        return

    if "pq_hist_case" not in st.session_state or st.session_state.pq_hist_case >= len(cases):
        st.session_state.pq_hist_case = 0

    left, right = st.columns([1, 2])
    with left:
        for i, case in enumerate(cases):
            is_sel = i == st.session_state.pq_hist_case
            icon = "✅" if case.get("status") == "passed_threshold" else "❌"
            score = case.get("score", 0)
            label = f"{icon} {case.get('name', '?')}\n📊 {score:.2f} / {case.get('threshold', 0.7):.2f}"
            if st.button(label, key=f"pq_case_{i}",
                         type="primary" if is_sel else "secondary",
                         use_container_width=True):
                st.session_state.pq_hist_case = i
                st.rerun()

    with right:
        c = cases[st.session_state.pq_hist_case]
        icon = "✅" if c.get("status") == "passed_threshold" else "❌"
        st.subheader(f"{icon} {c.get('name', '?')}")
        mc1, mc2 = st.columns(2)
        mc1.metric("Score", f"{c.get('score', 0):.2f}")
        mc2.metric("Threshold", f"{c.get('threshold', 0.7):.2f}")

        st.markdown("**Judge reason**")
        st.write(c.get("reason", ""))
        st.divider()

        turns = c.get("turns", [])
        for turn in turns:
            if turn.get("role") == "user":
                st.markdown("**Input / Criteria**")
                st.info(turn.get("content", ""))
            else:
                st.markdown("**Generated message**")
                color = "#21c354" if c.get("status") == "passed_threshold" else "#ff4b4b"
                st.markdown(
                    f"<div style='background:#1e1e2e;padding:10px 14px;border-radius:6px;"
                    f"border-left:4px solid {color}'>{turn.get('content','')}</div>",
                    unsafe_allow_html=True,
                )


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
