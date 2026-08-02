"""Report assembly for proactive runs.

The schema is the one `pages/1_Reports.py` already reads — `status` is the
literal string "passed_threshold" / "below_threshold", which the page compares
verbatim — so a proactive run appears in the existing panel with no changes
there. Everything specific to this suite rides in `metadata`, which the page
shows in its expander and ignores otherwise.

The one shape that needed thought is `turns`. A proactive case has no
conversation: there is a situation and there is one message. Rendering the
context pack as the "user" turn and the nudge as the "assistant" turn is not a
cosmetic choice — it means a reviewer reads exactly what the judge read, in the
same order, which is what makes a disputed score checkable by hand.
"""

from __future__ import annotations

from typing import Any

from proactive_scoring import CaseResult, generic_pairs


def _turns(case: dict[str, Any], r: CaseResult, situation: str) -> list[dict[str, Any]]:
    out = r.outcome
    verdict_line = f"**Verdict:** {out.verdict}"
    if out.gate:
        verdict_line += f" · gate `{out.gate}` · reason `{out.reason}`"
    if out.defer_until:
        verdict_line += f" · until {out.defer_until}"

    body = out.content or "_(nothing was sent)_"
    meta = [
        verdict_line,
        f"**Render source:** {out.render_source or '-'} · "
        f"**Hours since anchor:** {out.hours_elapsed} · "
        f"**Latency:** {out.latency_s:.1f}s",
    ]
    return [
        {"role": "user", "content": situation},
        {"role": "assistant", "content": body + "\n\n---\n" + "\n\n".join(meta)},
    ]


def _reason(r: CaseResult) -> str:
    """One readable line explaining the verdict.

    A passing case still gets its dimension scores: a 0.71 that passed today is
    the case most worth watching, and a report that only explains failures hides
    every regression until it lands.
    """
    bits = [f"{d.key} {d.label} {d.score:.2f}" for d in r.dimensions]
    head = " · ".join(bits) if bits else "not scored (nothing was sent)"
    if r.passed:
        return head
    return f"{head}\nFAILED: {r.failure_summary()}"


