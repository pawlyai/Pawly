#!/usr/bin/env python3
"""
Compare two regression report.json files and emit a markdown summary
suitable for a PR comment / Slack post.

Usage
-----
    python tests/blackbox_multiturn/utils/regression_diff.py BASELINE.json CANDIDATE.json
    python tests/blackbox_multiturn/utils/regression_diff.py --auto         # pick two most recent
    python tests/blackbox_multiturn/utils/regression_diff.py BASELINE.json CANDIDATE.json --out report-summary.md

Output sections
---------------
1. Headline: pass-rate delta + ✓/✗ verdict
2. Top-level numbers: total / passed / failed (baseline vs candidate)
3. Regression list: cases that PASSED on baseline but FAIL on candidate
4. Improvement list: cases that FAILED on baseline but PASS on candidate
5. Score-only deltas: same-status cases whose score moved by ≥0.1

The "pass" definition matches the report's own convention: status field
== "passed_threshold".
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPORTS_DIR = Path(__file__).resolve().parent.parent / "results"


def load_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        sys.exit(f"FATAL: {path} does not exist")
    return json.loads(path.read_text(encoding="utf-8"))


def case_index(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index cases by name for diffing."""
    return {c["name"]: c for c in report.get("cases", [])}


def is_pass(case: dict[str, Any]) -> bool:
    return case.get("status") == "passed_threshold"


