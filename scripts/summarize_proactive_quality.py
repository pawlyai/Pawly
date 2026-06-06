#!/usr/bin/env python3
"""
Print a markdown summary of proactive quality results for $GITHUB_STEP_SUMMARY.

Usage:
    python scripts/summarize_proactive_quality.py [results.jsonl]
    python scripts/summarize_proactive_quality.py proactive_quality_results.jsonl >> $GITHUB_STEP_SUMMARY
"""

import json
import os
import sys
from pathlib import Path


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("proactive_quality_results.jsonl")
    if not path.exists():
        print("## Proactive Quality Results\n\n_No results file found._")
        return

    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        print("## Proactive Quality Results\n\n_Results file is empty._")
        return

    judge = os.environ.get("PAWLY_EVAL_LLM", "unknown")
    passed = sum(1 for r in rows if r.get("passed"))
    total = len(rows)
    overall = "✅ All passed" if passed == total else f"⚠️ {total - passed} failed"

    print("## Proactive Quality Results\n")
    print(f"**Judge**: `{judge}` | **{passed}/{total} passed** — {overall}\n")
    print("| Case | Score | Status | Reason |")
    print("|------|-------|--------|--------|")
    for r in rows:
        icon = "✅" if r.get("passed") else "❌"
        status = "PASS" if r.get("passed") else "FAIL"
        score = r.get("score", 0.0)
        reason = (r.get("reason") or "")[:120]
        print(f"| `{r['case_id']}` | {score:.2f} | {icon} {status} | {reason} |")

    # Print generated messages section for failed cases
    failed = [r for r in rows if not r.get("passed")]
    if failed:
        print("\n### Failed case outputs\n")
        for r in failed:
            print(f"**`{r['case_id']}`**")
            print(f"> {r.get('generated', '')}\n")
            print(f"_Reason: {r.get('reason', '')}_\n")


if __name__ == "__main__":
    main()
