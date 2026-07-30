"""Sample real production turns for labelling.

A pass rate on a self-authored corpus is not a detection rate. This pulls what
users actually sent, so the two numbers that matter can be measured against real
language instead of language written by whoever built the tests.

Two samples, because one source cannot give both:

  ESCALATED   from analytics-service's `triage_records`, which holds the full
              chain (rule level, model level, final level, matched patterns) for
              every non-GREEN turn. Labelling these gives the FALSE-ALARM rate:
              of the turns we flagged, how many deserved it.

  GREEN       from chat-service's Mongo message log, filtered to turns that have
              NO triage_records row -- i.e. the ones the system decided were
              fine. Labelling these gives the MISS rate, and misses are the ones
              that kill animals.

The second sample is the hard one and the reason this script exists rather than
a single query. `triage_records` is written only for non-GREEN or health-flagged
turns, so it is structurally incapable of showing a missed emergency: a turn we
wrongly called GREEN leaves no row at all. Any audit that samples only that
table will report a reassuring false-alarm number and say nothing whatsoever
about recall.

Sampling GREEN turns uniformly is honest but inefficient -- emergencies are rare,
so most of the sample is genuinely fine and the labeller's time buys little. The
tempting fix is to prefilter on symptom keywords, and that is exactly wrong here:
the keywords are the rules engine's vocabulary, so filtering by them finds the
emergencies the rules ALREADY catch and systematically hides the ones phrased in
words nobody thought of. Those are the misses worth finding. `--green-mode` makes
the choice explicit rather than burying it:

    uniform    a true random sample. Slow to find misses, but the only mode whose
               result is a valid recall estimate.
    enriched   biased toward longer, symptom-shaped messages. Useful for finding
               problems fast; NOT a denominator you can quote a rate against.

IDs are hashed before they leave the box. The message text cannot be anonymised
without destroying what is being labelled, so treat the output as production
user data: keep it off shared drives and delete it when the labelling is done.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def anon(value: str, salt: str) -> str:
    """Stable pseudonym: the same user stays the same across a sample."""
    if not value:
        return ""
    return hashlib.sha256((salt + value).encode()).hexdigest()[:16]


def fetch_escalated(dsn: str, since: datetime, limit: int, salt: str) -> list[dict[str, Any]]:
    import psycopg

    sql = """
        SELECT id, user_id, pet_id, session_id, message_id,
               rule_level, llm_level, final_level, overridden, override_direction,
               matched_patterns, symptom_excerpt, score, created_at
        FROM triage_records
        WHERE created_at >= %s
        ORDER BY random()
        LIMIT %s
    """
    out = []
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(sql, (since, limit))
        cols = [c.name for c in cur.description]
        for row in cur.fetchall():
            r = dict(zip(cols, row))
            out.append({
                "source": "triage_records",
                "record_id": str(r["id"]),
                "user": anon(str(r["user_id"]), salt),
                "pet": anon(str(r["pet_id"]), salt),
                "session_id": str(r["session_id"]),
                "message_id": str(r["message_id"]),
                "text": r["symptom_excerpt"],
                "system": {
                    "rule_level": r["rule_level"],
                    "llm_level": r["llm_level"],
                    "final_level": r["final_level"],
                    "overridden": r["overridden"],
                    "override_direction": r["override_direction"],
                    "matched_patterns": r["matched_patterns"],
                    "score": float(r["score"]),
                },
                "created_at": r["created_at"].isoformat(),
                "label": None,
            })
    return out


def fetch_green(
    mongo_uri: str, db: str, since: datetime, limit: int, salt: str,
    escalated_message_ids: set[str], mode: str, seed: int,
) -> list[dict[str, Any]]:
    """User turns the system did not escalate.

    Identified by absence from triage_records rather than by any field on the
    message: chat-service does not stamp the triage level onto the user turn, and
    the assistant turn's level is not stored on the message either. Absence is
    the only signal available, which also means a turn whose analytics POST
    failed looks GREEN here. That is a known contaminant and it inflates the
    apparent miss rate rather than hiding misses, so it is the safe direction.
    """
    from pymongo import MongoClient

    rng = random.Random(seed)
    client = MongoClient(mongo_uri)
    coll = client[db]["messages"]

    query: dict[str, Any] = {
        "role": "user",
        "created_at": {"$gte": since},
    }
    # Oversample, then filter and subsample locally: the exclusion set lives in
    # Postgres and cannot be joined server-side.
    candidates = list(coll.find(query, limit=limit * 20))
    pool = [m for m in candidates if str(m.get("_id")) not in escalated_message_ids]

    if mode == "enriched":
        # Longer messages carry more clinical detail. Deliberately NOT a symptom
        # keyword filter -- see the module docstring.
        pool.sort(key=lambda m: len(m.get("content") or ""), reverse=True)
        pool = pool[: limit * 3]

    rng.shuffle(pool)
    out = []
    for m in pool[:limit]:
        out.append({
            "source": f"mongo_green_{mode}",
            "record_id": str(m.get("_id")),
            "user": anon(str(m.get("user_id", "")), salt),
            "pet": anon(str(m.get("pet_id", "")), salt),
            "session_id": str(m.get("session_id", "")),
            "message_id": str(m.get("_id")),
            "text": m.get("content", ""),
            "system": {"final_level": "green", "inferred": "no triage_records row"},
            "created_at": (m.get("created_at") or datetime.now(timezone.utc)).isoformat(),
            "label": None,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pg-dsn", default=os.environ.get("ANALYTICS_DSN", ""),
                    help="postgres DSN for analytics-service (triage_records)")
    ap.add_argument("--mongo-uri", default=os.environ.get("MONGO_URI", ""))
    ap.add_argument("--mongo-db", default=os.environ.get("MONGO_DATABASE", "pawly"))
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--escalated", type=int, default=150)
    ap.add_argument("--green", type=int, default=150)
    ap.add_argument("--green-mode", choices=["uniform", "enriched"], default="uniform",
                    help="uniform is the only mode whose result is a valid recall estimate")
    ap.add_argument("--salt", default=os.environ.get("SAMPLE_SALT", ""),
                    help="hashing salt; keep it constant to follow a user across samples")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="labelling/sample.jsonl")
    args = ap.parse_args()

    if not args.salt:
        print("refusing to run without --salt: an unsalted hash of a user id is "
              "reversible by anyone with the id list", file=sys.stderr)
        return 2

    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    rows: list[dict[str, Any]] = []
    escalated_ids: set[str] = set()

    if args.pg_dsn:
        esc = fetch_escalated(args.pg_dsn, since, args.escalated, args.salt)
        escalated_ids = {r["message_id"] for r in esc}
        rows += esc
        print(f"escalated sample: {len(esc)}")
    else:
        print("no --pg-dsn: skipping the escalated sample, so this run cannot "
              "measure the false-alarm rate", file=sys.stderr)

    if args.mongo_uri:
        green = fetch_green(args.mongo_uri, args.mongo_db, since, args.green,
                            args.salt, escalated_ids, args.green_mode, args.seed)
        rows += green
        print(f"green sample ({args.green_mode}): {len(green)}")
    else:
        print("no --mongo-uri: skipping the green sample, so this run cannot "
              "measure the miss rate -- which is the number that matters",
              file=sys.stderr)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"wrote {len(rows)} rows -> {out}")
    if args.green_mode == "enriched":
        print("NOTE: --green-mode=enriched is biased toward long messages. Use it "
              "to find problems, not to quote a recall figure.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
