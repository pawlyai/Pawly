"""
Conftest for blackbox proactive quality tests.

Sets up:
  - env vars (same as blackbox_multiturn)
  - deepeval_model fixture (session-scoped) using PAWLY_EVAL_LLM env var
  - cases fixture (parametrized) from proactive_quality_cases.json

Judge model priority:
  1. PAWLY_EVAL_LLM=deepseek-v4-pro → DeepSeekDeepEvalModel (handles reasoning output)
  2. PAWLY_EVAL_LLM=gemini/... or other → LiteLLMModel
  3. GOOGLE_API_KEY available → GeminiModel(gemini-2.5-flash)
  4. Skip
"""

import json
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load .env before setdefault so real keys win over test placeholders
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-bot-token")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-key")
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")

# Force UTF-8 on Windows to avoid cp1252 emoji crashes
if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") not in ("utf8", "utf-8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

TEST_DATA = Path(__file__).parent / "test_data" / "proactive_quality_cases.json"

_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
_DEEPSEEK_MODELS = {"deepseek-v4-pro", "deepseek-v4-flash"}
# Reasoning models need enough tokens for CoT before the actual answer appears
_DEEPSEEK_MAX_TOKENS = 4000


def _load_cases() -> list[dict]:
    with TEST_DATA.open(encoding="utf-8") as f:
        return json.load(f)


def _make_gemini_model(model_name: str, api_key: str):
    """Custom deepeval wrapper for Gemini — avoids GeminiModel.generate_raw_response crash."""
    import google.genai as genai
    from google.genai import types
    from deepeval.models import DeepEvalBaseLLM

    class GeminiDeepEvalModel(DeepEvalBaseLLM):
        def __init__(self):
            self._client = genai.Client(api_key=api_key)
            self.model_name = model_name

        def load_model(self):
            return self._client

        def generate(self, prompt: str, schema=None) -> str:
            resp = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=4000, temperature=0.0),
            )
            return resp.text or ""

        async def a_generate(self, prompt: str, schema=None) -> str:
            return self.generate(prompt, schema)

        def get_model_name(self) -> str:
            return self.model_name

    return GeminiDeepEvalModel()


def _make_deepseek_model(model_name: str, api_key: str):
    """
    Build a deepeval-compatible judge wrapper for DeepSeek reasoning models.

    DeepSeek v4-pro is a reasoning model: it stores chain-of-thought in
    `reasoning_content` and puts the final answer in `content` only after
    thinking completes. A small max_tokens budget produces an empty `content`.
    This wrapper sets max_tokens=4000 and extracts content correctly.
    """
    from deepeval.models import DeepEvalBaseLLM
    from openai import OpenAI

    class DeepSeekDeepEvalModel(DeepEvalBaseLLM):
        def __init__(self):
            self._client = OpenAI(api_key=api_key, base_url=_DEEPSEEK_BASE_URL)
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

    return DeepSeekDeepEvalModel()


@pytest.fixture(scope="session")
def deepeval_model():
    """
    Resolve the judge model.

    Priority:
      1. PAWLY_EVAL_LLM=deepseek-v4-pro  → DeepSeekDeepEvalModel
      2. PAWLY_EVAL_LLM=<other>           → LiteLLMModel
      3. GOOGLE_API_KEY available         → GeminiModel(gemini-2.5-flash)
      4. Skip
    """
    pytest.importorskip("deepeval")
    from deepeval.models import LiteLLMModel

    model_name = os.environ.get("PAWLY_EVAL_LLM") or os.environ.get("DEEPEVAL_MODEL")
    google_key = os.environ.get("GOOGLE_API_KEY", "")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")

    if model_name and model_name in _DEEPSEEK_MODELS:
        if not deepseek_key:
            pytest.skip(f"DEEPSEEK_API_KEY not set — cannot use judge {model_name}")
        return _make_deepseek_model(model_name, deepseek_key)

    if model_name:
        # Explicit override — use LiteLLM bridge (supports gemini/, claude/, etc.)
        return LiteLLMModel(model=model_name)

    if google_key and not google_key.startswith("test"):
        # Default: judge with Gemini Flash using the same key as generation.
        # Use custom wrapper — deepeval GeminiModel crashes on generate_raw_response.
        return _make_gemini_model("gemini-2.5-flash", google_key)

    pytest.skip("No eval LLM configured — set PAWLY_EVAL_LLM or GOOGLE_API_KEY")


@pytest.fixture(
    params=_load_cases(),
    ids=[c["id"] for c in _load_cases()],
)
def proactive_case(request) -> dict:
    return request.param
