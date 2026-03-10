# Pawly

Telegram AI pet care assistant. Send a message about your pet → Claude responds with health advice and tracks symptoms over time.

## Stack

| Layer | Tech |
|---|---|
| Bot | Python 3.12, aiogram 3.x |
| API | FastAPI + uvicorn |
| Database | PostgreSQL 16, SQLAlchemy 2.0 async, Alembic |
| Cache / Session | Redis 7 |
| Background jobs | ARQ |
| LLM | Anthropic Claude (Sonnet for chat, Haiku for extraction) |

## Setup

```bash
# 1. Copy and fill in credentials
cp .env.example .env
# edit .env: set TELEGRAM_BOT_TOKEN and ANTHROPIC_API_KEY

# 2. Start postgres + redis
docker compose up -d postgres redis

# 3. Run database migrations
alembic upgrade head

# 4. Seed test data (creates user test_001 + pet Milo)
python scripts/seed.py

# 5. Start the bot + API server
python -m src.main

# 6. Start the background worker (separate terminal)
python -m arq src.jobs.worker.WorkerSettings
```

## Architecture

```
Telegram user
     │
     ▼
aiogram handler (message.py)
     │
     ├── store raw message (RawMessage)
     ├── get/create ChatSession + Dialogue
     │
     ▼
orchestrator.generate_response()
     │
     ├── load_pet_context()   ← reads PetMemory (read-only)
     ├── build_system_prompt()
     ├── Claude API call
     └── triage (rules engine + LLM inference)
     │
     ▼
send reply to user
     │
     ├── store enriched Messages
     └── enqueue run_extraction (ARQ, fire-and-forget)
              │
              ▼
         extract_memories()
         validate_proposal()
         commit_proposals()   ← writes PetMemory / PendingMemoryChange
```

**Memory safety:** the LLM never writes to the database directly. All memory changes go through the extraction pipeline which validates every proposal. Critical fields (weight, diagnoses) require user confirmation before being committed.

## Scheduled Jobs (ARQ cron)

| Job | Schedule |
|---|---|
| `run_daily_summary` | 02:00 UTC daily |
| `run_weekly_summary` | 03:00 UTC Monday |
| `run_cleanup` | 04:00 UTC daily |

## Docker (full stack)

```bash
docker compose up -d
```

Runs postgres, redis, app (bot + API on port 8000), and worker.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✓ | — | `postgresql+asyncpg://...` |
| `REDIS_URL` | ✓ | `redis://localhost:6379` | Redis DSN |
| `TELEGRAM_BOT_TOKEN` | ✓ | — | From @BotFather |
| `ANTHROPIC_API_KEY` | ✓ | — | Anthropic API key |
| `NODE_ENV` | | `development` | `development` or `production` |
| `PORT` | | `8000` | uvicorn port |
| `MAIN_MODEL` | | `claude-sonnet-4-20250514` | Chat model |
| `EXTRACTION_MODEL` | | `claude-haiku-4-5-20251001` | Extraction model |
| `WEBHOOK_HOST` | prod only | — | e.g. `api.pawly.app` |
| `MAX_TURNS_IN_CONTEXT` | | `5` | Recent turns sent to Claude |
| `MAX_MESSAGES_PER_MINUTE` | | `30` | Per-user rate limit |

## Running Tests

```bash
# End-to-end flow test (requires seed data and ANTHROPIC_API_KEY)
python scripts/test_flow.py
```
