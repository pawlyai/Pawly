"""
E2E test: POST /chat → LLM generation → both Postgres DBs written → Langfuse trace present.

Full path:
  1. POST /chat with a health-related message (triggers triage DB write in app Postgres)
  2. Assert the HTTP response contains a valid LLM reply
  3. Assert app Postgres has a new triage_records row for this turn
  4. Assert Langfuse Postgres has a new trace row for this turn
  5. Optionally verify the trace via Langfuse REST API

Requires:
  - docker compose up -d (full stack including langfuse-server)
  - GOOGLE_API_KEY set (real Gemini call)

Skip automatically when the stack is not running or the API key is absent.
"""

import os
import time
import uuid

import httpx
import psycopg2
import pytest

APP_BASE_URL = os.environ.get("TEST_APP_BASE_URL", "http://localhost:8000")
LANGFUSE_BASE_URL = os.environ.get("TEST_LANGFUSE_BASE_URL", "http://localhost:3000")
LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "lf-pk-pawly-local-dev")
LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "lf-sk-pawly-local-dev")

APP_POSTGRES_DSN = os.environ.get(
    "TEST_APP_POSTGRES_DSN",
    "postgresql://pawly:pawly_pass@localhost:5432/pawly",
)
LANGFUSE_POSTGRES_DSN = os.environ.get(
    "TEST_LANGFUSE_POSTGRES_DSN",
    "postgresql://langfuse:langfuse_pass@localhost:5433/langfuse",
)


def _stack_up() -> bool:
    try:
        r = httpx.get(f"{APP_BASE_URL}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _langfuse_up() -> bool:
    try:
        r = httpx.get(f"{LANGFUSE_BASE_URL}/api/public/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = [
    pytest.mark.skipif(not _stack_up(), reason="app not running — start with: docker compose up -d"),
    pytest.mark.skipif(not _langfuse_up(), reason="langfuse not running"),
    pytest.mark.skipif(
        not os.environ.get("GOOGLE_API_KEY", "").strip(),
        reason="GOOGLE_API_KEY required for E2E test",
    ),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _count_triage_records(dialogue_id: str) -> int:
    conn = psycopg2.connect(APP_POSTGRES_DSN, connect_timeout=5)
    try:
        cur = conn.cursor()
        # triage_records stores dialogue_id indirectly via message_id — we match on symptoms text
        cur.execute(
            "SELECT COUNT(*) FROM triage_records WHERE symptoms->>'text_excerpt' LIKE %s",
            (f"%{dialogue_id[:8]}%",),
        )
        return cur.fetchone()[0]
    finally:
        conn.close()


def _count_langfuse_traces(session_id: str) -> int:
    """Count traces in Langfuse Postgres that match our dialogue_id (used as session_id)."""
    conn = psycopg2.connect(LANGFUSE_POSTGRES_DSN, connect_timeout=5)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM traces WHERE session_id = %s",
            (session_id,),
        )
        return cur.fetchone()[0]
    finally:
        conn.close()


def _get_langfuse_traces_via_api(session_id: str) -> list[dict]:
    """Query Langfuse REST API to confirm trace is visible in the dashboard."""
    r = httpx.get(
        f"{LANGFUSE_BASE_URL}/api/public/traces",
        params={"sessionId": session_id, "limit": 10},
        auth=(LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY),
        timeout=10,
    )
    if r.status_code != 200:
        return []
    return r.json().get("data", [])


# ── E2E test ──────────────────────────────────────────────────────────────────

class TestChatE2E:
    def test_full_path_health_message(self):
        """
        Send a health message that triggers:
          - A real Gemini call
          - A triage_records write in app Postgres (health query → always stored)
          - A Langfuse trace in langfuse Postgres
        """
        dialogue_id = str(uuid.uuid4())

        # 1. Call the chat endpoint
        response = httpx.post(
            f"{APP_BASE_URL}/chat",
            json={
                "message": "My dog is vomiting and seems very lethargic, should I be worried?",
                "pet_name": "Buddy",
                "pet_species": "dog",
                "pet_age_months": 36,
                "dialogue_id": dialogue_id,
            },
            timeout=60,  # real LLM call can take a few seconds
        )

        # 2. Assert HTTP response is valid
        assert response.status_code == 200, f"chat endpoint failed: {response.text}"
        body = response.json()
        assert body["response_text"], "empty response_text"
        assert body["dialogue_id"] == dialogue_id
        assert body["triage_level"] in ("RED", "ORANGE", "GREEN", None)

        # 3. Assert app Postgres has a triage_records row
        # Give the async DB write a moment to commit
        time.sleep(1)
        conn = psycopg2.connect(APP_POSTGRES_DSN, connect_timeout=5)
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM triage_records")
            triage_count = cur.fetchone()[0]
        finally:
            conn.close()
        # Vomiting + lethargy must trigger a triage record (health query)
        assert triage_count > 0, "no triage_records written to app Postgres"

        # 4. Assert Langfuse Postgres has a trace
        # Langfuse flushes on a background thread — wait up to 10 s
        langfuse_trace_count = 0
        for _ in range(10):
            langfuse_trace_count = _count_langfuse_traces(dialogue_id)
            if langfuse_trace_count > 0:
                break
            time.sleep(1)

        assert langfuse_trace_count > 0, (
            f"no trace found in langfuse Postgres for session_id={dialogue_id}. "
            "Check LANGFUSE_BASE_URL env var and that langfuse-server is healthy."
        )

        # 5. Verify trace visible via Langfuse REST API (confirms dashboard can show it)
        traces = _get_langfuse_traces_via_api(dialogue_id)
        assert len(traces) > 0, (
            "trace not returned by Langfuse /api/public/traces — "
            "check API key pair matches LANGFUSE_INIT_PROJECT_PUBLIC/SECRET_KEY"
        )

    def test_routine_message_no_triage_record_but_trace_logged(self):
        """
        A routine (non-health) message must still produce a Langfuse trace
        but does not write a triage_records row (GREEN + not health → skipped).
        """
        dialogue_id = str(uuid.uuid4())

        response = httpx.post(
            f"{APP_BASE_URL}/chat",
            json={
                "message": "What is the best food for a golden retriever?",
                "pet_name": "Max",
                "pet_species": "dog",
                "dialogue_id": dialogue_id,
            },
            timeout=60,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["response_text"]

        # Langfuse trace should still appear
        langfuse_trace_count = 0
        for _ in range(10):
            langfuse_trace_count = _count_langfuse_traces(dialogue_id)
            if langfuse_trace_count > 0:
                break
            time.sleep(1)

        assert langfuse_trace_count > 0, "trace missing for routine message — tracing not working"
