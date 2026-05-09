#!/usr/bin/env python3
"""Write a `.meta.json` sidecar describing one regression run.

Called by the CI workflow (after caching a report) and by the local
`make regression-promote-baseline` target. Reads metadata from environment
variables and writes JSON to OUTPUT_PATH.

Required env:
    TOPIC          e.g. multiturn_pawly_regression_light_30
    MODEL          e.g. deepseek-v4-pro
    TREE_SHA       e.g. abc123...

Optional env (filled when known):
    COMMIT_SHA, TRIGGER, PR_NUMBER, PR_TITLE, PR_URL, PR_BRANCH,
    ACTOR, RUN_ID, RUN_URL

The History page reads these sidecars to populate the PR / Title / Branch
columns. Missing fields render as "—" in the UI; they don't cause errors.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone


def _opt(name: str) -> str | None:
    val = os.environ.get(name, "").strip()
    return val or None


def _opt_int(name: str) -> int | None:
    val = _opt(name)
    if val is None:
        return None
    try:
        return int(val)
    except ValueError:
        return None


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: regression_write_meta.py OUTPUT_PATH", file=sys.stderr)
        return 2

    out_path = sys.argv[1]
    meta = {
        "topic": _opt("TOPIC"),
        "model": _opt("MODEL"),
        "tree_sha": _opt("TREE_SHA"),
        "commit_sha": _opt("COMMIT_SHA"),
        "trigger": _opt("TRIGGER"),
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pr_number": _opt_int("PR_NUMBER"),
        "pr_title": _opt("PR_TITLE"),
        "pr_url": _opt("PR_URL"),
        "pr_branch": _opt("PR_BRANCH"),
        "actor": _opt("ACTOR"),
        "run_id": _opt("RUN_ID"),
        "run_url": _opt("RUN_URL"),
    }

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