def build_report(
    results: list[CaseResult],
    cases_by_id: dict[str, dict[str, Any]],
    situations: dict[str, str],
    *,
    judge_model: str,
    d7_judges: list[str],
    sut_model: str,
    timestamp: str,
    report_path: str,
) -> dict[str, Any]:
    pet_names = {
        cid: ((c.get("context_pack") or {}).get("pet_profile") or {}).get("name", "")
        for cid, c in cases_by_id.items()
    }
    # Flag template-shaped output before writing, so the marks land on the cases
    # themselves rather than only in a summary nobody reads twice.
    twins = generic_pairs(results, pet_names)
    by_id = {r.case_id: r for r in results}
    for a, b, ratio in twins:
        by_id[a].generic_twin = f"{b} ({ratio:.2f})"
        by_id[b].generic_twin = f"{a} ({ratio:.2f})"
        for cid in (a, b):
            by_id[cid].passed = False

    cases_out = []
    for r in results:
        case = cases_by_id.get(r.case_id, {})
        cases_out.append({
            "name": r.name,
            "status": "passed_threshold" if r.passed else "below_threshold",
            "score": round(r.score, 4),
            "threshold": r.threshold,
            "reason": _reason(r),
            "turn_count": 1,
            "turns": _turns(case, r, situations.get(r.case_id, "")),
            "pet_profile": (case.get("context_pack") or {}).get("pet_profile") or {},
            "memories": (case.get("context_pack") or {}).get("memory") or [],
            "scenario": case.get("scenario", ""),
            "metadata": {
                "case_id": r.case_id,
                "proactive_type": case.get("proactive_type", ""),
                "persona": case.get("persona", ""),
                "memory_depth": case.get("memory_depth", ""),
                "region": case.get("region", ""),
                "should_send_expected": bool(case.get("should_send", True)),
                "should_send_actual": bool(r.outcome.should_send) if r.outcome else None,
                "sut_model": sut_model,
                "judge_model": judge_model,
                "d7_judges": d7_judges,
                "dimensions": [
                    {
                        "key": d.key, "label": d.label, "score": round(d.score, 4),
                        "threshold": d.threshold, "core": d.core,
                        "passed": d.passed, "reason": d.reason,
                    }
                    for d in r.dimensions
                ],
                "d7": None if r.d7 is None else {
                    "clean": r.d7.clean,
                    "needs_review": r.d7.needs_review,
                    "votes": [
                        {"judge": m, "clean": ok, "reason": why} for m, ok, why in r.d7.votes
                    ],
                },
                "assert_results": [
                    {"name": a.name, "passed": a.passed, "detail": a.detail} for a in r.asserts
                ],
                "assert_failures": [a.name for a in r.assert_failures],
                "generic_twin": r.generic_twin,
                "error": r.error,
                "request": r.outcome.request if r.outcome else {},
            },
            "root_cause": _root_cause(r),
        })

    passed = sum(1 for c in cases_out if c["status"] == "passed_threshold")
    breakdown: dict[str, int] = {}
    for c in cases_out:
        cat = (c["root_cause"] or {}).get("category")
        if cat:
            breakdown[cat] = breakdown.get(cat, 0) + 1

    # A case the judge never scored is not a case the system failed. Counted
    # separately because a judge quota that ran out mid-run otherwise reports as
    # a catastrophic regression that never happened.
    unscored = sum(1 for r in results if r.error)
    withheld = [r for r in results if r.outcome and not r.outcome.should_send]
    correctly_withheld = [r for r in withheld if r.passed]

    return {
        "summary": {
            "report_path": report_path,
            "llm_model": sut_model,
            "judge_model": judge_model,
            "d7_judges": d7_judges,
            "timestamp": timestamp,
            "total_cases": len(cases_out),
            "passed_threshold": passed,
            "below_threshold": len(cases_out) - passed,
            "root_cause_breakdown": breakdown,
            "judge_same_family": judge_model.split("-")[0] == sut_model.split("-")[0],
            "unscored": unscored,
            # The acceptance criteria from the brief, computed rather than
            # eyeballed. Each is a number a reviewer would otherwise derive by
            # hand from 200 rows, which is how a target quietly stops being met.
            "assertions_passed": sum(1 for r in results if not r.assert_failures),
            "restraint_cases": len(withheld),
            "restraint_correct": len(correctly_withheld),
            "d7_checked": sum(1 for r in results if r.d7 is not None),
            "d7_hooks_found": sum(1 for r in results if r.d7 and not r.d7.clean),
            "d7_needs_review": sum(1 for r in results if r.d7 and r.d7.needs_review),
            "core_dimension_failures": sum(1 for r in results if r.failed_core),
            "generic_pairs": [
                {"a": a, "b": b, "similarity": round(ratio, 3)} for a, b, ratio in twins
            ],
            "dimension_means": _dimension_means(results),
        },
        "cases": cases_out,
    }


def _root_cause(r: CaseResult) -> dict[str, str]:
    """Name the first thing that failed, in severity order.

    Ordered so the breakdown answers "what is wrong with this run" rather than
    "what did the last check happen to notice": a message carrying an upsell is
    a different kind of problem from one that scored 0.68 on warmth, and burying
    it behind a dimension score would let a D7 regression read as drift.
    """
    if r.error:
        return {"category": "scoring_error", "explanation": r.error}
    if r.d7 and not r.d7.clean:
        return {"category": "commercial_hook", "explanation": r.d7.detail}
    if r.d7 and r.d7.needs_review:
        return {"category": "d7_split_vote", "explanation": r.d7.detail}
    if r.generic_twin:
        return {"category": "generic_template", "explanation": f"near-identical to {r.generic_twin}"}
    if r.assert_failures:
        return {
            "category": "assertion",
            "explanation": "; ".join(f"{a.name}: {a.detail}" for a in r.assert_failures),
        }
    if r.failed_core:
        d = r.failed_core[0]
        return {
            "category": f"dimension_{d.key}",
            "explanation": f"{d.label} {d.score:.2f} < {d.threshold}: {d.reason[:300]}",
        }
    return {}


def _dimension_means(results: list[CaseResult]) -> dict[str, float]:
    sums: dict[str, list[float]] = {}
    for r in results:
        for d in r.dimensions:
            sums.setdefault(d.key, []).append(d.score)
    return {k: round(sum(v) / len(v), 4) for k, v in sorted(sums.items())}