def auto_pick_recent_two() -> tuple[Path, Path]:
    """Pick the two most recent regression reports of the same topic."""
    candidates = sorted(
        REPORTS_DIR.glob("multiturn_pawly_regression*_report_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if len(candidates) < 2:
        sys.exit(
            "FATAL: --auto requires ≥2 regression reports under "
            f"{REPORTS_DIR}; only found {len(candidates)}"
        )
    # Most recent = candidate, second most recent = baseline
    return candidates[1], candidates[0]


def fmt_pct(n: int, total: int) -> str:
    if total == 0:
        return "—"
    return f"{n}/{total} ({100 * n / total:.1f}%)"


def render(baseline_path: Path, candidate_path: Path,
           baseline: dict[str, Any], candidate: dict[str, Any]) -> str:
    b_sum = baseline["summary"]
    c_sum = candidate["summary"]

    b_pass = b_sum["passed_threshold"]
    b_total = b_sum["total_cases"]
    c_pass = c_sum["passed_threshold"]
    c_total = c_sum["total_cases"]

    b_rate = b_pass / b_total if b_total else 0.0
    c_rate = c_pass / c_total if c_total else 0.0
    delta = c_rate - b_rate
    delta_pp = delta * 100  # percentage points

    if delta > 0.001:
        verdict = "✅ improvement"
    elif delta < -0.001:
        verdict = "❌ regression"
    else:
        verdict = "➖ no change"

    # Per-case diff
    b_idx = case_index(baseline)
    c_idx = case_index(candidate)
    common_names = sorted(set(b_idx) & set(c_idx))

    new_fails: list[tuple[str, float, float, str]] = []
    new_passes: list[tuple[str, float, float]] = []
    score_drops: list[tuple[str, float, float]] = []
    score_gains: list[tuple[str, float, float]] = []

    for name in common_names:
        b = b_idx[name]
        c = c_idx[name]
        b_p = is_pass(b)
        c_p = is_pass(c)
        if b_p and not c_p:
            new_fails.append((name, b.get("score", 0), c.get("score", 0), c.get("reason", "")))
        elif not b_p and c_p:
            new_passes.append((name, b.get("score", 0), c.get("score", 0)))
        elif b_p == c_p:
            ds = c.get("score", 0) - b.get("score", 0)
            if ds <= -0.1:
                score_drops.append((name, b.get("score", 0), c.get("score", 0)))
            elif ds >= 0.1:
                score_gains.append((name, b.get("score", 0), c.get("score", 0)))

    only_in_b = sorted(set(b_idx) - set(c_idx))
    only_in_c = sorted(set(c_idx) - set(b_idx))

    # ── Render markdown ──────────────────────────────────────────────────
    lines: list[str] = []
    lines.append(f"## Regression diff — {verdict}")
    lines.append("")
    lines.append(f"**{delta_pp:+.1f} pp** ({fmt_pct(b_pass, b_total)} → {fmt_pct(c_pass, c_total)})")
    lines.append("")

    # Top-level numbers
    lines.append("|  | Baseline | Candidate | Δ |")
    lines.append("|---|---|---|---|")
    lines.append(f"| Total cases | {b_total} | {c_total} | {c_total - b_total:+d} |")
    lines.append(f"| Passed | {b_pass} | {c_pass} | {c_pass - b_pass:+d} |")
    lines.append(f"| Failed | {b_sum['below_threshold']} | {c_sum['below_threshold']} | "
                 f"{c_sum['below_threshold'] - b_sum['below_threshold']:+d} |")
    lines.append(f"| Pass rate | {b_rate:.1%} | {c_rate:.1%} | {delta_pp:+.1f}pp |")
    lines.append("")

    # Sources
    lines.append("<details><summary>Sources</summary>")
    lines.append("")
    lines.append(f"- Baseline: `{baseline_path.name}` "
                 f"(model: `{b_sum.get('llm_model', '?')}`, ts: {b_sum.get('timestamp', '?')})")
    lines.append(f"- Candidate: `{candidate_path.name}` "
                 f"(model: `{c_sum.get('llm_model', '?')}`, ts: {c_sum.get('timestamp', '?')})")
    lines.append("")
    lines.append("</details>")
    lines.append("")

    # Regressions
    if new_fails:
        lines.append(f"### ❌ New failures ({len(new_fails)})")
        lines.append("")
        lines.append("| Case | Baseline | Candidate | Why (judge) |")
        lines.append("|---|---|---|---|")
        for name, b_s, c_s, reason in new_fails[:20]:
            short_reason = reason.replace("\n", " ").replace("|", "\\|")
            if len(short_reason) > 200:
                short_reason = short_reason[:200] + "…"
            lines.append(f"| `{name}` | {b_s:.2f} ✓ | {c_s:.2f} ✗ | {short_reason} |")
        if len(new_fails) > 20:
            lines.append(f"| _… {len(new_fails) - 20} more (see artifact)_ | | | |")
        lines.append("")

    # Improvements
    if new_passes:
        lines.append(f"### ✅ New passes ({len(new_passes)})")
        lines.append("")
        lines.append("| Case | Baseline | Candidate |")
        lines.append("|---|---|---|")
        for name, b_s, c_s in new_passes[:10]:
            lines.append(f"| `{name}` | {b_s:.2f} ✗ | {c_s:.2f} ✓ |")
        if len(new_passes) > 10:
            lines.append(f"| _… {len(new_passes) - 10} more_ | | |")
        lines.append("")

    # Score deltas (status unchanged)
    if score_drops or score_gains:
        lines.append("<details><summary>Score-only changes (status unchanged, |Δscore| ≥ 0.1)</summary>")
        lines.append("")
        if score_drops:
            lines.append(f"**Drops ({len(score_drops)}):**")
            lines.append("")
            for name, b_s, c_s in score_drops[:10]:
                lines.append(f"- `{name}`: {b_s:.2f} → {c_s:.2f} ({c_s - b_s:+.2f})")
            lines.append("")
        if score_gains:
            lines.append(f"**Gains ({len(score_gains)}):**")
            lines.append("")
            for name, b_s, c_s in score_gains[:10]:
                lines.append(f"- `{name}`: {b_s:.2f} → {c_s:.2f} ({c_s - b_s:+.2f})")
            lines.append("")
        lines.append("</details>")
        lines.append("")

    # Asymmetric case sets (different test data versions)
    if only_in_b or only_in_c:
        lines.append("<details><summary>Case set differences</summary>")
        lines.append("")
        if only_in_b:
            lines.append(f"- {len(only_in_b)} case(s) only in baseline (removed in candidate)")
        if only_in_c:
            lines.append(f"- {len(only_in_c)} case(s) only in candidate (newly added)")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("baseline", nargs="?", help="Baseline report.json")
    p.add_argument("candidate", nargs="?", help="Candidate report.json")
    p.add_argument("--auto", action="store_true",
                   help="Auto-pick the two most recent regression reports")
    p.add_argument("--out", help="Write markdown to file (default: stdout)")
    args = p.parse_args()

    if args.auto:
        baseline_path, candidate_path = auto_pick_recent_two()
    else:
        if not args.baseline or not args.candidate:
            p.error("provide both BASELINE and CANDIDATE, or use --auto")
        baseline_path = Path(args.baseline)
        candidate_path = Path(args.candidate)

    baseline = load_report(baseline_path)
    candidate = load_report(candidate_path)

    md = render(baseline_path, candidate_path, baseline, candidate)

    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(md)

    return 0


if __name__ == "__main__":
    sys.exit(main())
