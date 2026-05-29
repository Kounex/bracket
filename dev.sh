#!/bin/bash
set -eo pipefail

COMPOSE_FILE="docker-compose.dev.yml"
PG_DSN="postgresql://bracket_dev:bracket_dev@localhost:5432/bracket_dev"
BACKEND_PORT=8400
FRONTEND_PORT=3000

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[dev]${NC} $*"; }
ok()   { echo -e "${GREEN}[dev]${NC} $*"; }

free_port() {
  local port=$1
  local pids
  pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    log "Killing stale processes on port $port..."
    echo "$pids" | xargs kill -9 2>/dev/null || true
    sleep 0.5
  fi
}

cleanup() {
  log "Shutting down..."
  kill 0 2>/dev/null || true
  wait 2>/dev/null || true
  ok "Stopped. Postgres container is still running (use 'podman compose -f $COMPOSE_FILE down' to stop it)."
}

wait_for_pg() {
  local retries=30
  while ! python3 -c "
import socket, sys
s = socket.socket(); s.settimeout(1)
try: s.connect(('localhost', 5432)); s.close()
except: sys.exit(1)
" 2>/dev/null; do
    retries=$((retries - 1))
    if [ $retries -le 0 ]; then
      echo -e "${RED}[dev] Postgres did not become ready${NC}"
      exit 1
    fi
    sleep 1
  done
}

# ── Main ──────────────────────────────────────────────────────────────

free_port $BACKEND_PORT
free_port $FRONTEND_PORT

log "Starting Postgres..."
podman compose -f "$COMPOSE_FILE" up -d 2>/dev/null

log "Waiting for Postgres..."
wait_for_pg
ok "Postgres ready on localhost:5432"

log "Seeding database (skips if already populated)..."
cd backend
PG_DSN="$PG_DSN" ENVIRONMENT=DEVELOPMENT uv run ./cli.py create-dev-db 2>&1 | grep -v "^\[" || true
cd ..

echo ""
ok "┌──────────────────────────────────────────┐"
ok "│  Backend   →  http://localhost:$BACKEND_PORT      │"
ok "│  Frontend  →  http://localhost:$FRONTEND_PORT       │"
ok "│  Postgres  →  localhost:5432              │"
ok "│  Login     →  test@example.org            │"
ok "│  Password  →  aeGhoe1ahng2Aezai0Dei6...  │"
ok "├──────────────────────────────────────────┤"
ok "│  Ctrl+C to stop backend + frontend       │"
ok "└──────────────────────────────────────────┘"
echo ""

(
  trap cleanup SIGINT SIGTERM EXIT

  cd frontend && pnpm run dev --port $FRONTEND_PORT --strictPort 2>&1 | while IFS= read -r line; do
    echo -e "${YELLOW}[frontend]${NC} $line"
  done &

  cd backend && PG_DSN="$PG_DSN" ENVIRONMENT=DEVELOPMENT uv run gunicorn \
    -k bracket.uvicorn.RestartableUvicornWorker \
    bracket.app:app \
    --bind "localhost:$BACKEND_PORT" \
    --workers 1 \
    --reload 2>&1 | while IFS= read -r line; do
    echo -e "${GREEN}[backend]${NC}  $line"
  done &

  wait
)
