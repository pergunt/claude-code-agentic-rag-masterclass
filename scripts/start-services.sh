#!/usr/bin/env bash
# Start the local dev services: FastAPI backend (:8000) and Vite frontend (:5173).
# Supabase is hosted, so there is nothing to start for it locally.
# Ctrl-C stops everything.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=5173

log() { printf '\033[1;34m[start]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[start]\033[0m %s\n' "$*" >&2; exit 1; }

port_in_use() { lsof -iTCP:"$1" -sTCP:LISTEN -t >/dev/null 2>&1; }

# --- preflight ---------------------------------------------------------------
[[ -f "$ROOT/backend/.env" ]]  || die "backend/.env missing (copy backend/.env.example)"
[[ -f "$ROOT/frontend/.env" ]] || die "frontend/.env missing (copy frontend/.env.example)"
port_in_use "$BACKEND_PORT"  && die "port $BACKEND_PORT already in use"
port_in_use "$FRONTEND_PORT" && die "port $FRONTEND_PORT already in use (backend CORS expects this port)"

if [[ ! -x "$ROOT/backend/venv/bin/uvicorn" ]]; then
  log "creating backend venv and installing requirements"
  python3 -m venv "$ROOT/backend/venv"
  "$ROOT/backend/venv/bin/pip" install -q -r "$ROOT/backend/requirements.txt"
fi

if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  log "installing frontend dependencies"
  (cd "$ROOT/frontend" && npm install)
fi

# --- run ---------------------------------------------------------------------
pids=()
# npm and uvicorn's reloader spawn children, so kill each whole tree.
kill_tree() {
  local child
  for child in $(pgrep -P "$1" 2>/dev/null); do kill_tree "$child"; done
  kill "$1" 2>/dev/null || true
}
cleanup() {
  trap - EXIT INT TERM
  log "stopping services"
  for pid in ${pids[@]+"${pids[@]}"}; do kill_tree "$pid"; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

log "backend  -> http://localhost:$BACKEND_PORT"
(cd "$ROOT/backend" && exec venv/bin/uvicorn app.main:app --reload --port "$BACKEND_PORT") &
pids+=($!)

log "frontend -> http://localhost:$FRONTEND_PORT"
(cd "$ROOT/frontend" && exec npm run dev -- --port "$FRONTEND_PORT" --strictPort) &
pids+=($!)

for _ in {1..30}; do
  curl -sf "http://localhost:$BACKEND_PORT/health" >/dev/null && break
  sleep 1
done
curl -sf "http://localhost:$BACKEND_PORT/health" >/dev/null \
  && log "backend healthy" \
  || log "backend did not answer /health within 30s, check output above"

# Exit (and tear down the other service) as soon as either one dies.
# Polling instead of `wait -n` so this works with macOS's bash 3.2.
while kill -0 "${pids[0]}" 2>/dev/null && kill -0 "${pids[1]}" 2>/dev/null; do
  sleep 1
done
log "a service exited"
