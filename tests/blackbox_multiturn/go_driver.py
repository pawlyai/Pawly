"""HTTP driver for the Go chat-service.

The existing harness drives the Python monolith in-process:

    from src.bot.handlers import message as message_handler
    ...
    result = await message_handler.generate_response(...)

That system no longer exists. Production is the Go stack, reached over HTTP, so
a case is now run by creating a user + pet, opening a session, and posting each
user turn to the SSE endpoint.

Everything else in the suite — the corpora, the deepeval rubrics, the report
format, the Streamlit pages — is unchanged and does not know the difference.

The driver deliberately owns nothing but transport. It returns the assistant
text plus the structured fields the wire already carries (triage_level, alert),
so assertions can be made on the classification without re-deriving it from
prose, which is exactly what the iOS client used to do wrong.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import httpx


# ── Auth ─────────────────────────────────────────────────────────────────────
#
# The eval stack has no OTP delivery, so tokens are minted directly with the
# stack's JWT secret. This mirrors pawly-common/jwt: HS256, `sub` = user id,
# and an `iss` the services verify.


def mint_token(user_id: str, secret: str, issuer: str = "pawly", ttl_s: int = 3600) -> str:
    def b64(raw: bytes) -> bytes:
        return base64.urlsafe_b64encode(raw).rstrip(b"=")

    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    now = int(time.time())
    payload = b64(
        json.dumps(
            {
                "sub": user_id,
                "iss": issuer,
                "iat": now,
                "exp": now + ttl_s,
                "jti": str(uuid.uuid4()),
            },
            separators=(",", ":"),
        ).encode()
    )
    signing_input = header + b"." + payload
    sig = b64(hmac.new(secret.encode(), signing_input, hashlib.sha256).digest())
    return (signing_input + b"." + sig).decode()


# ── Results ──────────────────────────────────────────────────────────────────


@dataclass
class Turn:
    """One exchange: what was sent, what came back, and how it was classified."""

    user: str
    assistant: str
    triage_level: str | None = None
    alert: str | None = None
    llm_source: str | None = None
    trace_url: str | None = None
    latency_s: float = 0.0


@dataclass
class CaseRun:
    case_name: str
    session_id: str
    pet_id: str
    user_id: str
    turns: list[Turn] = field(default_factory=list)
    #: How many corpus memories actually reached memory-service. Zero on a case
    #: that declares memories means the run is not comparable to a baseline.
    memories_seeded: int = 0
    #: Corpus `recent_turns` are not replayed; recorded so a report can say so.
    recent_turns_skipped: int = 0
    #: Other pets created for the household. Empty for a single-pet case; a
    #: non-empty list is what makes multiPet true on the service side.
    extra_pet_ids: list[str] = field(default_factory=list)

    @property
    def transcript(self) -> list[str]:
        """Flat alternating transcript, the shape the deepeval rubrics expect."""
        out: list[str] = []
        for t in self.turns:
            out.append(t.user)
            out.append(t.assistant)
        return out


# ── Driver ───────────────────────────────────────────────────────────────────


class GoChatDriver:
    """Drives one case against a running chat-service.

    `user_base` and `chat_base` are the eval stack's published ports, e.g.
    http://127.0.0.1:18001 and http://127.0.0.1:18004.
    """

    def __init__(
        self,
        chat_base: str,
        user_base: str,
        jwt_secret: str,
        *,
        memory_base: str | None = None,
        timeout_s: float = 120.0,
    ) -> None:
        self.chat_base = chat_base.rstrip("/")
        self.user_base = user_base.rstrip("/")
        # Optional: when unset, cases still run but their seeded memories are
        # skipped, and any expectation that depends on recall will not hold.
        self.memory_base = memory_base.rstrip("/") if memory_base else None
        self.jwt_secret = jwt_secret
        self.timeout_s = timeout_s

    # -- setup ---------------------------------------------------------------

    @staticmethod
    def new_user_sql(user_id: str, phone: str) -> str:
        """SQL that provisions one eval user.

        There is no admin create-user endpoint and the OTP path needs SMS
        delivery, so the row is written directly. The eval stack's Postgres is
        a tmpfs that dies with the run, so nothing is left behind.

        Each case gets its OWN user rather than sharing one. Pets are per-user
        and the free tier caps them, so a shared user starts failing partway
        through a corpus — and it would also let one case's pet roster leak into
        the next case's prompt, which is precisely what multi-pet attribution
        is sensitive to.
        """
        return (
            "INSERT INTO users (id, phone, password_hash, display_name, status, provider) "
            f"VALUES ('{user_id}', '{phone}', 'x', 'Eval', 'active', 'password') "
            "ON CONFLICT (id) DO NOTHING;"
        )

    def create_pet(self, token: str, profile: dict[str, Any]) -> str:
        """Create the case's pet and return its id.

        Corpora describe age as `age_in_months`; user-service stores a birth
        date. Converting here rather than in the corpus keeps the case files
        usable by both the old harness and this one.
        """
        body: dict[str, Any] = {
            "name": profile["name"],
            "species": profile.get("species", "dog"),
        }
        if profile.get("breed"):
            body["breed"] = profile["breed"]
        gender = profile.get("gender")
        if gender in ("male", "female", "unknown"):
            body["gender"] = gender
        if profile.get("age_in_months") is not None:
            born = date.today() - timedelta(days=int(profile["age_in_months"]) * 30)
            body["birth_date"] = born.isoformat()
        neutered = profile.get("neutered_status")
        if neutered in ("neutered", "spayed"):
            body["is_neutered"] = True
        elif neutered == "intact":
            body["is_neutered"] = False
        if profile.get("weight_latest") is not None:
            body["weight_kg"] = float(profile["weight_latest"])

        r = httpx.post(
            f"{self.user_base}/v1/pets",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        r.raise_for_status()
        return r.json()["data"]["id"]

    def seed_memories(self, token: str, pet_id: str, memories: list[dict[str, Any]]) -> int:
        """Write the case's pre-existing memories into memory-service.

        Corpora describe a memory as:

            {"memory_type": "baseline", "memory_term": "long",
             "field": "diet", "value": {"detail": "..."}}

        which maps onto POST /v1/facts — `field` is the fact key, `value` is
        carried through verbatim. `memory_term` has no counterpart on the Go
        side (facts have no long/short split) and is dropped rather than
        smuggled into a field that means something else.

        Returns how many were written so a caller can assert the seeding
        actually happened; a case that quietly seeds nothing would look like a
        model failure.
        """
        if not self.memory_base or not memories:
            return 0

        written = 0
        for m in memories:
            key = m.get("field")
            if not key:
                continue
            body = {
                "pet_id": pet_id,
                "key": key,
                "value": m.get("value", {}),
                "source": "manual",
                "confidence": 1.0,
            }
            if m.get("memory_type"):
                body["memory_type"] = m["memory_type"]
            r = httpx.post(
                f"{self.memory_base}/v1/facts",
                json=body,
                headers={"Authorization": f"Bearer {token}"},
                timeout=30.0,
            )
            r.raise_for_status()
            written += 1
        return written

    def create_session(self, token: str, pet_id: str, mode: str = "normal") -> str:
        r = httpx.post(
            f"{self.chat_base}/v1/sessions",
            json={"mode": mode, "pet_id": pet_id},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        r.raise_for_status()
        return r.json()["data"]["id"]

    # -- driving -------------------------------------------------------------

    def send_turn(self, token: str, session_id: str, content: str) -> Turn:
        """Post one user turn and assemble the streamed reply.

        chat-service answers with SSE regardless of mode; in structured mode the
        whole reply arrives as a single delta. Both are handled by simply
        concatenating every delta.
        """
        started = time.monotonic()
        assistant = ""
        triage = alert = source = trace_url = None

        with httpx.stream(
            "POST",
            f"{self.chat_base}/v1/sessions/{session_id}/messages",
            json={"content": content},
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout_s,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    ev = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                kind = ev.get("type")
                if kind == "assistant_delta":
                    assistant += ev.get("delta", "")
                elif kind == "assistant_done":
                    triage = ev.get("triage_level")
                    alert = ev.get("alert")
                    source = ev.get("llm_source")
                    trace_url = ev.get("langfuse_trace_url")
                elif kind == "error":
                    raise RuntimeError(f"chat-service returned an error event: {ev.get('error')}")

        return Turn(
            user=content,
            assistant=assistant,
            triage_level=triage,
            alert=alert,
            llm_source=source,
            trace_url=trace_url,
            latency_s=time.monotonic() - started,
        )

    def run_case(self, case: dict[str, Any], user_id: str) -> CaseRun:
        """Set up the pet, then walk every user turn in order.

        `memories` are seeded into memory-service when one is configured.
        `recent_turns` is NOT replayed: those are prior conversation, and
        injecting them as real turns would consume LLM calls and change what the
        history window contains. Cases that depend on them are noted by a
        non-zero `recent_turns` on the CaseRun so a reader can tell the
        difference between "passed" and "passed without its setup".
        """
        token = mint_token(user_id, self.jwt_secret)
        pet_id = self.create_pet(token, case["pet_profile"])
        seeded = self.seed_memories(token, pet_id, case.get("memories") or [])

        # `extra_pets` makes the household multi-pet. The session is still opened
        # against `pet_profile`, which is what gives attribution cases something
        # to get wrong: the owner asks about one of these instead, and the reply
        # has to follow the question rather than the session binding.
        extra_ids = [
            self.create_pet(token, p) for p in (case.get("extra_pets") or [])
        ]

        session_id = self.create_session(token, pet_id)

        run = CaseRun(
            case_name=case["name"],
            session_id=session_id,
            pet_id=pet_id,
            user_id=user_id,
            memories_seeded=seeded,
            recent_turns_skipped=len(case.get("recent_turns") or []),
            extra_pet_ids=extra_ids,
        )
        for content in case["user_turns"]:
            run.turns.append(self.send_turn(token, session_id, content))
        return run
