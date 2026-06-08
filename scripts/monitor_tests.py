#!/usr/bin/env python3
"""
Monitor 200-case test progress in real-time.

Polls pytest output logs and displays running statistics.
"""
import pathlib
import re
import time
import sys
from datetime import datetime

LOG_FILES = {
    "Mem0": pathlib.Path("test_200cases_mem0.log"),
    "Multiagent": pathlib.Path("test_200cases_multiagent.log"),
}

def parse_pytest_progress(log_path: pathlib.Path) -> dict:
    """Extract test progress from pytest output."""
    if not log_path.exists():
        return {"status": "not_started"}

    try:
        content = log_path.read_text(encoding="utf-8", errors="replace")
    except:
        return {"status": "reading_error"}

    # Look for progress patterns: "...FF...." or "[X%]"
    progress_match = re.search(r"(\d+)%.*?created", content)
    if progress_match:
        pct = int(progress_match.group(1))
        return {"status": "running", "progress": pct}

    # Look for final summary
    summary_match = re.search(r"(\d+)\s+(?:passed|failed|error)", content)
    if summary_match:
        passed_match = re.search(r"(\d+)\s+passed", content)
        failed_match = re.search(r"(\d+)\s+failed", content)
        error_match = re.search(r"(\d+)\s+error", content)

        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        errors = int(error_match.group(1)) if error_match else 0
        total = passed + failed + errors

        return {
            "status": "completed" if total == 200 else "incomplete",
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "total": total,
            "pass_rate": round(100 * passed / 200, 1) if total > 0 else 0,
        }

    # Check if still initializing
    if "created:" in content or "workers" in content:
        return {"status": "initializing"}

    return {"status": "unknown"}


def display_status():
    """Display current status of both tests."""
    print("\n" + "=" * 80)
    print(f"Test Monitor — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    all_done = True
    for backend, log_path in LOG_FILES.items():
        status = parse_pytest_progress(log_path)
        print(f"\n{backend}:")
        print("-" * 40)

        if status["status"] == "not_started":
            print("  [X] Not started")
            all_done = False
        elif status["status"] == "initializing":
            print("  [~] Initializing workers...")
            all_done = False
        elif status["status"] == "running":
            print(f"  [~] Running ({status.get('progress', '?')}%)...")
            all_done = False
        elif status["status"] == "completed":
            pct = status.get("pass_rate", 0)
            symbol = "[OK]" if pct >= 80 else "[!]" if pct >= 60 else "[FAIL]"
            print(f"  {symbol} Completed")
            print(f"    Passed: {status['passed']}/200")
            print(f"    Failed: {status['failed']}/200")
            print(f"    Errors: {status['errors']}/200")
            print(f"    Pass Rate: {pct}%")
        elif status["status"] == "incomplete":
            print(f"  [?] Incomplete run")
            print(f"    Passed: {status.get('passed', '?')}/200")
            print(f"    Failed: {status.get('failed', '?')}/200")
            all_done = False
        else:
            print(f"  ? Status unknown (check log)")
            all_done = False

    print("\n" + "=" * 80)
    if all_done:
        print("BOTH TESTS COMPLETED")
        print("Compare results with: python scripts/compare_200case_results.py")
    else:
        print("Tests still running. Check logs:")
        for backend, log_path in LOG_FILES.items():
            print(f"  tail -f {log_path}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    if "--loop" in sys.argv:
        # Run continuously
        while True:
            display_status()
            time.sleep(30)  # Check every 30 seconds
    else:
        display_status()
