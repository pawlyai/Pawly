"""Run a proactive corpus against a live eval stack and score it.

    docker compose -f deploy/docker-compose.eval.yml -p pawly-eval up -d --build
    export ANTHROPIC_API_KEY=...   # judge
    export DEEPSEEK_API_KEY=...    # second D7 judge
    python tests/blackbox_proactive/run_proactive_eval.py --corpus test_data/proactive_smoke_20_cases.json

The report lands in tests/blackbox_multiturn/results/ under the name the
Streamlit pages already glob for, so a proactive run shows up beside the
multi-turn ones.

Nothing is provisioned. A proactive case declares its world instead of building
it — no users, no pets, no sessions, no database — which is why 200 of these run
in the time it takes to drive a handful of chat cases.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from proactive_driver import ProactiveDryRunDriver  # noqa: E402
from proactive_report import build_report  # noqa: E402
from proactive_scoring import (  # noqa: E402
    CaseResult,
    background_text,
    build_judge,
    check_asserts,
    evaluate,
)
from validate_corpus import resolve_corpus, validate  # noqa: E402

RESULTS_DIR = HERE.parent / "blackbox_multiturn" / "results"
DEFAULT_CORPUS = HERE / "test_data" / "proactive_smoke_20_cases.json"


def load_cases(path: Path) -> list[dict]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(cases, dict):
        cases = cases.get("cases", [])
    return cases


def pet_names(cases: list[dict]) -> dict[str, str]:
    return {
        c["id"]: ((c.get("context_pack") or {}).get("pet_profile") or {}).get("name", "")
        for c in cases
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    ap.add_argument("--base", default="http://127.0.0.1:18008",
                    help="notification-service on the eval stack")
    ap.add_argument("--service-auth", default=os.environ.get("EVAL_SERVICE_AUTH", ""))
    # Cross-family by default and never the model under test. A judge sharing a
    # family with the SUT reads its blind spots as fine, so exactly the failures
    # worth catching go unflagged — the same reasoning as run_go_eval.py, which
    # settled on sonnet after comparing judges over stored transcripts.
    ap.add_argument("--judge-model", default=os.environ.get("EVAL_JUDGE_MODEL", "claude-sonnet-5"))
    # D7 is pass/fail and kills a case outright, so it gets a second opinion from
    # a different family. Set to "" to run it single-judge.
    ap.add_argument("--d7-second-judge", default=os.environ.get("EVAL_D7_JUDGE", "deepseek-v4-pro"))
    ap.add_argument("--sut-model", default=os.environ.get("EVAL_LLM_MODEL", "gemini-2.5-flash"))
    ap.add_argument("--topic", default="proactive_quality")
    ap.add_argument("--only", default="", help="comma-separated substrings matched against id or name")
    ap.add_argument("--no-score", action="store_true",
                    help="drive the cases and record what would be sent, skip every judge")
    ap.add_argument("--dimensions", default="",
                    help="comma-separated subset (e.g. D2,D4) for cheap iteration")
    # Judges are the bottleneck and both are rate-limited. Four matches the
    # multi-turn runner; raise it if you are paying for headroom.
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--skip-validation", action="store_true",
                    help="run a corpus that does not yet meet the coverage quotas")
    args = ap.parse_args()

    cases = load_cases(resolve_corpus(args.corpus))

    # Structural problems are found before a single model call, not forty
    # minutes in. A case missing its trigger block produces a confident,
    # meaningless score otherwise.
    errors, warnings = validate(cases, enforce_quotas=not args.skip_validation)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if errors:
        for e in errors:
            print(f"corpus error: {e}", file=sys.stderr)
        print(f"\n{len(errors)} corpus errors — nothing was run.", file=sys.stderr)
        return 2

    if args.only:
        wanted = [s.strip() for s in args.only.split(",") if s.strip()]
        cases = [c for c in cases if any(s in c["id"] or s in c["name"] for s in wanted)]
    if not cases:
        print(f"no cases matched --only={args.only!r}", file=sys.stderr)
        return 2

    if args.dimensions:
        keep = {d.strip().upper() for d in args.dimensions.split(",") if d.strip()}
        import proactive_scoring
        for key in list(proactive_scoring.DIMENSIONS):
            if key not in keep:
                del proactive_scoring.DIMENSIONS[key]
        print(f"scoring only {sorted(keep)}", file=sys.stderr)

    judge = None
    d7_judges: list[tuple[str, object]] = []
    if not args.no_score:
        judge, err, _ = build_judge(args.judge_model)
        if err:
            print(f"judge unavailable: {err}", file=sys.stderr)
            return 2
        d7_judges.append((args.judge_model, judge))
        if args.d7_second_judge:
            second, err2, _ = build_judge(args.d7_second_judge)
            if err2:
                # Not fatal: one judge is worse than two but far better than
                # skipping the check. Loud, because a run with a single D7 judge
                # is not the run the acceptance criteria describe.
                print(f"WARNING: second D7 judge unavailable ({err2}) — "
                      f"D7 runs single-judge and split votes cannot be detected.",
                      file=sys.stderr)
            else:
                d7_judges.append((args.d7_second_judge, second))
        if args.judge_model.split("-")[0] == args.sut_model.split("-")[0]:
            print(f"WARNING: judge ({args.judge_model}) and system under test "
                  f"({args.sut_model}) are the same family — subjective scores are optimistic.",
                  file=sys.stderr)

    driver = ProactiveDryRunDriver(args.base, service_auth=args.service_auth)
    names = pet_names(cases)
    all_pet_names = {n for n in names.values() if n}

    def run_one(case: dict) -> CaseResult:
        """Drive and score one case. Never raises: a broken case is a result."""
        try:
            out = driver.run(case)
        except Exception as e:  # noqa: BLE001
            detail = getattr(getattr(e, "response", None), "text", "") or str(e)
            return CaseResult(
                name=case["name"], case_id=case["id"], passed=False, score=0.0,
                threshold=float(case.get("threshold", 0.7)),
                error=f"drive failed: {detail[:400]}",
            )

        # Every other pet in the corpus is a name this message must not use.
        # Attribution errors are the most trust-destroying failure available
        # here and they are exactly detectable, so they are checked against the
        # whole roster rather than a per-case list somebody has to maintain.
        own = names.get(case["id"], "")
        foreign = {n for n in all_pet_names if n != own}

        if judge is None:
            asserts = check_asserts(case, out, foreign_pet_names=foreign)
            return CaseResult(
                name=case["name"], case_id=case["id"],
                passed=all(a.passed for a in asserts), score=0.0,
                threshold=float(case.get("threshold", 0.7)),
                asserts=asserts, outcome=out,
            )
        return evaluate(case, out, judge, d7_judges, foreign_pet_names=foreign)

    by_id: dict[str, CaseResult] = {}
    workers = max(1, min(args.workers, len(cases)))
    started = time.monotonic()

    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_one, c): c for c in cases}
        for done, fut in enumerate(cf.as_completed(futures), start=1):
            res = fut.result()
            by_id[res.case_id] = res
            mark = "PASS" if res.passed else "FAIL"
            sent = "—"
            if res.outcome:
                sent = res.outcome.verdict + ("" if res.outcome.should_send else f"/{res.outcome.reason}")
            print(f"[{done}/{len(cases)}] {mark} {res.case_id[:38]:38s} "
                  f"{sent:24s} score={res.score:.2f}"
                  + (f" | {res.failure_summary()[:110]}" if not res.passed else ""),
                  flush=True)

    # Corpus order, so two reports of the same suite diff cleanly whatever order
    # the pool finished in.
    results = [by_id[c["id"]] for c in cases if c["id"] in by_id]
    print(f"\ndrove {len(results)} cases on {workers} workers in {time.monotonic() - started:.0f}s")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"{args.topic}_report_{args.sut_model}_v{ts}.json"
    report = build_report(
        results,
        {c["id"]: c for c in cases},
        {c["id"]: background_text(c) for c in cases},
        judge_model=args.judge_model,
        d7_judges=[m for m, _ in d7_judges],
        sut_model=args.sut_model,
        timestamp=ts,
        report_path=str(out_path),
    )
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    s = report["summary"]
    print(f"\n{s['passed_threshold']}/{s['total_cases']} passed -> {out_path.name}")
    print(f"assertions (judge-independent): {s['assertions_passed']}/{s['total_cases']}")
    print(f"restraint (should_send=false):  {s['restraint_correct']}/{s['restraint_cases']}")
    print(f"D7 no-upsell:                   {s['d7_checked'] - s['d7_hooks_found']}/{s['d7_checked']} clean"
          + (f", {s['d7_needs_review']} split votes" if s["d7_needs_review"] else ""))
    if s["dimension_means"]:
        print("dimension means: " + "  ".join(f"{k}={v:.2f}" for k, v in s["dimension_means"].items()))
    if s["generic_pairs"]:
        print(f"\n{len(s['generic_pairs'])} pairs of near-identical nudges "
              f"(the template failure): {[(p['a'], p['b']) for p in s['generic_pairs'][:5]]}",
              file=sys.stderr)
    if s["unscored"]:
        # Loud, because the headline above is not a result when this is non-zero.
        print(f"\nWARNING: {s['unscored']}/{s['total_cases']} cases were never scored "
              f"(judge error). The pass rate above is NOT a valid result for this run — "
              f"only the assertion count is.", file=sys.stderr)
        return 2
    return 0 if s["below_threshold"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
