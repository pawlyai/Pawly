"""Programme LLM Eval — centralized dashboard for the new-pet-arrival
validation set.

Rows are produced by the Go in-process runner (records-service
`cmd/programme_eval`) and written to the `programme_eval_run` Postgres table.
This page reads that table directly — Postgres is the seam, so the Go runner
and this Python dashboard stay fully decoupled.
"""

import os
import re

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

st.set_page_config(page_title="Programme LLM Eval", page_icon="🧪", layout="wide")

# Default points at the throwaway eval Postgres the runner writes to.
DEFAULT_DB = "postgresql://pawly:pawly_dev@localhost:55432/pawly"


def sync_url(url: str) -> str:
    """Normalise an async DSN to a sync (psycopg2) one for pandas/SQLAlchemy."""
    url = re.sub(r"\+asyncpg", "", url or "")
    return url or DEFAULT_DB


@st.cache_data(ttl=20)
def load(url: str) -> pd.DataFrame:
    engine = create_engine(url)
    return pd.read_sql(
        "SELECT * FROM programme_eval_run ORDER BY created_at DESC", engine
    )


st.title("🧪 Programme LLM Eval")
st.caption(
    "New-pet-arrival LLM validation — written by the Go in-process runner, "
    "read live from Postgres."
)

# Default to the eval DB (NOT the app's DATABASE_URL — that's a different
# database and doesn't hold programme_eval_run). Override in the box below.
default_db = os.environ.get("PROGRAMME_EVAL_DB", DEFAULT_DB)
db_url = sync_url(st.sidebar.text_input("Eval DATABASE_URL", value=default_db))

try:
    df = load(db_url)
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not read `programme_eval_run`: {exc}")
    st.stop()

if df.empty:
    st.info(
        "No eval runs yet. Produce some with:\n\n"
        "```\nGOOGLE_API_KEY=… go run ./cmd/programme_eval \\\n"
        "  -db 'host=localhost port=55432 user=pawly password=pawly_dev dbname=pawly sslmode=disable' \\\n"
        "  -judge -samples 3\n```"
    )
    st.stop()

# ── Filters ──────────────────────────────────────────────────────────────────
runs = sorted(df["run_id"].dropna().unique(), reverse=True)
run = st.sidebar.selectbox("Run", runs)
d = df[df["run_id"] == run].copy()

surfaces = sorted(d["surface"].dropna().unique())
picked = st.sidebar.multiselect("Surfaces", surfaces, default=surfaces)
d = d[d["surface"].isin(picked)]

if st.sidebar.button("↻ Refresh"):
    st.cache_data.clear()
    st.rerun()

# ── Overview ─────────────────────────────────────────────────────────────────
judged = d[d["judge_score"].notna()]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Scenarios", len(d))
c2.metric("Mean judge score", f"{judged['judge_score'].mean():.2f}" if len(judged) else "—")
c3.metric("Safety pass", f"{100 * d['safety_pass'].mean():.0f}%")
c4.metric("Judge pass", f"{100 * d['judge_pass'].fillna(False).mean():.0f}%")

model_str = ", ".join(sorted(d["model"].dropna().unique()))
st.caption(f"run **{run}** · model(s): {model_str}")

# ── Mean score by surface ────────────────────────────────────────────────────
if len(judged):
    st.subheader("Mean judge score by surface (1–5)")
    st.bar_chart(judged.groupby("surface")["judge_score"].mean())

# ── Safety board (violations first) ──────────────────────────────────────────
violations = d[~d["safety_pass"].astype(bool)]
if len(violations):
    st.subheader("🔴 Safety violations")
    st.dataframe(
        violations[["scenario_id", "surface", "llm_output"]],
        use_container_width=True,
        hide_index=True,
    )

# ── Scenario drill-down ──────────────────────────────────────────────────────
st.subheader("Scenarios")


def badge(ok) -> str:
    return "✅" if bool(ok) else "❌"


for _, row in d.iterrows():
    score = row["judge_score"]
    score_str = f"{score:.2f}" if pd.notna(score) else "—"
    mark = "🟢" if bool(row.get("judge_pass")) else ("🔴" if pd.notna(score) else "⚪")
    with st.expander(f"{mark}  {row['scenario_id']}  ·  {row['surface']}  ·  judge={score_str}"):
        b = st.columns(3)
        b[0].markdown(f"**Safety** {badge(row['safety_pass'])}")
        b[1].markdown(f"**Grounding** {badge(row['grounding_pass'])}")
        b[2].markdown(f"**Structure** {badge(row['structure_pass'])}")

        st.markdown("**Input context**")
        st.code(row["input_context"] or "", language="text")
        st.markdown("**LLM output**")
        st.write(row["llm_output"] or "_(empty)_")
        st.markdown("**Judge reason**")
        st.info(row["judge_reason"] or "—")
        st.caption(f"model={row['model']} · latency={row['latency_ms']}ms")
