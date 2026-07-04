"""
parity_runner.py — Migration parity harness.

Fires each row of a corpus through BOTH the Python triage rules engine AND
(optionally) the Go chat-service endpoint, then diffs the outputs on the
fields that matter for migration correctness.

USAGE
-----
# Python-only run (no Go service needed):
    python scripts/parity_runner.py --corpus scripts/parity_corpus.json

# Full parity run (Go service must be running):
    python scripts/parity_runner.py \\
        --corpus scripts/parity_corpus.json \\
        --go-endpoint http://localhost:8080

# Fail-fast mode (stop on first mismatch):
    python scripts/parity_runner.py --corpus scripts/parity_corpus.json --fail-fast

# Filter by category:
    python scripts/parity_runner.py --corpus scripts/parity_corpus.json --category RED

PARITY GATES (per acceptance criteria)
---------------------------------------
  final_triage:  ≥99% row match
  matched_rules: ≥95% row match  (checked only when Go endpoint is provided)

OUTPUT FORMAT
-------------
  JSON report written to parity_report.json (--output flag to override).
  Console summary: pass/fail counts and per-field rates.

CORPUS FORMAT (parity_corpus.json)
-----------------------------------
  [
    {
      "id": "row_001",
      "user_message": "my dog ate chocolate",
      "pet_context": {"species": "dog", "gender": "male", "life_stage": "adult"},
      "category": "RED",      // informational grouping
      "notes": ""             // optional
    },
    ...
  ]
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
import urllib.request
import urllib.error

# ── Import Python triage engine ───────────────────────────────────────────────
# Add repo root to path so we can import src.*
import os
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _REPO_ROOT)

try:
    from src.triage.rules_engine import classify_by_rules, TriageRuleResult
    from src.db.models import Pet, Species, Gender, LifeStage
    _PYTHON_ENGINE_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: could not import Python triage engine: {e}", file=sys.stderr)
    print("  Run from the Pawly repo root, or set PYTHONPATH appropriately.", file=sys.stderr)
    _PYTHON_ENGINE_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════════
# Data types
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CorpusRow:
    id: str
    user_message: str
    pet_context: Optional[dict] = None
    category: str = ""
    notes: str = ""


@dataclass
class TriageOutput:
    final_triage: str               # "RED" | "ORANGE" | "GREEN"
    matched_rules: list[str] = field(default_factory=list)
    banner_present: bool = False
    wrapper_present: bool = False   # True when response contains RED FLAG ALERT wrapper
    intent: str = ""
    symptom_tags: list[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class RowResult:
    row_id: str
    user_message: str
    category: str
    python: Optional[TriageOutput]
    go: Optional[TriageOutput]
    # diff fields
    triage_match: Optional[bool] = None
    rules_match: Optional[bool] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Python engine runner
# ═══════════════════════════════════════════════════════════════════════════════

def _build_pet(pet_context: Optional[dict]) -> Optional["Pet"]:  # type: ignore[name-defined]
    if not pet_context or not _PYTHON_ENGINE_AVAILABLE:
        return None
    try:
        kwargs: dict[str, Any] = {
            "id": 0,
            "user_id": 0,
            "name": "Test",
        }
        species_str = pet_context.get("species", "")
        if species_str:
            kwargs["species"] = Species(species_str)
        gender_str = pet_context.get("gender", "")
        if gender_str:
            kwargs["gender"] = Gender(gender_str)
        life_stage_str = pet_context.get("life_stage", "")
        if life_stage_str:
            kwargs["life_stage"] = LifeStage(life_stage_str)
        kwargs["breed"] = pet_context.get("breed", "")
        return Pet(**kwargs)  # type: ignore[arg-type]
    except Exception:
        return None


def run_python(row: CorpusRow) -> TriageOutput:
    """Run the Python rules engine on one corpus row."""
    if not _PYTHON_ENGINE_AVAILABLE:
        return TriageOutput(final_triage="UNKNOWN", error="python engine not available")

    try:
        pet = _build_pet(row.pet_context)
        result: TriageRuleResult = classify_by_rules(pet, row.user_message)
        triage_str = result.classification.value.upper()  # TriageLevel enum → "RED" etc.
        banner_present = bool(result.matched_rules)
        return TriageOutput(
            final_triage=triage_str,
            matched_rules=list(result.matched_rules),
            banner_present=banner_present,
            wrapper_present=False,  # rules engine alone doesn't apply wrapper
        )
    except Exception as exc:
        return TriageOutput(final_triage="ERROR", error=str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# Go service runner
# ═══════════════════════════════════════════════════════════════════════════════

def run_go(row: CorpusRow, endpoint: str, session_id: str, bearer_token: str = "test") -> TriageOutput:
    """
    Send one message to the Go chat-service and parse the triage from the SSE stream.

    The endpoint must be a running instance: e.g. http://localhost:8080
    The function calls POST /v1/sessions/{session_id}/messages with the user
    message and collects all SSE events until EventAssistantDone.
    """
    url = f"{endpoint.rstrip('/')}/v1/sessions/{session_id}/messages"
    payload = json.dumps({
        "content": row.user_message,
        "pet_context": row.pet_context or {},
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
            "Accept": "text/event-stream",
        },
        method="POST",
    )

    try:
        response_text = ""
        triage_level = ""
        matched_rules: list[str] = []
        banner_present = False
        wrapper_present = False
        intent = ""
        symptom_tags: list[str] = []

        with urllib.request.urlopen(req, timeout=30) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                ev_type = event.get("type", "")
                if ev_type == "assistant_delta":
                    response_text += event.get("delta", "")
                elif ev_type == "assistant_done":
                    # The done event carries triage metadata when structured mode is on.
                    triage_level = event.get("triage_level", "")
                    matched_rules = event.get("matched_rules", [])
                    intent = event.get("intent", "")
                    symptom_tags = event.get("symptom_tags", [])

        # Derive banner and wrapper from assembled response text if not in event.
        banner_present = "🔴" in response_text or "🟠" in response_text or bool(matched_rules)
        wrapper_present = "RED FLAG ALERT" in response_text or "🚨" in response_text

        if not triage_level:
            # Fall back to text-based detection.
            if "🔴" in response_text or "RED FLAG ALERT" in response_text:
                triage_level = "RED"
            elif "🟠" in response_text:
                triage_level = "ORANGE"
            else:
                triage_level = "GREEN"

        return TriageOutput(
            final_triage=triage_level.upper(),
            matched_rules=matched_rules,
            banner_present=banner_present,
            wrapper_present=wrapper_present,
            intent=intent,
            symptom_tags=symptom_tags,
        )

    except urllib.error.URLError as exc:
        return TriageOutput(final_triage="ERROR", error=f"http error: {exc}")
    except Exception as exc:
        return TriageOutput(final_triage="ERROR", error=str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# Diffing
# ═══════════════════════════════════════════════════════════════════════════════

def diff_outputs(python_out: TriageOutput, go_out: TriageOutput) -> dict:
    """Return a diff dict comparing the two outputs."""
    diffs = {}
    if python_out.final_triage != go_out.final_triage:
        diffs["final_triage"] = {
            "python": python_out.final_triage,
            "go": go_out.final_triage,
        }
    # Rules match: check whether matched_rules sets overlap sufficiently.
    py_rules = set(python_out.matched_rules)
    go_rules = set(go_out.matched_rules)
    if py_rules != go_rules:
        diffs["matched_rules"] = {
            "python_only": sorted(py_rules - go_rules),
            "go_only": sorted(go_rules - py_rules),
        }
    if python_out.banner_present != go_out.banner_present:
        diffs["banner_present"] = {
            "python": python_out.banner_present,
            "go": go_out.banner_present,
        }
    return diffs


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def load_corpus(path: str) -> list[CorpusRow]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    rows = []
    for item in raw:
        rows.append(CorpusRow(
            id=item.get("id", ""),
            user_message=item["user_message"],
            pet_context=item.get("pet_context"),
            category=item.get("category", ""),
            notes=item.get("notes", ""),
        ))
    return rows


def run_parity(
    corpus: list[CorpusRow],
    go_endpoint: Optional[str],
    fail_fast: bool,
    category_filter: Optional[str],
    session_id: str,
    bearer_token: str,
) -> tuple[list[RowResult], dict]:
    """
    Run parity check. Returns (row_results, summary_stats).
    """
    if category_filter:
        corpus = [r for r in corpus if r.category.upper() == category_filter.upper()]

    results: list[RowResult] = []
    triage_match_count = 0
    rules_match_count = 0
    triage_compared = 0
    rules_compared = 0
    error_count = 0

    for row in corpus:
        py_out = run_python(row)
        go_out = None

        if go_endpoint:
            go_out = run_go(row, go_endpoint, session_id, bearer_token)
            # Small delay to avoid flooding a local service.
            time.sleep(0.05)

        rr = RowResult(
            row_id=row.id,
            user_message=row.user_message,
            category=row.category,
            python=py_out,
            go=go_out,
        )

        if go_out is not None:
            triage_compared += 1
            triage_ok = py_out.final_triage == go_out.final_triage
            rr.triage_match = triage_ok
            if triage_ok:
                triage_match_count += 1

            # Rules match: True when either side has no rules (GREEN baseline)
            # or the sets are identical.
            rules_compared += 1
            py_rules = set(py_out.matched_rules)
            go_rules = set(go_out.matched_rules)
            rules_ok = py_rules == go_rules
            rr.rules_match = rules_ok
            if rules_ok:
                rules_match_count += 1

            if go_out.error or py_out.error:
                error_count += 1

            if fail_fast and (not triage_ok or not rules_ok):
                results.append(rr)
                break

        results.append(rr)

    summary: dict = {
        "total_rows": len(corpus),
        "rows_evaluated": len(results),
        "error_count": error_count,
    }
    if triage_compared > 0:
        triage_rate = triage_match_count / triage_compared * 100
        summary["triage_match"] = {
            "count": triage_match_count,
            "total": triage_compared,
            "rate_pct": round(triage_rate, 2),
            "gate_99pct": triage_rate >= 99.0,
        }
    if rules_compared > 0:
        rules_rate = rules_match_count / rules_compared * 100
        summary["rules_match"] = {
            "count": rules_match_count,
            "total": rules_compared,
            "rate_pct": round(rules_rate, 2),
            "gate_95pct": rules_rate >= 95.0,
        }

    return results, summary


def print_summary(summary: dict, go_mode: bool) -> None:
    print("\n═══════════════════════════════════════════════")
    print("  PARITY RUNNER SUMMARY")
    print("═══════════════════════════════════════════════")
    print(f"  Total corpus rows  : {summary['total_rows']}")
    print(f"  Rows evaluated     : {summary['rows_evaluated']}")
    if summary.get("error_count"):
        print(f"  Errors             : {summary['error_count']}")

    if not go_mode:
        print("\n  Go endpoint not provided — Python-only run.")
        print("  Pass --go-endpoint http://localhost:8080 for full parity check.")
        return

    if "triage_match" in summary:
        tm = summary["triage_match"]
        gate = "PASS ✓" if tm["gate_99pct"] else "FAIL ✗"
        print(f"\n  final_triage match : {tm['count']}/{tm['total']} ({tm['rate_pct']}%)  [{gate} ≥99%]")

    if "rules_match" in summary:
        rm = summary["rules_match"]
        gate = "PASS ✓" if rm["gate_95pct"] else "FAIL ✗"
        print(f"  matched_rules match: {rm['count']}/{rm['total']} ({rm['rate_pct']}%)  [{gate} ≥95%]")

    all_pass = all([
        summary.get("triage_match", {}).get("gate_99pct", True),
        summary.get("rules_match", {}).get("gate_95pct", True),
    ])
    print(f"\n  Overall: {'PASS ✓' if all_pass else 'FAIL ✗'}")
    print("═══════════════════════════════════════════════\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pawly migration parity runner")
    parser.add_argument("--corpus", required=True, help="path to parity_corpus.json")
    parser.add_argument("--go-endpoint", default="", help="Go chat-service base URL")
    parser.add_argument("--output", default="parity_report.json", help="output report path")
    parser.add_argument("--fail-fast", action="store_true", help="stop on first mismatch")
    parser.add_argument("--category", default="", help="filter corpus by category (RED/ORANGE/GREEN)")
    parser.add_argument("--session-id", default="parity-test-session", help="session ID for Go calls")
    parser.add_argument("--bearer-token", default="test", help="bearer token for Go calls")
    args = parser.parse_args()

    corpus = load_corpus(args.corpus)
    print(f"Loaded {len(corpus)} corpus rows from {args.corpus}")

    results, summary = run_parity(
        corpus=corpus,
        go_endpoint=args.go_endpoint or None,
        fail_fast=args.fail_fast,
        category_filter=args.category or None,
        session_id=args.session_id,
        bearer_token=args.bearer_token,
    )

    # Write JSON report.
    report = {
        "summary": summary,
        "rows": [
            {
                "id": r.row_id,
                "user_message": r.user_message,
                "category": r.category,
                "python": asdict(r.python) if r.python else None,
                "go": asdict(r.go) if r.go else None,
                "triage_match": r.triage_match,
                "rules_match": r.rules_match,
            }
            for r in results
        ],
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Report written to {args.output}")

    print_summary(summary, go_mode=bool(args.go_endpoint))

    # Exit non-zero if gates fail (when Go endpoint was used).
    if args.go_endpoint:
        gates_pass = all([
            summary.get("triage_match", {}).get("gate_99pct", True),
            summary.get("rules_match", {}).get("gate_95pct", True),
        ])
        sys.exit(0 if gates_pass else 1)


if __name__ == "__main__":
    main()
