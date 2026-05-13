"""
Push prompt sections from prompts_config.yaml to Langfuse Prompt Management.

Usage:
    python scripts/push_prompts_to_langfuse.py

Reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST from .env.
Creates (or updates) the 10 prompts in Langfuse with label "production".
Prompt names match YAML keys 1:1 with a ``pawly_`` prefix
(e.g. ``role`` -> ``pawly_role``).
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

YAML_FILE = (
    pathlib.Path(__file__).parent.parent / "src" / "llm" / "prompts" / "prompts_config.yaml"
)

# Mirrors src.llm.prompts.system.SECTION_KEYS / _LF_PROMPT_NAMES.
SECTION_KEYS = (
    "role",
    "persona",
    "response_format",
    "continuity_rules",
    "pet_health_consultation",
    "pet_behavior_consultation",
    "followup_reminder_support",
    "knowledge_safety",
    "final_reminders",
    "special_population_modifiers",
)
PROMPT_NAMES = {key: f"pawly_{key}" for key in SECTION_KEYS}


def main() -> None:
    with YAML_FILE.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    lf = Langfuse()

    missing = [key for key in SECTION_KEYS if key not in cfg]
    if missing:
        print(f"ERROR: prompts_config.yaml is missing sections: {missing}")
        sys.exit(1)

    for key in SECTION_KEYS:
        name = PROMPT_NAMES[key]
        text = str(cfg[key]).strip()
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
