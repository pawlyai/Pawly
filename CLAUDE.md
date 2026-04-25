# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Pawly

Pawly is a Telegram AI pet care assistant powered by Google Gemini 2.0 Flash. Users chat with a bot about their pets; the system extracts structured health facts into a persistent memory, runs scheduled health summaries, and classifies medical events via a triage engine.

## Development Setup

```bash
cp .env.example .env
# Required: DATABASE_URL, TELEGRAM_BOT_TOKEN, GOOGLE_API_KEY
docker compose up -d postgres redis
alembic upgrade head
python scripts/seed.py          # creates test user test_001 + pet Milo
```

Run both processes concurrently:
```bash
python -m src.main              # bot (long-poll) + FastAPI on :8000
python -m arq src.jobs.worker.WorkerSettings   # ARQ background worker
```

Full Docker stack (includes Langfuse observability):
```bash
./scripts/dev.sh
```

## Commands

| Task | Command |
|------|---------|
| Lint | `ruff check .` |
| Run all tests | `pytest` |
| Memory unit tests (no external deps) | `pytest tests/memory -q` |
| E2E flow test (needs GOOGLE_API_KEY) | `python scripts/test_flow.py` |
| Create migration | `alembic revision --autogenerate -m "description"` |
| Apply migrations | `alembic upgrade head` |

CI runs `ruff check .` and `pytest` on every push/PR.

## Architecture

### Core Request Flow

```
Telegram message
  → aiogram handler (src/bot/handlers/message.py)
  → store RawMessage (audit log)
  → get/create ChatSession + Dialogue
  → LLM orchestrator (src/llm/orchestrator.py)
  → Gemini client → response text
  → send reply + store enriched Message
  → enqueue ARQ job: run_extraction

ARQ extraction job
  → extract structured facts from conversation (src/memory/extractor.py)
  → validate changes (src/memory/validator.py)
  → if critical: create PendingMemoryChange → user confirmation callback
  → else: commit to PetMemory (src/memory/committer.py)
```

The **LLM never writes directly to the database** — all memory changes go through the extraction → validation → confirmation pipeline.

### Key Directories

- `src/bot/` — aiogram handlers (`message.py`, `start.py`, `admin.py`, `callbacks.py`) + rate-limit middleware
- `src/llm/` — orchestrator, Gemini client, prompt templates (`prompts/prompts_config.yaml`), context builder
- `src/llm/graph/` — experimental LangGraph pipeline (toggled by `USE_LANGGRAPH=true` env var)
- `src/memory/` — extraction, validation, committer, reader, summarizer
- `src/jobs/` — ARQ background jobs: `run_extraction`, `run_daily_summary`, `run_weekly_summary`, `run_cleanup`
- `src/triage/` — rules engine for classifying medical events
- `src/api/` — FastAPI routes: `GET /health`, `POST /chat` (mirrors bot flow for web), `/admin` prompt reload
- `src/db/` — SQLAlchemy 2.0 async models + engine, Redis client
- `src/observability/` — Langfuse tracing integration (optional)
- `alembic/` — database migrations
- `tests/memory/` — unit tests (no network), `tests/blackbox_multiturn/` — DeepEval LLM evaluation

### Database Models

`User` → `Pet` → `PetMemory` (confirmed facts), `PendingMemoryChange` (awaiting user confirmation)
`User` → `ChatSession` → `Dialogue` → `Message` / `RawMessage`
`Pet` → `TriageRecord`, `DailySummary`, `WeeklySummary`

### Feature Flags & Hot Reload

- `USE_LANGGRAPH=true` — switches orchestrator to the LangGraph pipeline
- Prompt hot-reload: edit `src/llm/prompts/prompts_config.yaml`, then send `/reload_prompt` to the bot (requires `ADMIN_TELEGRAM_IDS` env var)

### Observability

Langfuse traces all LLM calls. Set `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` in `.env`. The docker-compose stack includes a self-hosted Langfuse instance (separate Postgres on port 5433).
