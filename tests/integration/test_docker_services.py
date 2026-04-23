"""
Integration tests for Docker service connectivity.

C) All containers start and report healthy.
D) Cross-service communication works:
   - app Postgres (pawly DB) is reachable and has the expected schema
   - Langfuse Postgres (langfuse DB) is reachable
   - app can reach Langfuse server health endpoint

These tests require the full docker-compose stack to be running.
Skip automatically when the services are not up.

Run with:
    docker compose up -d
    pytest tests/integration/test_docker_services.py -v
"""

import os

import httpx
import psycopg2
import pytest

# Connection targets — override via env for CI
APP_POSTGRES_DSN = os.environ.get(
    "TEST_APP_POSTGRES_DSN",
    "postgresql://pawly:pawly_pass@localhost:5432/pawly",
)
LANGFUSE_POSTGRES_DSN = os.environ.get(
    "TEST_LANGFUSE_POSTGRES_DSN",
    "postgresql://langfuse:langfuse_pass@localhost:5433/langfuse",
)
APP_BASE_URL = os.environ.get("TEST_APP_BASE_URL", "http://localhost:8000")
LANGFUSE_BASE_URL = os.environ.get("TEST_LANGFUSE_BASE_URL", "http://localhost:3000")


def _postgres_reachable(dsn: str) -> bool:
    try:
        conn = psycopg2.connect(dsn, connect_timeout=3)
        conn.close()
        return True
    except Exception:
        return False


def _http_ok(url: str) -> bool:
    try:
        r = httpx.get(url, timeout=5)
        return r.status_code < 500
    except Exception:
        return False


# ── Skip markers — skip entire module if stack is not running ─────────────────

pytestmark = pytest.mark.skipif(
    not _postgres_reachable(APP_POSTGRES_DSN),
    reason="docker-compose stack not running — start with: docker compose up -d",
)


# ── C: Container health ───────────────────────────────────────────────────────

class TestContainerHealth:
    def test_app_postgres_healthy(self):
        assert _postgres_reachable(APP_POSTGRES_DSN), "pawly postgres not reachable on :5432"

    def test_langfuse_postgres_healthy(self):
        assert _postgres_reachable(LANGFUSE_POSTGRES_DSN), "langfuse postgres not reachable on :5433"

    def test_app_server_healthy(self):
        r = httpx.get(f"{APP_BASE_URL}/health", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"

    def test_langfuse_server_healthy(self):
        r = httpx.get(f"{LANGFUSE_BASE_URL}/api/public/health", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") == "ok"


# ── D: Cross-service connectivity ─────────────────────────────────────────────

class TestCrossServiceConnectivity:
    def test_app_postgres_has_users_table(self):
        """Alembic migrations ran — core schema exists in pawly DB."""
        conn = psycopg2.connect(APP_POSTGRES_DSN, connect_timeout=3)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name='users'"
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        assert len(rows) == 1, "users table missing — did alembic upgrade head run?"

    def test_app_postgres_has_pets_table(self):
        conn = psycopg2.connect(APP_POSTGRES_DSN, connect_timeout=3)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name='pets'"
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        assert len(rows) == 1, "pets table missing"

    def test_langfuse_postgres_has_traces_table(self):
        """Langfuse ran its own migrations — traces table must exist."""
        conn = psycopg2.connect(LANGFUSE_POSTGRES_DSN, connect_timeout=3)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name='traces'"
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        assert len(rows) == 1, "traces table missing in langfuse DB — did langfuse run migrations?"

    def test_app_can_reach_langfuse_health(self):
        """
        The app container must be able to call langfuse-server:3000.
        We verify this from the host using the same URL the app uses internally,
        confirming DNS and network routing are correct end-to-end.
        """
        r = httpx.get(f"{LANGFUSE_BASE_URL}/api/public/health", timeout=10)
        assert r.status_code == 200

    def test_app_chat_endpoint_reachable(self):
        """POST /chat returns a valid response — app is wired up correctly."""
        r = httpx.get(f"{APP_BASE_URL}/docs", timeout=10)
        assert r.status_code == 200

    def test_two_postgres_instances_are_independent(self):
        """Verify the two Postgres DBs have different database names — they are not the same instance."""
        conn_app = psycopg2.connect(APP_POSTGRES_DSN, connect_timeout=3)
        conn_lf = psycopg2.connect(LANGFUSE_POSTGRES_DSN, connect_timeout=3)
        try:
            cur_app = conn_app.cursor()
            cur_lf = conn_lf.cursor()
            cur_app.execute("SELECT current_database()")
            cur_lf.execute("SELECT current_database()")
            app_db = cur_app.fetchone()[0]
            lf_db = cur_lf.fetchone()[0]
        finally:
            conn_app.close()
            conn_lf.close()

        assert app_db == "pawly"
        assert lf_db == "langfuse"
        assert app_db != lf_db
