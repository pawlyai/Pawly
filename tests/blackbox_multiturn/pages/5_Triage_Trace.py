"""Per-turn triage signal inspector for any regression test case."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
for _p in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-bot-token")
os.environ.setdefault("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))

import streamlit as st

st.set_page_config(page_title="Triage Trace", page_icon="🔍", layout="wide")

from triage_trace_core import CaseMeta, TraceResult, TurnTrace, list_case_names, load_case_meta, run_trace_sync  # noqa: E402
from src.llm.providers import SUPPORTED_MODELS  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

_LEVEL_COLOR = {"RED": "#ff4b4b", "ORANGE": "#ff8c00", "GREEN": "#21c354"}
_LEVEL_ICON  = {"RED": "🔴", "ORANGE": "🟠", "GREEN": "🟢"}


def _badge(level: str | None) -> str:
    if not level:
        return "<span style='color:#888'>—</span>"
    upper = level.upper()
    color = _LEVEL_COLOR.get(upper, "#888")
    icon  = _LEVEL_ICON.get(upper, "")
    return (
        f"<span style='background:{color};color:white;padding:2px 10px;"
        f"border-radius:4px;font-weight:700;font-size:0.9em'>"
        f"{icon} {upper}</span>"
    )


def _render_turn(tt: TurnTrace) -> None:
    rule_upper = (tt.rule_classification or "").upper()
    final_upper = (tt.final_level or "").upper()
    color = _LEVEL_COLOR.get(final_upper, "#888")

    title = (
        f"Turn {tt.turn_num}  —  "
        f"Rule: {tt.rule_classification}  |  "
        f"LLM: {tt.llm_level or '—'}  |  "
        f"Final: {tt.final_level or '—'}"
        + ("  ⚠️ OVERRIDE" if tt.overridden else "")
        + ("  🚨 BANNER" if tt.safety_banner else "")
        + ("  ❌ ERROR" if tt.error else "")
    )

    with st.expander(title, expanded=(final_upper == "RED" or tt.error is not None)):
        st.markdown(
            f"<div style='background:#1e1e2e;padding:10px 14px;border-radius:6px;"
            f"border-left:4px solid {color};margin-bottom:12px'>"
            f"<span style='color:#aaa;font-size:0.8em'>USER</span><br>"
            f"<span style='font-size:1em'>{tt.user_text}</span></div>",
            unsafe_allow_html=True,
        )

        if tt.error:
            st.error(f"Orchestrator error: {tt.error}")
            return

        col_rule, col_llm, col_final = st.columns(3)

        with col_rule:
            st.markdown("**Rule engine**")
            st.markdown(_badge(tt.rule_classification), unsafe_allow_html=True)
            st.caption(f"score {tt.rule_score:.3f}  ·  {tt.rule_confidence} confidence")
            if tt.rule_matched:
                st.caption("matched: " + ", ".join(f"`{r}`" for r in tt.rule_matched))
            else:
                st.caption("matched: *(none)*")

        with col_llm:
            st.markdown("**LLM output**")
            st.markdown(_badge(tt.llm_level), unsafe_allow_html=True)

        with col_final:
            st.markdown("**Final (resolved)**")
            st.markdown(_badge(tt.final_level), unsafe_allow_html=True)
            if tt.overridden:
                st.caption(f"⚠️ overridden — {tt.override_direction}")
            if tt.safety_banner:
                st.warning("Safety banner prepended (rule=RED, LLM≠RED)", icon="🚨")

        st.markdown("---")
        st.markdown(
            f"<span style='color:#aaa;font-size:0.8em'>RESPONSE PREVIEW</span><br>"
            f"<em>{tt.response_preview}…</em>",
            unsafe_allow_html=True,
        )


def _render_result(result: TraceResult) -> None:
    # Summary bar
    levels = [t.final_level or "" for t in result.turns]
    reds    = levels.count("RED")
    oranges = levels.count("ORANGE")
    greens  = levels.count("GREEN")

    st.markdown(
        f"**{result.case_name}** · `{result.model}` · "
        f"{len(result.turns)} turns · "
        f"🔴 {reds}  🟠 {oranges}  🟢 {greens}"
    )
    st.caption(result.pet_summary)
    if result.scenario:
        st.info(result.scenario, icon="📋")

    st.markdown("---")
    for tt in result.turns:
        _render_turn(tt)


# ── Main UI ───────────────────────────────────────────────────────────────────

def main() -> None:
    st.title("🔍 Triage Trace")
    st.caption("Step through each turn and inspect rule engine → LLM → final resolution.")

    case_names = list_case_names()
    if not case_names:
        st.error("No test cases found. Check TEST_DATA path in triage_trace_core.py.")
        return

    # ── Controls ─────────────────────────────────────────────────────────────
    col_case, col_model, col_btn = st.columns([3, 2, 1])

    with col_case:
        case_name = st.selectbox("Test case", case_names, key="tt_case")

    with col_model:
        flat_models = [m for ms in SUPPORTED_MODELS.values() for m in ms]
        default_idx = next(
            (i for i, m in enumerate(flat_models) if "flash" in m.lower()), 0
        )
        model = st.selectbox("Model", flat_models, index=default_idx, key="tt_model")

    with col_btn:
        st.write("")  # vertical align
        run_btn = st.button("▶ Run Trace", type="primary", use_container_width=True)

    # ── Case preview ──────────────────────────────────────────────────────────
    if case_name:
        meta = load_case_meta(case_name)
        if meta:
            with st.expander("Case preview", expanded=False):
                st.markdown(f"**Scenario:** {meta.scenario}")
                st.markdown(f"**Pet:** {meta.pet_summary}")
                st.markdown(f"**Turns:** {meta.turn_count}")

    # ── Run ───────────────────────────────────────────────────────────────────
    if run_btn:
        google_key = os.environ.get("GOOGLE_API_KEY", "")
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if model.startswith("gemini") and (not google_key or google_key.startswith("test")):
            st.error("GOOGLE_API_KEY not set — cannot call Gemini.")
            return
        if "deepseek" in model and not deepseek_key:
            st.error("DEEPSEEK_API_KEY not set — cannot call DeepSeek.")
            return

        with st.spinner(f"Running {case_name} on {model}…"):
            try:
                result = run_trace_sync(case_name, model)
                st.session_state["tt_result"] = result
            except Exception as exc:
                st.error(f"Trace failed: {exc}")
                st.session_state["tt_result"] = None

    # ── Render stored result ──────────────────────────────────────────────────
    result: TraceResult | None = st.session_state.get("tt_result")
    if result is not None:
        if result.case_name != case_name:
            st.info(
                f"Showing trace for **{result.case_name}** "
                f"(press ▶ Run Trace to re-run for the current selection).",
                icon="ℹ️",
            )
        _render_result(result)


main()
