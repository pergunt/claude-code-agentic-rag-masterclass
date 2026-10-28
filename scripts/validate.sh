#!/usr/bin/env bash
# Run the validation suite and write validation-report/<ts>/report.md.
#   scripts/validate.sh [quick|full] [--only <regex>] [--restart]
#
# quick  static + pytest -m "live and not llm" + Playwright @smoke
# full   static (+ npm run build) + pytest -m live + all Playwright specs + LangSmith trace checks
#
# --only accepts "|"-separated catalogue ID prefixes or IDs, e.g. `RET`, `RET-02|CHAT`
#   (pytest -k is not a regex, so only this simple form is supported; "-" and "_" are interchangeable).
#   In quick mode the Playwright grep is "@smoke AND matches", so quick --only X runs only smoke
#   e2e tests that match X. Use `full --only X` to run any e2e test.
# --restart  kill any running services and start fresh ones (stopped again at exit).
#
# Services that were already running are reused and are NOT stopped at exit.
# Exit code: 0 unless the report has a FAIL or UNCOVERED row.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 2

MODE=full
ONLY=""
RESTART=0
while (( $# )); do
  case "$1" in
    quick|full) MODE="$1" ;;
    --only) shift; ONLY="${1:-}" ;;
    --restart) RESTART=1 ;;
    *) echo "usage: scripts/validate.sh [quick|full] [--only <regex>] [--restart]" >&2; exit 2 ;;
  esac
  shift
done

log() { printf '\033[1;35m[validate]\033[0m %s\n' "$*"; }

TS="$(date +%Y%m%d-%H%M%S)"
export VALIDATION_REPORT_DIR="$ROOT/validation-report/$TS"
DIR="$VALIDATION_REPORT_DIR"
mkdir -p "$DIR/static"
START_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
START_EPOCH="$(date +%s)"

# --only (ID prefixes joined by "|") -> pytest -k ("RET_ or CHAT_02") and Playwright grep ("RET-|CHAT-02")
K_EXPR=""; PW_ONLY=""
if [[ -n "$ONLY" ]]; then
  IFS='|' read -r -a parts <<< "$ONLY"
  for part in "${parts[@]}"; do
    [[ -z "$part" ]] && continue
    us="${part//-/_}"; dash="${part//_/-}"
    [[ "$us" =~ [0-9]$ ]] || { us="${us}_"; dash="${dash}-"; }
    K_EXPR+="${K_EXPR:+ or }$us"
    PW_ONLY+="${PW_ONLY:+|}$dash"
  done
fi

