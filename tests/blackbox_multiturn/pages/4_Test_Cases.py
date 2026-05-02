"""Test case browser, editor, and LLM-assisted generator."""

import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import streamlit as st

st.set_page_config(page_title="Test Cases", page_icon="📝", layout="wide")

TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"


def list_topic_files() -> list[Path]:
    if not TEST_DATA_DIR.exists():
        return []
    return sorted(TEST_DATA_DIR.glob("*_cases.json"))


def load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_cases(path: Path, cases: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8")


CASE_TEMPLATE = {
    "name": "new_case_name",
    "user_display_name": "Owner",
    "scenario": "Describe the conversational scenario being evaluated.",
    "expected_outcome": "What should the assistant do well?",
    "chatbot_role": "Pawly is a pet care assistant. ...",
    "criteria": "How should the judge evaluate this case? List specific must-do and must-not-do behaviors.",
    "threshold": 0.7,
    "pet_profile": {
        "name": "Pet",
        "species": "dog",
        "breed": "Mixed",
        "age_in_months": 36,
        "gender": "female",
        "neutered_status": "neutered",
        "weight_latest": 12.0,
    },
    "memories": [],
    "recent_turns": [],
    "user_turns": [
        "First user message.",
        "Follow-up message.",
    ],
    "metadata": {"focus": "general", "layer": "handler_blackbox_multiturn"},
}


GENERATOR_PROMPT = """You generate Pawly multi-turn evaluation test cases as a JSON array.
Each case is a JSON object with this exact schema:
{
  "name": "snake_case_unique_id",
  "user_display_name": "Owner first name",
  "scenario": "1-2 sentence summary of the conversational scenario",
  "expected_outcome": "what the assistant should accomplish",
  "chatbot_role": "Pawly's role and constraints",
  "criteria": "evaluation rubric — what to reward and what to penalize",
  "threshold": 0.6 to 0.8,
  "pet_profile": {"name": "...", "species": "dog|cat", "breed": "...",
                  "age_in_months": int, "gender": "male|female",
                  "neutered_status": "neutered|intact|unknown", "weight_latest": float},
  "memories": [],
  "recent_turns": [],
  "user_turns": [3-6 conversational turns from the owner, plain strings],
  "metadata": {"focus": "<<FOCUS>>", "layer": "handler_blackbox_multiturn"}
}

Topic: <<TOPIC>>
Focus area: <<FOCUS>>
Number of cases to generate: <<COUNT>>

Output ONLY the JSON array — no commentary, no markdown fences."""


def build_prompt(topic: str, focus: str, count: int) -> str:
    return (
        GENERATOR_PROMPT
        .replace("<<TOPIC>>", topic)
        .replace("<<FOCUS>>", focus)
        .replace("<<COUNT>>", str(count))
    )


def call_generator(prompt: str, model: str) -> str:
    """Run the generator prompt through whichever provider matches the model name."""
    if model.startswith("claude"):
        from anthropic import Anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    if model.startswith("gpt"):
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        return resp.choices[0].message.content or ""
    if model.startswith("deepseek"):
        # DeepSeek serves an OpenAI-compatible API at https://api.deepseek.com/v1
        from openai import OpenAI
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not set")
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        return resp.choices[0].message.content or ""
    # Default: Gemini
    from google import genai
    from google.genai import types
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
        config=types.GenerateContentConfig(max_output_tokens=4096, temperature=0.9),
    )
    return resp.text or ""


def parse_generated(text: str) -> list[dict[str, Any]]:
    s = text.strip()
    if s.startswith("```"):
        # Strip code fences
        s = s.split("```", 2)
        s = s[1] if len(s) > 1 else s[0]
        if s.startswith("json"):
            s = s[4:]
    s = s.strip()
    return json.loads(s)


