"""HTTP driver for the Go notification-service proactive dry-run.

The reactive suite drives chat-service by posting user turns and reading the
reply. A proactive nudge has no user turn to post: the whole question is what
the system says when nobody asked. So a case here describes a *situation* — the
candidate a producer would have filed, the owner's surrounding state, and the
instant — and the service answers with what it would have sent.

    POST /v1/internal/proactive/dry-run
      { now, candidate: {...}, state: {...} }
    → { result: { verdict, gate, reason, content, render_source, ... } }

Everything downstream — the rubrics, the report schema, the Streamlit pages —
is shared with the multi-turn suite and does not know the difference.

# Times

Cases declare time the way a person describes it: "20:00 in the owner's zone,
fourteen hours after the RED turn". Absolute timestamps in a corpus are
unreadable and rot — a case written against a real date starts failing when the
date passes. So the driver resolves relative times against a fixed epoch, and
the epoch never changes, which is what makes a run in August reproduce a run in
March exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

#: The day every case is evaluated on. A Tuesday, deliberately far from any DST
#: transition in the zones the corpus uses (US Eastern, Singapore) so the
#: offset arithmetic never lands on an hour that exists twice or not at all.
CORPUS_EPOCH = datetime(2026, 3, 10, 0, 0, 0, tzinfo=timezone.utc)


def resolve_now(trigger: dict[str, Any]) -> datetime:
    """The UTC instant a case is evaluated at.

    `local_hour` is the owner's wall clock, which is what every gate and every
    case actually reasons about ("a 2am nudge", "the evening digest"). The UTC
    instant is derived from it, never the other way round: a corpus that pinned
    UTC hours would silently mean a different local hour for each region, and
    the SG cases would all be testing the wrong side of quiet hours.
    """
    offset_min = int(trigger.get("utc_offset_minutes", 0))
    local_hour = int(trigger.get("local_hour", 20))
    day_offset = int(trigger.get("local_day_offset", 0))
    local_wall = CORPUS_EPOCH + timedelta(days=day_offset, hours=local_hour)
    return local_wall - timedelta(minutes=offset_min)


def resolve_anchor(trigger: dict[str, Any], now: datetime) -> datetime | None:
    """When the situation being followed up on was assessed.

    Returns None when the case declares no gap, which is right for a trigger
    that is not following up on anything (a milestone, a seasonal note).
    """
    hours = trigger.get("hours_since_anchor")
    if hours is None:
        return None
    return now - timedelta(hours=float(hours))


def _iso(t: datetime | None) -> str | None:
    return None if t is None else t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class DryRunOutcome:
    """What the service said it would do."""

    verdict: str  # send | skip | defer | error
    should_send: bool
    gate: str = ""
    reason: str = ""
    content: str = ""
    render_source: str = ""
    hours_elapsed: int = 0
    defer_until: str = ""
    unexpected_calls: list[str] = field(default_factory=list)
    error: str = ""
    #: The exact request body, kept so a report can show what was actually asked
    #: rather than what the case file says. These have diverged before.
    request: dict[str, Any] = field(default_factory=dict)
    latency_s: float = 0.0


class ProactiveDryRunDriver:
    """Drives one case against a running notification-service.

    `base` is the eval stack's published port, e.g. http://127.0.0.1:18008.
    """

    def __init__(self, base: str, *, service_auth: str = "", timeout_s: float = 120.0) -> None:
        self.base = base.rstrip("/")
        self.service_auth = service_auth
        self.timeout_s = timeout_s

    def build_request(self, case: dict[str, Any]) -> dict[str, Any]:
        """Assemble the wire request from a case.

        Split out from `run` so the corpus validator can check every case builds
        a well-formed request without a stack being up — which is the difference
        between finding a malformed case in a second and finding it forty
        minutes into a 200-case run.
        """
        trigger = case.get("trigger") or {}
        now = resolve_now(trigger)
        anchor = resolve_anchor(trigger, now)

        cand = dict(case["candidate"])
        render = dict(cand.get("render") or {})
        if anchor is not None and "anchor_at" not in render:
            render["anchor_at"] = _iso(anchor)
        if render:
            cand["render"] = render

        cand.setdefault("utc_offset_minutes", int(trigger.get("utc_offset_minutes", 0)))
        cand.setdefault("user_id", case["id"])
        cand.setdefault("session_id", f"sess-{case['id']}")
        cand.setdefault("pet_id", f"pet-{case['id']}")
        # created_at backs the elapsed-time fallback when there is no anchor.
        cand.setdefault("created_at", _iso(anchor or now))

        cascade = cand.get("cascade")
        if cascade and cascade.get("prev_stage_hours_ago") is not None:
            # Same relative-time treatment as the anchor: a case says "the last
            # stage went out a day ago", not a timestamp.
            hours = float(cascade.pop("prev_stage_hours_ago"))
            cascade["prev_stage_sent_at"] = _iso(now - timedelta(hours=hours))
            cand["cascade"] = cascade

        state = dict(case.get("user_state") or {})
        state = _resolve_state_times(state, now)

        return {"now": _iso(now), "candidate": cand, "state": state}

    def run(self, case: dict[str, Any]) -> DryRunOutcome:
        """Evaluate one case. Transport failures raise; a rejected candidate
        does not — that is a verdict."""
        import time

        body = self.build_request(case)
        headers = {"Content-Type": "application/json"}
        if self.service_auth:
            headers["X-Service-Auth"] = self.service_auth

        started = time.monotonic()
        r = httpx.post(
            f"{self.base}/v1/internal/proactive/dry-run",
            json=body,
            headers=headers,
            timeout=self.timeout_s,
        )
        r.raise_for_status()
        res = (r.json().get("data") or {}).get("result") or {}
        return DryRunOutcome(
            verdict=res.get("verdict", ""),
            should_send=bool(res.get("should_send")),
            gate=res.get("gate", "") or "",
            reason=res.get("reason", "") or "",
            content=res.get("content", "") or "",
            render_source=res.get("render_source", "") or "",
            hours_elapsed=int(res.get("hours_elapsed") or 0),
            defer_until=res.get("defer_until", "") or "",
            unexpected_calls=res.get("unexpected_calls") or [],
            error=res.get("error", "") or "",
            request=body,
            latency_s=time.monotonic() - started,
        )


def _resolve_state_times(state: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Turn the state block's relative times into instants.

    A case says "the owner last wrote 30 days ago" and "one capped nudge went
    out four hours ago". Both are relative to the instant under evaluation, and
    both are load-bearing: the first decides a cascade, the second decides the
    daily cap.
    """
    out = dict(state)

    ago = out.pop("last_user_message_hours_ago", None)
    if ago is not None:
        out["last_user_message_at"] = _iso(now - timedelta(hours=float(ago)))

    sent = out.get("sent_today")
    if sent:
        resolved = []
        for row in sent:
            row = dict(row)
            hours = row.pop("hours_ago", None)
            if hours is not None:
                row["sent_at"] = _iso(now - timedelta(hours=float(hours)))
            resolved.append(row)
        out["sent_today"] = resolved
    return out
