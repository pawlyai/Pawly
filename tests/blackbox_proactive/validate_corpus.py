"""Structural and coverage validation for a proactive corpus.

Two jobs, and they fail differently.

**Errors** are cases that cannot be scored meaningfully — a missing trigger, a
should_send=false case with no expected reason, a red-flag case with no prior
transcript to be following up on. These stop a run: a malformed case does not
fail, it produces a confident number about nothing.

**Warnings** are coverage quotas from the brief — persona spread, region mix,
memory depth, the share of restraint cases, the D7 negative count. A 20-case
smoke corpus cannot meet quotas written for 200, so these never block; they are
the QA summary the brief asks for, computed instead of counted by hand.

Run standalone against any corpus:

    python tests/blackbox_proactive/validate_corpus.py test_data/<corpus>.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROACTIVE_TYPES = {"POST_REDFLAG", "UNFINISHED", "WINBACK", "TREND"}

PERSONAS = [f"PA-{i:02d}" for i in range(1, 13)]

#: The five blocks the brief requires on every case. The whole premise is that a
#: proactive message can only be judged against what the AI could see, so a case
#: missing one is not a weaker case — it is an unanswerable question.
REQUIRED_CONTEXT = ("pet_profile", "user_persona", "memory", "prior_transcript")

#: Quotas from the brief, expressed as a fraction of the corpus so they hold for
#: a 20-case smoke run and a 200-case regression alike.
QUOTAS = {
    "restraint_share": 0.15,        # should_send=false >= 15%
    "d7_share": 0.14,               # >= 28/200
    "long_memory_share": 0.40,      # >= 80/200
    "region_us_share": 0.50,
    "region_sg_share": 0.30,
    "persona_min_share": 0.06,      # >= 12/200 each
}


def resolve_corpus(arg: str) -> Path:
    """Accept a corpus path relative to the cwd, the repo root, or this package.

    All three get typed in practice — the runner is invoked from the repo root,
    the validator from anywhere — and guessing wrong produces a FileNotFound
    naming a path nobody wrote.
    """
    candidates = [Path(arg), Path.cwd() / arg, Path(__file__).resolve().parent / arg]
    for p in candidates:
        if p.is_file():
            return p
    raise FileNotFoundError(f"corpus not found; tried: {[str(p) for p in candidates]}")


def validate(
    cases: list[dict[str, Any]], *, enforce_quotas: bool = True
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    seen_ids: set[str] = set()
    for c in cases:
        errors.extend(_validate_case(c, seen_ids))

    if not cases:
        return ["corpus is empty"], warnings

    warnings.extend(_coverage(cases, enforce=enforce_quotas))
    return errors, warnings


def _validate_case(c: dict[str, Any], seen_ids: set[str]) -> list[str]:
    out: list[str] = []
    cid = c.get("id") or "<no id>"

    def bad(msg: str) -> None:
        out.append(f"{cid}: {msg}")

    for field in ("id", "name", "proactive_type", "candidate", "trigger"):
        if not c.get(field):
            bad(f"missing required field {field!r}")
    if not out and c["id"] in seen_ids:
        bad("duplicate id")
    seen_ids.add(c.get("id", ""))

    if c.get("proactive_type") and c["proactive_type"] not in PROACTIVE_TYPES:
        bad(f"unknown proactive_type {c['proactive_type']!r}")
    if c.get("persona") and c["persona"] not in PERSONAS:
        bad(f"unknown persona {c['persona']!r}")

    pack = c.get("context_pack") or {}
    for block in REQUIRED_CONTEXT:
        if not pack.get(block):
            bad(f"context_pack is missing {block!r} — the message cannot be judged "
                f"against background the AI never had")

    cand = c.get("candidate") or {}
    for field in ("category", "priority", "content"):
        if not cand.get(field):
            bad(f"candidate is missing {field!r}")
    # Content is the template the renderer falls back to. Without it a provider
    # failure is indistinguishable from an empty render.
    if cand.get("content") and len(cand["content"]) < 15:
        bad("candidate.content looks like a placeholder, not a real template")

    trigger = c.get("trigger") or {}
    if "local_hour" not in trigger:
        bad("trigger has no local_hour — the timing gates are the point of the case")
    elif not 0 <= int(trigger["local_hour"]) <= 23:
        bad(f"trigger.local_hour {trigger['local_hour']} is not an hour")

    expect = c.get("expect") or {}
    should_send = c.get("should_send", True)

    if not should_send:
        # A restraint case that does not say which rule should hold the nudge is
        # satisfied by any silence at all, including silence caused by a bug.
        if not expect.get("reason") and not expect.get("gate"):
            bad("should_send=false but expect declares neither gate nor reason — "
                "the case would pass on the wrong kind of silence")
    else:
        if not expect.get("anchors"):
            bad("should_send=true but expect.anchors is empty — nothing distinguishes "
                "a real message from a template that mentions the pet's name")

    if c.get("proactive_type") == "POST_REDFLAG":
        if not pack.get("prior_transcript"):
            bad("POST_REDFLAG with no prior_transcript — there is no red flag to follow up on")
        if should_send and not (c.get("redlines") or (c.get("gold_rubric") or {}).get("D6")):
            bad("POST_REDFLAG with no D6 safety redline — the brief makes safety hard here")

    if c.get("memory_depth") not in (None, "short", "medium", "long"):
        bad(f"unknown memory_depth {c['memory_depth']!r}")
    if c.get("memory_depth") == "long":
        span = len(pack.get("prior_transcript") or [])
        if span < 6:
            bad(f"memory_depth=long but prior_transcript has {span} turns — a long-memory "
                f"case has to show the span it is testing recall over")

    if c.get("region") not in (None, "US", "SG"):
        bad(f"unknown region {c['region']!r}")

    return out


def _coverage(cases: list[dict[str, Any]], *, enforce: bool) -> list[str]:
    """Coverage against the brief's quotas, as warnings."""
    n = len(cases)
    out: list[str] = []

    def note(msg: str) -> None:
        out.append(msg)

    def check(label: str, got: int, share: float) -> None:
        want = int(round(share * n))
        if got < want:
            note(f"coverage: {label} {got}/{n} (brief wants >= {want}, {share:.0%})")

    types = Counter(c.get("proactive_type") for c in cases)
    personas = Counter(c.get("persona") for c in cases if c.get("persona"))
    regions = Counter(c.get("region") for c in cases if c.get("region"))
    depths = Counter(c.get("memory_depth") for c in cases if c.get("memory_depth"))

    note(f"coverage: {n} cases — types {dict(types)}")
    note(f"coverage: memory depth {dict(depths)}")
    note(f"coverage: regions {dict(regions)}")

    if not enforce:
        return out

    restraint = sum(1 for c in cases if not c.get("should_send", True))
    check("should_send=false restraint cases", restraint, QUOTAS["restraint_share"])

    # A D7 negative is not merely a case with the check on — it is a case whose
    # situation contains a commercial temptation. Counting the flag alone would
    # let 200 untempting cases satisfy the quota and prove nothing.
    d7 = sum(1 for c in cases if c.get("d7_temptation"))
    check("D7 cases with a commercial temptation in the situation", d7, QUOTAS["d7_share"])

    check("long-memory cases", depths.get("long", 0), QUOTAS["long_memory_share"])
    check("US cases", regions.get("US", 0), QUOTAS["region_us_share"])
    check("SG cases", regions.get("SG", 0), QUOTAS["region_sg_share"])

    for p in PERSONAS:
        check(f"persona {p}", personas.get(p, 0), QUOTAS["persona_min_share"])

    missing = [p for p in PERSONAS if not personas.get(p)]
    if missing:
        note(f"coverage: personas absent entirely: {missing}")
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    cases = json.loads(resolve_corpus(sys.argv[1]).read_text(encoding="utf-8"))
    if isinstance(cases, dict):
        cases = cases.get("cases", [])

    errors, warnings = validate(cases)
    for w in warnings:
        print(w)
    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)
    print(f"\n{len(cases)} cases, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
