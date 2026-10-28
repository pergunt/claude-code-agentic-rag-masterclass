#!/usr/bin/env bash
# Kill every running instance of this app's dev services, then start them fresh.
# Catches services started by other terminals or other Claude sessions: any
# start-services.sh, uvicorn backend, or npm/vite frontend belonging to this repo,
# plus whatever still listens on the backend/frontend ports.
# Ctrl-C stops the new services, same as start-services.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=5173

log() { printf '\033[1;34m[restart]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[restart]\033[0m %s\n' "$*" >&2; exit 1; }

# Dev-server command lines, anchored at the start so they match the server
# processes themselves and not a shell (e.g. another Claude session's command)
# whose text merely mentions them. Editors and shells in the repo stay alive.
PATTERNS=(
  '^([^ ]*/)?((ba|z)?sh )?([^ ]*/)?start-services\.sh'   # not restart-services.sh
  '^[^ ]*[Pp]ython[^ ]* ([^ ]*/)?uvicorn app\.main:app'
  '^[^ ]*[Pp]ython[^ ]* -c from multiprocessing'          # uvicorn --reload workers
  '^npm run dev'
  '^node [^ ]*node_modules/[^ ]*vite'
  '^[^ ]*node_modules/[^ ]*esbuild'
)

cwd_of() { lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p'; }

# A process belongs to this app if its command line or working directory is in the repo.
belongs_here() {
  local cmd
  cmd="$(ps -o command= -p "$1" 2>/dev/null)" || return 1
  [[ "$cmd" == *"$ROOT"* ]] && return 0
  [[ "$(cwd_of "$1")" == "$ROOT"* ]]
}

# This script and its parents (e.g. the shell that launched it) must survive.
protected=" $$ "
p=$PPID
while [[ -n "$p" && "$p" -gt 1 ]]; do
  protected+="$p "
  p="$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')"
done

find_app_pids() {
  local pattern pid
  {
    for pattern in "${PATTERNS[@]}"; do pgrep -f "$pattern" || true; done
    lsof -iTCP:"$BACKEND_PORT" -iTCP:"$FRONTEND_PORT" -sTCP:LISTEN -t 2>/dev/null || true
  } | sort -un | while read -r pid; do
    [[ "$protected" == *" $pid "* ]] && continue
    if belongs_here "$pid"; then echo "$pid"; fi
  done
}

# --- stop ----------------------------------------------------------------------
pids=($(find_app_pids))
if (( ${#pids[@]} )); then
  log "stopping ${#pids[@]} process(es):"
  for pid in "${pids[@]}"; do
    printf '  %6s  %s\n' "$pid" "$(ps -o command= -p "$pid" 2>/dev/null | cut -c1-100)"
  done
  kill "${pids[@]}" 2>/dev/null || true
  for _ in {1..10}; do
    [[ -z "$(find_app_pids)" ]] && break
    sleep 0.5
  done
  leftover=($(find_app_pids))
  if (( ${#leftover[@]} )); then
    log "force-killing ${leftover[*]}"
    kill -9 "${leftover[@]}" 2>/dev/null || true
    sleep 0.5
  fi
else
  log "no running services found"
fi

# A port still busy here is held by something outside this repo; don't kill it blindly.
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  holder="$(lsof -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | head -1 || true)"
  [[ -z "$holder" ]] && continue
  die "port $port is held by PID $holder, which isn't part of this app: $(ps -o command= -p "$holder" | cut -c1-100)"
done

# --- start ---------------------------------------------------------------------
log "starting services"
exec "$ROOT/scripts/start-services.sh"
