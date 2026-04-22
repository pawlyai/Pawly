#!/usr/bin/env bash
# dev.sh — start the full Pawly dev stack (app + worker + postgres + redis + langfuse)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'

info()    { echo -e "${CYAN}[dev]${NC} $*"; }
success() { echo -e "${GREEN}[dev]${NC} $*"; }
warn()    { echo -e "${YELLOW}[dev]${NC} $*"; }
die()     { echo -e "${RED}[dev] ERROR:${NC} $*" >&2; exit 1; }

# ── 1. Prerequisites ──────────────────────────────────────────────────────────

command -v docker >/dev/null 2>&1 || die "docker not found"
docker info >/dev/null 2>&1      || die "Docker daemon not running — start Docker Desktop"

# ── 2. .env check ─────────────────────────────────────────────────────────────

if [[ ! -f "$ROOT/.env" ]]; then
  warn ".env not found — copying from .env.example"
  cp "$ROOT/.env.example" "$ROOT/.env"
  warn "Edit .env and set GOOGLE_API_KEY, then re-run this script."
  exit 1
fi

if ! grep -q "^GOOGLE_API_KEY=.\+" "$ROOT/.env" 2>/dev/null; then
  die "GOOGLE_API_KEY is not set in .env — LLM calls will fail"
fi

# TELEGRAM_BOT_TOKEN can be a dummy in dev (bot won't connect but API works)
if ! grep -q "^TELEGRAM_BOT_TOKEN=.\+" "$ROOT/.env" 2>/dev/null; then
  warn "TELEGRAM_BOT_TOKEN not set — Telegram bot won't connect, but /chat API will work"
  echo "TELEGRAM_BOT_TOKEN=dev-dummy-token" >> "$ROOT/.env"
fi

# ── 3. Start containers ───────────────────────────────────────────────────────

info "Starting containers..."
docker compose up -d --build

# ── 4. Wait for services ──────────────────────────────────────────────────────

wait_http() {
  local name="$1" url="$2" max="${3:-60}"
  local elapsed=0
  printf "${CYAN}[dev]${NC} Waiting for %s " "$name"
  until curl -sf "$url" >/dev/null 2>&1; do
    sleep 2; elapsed=$((elapsed + 2))
    printf "."
    if [[ $elapsed -ge $max ]]; then
      echo ""
      die "$name did not become ready after ${max}s — run: docker compose logs $name"
    fi
  done
  echo ""
  success "$name is up"
}

wait_pg() {
  local name="$1" container="$2" user="$3" db="$4" max="${5:-30}"
  local elapsed=0
  printf "${CYAN}[dev]${NC} Waiting for %s " "$name"
  until docker exec "$container" pg_isready -U "$user" -d "$db" >/dev/null 2>&1; do
    sleep 2; elapsed=$((elapsed + 2))
    printf "."
    if [[ $elapsed -ge $max ]]; then
      echo ""
      die "$name did not become ready after ${max}s — run: docker compose logs $name"
    fi
  done
  echo ""
  success "$name is up"
}

wait_pg   "pawly postgres"    "pawly_postgres"    "pawly"    "pawly"    30
wait_pg   "langfuse postgres" "langfuse_postgres" "langfuse" "langfuse" 30
wait_http "pawly app"         "http://localhost:8000/health"           60
wait_http "langfuse server"   "http://localhost:3000/api/public/health" 90

# ── 5. Summary ────────────────────────────────────────────────────────────────

echo ""
success "Dev stack is ready"
echo ""
echo -e "  ${CYAN}Pawly API${NC}          http://localhost:8000"
echo -e "  ${CYAN}Swagger UI${NC}         http://localhost:8000/docs"
echo -e "  ${CYAN}POST /chat${NC}         http://localhost:8000/chat"
echo -e "  ${CYAN}Langfuse dashboard${NC} http://localhost:3000"
echo -e "    login: admin@pawly.local / pawly-admin-dev"
echo ""
echo -e "  Tail logs:  ${YELLOW}docker compose logs -f app worker${NC}"
echo -e "  Stop all:   ${YELLOW}docker compose down${NC}"
echo ""