STARTED=0
cleanup() {
  trap - EXIT
  if (( STARTED )); then
    log "stopping services this run started"
    "$ROOT/scripts/restart-services.sh" --stop >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

PY="$ROOT/backend/venv/bin/python"
set_status() { printf '%s\n%s\n' "$2" "$3" > "$DIR/static/$1.status"; }

# --- Tier 1: static ----------------------------------------------------------
log "tier 1: static checks"
(cd backend && venv/bin/python -m pytest -q -m "not live" --junitxml="$DIR/junit-unit.xml" ${K_EXPR:+-k "$K_EXPR"}) > "$DIR/unit.log" 2>&1
rc=$?
if (( rc == 0 || rc == 5 )); then set_status STA-01 PASS "pytest -m 'not live' exit $rc (see unit.log)"
else set_status STA-01 FAIL "pytest -m 'not live' exit $rc (see unit.log)"; fi

(cd frontend && npx tsc -b) > "$DIR/tsc.log" 2>&1
tsc_rc=$?
build_note=""
if (( tsc_rc == 0 )) && [[ "$MODE" == full ]]; then
  (cd frontend && npm run build) > "$DIR/build.log" 2>&1
  tsc_rc=$?
  build_note=" + npm run build"
fi
if (( tsc_rc == 0 )); then set_status STA-02 PASS "tsc -b${build_note} exit 0"
else set_status STA-02 FAIL "tsc -b${build_note} failed, see tsc.log / build.log"; fi

(cd frontend && npm run lint) > "$DIR/lint.log" 2>&1
lint_rc=$?
baseline="$(tr -dc '0-9' < validation/lint-baseline.txt)"; baseline="${baseline:-0}"
# oxlint prints one "<file>:L:C: warning|error ..." line per diagnostic
errors="$(grep -cE '^(file://)?[^ ]+:[0-9]+:[0-9]+: error ' "$DIR/lint.log")"
warnings="$(grep -cE '^(file://)?[^ ]+:[0-9]+:[0-9]+: warning ' "$DIR/lint.log")"
summary="$errors$warnings"
if (( errors > 0 )) || (( warnings > baseline )); then
  set_status STA-03 FAIL "lint: $errors errors, $warnings warnings (baseline $baseline), see lint.log"
elif (( lint_rc != 0 && errors == 0 )); then
  set_status STA-03 FAIL "lint exited $lint_rc with no parsed errors, see lint.log"
else
  set_status STA-03 PASS "lint: $errors errors, $warnings warnings (baseline $baseline)"
fi

# --- Tier 2: services --------------------------------------------------------
healthy() { curl -sf localhost:8000/health >/dev/null 2>&1 && curl -sf localhost:5173 >/dev/null 2>&1; }
SERVICES_OK=0
if healthy && (( ! RESTART )); then
  log "WARNING: reusing running services on :8000/:5173 - testing the code those services were started from"
  SERVICES_OK=1
else
  if (( RESTART )); then
    log "restarting services"
    "$ROOT/scripts/restart-services.sh" > "$DIR/services.log" 2>&1 &
  else
    log "starting services"
    "$ROOT/scripts/start-services.sh" > "$DIR/services.log" 2>&1 &
  fi
  STARTED=1
  for _ in $(seq 1 90); do
    healthy && { SERVICES_OK=1; break; }
    sleep 1
  done
fi
if (( SERVICES_OK )); then
  printf 'PASS\nservices healthy\n' > "$DIR/services.status"
else
  log "services did not come up within 90s (see services.log); live/e2e tiers skipped"
  printf 'FAIL\nservices did not come up within 90s (see services.log)\n' > "$DIR/services.status"
fi

# --- Tier 3: live API tests ----------------------------------------------------
if (( SERVICES_OK )); then
  log "tier 3: live API tests"
  if [[ "$MODE" == quick ]]; then LIVE_M="live and not llm"; else LIVE_M="live"; fi
  (cd backend && venv/bin/python -m pytest -q -m "$LIVE_M" --junitxml="$DIR/junit-live.xml" ${K_EXPR:+-k "$K_EXPR"}) > "$DIR/live.log" 2>&1
  log "live tier exit $?"

  # --- Tier 4: Playwright ------------------------------------------------------
  log "tier 4: Playwright"
  grep_args=()
  if [[ "$MODE" == quick && -n "$PW_ONLY" ]]; then grep_args=(--grep "(?=.*@smoke)(?=.*(${PW_ONLY}))")
  elif [[ "$MODE" == quick ]]; then grep_args=(--grep "@smoke")
  elif [[ -n "$PW_ONLY" ]]; then grep_args=(--grep "${PW_ONLY}"); fi
  (cd frontend && npx playwright test ${grep_args[@]+"${grep_args[@]}"}) > "$DIR/playwright.log" 2>&1
  log "playwright exit $?"

  # --- Tier 5: traces (full only) ----------------------------------------------
  if [[ "$MODE" == full ]] && { [[ -z "$ONLY" ]] || grep -qE "${ONLY//_/-}" <<< "OBS-01 OBS-02" ; }; then
    log "tier 5: LangSmith traces"
    UID_A=""
    [[ -f "$DIR/fixtures.json" ]] && UID_A="$(jq -r '.a.id // empty' "$DIR/fixtures.json" 2>/dev/null)"
    if [[ -z "$UID_A" ]]; then
      UID_A="$(cd backend && venv/bin/python -c 'from app.scripts.validation_fixtures import ensure_user, VAL_A; print(ensure_user(VAL_A)[1])' 2>/dev/null)"
    fi
    (cd backend && venv/bin/python -m app.scripts.check_traces --since "$START_ISO" --user-id "$UID_A" --out "$DIR/traces.json") > "$DIR/traces.log" 2>&1
  fi
fi

# --- Tier 6: report ------------------------------------------------------------
printf '{"mode":"%s","only":"%s","start":"%s","end":"%s","duration_s":%d}\n' \
  "$MODE" "$ONLY" "$START_ISO" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(( $(date +%s) - START_EPOCH ))" > "$DIR/meta.json"
(cd backend && venv/bin/python -m app.scripts.validation_report "$DIR" --mode "$MODE" ${ONLY:+--only "$ONLY"})
report_rc=$?
ln -sfn "$TS" "$ROOT/validation-report/latest"
log "report: validation-report/$TS/report.md (also validation-report/latest/report.md)"
exit "$report_rc"
