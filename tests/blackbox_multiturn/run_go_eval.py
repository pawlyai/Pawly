"""Run the Go multi-turn corpus against a live eval stack and score it.

    docker compose -f deploy/docker-compose.eval.yml -p pawly-eval up -d --build
    export DEEPSEEK_API_KEY=...
    python tests/blackbox_multiturn/run_go_eval.py

The report lands in results/ under the name the Streamlit pages already glob
for, so nothing downstream needs to know these cases came from the Go stack.

Users are provisioned with SQL through `docker compose exec postgres psql`
because user-service has no admin create-user endpoint and the OTP path needs
SMS. That is acceptable only because the eval Postgres is a tmpfs that dies
with the stack.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from go_driver import GoChatDriver  # noqa: E402
from go_scoring import build_judge, build_report, evaluate  # noqa: E402

RESULTS_DIR = HERE / "results"
DEFAULT_CORPUS = HERE / "test_data" / "multiturn_go_regression_v1_cases.json"


def provision_user(args, user_id: str, phone: str) -> None:
    """Insert the case's user row directly into the eval Postgres."""
    cwd = args.backend_dir if Path(args.backend_dir).is_dir() else None
    subprocess.run(
        ["docker", "compose", "-f", args.compose_file, "-p", args.compose_project,
         "exec", "-T", "postgres", "psql", "-U", "pawly", "-d", "pawly_user",
         "-c", GoChatDriver.new_user_sql(user_id, phone)],
        check=True, capture_output=True, cwd=cwd,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    ap.add_argument("--chat-base", default="http://127.0.0.1:18004")
    ap.add_argument("--user-base", default="http://127.0.0.1:18001")
    ap.add_argument("--memory-base", default="http://127.0.0.1:18005")
    ap.add_argument("--jwt-secret", default=os.environ.get(
        "EVAL_JWT_SECRET", "eval-secret-not-for-production"))
    ap.add_argument("--compose-file", default="deploy/docker-compose.eval.yml")
    ap.add_argument("--compose-project", default="pawly-eval")
    ap.add_argument("--backend-dir", default=str(Path(__file__).resolve().parents[3] / "backend"))
    # Cross-family by default, and not the model under test. Two reasons for
    # this particular default:
    #
    #   gemini-pro-latest shares a family with the SUT, and scored 1.00 on 29 of
    #   30 cases -- a judge that finds everything perfect is not grading.
    #
    #   claude-haiku-4.5 spreads scores but not reliably: of five cases where it
    #   disagreed with the others, one verdict contradicted its own stated
    #   reasoning, one applied a prompt rule to a hardcoded response the model
    #   never generates, and one marked a correct veterinary claim wrong. A judge
    #   that moves scores at random is worse than one that does not move them.
    #
    # Sonnet agreed with a manual read of all five. See rescore_report.py, which
    # compares judges over identical stored transcripts.
    ap.add_argument("--judge-model",
                    default=os.environ.get("EVAL_JUDGE_MODEL", "claude-sonnet-5"))
    ap.add_argument("--sut-model", default=os.environ.get("EVAL_LLM_MODEL", "gemini-2.5-flash"))
    ap.add_argument("--topic", default="multiturn_go_regression")
    ap.add_argument("--only", default="", help="substring filter on case name")
    ap.add_argument("--no-score", action="store_true",
                    help="drive the cases and write transcripts, skip the judge")
    args = ap.parse_args()

    cases = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    if isinstance(cases, dict):
        cases = cases.get("cases", [])
    if args.only:
        cases = [c for c in cases if args.only in c["name"]]
    if not cases:
        print("no cases selected", file=sys.stderr)
        return 2

    judge = None
    if not args.no_score:
        judge, err, _ = build_judge(args.judge_model)
        if err:
            print(f"judge unavailable: {err}", file=sys.stderr)
            return 2
        # Same-family judging is a known weakness, not a detail: a Gemini judge
        # scoring a Gemini SUT shares its blind spots, so the failures most
        # worth catching are the ones least likely to be flagged. Allowed
        # (DeepSeek needs a key that is not always present) but never silent —
        # the warning is recorded in the report too.
        if args.judge_model.split("-")[0] == args.sut_model.split("-")[0]:
            print(f"WARNING: judge ({args.judge_model}) and system under test "
                  f"({args.sut_model}) are the same model family - scores are "
                  f"optimistic on subjective criteria.", file=sys.stderr)

    driver = GoChatDriver(
        chat_base=args.chat_base,
        user_base=args.user_base,
        memory_base=args.memory_base,
        jwt_secret=args.jwt_secret,
    )

    results = []
    for i, case in enumerate(cases, 1):
        name = case["name"]
        # A distinct user per case: pets are per-user and one case's roster
        # leaking into the next is exactly what attribution cases are sensitive
        # to. uuid4 keeps reruns from colliding on the ON CONFLICT DO NOTHING.
        user_id = str(uuid.uuid4())
        # Derived from the user id, not from the clock. `phone` carries a UNIQUE
        # index and the insert only says ON CONFLICT (id) DO NOTHING, so a
        # repeated number is a constraint violation rather than a no-op — and a
        # counter salted with `time % 100` repeats every hundred runs against a
        # long-lived stack.
        phone = "+65" + str(int(user_id.replace("-", "")[:12], 16))[:11]

        print(f"[{i}/{len(cases)}] {name} ... ", end="", flush=True)
        started = time.monotonic()
        try:
            provision_user(args, user_id, phone)
            run = driver.run_case(case, user_id)
        except Exception as e:  # noqa: BLE001 — one broken case must not end the run
            detail = getattr(getattr(e, "response", None), "text", "") or str(e)
            print(f"DRIVE FAILED - {detail[:200]}")
            from go_scoring import CaseResult
            results.append(CaseResult(
                name=name, passed=False, score=0.0,
                threshold=float(case.get("threshold", 0.7)),
                reason="", error=f"drive failed: {detail[:500]}",
            ))
            continue

        if judge is None:
            from go_scoring import CaseResult, check_asserts, flatten_turns
            asserts = check_asserts(case, run)
            res = CaseResult(
                name=name, passed=all(a.passed for a in asserts), score=0.0,
                threshold=float(case.get("threshold", 0.7)),
                reason="scoring skipped (--no-score)", asserts=asserts,
                memories_seeded=run.memories_seeded, turns=flatten_turns(run),
            )
        else:
            res = evaluate(case, run, judge)

        results.append(res)
        elapsed = time.monotonic() - started
        mark = "PASS" if res.passed else "FAIL"
        bad = ", ".join(a.name for a in res.assert_failures)
        print(f"{mark} score={res.score:.2f}/{res.threshold} "
              f"mem={res.memories_seeded} {elapsed:.0f}s"
              + (f" | asserts: {bad}" if bad else "")
              + (f" | {res.error}" if res.error else ""))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"{args.topic}_report_{args.sut_model}_v{ts}.json"
    report = build_report(
        results,
        {c["name"]: c for c in cases},
        judge_model=args.judge_model,
        sut_model=args.sut_model,
        timestamp=ts,
        report_path=str(out_path),
    )
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    s = report["summary"]
    print(f"\n{s['passed_threshold']}/{s['total_cases']} passed -> {out_path.name}")
    print(f"assertions (judge-independent): {s['assertions_passed']}/{s['total_cases']}")
    if s.get("unscored"):
        # Loud, because the headline number above is not a result when this is
        # non-zero: an exhausted judge quota reports every unscored case as a
        # failure, which reads as a regression that never happened.
        print(f"\nWARNING: {s['unscored']}/{s['total_cases']} cases were never scored "
              f"(judge error). The pass rate above is NOT a valid result for this "
              f"run -- only the assertion count is.", file=sys.stderr)
        return 2
    return 0 if s["below_threshold"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
