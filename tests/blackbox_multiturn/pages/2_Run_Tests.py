"""Trigger a new evaluation run with a chosen model + topics."""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import streamlit as st

from src.llm.providers import SUPPORTED_MODELS

st.set_page_config(page_title="Run Tests", page_icon="▶️", layout="wide")
TEST_DATA_DIR = REPO_ROOT / "tests" / "blackbox_multiturn" / "test_data"
TEST_FILE = "tests/blackbox_multiturn/test_message_handler_multiturn.py"


def list_topics() -> list[str]:
    if not TEST_DATA_DIR.exists():
        return []
    return sorted(
        f.name.replace("_cases.json", "") for f in TEST_DATA_DIR.glob("*_cases.json")
    )


def main() -> None:
    st.title("▶️ Run Tests")
    st.caption("Pick a model and topics, then trigger a fresh evaluation.")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Model")
        provider = st.selectbox("Provider", list(SUPPORTED_MODELS.keys()))
        model = st.selectbox("Model", SUPPORTED_MODELS[provider])

        st.subheader("API key check")
        env_key = {
            "Gemini": "GOOGLE_API_KEY",
            "Anthropic": "ANTHROPIC_API_KEY",
            "OpenAI": "OPENAI_API_KEY",
            "DeepSeek": "DEEPSEEK_API_KEY",
        }[provider]
        if os.environ.get(env_key, "").strip():
            st.success(f"{env_key} is set ✓")
        else:
            st.error(f"{env_key} is not set — runs will be skipped")

    with col2:
        st.subheader("Topics")
        topics = list_topics()
        if not topics:
            st.error("No topics found under tests/blackbox_multiturn/test_data/")
            return
        selected_topics = st.multiselect(
            "Test topics to run",
            topics,
            default=topics[:1] if topics else [],
        )

        st.subheader("Options")
        verbose = st.checkbox("Verbose output (-vv)", value=True)

    st.divider()

    if st.button("🚀 Run Evaluation", type="primary", use_container_width=True):
        if not selected_topics:
            st.warning("Pick at least one topic.")
            return

        log_area = st.empty()
        progress = st.progress(0.0, text="Starting…")
        all_logs: list[str] = []

        for idx, topic in enumerate(selected_topics):
            progress.progress(
                idx / len(selected_topics),
                text=f"Running {topic} on {model}…",
            )
            cmd = [
                sys.executable, "-m", "pytest",
                TEST_FILE,
                f"--multiturn-topic={topic}",
                f"--model={model}",
                "-s",
                "-vv" if verbose else "-v",
            ]
            env = {**os.environ, "PAWLY_MODEL": model}
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(REPO_ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env,
                    text=True,
                    bufsize=1,
                )
                all_logs.append(f"\n━━ {topic} | {model} ━━")
                assert proc.stdout is not None
                for line in proc.stdout:
                    all_logs.append(line.rstrip())
                    log_area.code("\n".join(all_logs[-200:]), language="text")
                proc.wait()
                all_logs.append(f"[exit code: {proc.returncode}]")
            except Exception as exc:
                all_logs.append(f"[error] {exc}")
                log_area.code("\n".join(all_logs[-200:]), language="text")

        progress.progress(1.0, text="Done")
        st.success("Run finished. Check the **Reports** or **Compare** pages for results.")


main()