def main() -> None:
    st.title("📝 Test Cases")
    st.caption("Browse, edit, add, or LLM-generate evaluation cases.")

    files = list_topic_files()
    if not files:
        st.error("No test data files found.")
        return

    file_names = [f.name for f in files]
    selected_name = st.selectbox("Topic file", file_names)
    selected_file = TEST_DATA_DIR / selected_name
    cases = load_cases(selected_file)

    tab_browse, tab_edit, tab_add, tab_generate = st.tabs(
        ["📚 Browse", "✏️ Edit", "➕ Add", "🤖 Generate"]
    )

    # ── Browse ───────────────────────────────────────────────────────────────
    with tab_browse:
        st.markdown(f"**{len(cases)} cases in {selected_name}**")
        for case in cases:
            with st.expander(f"{case.get('name', '?')} — threshold {case.get('threshold', '?')}"):
                st.markdown(f"**Scenario:** {case.get('scenario', '')}")
                st.markdown(f"**Expected:** {case.get('expected_outcome', '')}")
                st.markdown("**User turns:**")
                for i, turn in enumerate(case.get("user_turns", []), 1):
                    st.markdown(f"{i}. {turn}")

    # ── Edit ─────────────────────────────────────────────────────────────────
    with tab_edit:
        names = [c.get("name", f"case_{i}") for i, c in enumerate(cases)]
        if not names:
            st.info("No cases to edit.")
        else:
            pick = st.selectbox("Case", names, key="edit_pick")
            idx = names.index(pick)
            edited = st.text_area(
                "JSON",
                value=json.dumps(cases[idx], indent=2, ensure_ascii=False),
                height=500,
                key=f"edit_text_{idx}",
            )
            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("💾 Save", type="primary"):
                    try:
                        cases[idx] = json.loads(edited)
                        save_cases(selected_file, cases)
                        st.success("Saved.")
                    except json.JSONDecodeError as e:
                        st.error(f"Invalid JSON: {e}")
            with c2:
                if st.button("🗑 Delete"):
                    cases.pop(idx)
                    save_cases(selected_file, cases)
                    st.success("Deleted. Reload the page.")

    # ── Add ──────────────────────────────────────────────────────────────────
    with tab_add:
        st.markdown("Edit the template below and click **Add**.")
        new_text = st.text_area(
            "New case JSON",
            value=json.dumps(CASE_TEMPLATE, indent=2, ensure_ascii=False),
            height=500,
            key="add_text",
        )
        if st.button("➕ Add", type="primary"):
            try:
                new_case = json.loads(new_text)
                cases.append(new_case)
                save_cases(selected_file, cases)
                st.success(f"Added {new_case.get('name', '?')}.")
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")

    # ── Generate ─────────────────────────────────────────────────────────────
    with tab_generate:
        st.markdown("Generate cases via an LLM. The output is parsed as JSON; review before saving.")
        from src.llm.providers import all_models
        col1, col2, col3 = st.columns(3)
        with col1:
            gen_model = st.selectbox("Model", all_models(), index=0)
        with col2:
            count = st.number_input("Count", min_value=1, max_value=10, value=3)
        with col3:
            focus = st.text_input("Focus area", value="vomiting clarification")

        topic = selected_name.replace("_cases.json", "")
        prompt = build_prompt(topic=topic, focus=focus, count=count)
        with st.expander("Show prompt"):
            st.code(prompt, language="text")

        if st.button("🤖 Generate", type="primary"):
            with st.spinner(f"Calling {gen_model}…"):
                try:
                    raw = call_generator(prompt, gen_model)
                    parsed = parse_generated(raw)
                    st.session_state["last_generated"] = parsed
                    st.success(f"Got {len(parsed)} cases.")
                except Exception as exc:
                    st.error(f"Generation failed: {exc}")
                    st.session_state["last_generated"] = None

        if st.session_state.get("last_generated"):
            preview = st.text_area(
                "Generated cases (review before saving)",
                value=json.dumps(st.session_state["last_generated"], indent=2, ensure_ascii=False),
                height=400,
                key="gen_preview",
            )
            if st.button("💾 Append to topic file", type="primary"):
                try:
                    new_cases = json.loads(preview)
                    cases.extend(new_cases)
                    save_cases(selected_file, cases)
                    st.success(f"Appended {len(new_cases)} cases to {selected_name}.")
                    st.session_state["last_generated"] = None
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON: {e}")


main()
