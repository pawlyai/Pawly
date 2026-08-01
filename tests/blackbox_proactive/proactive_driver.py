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


# How a case's pet_profile block maps onto the wire profile. Scalars first,
# then lists.
_PROFILE_SCALARS = {
    "breed": "breed",
    "age": "age",
    "sex": "sex",
    "gender": "sex",
    "weight": "weight",
    "neutered": "neutered",
    "spayed": "neutered",
    "breed_risk": "breed_risk",
}
_PROFILE_LISTS = {
    "chronic_conditions": "conditions",
    "conditions": "conditions",
    "medications": "medications",
    "allergies": "allergies",
    "baseline": "baselines",
    "baselines": "baselines",
}
#: Keys a case carries for the judge's benefit that are not part of the pet's
#: clinical picture — they are already in the scenario text and would read as
#: noise in a prompt.
_PROFILE_SKIP = {"name", "species"}


def pack_to_render(pack: dict[str, Any]) -> dict[str, Any]:
    """Turn a case's context_pack into the wire fields the renderer reads.

    Anything unrecognised in `pet_profile` lands in `conditions` rather than
    being dropped. A case author adding `care_plan: comfort care at home` is
    stating the single most important thing about that animal, and silently
    discarding it because the key is new would produce a nudge that suggests
    treatment against an agreed plan — and a corpus that scored it without ever
    showing the model why it was wrong.
    """
    out: dict[str, Any] = {}

    profile: dict[str, Any] = {}
    extra_conditions: list[str] = []
    for key, value in (pack.get("pet_profile") or {}).items():
        if key in _PROFILE_SKIP or value in (None, "", [], {}):
            continue
        if key in _PROFILE_SCALARS:
            profile[_PROFILE_SCALARS[key]] = str(value)
        elif key in _PROFILE_LISTS:
            field = _PROFILE_LISTS[key]
            values = value if isinstance(value, list) else [str(value)]
            profile.setdefault(field, []).extend(str(v) for v in values)
        else:
            extra_conditions.append(f"{key.replace('_', ' ')}: {value}")
    if extra_conditions:
        profile.setdefault("conditions", []).extend(extra_conditions)
    if profile:
        out["profile"] = profile

    memories = [
        {"when": str(m.get("when", "")), "fact": str(m.get("fact", m))}
        for m in (pack.get("memory") or [])
        if (m.get("fact") if isinstance(m, dict) else m)
    ]
    if memories:
        out["memories"] = memories

    transcript = [
        {
            "role": str(t.get("role", "user")),
            "when": str(t.get("when", "")),
            "content": str(t.get("content", "")),
        }
        for t in (pack.get("prior_transcript") or [])
        if isinstance(t, dict) and t.get("content")
    ]
    if transcript:
        out["transcript"] = transcript

    if last := pack.get("last_proactive_context"):
        out["last_proactive"] = str(last)

    # The persona is how this owner writes and what they need from a message —
    # the difference between a clinical sentence and one an elderly owner with
    # limited English can answer. It is a hint to a writer, not a field to
    # branch on, so it travels as the prose the case wrote.
    persona = pack.get("user_persona") or {}
    style_bits = [str(persona[k]) for k in ("style", "engagement") if persona.get(k)]
    if style_bits:
        out["owner_style"] = " · ".join(style_bits)

    return out


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
        # The context pack is declared once per case and reaches BOTH the model
        # and the judge. That symmetry is the point: a judge scoring relevance
        # against background the model was never given is measuring the gap
        # between two fixtures, not the quality of a message.
        render.update(pack_to_render(case.get("context_pack") or {}))
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
