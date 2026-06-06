"""
Seed Langfuse with the current YAML prompt sections from prompts_config.yaml.

Each section is created/updated as a Langfuse text prompt named ``pawly_{key}``.
Running this script is idempotent — re-running creates a new version but keeps prior versions
in Langfuse history, so you can roll back via the Langfuse UI.

Usage:
    # Uses .env from repo root (picks up LANGFUSE_* and PROMPT_HOT_RELOAD):
    python scripts/seed_langfuse_prompts.py

    # Override Langfuse host for a remote instance:
    LANGFUSE_HOST=http://129.212.231.81:3000 python scripts/seed_langfuse_prompts.py
"""

import io
import pathlib
import sys

import yaml
from dotenv import load_dotenv

# Force UTF-8 on Windows consoles to avoid cp1252 encoding errors
if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") not in ("utf8", "utf-8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env", override=False)

import os  # noqa: E402 — after dotenv
import sys as _sys  # noqa: E402
_sys.path.insert(0, str(REPO_ROOT))
from src.llm.prompts.system import SECTION_KEYS  # noqa: E402 — after path setup

LANGFUSE_HOST = os.environ.get("LANGFUSE_HOST", "http://localhost:3000")
LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "")

if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
    print("ERROR: LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set.")
    sys.exit(1)

try:
    from langfuse import Langfuse
except ImportError:
    print("ERROR: langfuse package not installed. Run: pip install langfuse")
    sys.exit(1)

CONFIG_FILE = REPO_ROOT / "src" / "llm" / "prompts" / "prompts_config.yaml"
PROACTIVE_CONFIG_FILE = REPO_ROOT / "src" / "llm" / "prompts" / "proactive_prompts.yaml"


def load_yaml_sections() -> dict[str, str]:
    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        cfg: dict = yaml.safe_load(f)
    with PROACTIVE_CONFIG_FILE.open("r", encoding="utf-8") as f:
        cfg.update(yaml.safe_load(f) or {})
    return {key: str(cfg[key]).rstrip("\n") for key in SECTION_KEYS if key in cfg}


def main() -> None:
    print(f"Connecting to Langfuse at {LANGFUSE_HOST} …")
    lf = Langfuse(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_HOST,
    )

    sections = load_yaml_sections()
    print(f"Loaded {len(sections)} sections from {CONFIG_FILE.relative_to(REPO_ROOT)}\n")

    for key, text in sections.items():
        prompt_name = f"pawly_{key}"
        preview = text[:80].replace("\n", " ")
        print(f"  -> {prompt_name}  ({len(text)} chars)  \"{preview}...\"")
        lf.create_prompt(
            name=prompt_name,
            type="text",
            prompt=text,
            labels=["production"],
        )

    lf.flush()
    print(f"\nDone. {len(sections)} prompts seeded/updated in Langfuse.")
    print("The bot will pick up changes within ~5 minutes (Langfuse SDK TTL).")
    print("Make sure PROMPT_HOT_RELOAD=true is set in the VPS .env.")


if __name__ == "__main__":
    main()
