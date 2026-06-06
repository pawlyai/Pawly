"""
Run a single test case through the orchestrator and print per-turn triage signals.

Usage:
    python scripts/run_triage_trace.py <case_name> [model]

    python scripts/run_triage_trace.py alicia_toast_safety_steroid_dose_adjustment
    python scripts/run_triage_trace.py alicia_toast_safety_steroid_dose_adjustment deepseek-v4-pro
"""

import asyncio
import io
import sys
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from dotenv import load_dotenv
load_dotenv()

import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-bot-token")

from triage_trace_core import TraceResult, TurnTrace, list_case_names, run_trace

RESET  = "\033[0m"
RED    = "\033[91m"
ORANGE = "\033[93m"
GREEN  = "\033[92m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[96m"


def _color(level: str | None) -> str:
    if not level:
        return DIM + "none" + RESET
    level = str(level).upper()
    if level == "RED":
        return RED + BOLD + "RED" + RESET
    if level == "ORANGE":
        return ORANGE + BOLD + "ORANGE" + RESET
    if level == "GREEN":
        return GREEN + BOLD + "GREEN" + RESET
    return level


def render(result: TraceResult) -> None:
    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"{BOLD}{CYAN}  TRIAGE TRACE: {result.case_name}{RESET}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"  Pet:      {result.pet_summary}")
    print(f"  Model:    {BOLD}{result.model}{RESET}")
    print(f"  Scenario: {result.scenario[:120]}")
    print(f"  Turns:    {len(result.turns)}")
    print()

    for tt in result.turns:
        print(f"{BOLD}{'-'*70}{RESET}")
        print(f"{BOLD}Turn {tt.turn_num}{RESET}")
        print(f"  {DIM}User:{RESET} {tt.user_text}")
        print()

        print(f"  {BOLD}Rule engine:{RESET}")
        print(f"    Classification : {_color(tt.rule_classification)}")
        print(f"    Score          : {tt.rule_score:.3f}  (RED≥0.70 / ORANGE≥0.30)")
        print(f"    Confidence     : {tt.rule_confidence}")
        if tt.rule_matched:
            print(f"    Matched        : {', '.join(tt.rule_matched)}")
        else:
            print(f"    Matched        : {DIM}(none){RESET}")
        print()

        if tt.error:
            print(f"  {RED}Orchestrator error: {tt.error}{RESET}")
        else:
            print(f"  {BOLD}LLM structured output:{RESET}")
            print(f"    triage_level : {_color(tt.llm_level)}")
            print()
            print(f"  {BOLD}Resolution (take stricter):{RESET}")
            print(f"    Final        : {_color(tt.final_level)}")
            if tt.overridden:
                print(f"    Override     : {BOLD}YES{RESET} — {tt.override_direction}")
            else:
                print(f"    Override     : no")
            if tt.safety_banner:
                print(f"    Safety banner: {RED}{BOLD}PREPENDED{RESET} (rule=RED, llm≠RED)")
            print()
            print(f"  {BOLD}Response preview:{RESET}")
            print(f"    {DIM}{tt.response_preview}...{RESET}")

        print()

    print(f"{BOLD}{CYAN}{'='*70}{RESET}\n")


async def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        names = list_case_names()
        print("Usage: run_triage_trace.py <case_name> [model]")
        print(f"Available cases ({len(names)}):")
        for n in names[:20]:
            print(f"  {n}")
        if len(names) > 20:
            print(f"  ... and {len(names) - 20} more")
        return

    case_name = sys.argv[1]
    model_arg = sys.argv[2] if len(sys.argv) > 2 else None
    result = await run_trace(case_name, model_arg)
    render(result)


if __name__ == "__main__":
    asyncio.run(main())
