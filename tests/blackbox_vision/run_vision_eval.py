"""Run the vision eval corpus against a live eval stack and score it.

    docker compose -f deploy/docker-compose.eval.yml -p pawly-eval up -d --build
    export ANTHROPIC_API_KEY=...
    python tests/blackbox_vision/run_vision_eval.py

Images referenced in the corpus are resolved relative to
tests/blackbox_vision/test_data/images/. See that directory's README
for how to supply them; cases with a missing image file are skipped.

Results land in tests/blackbox_vision/results/ in the same JSON shape
the Streamlit pages already glob for.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "blackbox_multiturn"))

from go_driver import GoChatDriver  # noqa: E402
from go_scoring import build_judge  # noqa: E402
from vision_driver import VisionChatDriver  # noqa: E402
from vision_scoring import DeterministicVisionAssert, score_turn_with_judge  # noqa: E402

RESULTS_DIR = HERE / "results"
DEFAULT_CORPUS = HERE / "test_data" / "vision_cases.json"
IMAGES_DIR = HERE / "test_data" / "images"


def provision_user(args, user_id: str, phone: str) -> None:
    cwd = args.backend_dir if Path(args.backend_dir).is_dir() else None
    subprocess.run(
        ["docker", "compose", "-f", args.compose_file, "-p", args.compose_project,
         "exec", "-T", "postgres", "psql", "-U", "pawly", "-d", "pawly_user",
         "-c", GoChatDriver.new_user_sql(user_id, phone)],
        check=True, capture_output=True, cwd=cwd,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Run vision eval corpus")
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    ap.add_argument("--chat-base", default="http://127.0.0.1:18004")
    ap.add_argument("--user-base", default="http://127.0.0.1:18001")
    ap.add_argument("--memory-base", default="http://127.0.0.1:18005")
    ap.add_argument("--file-base", default="http://127.0.0.1:18006")
    ap.add_argument("--jwt-secret",
                    default=os.environ.get("EVAL_JWT_SECRET", "eval-secret-not-for-production"))
    ap.add_argument("--compose-file", default="deploy/docker-compose.eval.yml")
    ap.add_argument("--compose-project", default="pawly-eval")
    ap.add_argument("--backend-dir",
                    default=str(Path(__file__).resolve().parents[3] / "backend"))
    ap.add_argument("--judge-model",
                    default=os.environ.get("EVAL_JUDGE_MODEL", "claude-sonnet-5"))
    ap.add_argument("--sut-model",
                    default=os.environ.get("EVAL_LLM_MODEL", "gemini-2.5-flash"))
    ap.add_argument("--topic", default="vision_regression")
    ap.add_argument("--only", default="",
                    help="comma-separated substrings; run cases matching any of them")
    ap.add_argument("--no-score", action="store_true",
                    help="drive cases and write transcripts, skip the judge")
    ap.add_argument("--workers", type=int, default=2,
                    help="cases to drive concurrently (default 2, lower for rate limits)")
    args = ap.parse_args()

    cases: list[dict] = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    if isinstance(cases, dict):
        cases = cases.get("cases", [])
    if args.only:
        wanted = [s.strip() for s in args.only.split(",") if s.strip()]
        cases = [c for c in cases if any(s in c["name"] for s in wanted)]
    if not cases:
        print(f"no cases matched --only={args.only!r}", file=sys.stderr)
        return 2

    # Normalise: promote legacy flat-turn cases into the turns[] format so the
    # rest of the code only deals with one shape.
    for c in cases:
        if "turns" not in c:
            c["turns"] = [{
                "turn_id": "T1",
                "message": c.get("message", ""),
                "image_files": c.get("image_files", []),
                "deterministic": c.get("deterministic", {}),
                "judged_criteria": c.get("judged_criteria", []),
            }]

    # Skip cases whose required images are missing.
    runnable: list[dict] = []
    for c in cases:
        case_allow_missing = c.get("allow_missing_images", False)
        missing_any = False
        for turn in c["turns"]:
            turn_allow_missing = turn.get("allow_missing_images", case_allow_missing)
            missing = [f for f in turn.get("image_files", [])
                       if not (IMAGES_DIR / f).exists()]
            if missing and not turn_allow_missing:
                print(f"SKIP {c['name']}.{turn.get('turn_id','?')}: missing images {missing}",
                      file=sys.stderr)
                missing_any = True
                break
        if not missing_any:
            runnable.append(c)
    if not runnable:
        print("no runnable cases (all images missing?)", file=sys.stderr)
        return 2

    judge = None
    if not args.no_score:
        judge, err, _ = build_judge(args.judge_model)
        if err:
            print(f"judge unavailable: {err}", file=sys.stderr)
            return 2
        if args.judge_model.split("-")[0] == args.sut_model.split("-")[0]:
            print(
                "WARNING: judge and SUT are the same family — scores are optimistic",
                file=sys.stderr,
            )

    driver = VisionChatDriver(
        chat_base=args.chat_base,
        user_base=args.user_base,
        memory_base=args.memory_base,
        jwt_secret=args.jwt_secret,
        file_base=args.file_base,
    )

    results: list[dict] = []

    def run_one(case: dict) -> dict:
        name = case["name"]
        user_id = str(uuid.uuid4())
        phone = "+65" + str(int(user_id.replace("-", "")[:12], 16))[:11]

        try:
            provision_user(args, user_id, phone)
        except Exception as e:
            return _error_result(name, f"provision failed: {e}")

        try:
            token = driver.mint_token(user_id)
            pet_id = driver.create_pet(token, case.get("pet_profile", _default_pet()))
            session_id = driver.create_session(token, pet_id)
        except Exception as e:
            return _error_result(name, f"setup failed: {e}")

        turns_spec: list[dict] = case["turns"]
        turn_results: list[dict] = []
        last_turn = None

        for t_spec in turns_spec:
            turn_id = t_spec.get("turn_id", f"T{len(turn_results)+1}")
            msg = t_spec.get("message", "")
            image_files = t_spec.get("image_files", [])
            # Resolve image paths; skip missing when allow_missing_images is set
            allow_missing = t_spec.get("allow_missing_images",
                                       case.get("allow_missing_images", False))
            image_paths = []
            for f in image_files:
                p = IMAGES_DIR / f
                if p.exists():
                    image_paths.append(str(p))
                elif not allow_missing:
                    # Should not happen after pre-flight, but guard defensively
                    return _error_result(name, f"missing image at runtime: {f}")

            try:
                turn = driver.send_image_turn(
                    token=token,
                    session_id=session_id,
                    content=msg,
                    image_paths=image_paths,
                )
                last_turn = turn
            except Exception as e:
                turn_results.append({
                    "turn_id": turn_id, "passed": False,
                    "deterministic": {"failures": [str(e)], "passed": False},
                    "judged": {}, "error": str(e),
                })
                continue

            det_spec = t_spec.get("deterministic", {})
            det_assert = DeterministicVisionAssert(
                expected_triage=det_spec.get("expected_triage"),
                require_alert=det_spec.get("require_alert", False),
                forbid_medical=det_spec.get("forbid_medical", False),
                require_vet_mention=det_spec.get("require_vet_mention", False),
            )
            det_failures = det_assert.check(turn)

            judged: dict = {}
            if judge is not None and not args.no_score:
                criteria = t_spec.get("judged_criteria", [])
                if criteria:
                    judged = score_turn_with_judge(
                        turn, msg, criteria, judge,
                        image_count=len(image_paths),
                    )

            turn_pass = (
                not det_failures
                and all(v.get("passed", True) for v in judged.values())
            )
            turn_results.append({
                "turn_id": turn_id,
                "passed": turn_pass,
                "triage_level": turn.triage_level,
                "response_snippet": turn.assistant[:200],
                # Full text as well: the judge scores turn.assistant in its
                # entirety, so a 200-char snippet cannot be used to check a
                # judged verdict against the evidence it cites.
                "response": turn.assistant,
                "deterministic": {"failures": det_failures, "passed": not det_failures},
                "judged": judged,
                "error": None,
            })

        all_pass = all(t["passed"] for t in turn_results)
        triage = last_turn.triage_level if last_turn else None
        snippet = last_turn.assistant[:300] if last_turn else ""

        return {
            "name": name,
            "passed": all_pass,
            "triage_level": triage,
            "response_snippet": snippet,
            "response": last_turn.assistant if last_turn else "",
            "turns": turn_results,
            # Legacy flat fields for Streamlit compatibility
            "deterministic": {"failures": [], "passed": all_pass},
            "judged": {},
            "error": None,
        }

    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, c): c["name"] for c in runnable}
        for fut in cf.as_completed(futures):
            r = fut.result()
            results.append(r)
            status = "PASS" if r["passed"] else ("ERR" if r["error"] else "FAIL")
            print(f"  [{status}] {r['name']}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS_DIR / f"{args.topic}_{ts}.json"
    summary = {
        "topic": args.topic,
        "sut_model": args.sut_model,
        "judge_model": args.judge_model if not args.no_score else None,
        "run_at": ts,
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "cases": results,
    }
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{summary['passed']}/{summary['total']} passed → {out_path}")
    return 0 if summary["passed"] == summary["total"] else 1


def _error_result(name: str, msg: str) -> dict:
    return {
        "name": name, "passed": False, "triage_level": None,
        "response_snippet": "", "response": "", "deterministic": {"failures": [], "passed": True},
        "judged": {}, "error": msg,
    }


def _default_pet() -> dict:
    return {"name": "TestPet", "species": "dog", "breed": "mixed", "age_years": 3, "weight_kg": 10}


if __name__ == "__main__":
    sys.exit(main())
