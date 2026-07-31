"""Re-score an existing report's transcripts with a different judge.

Comparing two judges by running the suite twice confounds the thing being
measured: the system under test is non-deterministic, so a score that moves
could be the new judge or could be a different reply. This re-reads the
transcripts already stored in a report and scores that exact text again, so the
only variable is the judge.

It also costs nothing to drive — no eval stack, no LLM calls to the system under
test, no waiting.

    python rescore_report.py results/<report>.json --judge-model claude-sonnet-5
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from go_scoring import build_judge, check_asserts, score_with_retry  # noqa: E402


@dataclass
class _Turn:
    user: str
    assistant: str
    triage_level: str | None = None
    alert: str | None = None


@dataclass
class _Run:
    turns: list[_Turn] = field(default_factory=list)
    memories_seeded: int = 0


def rebuild_run(case: dict[str, Any]) -> _Run:
    """Fold a report's flat role/content list back into paired turns.

    The stored shape is what the Streamlit pages read; the scorers want pairs.
    An assistant turn with no preceding user turn is dropped rather than paired
    with an empty string, so a malformed report cannot silently invent a turn.
    """
    run = _Run(memories_seeded=(case.get("metadata") or {}).get("memories_seeded", 0))
    pending: str | None = None
    for t in case.get("turns") or []:
        if t.get("role") == "user":
            pending = t.get("content", "")
        elif pending is not None:
            lvl = ((t.get("triage_trace") or {}).get("resolved") or {}).get("level") or None
            run.turns.append(_Turn(pending, t.get("content", ""), lvl, t.get("alert")))
            pending = None
    return run


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--judge-model", required=True)
    ap.add_argument("--corpus", default=str(HERE / "test_data" / "multiturn_go_regression_v1_cases.json"))
    ap.add_argument("--out", default="")
    ap.add_argument("--only", default="",
                    help="comma-separated substrings; score just these cases")
    args = ap.parse_args()
    only = [s for s in args.only.split(",") if s]

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    cases = {c["name"]: c for c in json.loads(Path(args.corpus).read_text(encoding="utf-8"))}

    judge, err, _ = build_judge(args.judge_model)
    if err:
        print(f"judge unavailable: {err}", file=sys.stderr)
        return 2

    old_judge = report["summary"].get("judge_model", "?")
    rows = []
    for c in report["cases"]:
        if only and not any(s in c["name"] for s in only):
            continue
        case = cases.get(c["name"])
        if not case:
            print(f"skip {c['name']}: not in corpus", file=sys.stderr)
            continue
        run = rebuild_run(c)
        if not run.turns:
            print(f"skip {c['name']}: no transcript in report", file=sys.stderr)
            continue

        asserts = check_asserts(case, run)
        try:
            score, reason = score_with_retry(case, run, judge)
            error = None
        except Exception as e:  # noqa: BLE001
            score, reason, error = 0.0, "", f"{type(e).__name__}: {str(e)[:200]}"

        threshold = float(case.get("threshold", 0.7))
        # A case unscored by the ORIGINAL judge has nothing to compare against;
        # keep it in the output but mark it so the delta column stays honest.
        old_err = str((c.get("metadata") or {}).get("error") or "")
        old_score = None if old_err.startswith("scoring failed") else c.get("score")

        rows.append({
            "name": c["name"],
            "threshold": threshold,
            "old_score": old_score,
            "new_score": None if error else round(score, 4),
            "assert_ok": all(a.passed for a in asserts),
            "reason": reason,
            "error": error,
        })
        d = ("  n/a" if old_score is None or error
             else f"{score - old_score:+.2f}")
        print(f"{c['name'][:48]:48s} {old_judge[:12]:>12}={old_score if old_score is not None else '  --'!s:>5} "
              f"{args.judge_model[:14]:>14}={'--' if error else f'{score:.2f}':>5}  delta {d}"
              + (f"  [{error}]" if error else ""))

    comparable = [r for r in rows if r["old_score"] is not None and r["new_score"] is not None]
    print()
    if comparable:
        old_pass = sum(1 for r in comparable if r["old_score"] >= r["threshold"] and r["assert_ok"])
        new_pass = sum(1 for r in comparable if r["new_score"] >= r["threshold"] and r["assert_ok"])
        mean_delta = sum(r["new_score"] - r["old_score"] for r in comparable) / len(comparable)
        print(f"comparable cases: {len(comparable)}")
        print(f"  {old_judge}: {old_pass}/{len(comparable)} pass")
        print(f"  {args.judge_model}: {new_pass}/{len(comparable)} pass")
        print(f"  mean score change: {mean_delta:+.3f}")
    else:
        print("no comparable cases — the original run has no valid judge scores")

    out = Path(args.out) if args.out else Path(args.report).with_suffix(".rescored.json")
    out.write_text(json.dumps({
        "source_report": str(args.report),
        "old_judge": old_judge,
        "new_judge": args.judge_model,
        "cases": rows,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
