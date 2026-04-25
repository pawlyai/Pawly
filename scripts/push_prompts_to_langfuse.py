"""
Push prompt sections from prompts_config.yaml to Langfuse Prompt Management.

Usage:
    python scripts/push_prompts_to_langfuse.py

Reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST from .env
Creates (or updates) 4 prompts in Langfuse with label "production".
"""

import pathlib
import sys

import yaml
from dotenv import load_dotenv

load_dotenv()

try:
    from langfuse import Langfuse
except ImportError:
    print("ERROR: langfuse not installed. Run: pip install langfuse")
    sys.exit(1)

YAML_FILE = pathlib.Path(__file__).parent.parent / "src" / "llm" / "prompts" / "prompts_config.yaml"

PROMPT_NAMES = {
    "identity": "pawly-identity",
    "conversation_rules": "pawly-conversation-rules",
    "hard_rules": "pawly-hard-rules",
    "medical_format": "pawly-medical-format",
}

def main() -> None:
    with YAML_FILE.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    lf = Langfuse()

    for key, name in PROMPT_NAMES.items():
        text = cfg[key].strip()
        lf.create_prompt(
            name=name,
            prompt=text,
            type="text",
            labels=["production"],
        )
        print(f"  pushed: {name}")

    print("\nDone. Open Langfuse > Prompts to verify.")

if __name__ == "__main__":
    main()
