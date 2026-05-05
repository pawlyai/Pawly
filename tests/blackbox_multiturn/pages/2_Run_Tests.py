"""Trigger a new evaluation run with a chosen model + topics."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent
BLACKBOX_DIR = Path(__file__).parent.parent  # tests/blackbox_multiturn/
RESULTS_DIR = BLACKBOX_DIR / "results"
CACHE_PATH = RESULTS_DIR / "translation_cache.json"

for _p in (str(REPO_ROOT), str(BLACKBOX_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st

from src.llm.providers import SUPPORTED_MODELS
from utils.export import pre_translate_report  # noqa: E402

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

        st.subheader("Code branch / tag")
        git_ref_input = st.text_input(
            "Branch, tag, or version label",
            value="",
            placeholder="e.g. main, release-1.2, v0.4.0, abcdef0",
            help="Free-form label stamped on the report so you can triage and "
                 "compare runs from different code revisions. Stored in the "
                 "report filename and summary content.",
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

        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        # Single session ID shared across all topics in this batch run so the
        # export panel can group them as one regression run.
        _run_session_id = time.strftime("%Y%m%d_%H%M%S")

        for idx, topic in enumerate(selected_topics):
            progress.progress(
                idx / len(selected_topics),
                text=f"Running {topic} on {model}…",
            )

            # Snapshot existing reports so we can identify new ones after the run.
            before = {
                f for f in RESULTS_DIR.glob("*.json")
                if f.name != "translation_cache.json"
            } if RESULTS_DIR.exists() else set()

            cmd = [
                sys.executable, "-m", "pytest",
                TEST_FILE,
                f"--multiturn-topic={topic}",
                f"--model={model}",
                f"--git-ref={git_ref_input}",
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
                continue

            # Detect new report files produced by this topic run.
            if RESULTS_DIR.exists():
                after = {
                    f for f in RESULTS_DIR.glob("*.json")
                    if f.name != "translation_cache.json"
                }
                new_reports = sorted(after - before, key=lambda f: f.stat().st_mtime)

                # Tag each new report with the shared session ID so the export
                # panel can group all topics from this batch into one run.
                for _rp in new_reports:
                    try:
                        _rd = json.loads(_rp.read_text(encoding="utf-8"))
                        _rd.setdefault("summary", {})["run_session_id"] = _run_session_id
                        _rp.write_text(json.dumps(_rd, indent=2, ensure_ascii=True), encoding="utf-8")
                    except Exception:
                        pass
            else:
                new_reports = []

            # Pre-translate turns in any new report so CSV export is instant later.
            if api_key and new_reports:
                for report_path in new_reports:
                    trans_bar = st.progress(
                        0.0,
                        text=f"Pre-translating {report_path.name}…",
                    )

                    def _on_trans(
                        done: int,
                        total: int,
                        _bar: st.delta_generator.DeltaGenerator = trans_bar,
                    ) -> None:
                        _bar.progress(
                            done / max(total, 1),
                            text=f"Pre-translating turns… ({done}/{total})",
                        )

                    n = pre_translate_report(report_path, CACHE_PATH, api_key, on_progress=_on_trans)
                    label = (
                        f"Cached {n} translations for {report_path.stem} ✓"
                        if n
                        else f"All turns already cached for {report_path.stem} ✓"
                    )
                    trans_bar.progress(1.0, text=label)

        progress.progress(1.0, text="Done")
        st.success("Run finished. Check the **Reports** or **Compare** pages for results.")


main()
