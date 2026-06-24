#!/usr/bin/env bash
# Shared attach-orchestrator library for Indeed / Glassdoor / Dice.
# Sourced by run_*_attach.sh — do not execute directly.

[[ -n "${ATTACH_COMMON_LOADED:-}" ]] && return 0
ATTACH_COMMON_LOADED=1

# BASH_SOURCE[0] is this file (maintance/lib/); [1] is the caller (maintance/).
ATTACH_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ATTACH_MAINT_DIR="$(cd "$ATTACH_LIB_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$ATTACH_MAINT_DIR/.." && pwd)"
CLEANUP_SCRIPT="$ATTACH_MAINT_DIR/chrome_cache_cleanup.sh"
WARM_SCRIPT="$PROJECT_ROOT/modules/warm_indeed_profile.py"
MAIN_SCRIPT="$PROJECT_ROOT/src/main.py"
JSON_DIR="$PROJECT_ROOT/artifacts/json"
STATE_DIR="${TMPDIR:-/tmp}/indeed_scraper_state"
STATE_FILE="$STATE_DIR/latest.env"
PYTHON="${PYTHON:-python3}"

# Set by each board entry script before attach_init:
#   export SCRAPER_BOARD=indeed|glassdoor|dice
BOARD="${SCRAPER_BOARD:-indeed}"

DUAL_TERMINAL=false
CLEANUP_ONLY=false
DRY_RUN_CLEANUP=false
YES_CLEANUP=false
QUIT_CHROME=true
RUN_DOCKER=false
SKIP_CACHE_CLEANUP=false
RUN_WARM=true
RUN_SCRAPER=true

DEBUG_PORT=""
CHROME_PROFILE_DIR=""
CHROME_PID=""
SCRAPER_PID=""
WARM_PID=""
RUN_START_EPOCH=""
SCRAPER_EXIT=0
CLEANUP_RAN=false

log()  { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
warn() { log "WARN: $*" >&2; }
die()  { log "ERROR: $*" >&2; exit 1; }

board_debug_port() {
  local b="${1:-indeed}"
  case "$b" in
    indeed) echo "${INDEED_DEBUG_PORT:-9222}" ;;
    glassdoor) echo "${GLASSDOOR_DEBUG_PORT:-9223}" ;;
    dice) echo "${DICE_DEBUG_PORT:-9224}" ;;
    *) die "Unknown board: $b" ;;
  esac
}

board_profile_dir() {
  local b="${1:-indeed}"
  case "$b" in
    indeed) echo "$PROJECT_ROOT/artifacts/chrome_profile" ;;
    glassdoor) echo "$PROJECT_ROOT/artifacts/chrome_profile_glassdoor" ;;
    dice) echo "$PROJECT_ROOT/artifacts/chrome_profile_dice" ;;
    *) die "Unknown board: $b" ;;
  esac
}

board_label() {
  case "${1:-indeed}" in
    indeed) echo "Indeed" ;;
    glassdoor) echo "Glassdoor" ;;
    dice) echo "Dice" ;;
    *) echo "$1" ;;
  esac
}

board_entry_script() {
  case "${1:-indeed}" in
    indeed) echo "$ATTACH_MAINT_DIR/run_indeed_attach.sh" ;;
    glassdoor) echo "$ATTACH_MAINT_DIR/run_glassdoor_attach.sh" ;;
    dice) echo "$ATTACH_MAINT_DIR/run_dice_attach.sh" ;;
    *) die "Unknown board: $1" ;;
  esac
}

setup_board_vars() {
  BOARD="${SCRAPER_BOARD:-indeed}"
  DEBUG_PORT="$(board_debug_port "$BOARD")"
  CHROME_PROFILE_DIR="$(board_profile_dir "$BOARD")"
  export SCRAPER_BOARD="$BOARD"
  export INDEED_DEBUG_PORT="$DEBUG_PORT"
}

attach_usage() {
  local script_name="${1:-run_*_attach.sh}"
  cat <<EOF
Usage: $(basename "$script_name") [OPTIONS]

Board: $(board_label "$BOARD")  |  port $(board_debug_port "$BOARD")  |  profile $(board_profile_dir "$BOARD")

Workflow: warm Chrome → attach scrape (src/main.py) → JSON summary → HTML reports

Options:
  --dual-terminal     Warm + scraper in separate terminals
  --mode docker       build/build.sh interactive (not attach)
  --cleanup-only      Teardown + reports for THIS board only
  --leave-chrome-open Keep Chrome open after scrape
  --quit-chrome       Quit Chrome after scrape (default)
  --scan-cache        Sudo Chrome clone scan (-d)
  --dry-run-cleanup   Sudo scan only
  --yes-cleanup       Quit + auto-delete clone caches (sudo)
  --skip-cache        Skip chrome_cache_cleanup.sh
  --warm-only         Launch Chrome only
  --scrape-only       Scraper only (Chrome already warm)
  -h, --help          Show help

Other boards:
  $(basename "$(board_entry_script indeed)")
  $(basename "$(board_entry_script glassdoor)")
  $(basename "$(board_entry_script dice)")
  $(basename "$ATTACH_MAINT_DIR/run_scraper_attach.sh")  (menu / run all)
EOF
}

attach_parse_args() {
  local entry_script="${1:-unknown}"
  shift || true
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --board)
        warn "Ignoring --board (fixed to $(board_label "$BOARD") in this script)"
        shift 2
        ;;
      --board=*)
        warn "Ignoring $1 (board fixed to $(board_label "$BOARD"))"
        shift
        ;;
      --dual-terminal) DUAL_TERMINAL=true; shift ;;
      --mode=docker|--docker) RUN_DOCKER=true; shift ;;
      --mode)
        [[ "${2:-}" == "docker" ]] && RUN_DOCKER=true || die "Unknown mode: ${2:-}"
        shift 2
        ;;
      --cleanup-only)
        CLEANUP_ONLY=true
        QUIT_CHROME=true
        RUN_WARM=false
        RUN_SCRAPER=false
        shift
        ;;
      --quit-chrome) QUIT_CHROME=true; shift ;;
      --leave-chrome-open) QUIT_CHROME=false; shift ;;
      --scan-cache) DRY_RUN_CLEANUP=true; shift ;;
      --dry-run-cleanup) DRY_RUN_CLEANUP=true; QUIT_CHROME=true; shift ;;
      --yes-cleanup) YES_CLEANUP=true; QUIT_CHROME=true; shift ;;
      --skip-cache) SKIP_CACHE_CLEANUP=true; shift ;;
      --warm-only) RUN_SCRAPER=false; shift ;;
      --scrape-only) RUN_WARM=false; shift ;;
      -h|--help) attach_usage "$entry_script"; exit 0 ;;
      *) die "Unknown option: $1 (use -h)" ;;
    esac
  done
}

attach_init() {
  mkdir -p "$STATE_DIR" "$JSON_DIR"
  RUN_START_EPOCH="$(date +%s)"
  export INDEED_RUN_ID="${INDEED_RUN_ID:-$(uuidgen 2>/dev/null || date +%s)}"
  setup_board_vars
}

write_state() {
  cat > "$STATE_FILE" <<EOF
BOARD=${BOARD}
CHROME_PID=${CHROME_PID:-}
SCRAPER_PID=${SCRAPER_PID:-}
WARM_PID=${WARM_PID:-}
DEBUG_PORT=${DEBUG_PORT}
CHROME_PROFILE_DIR=${CHROME_PROFILE_DIR}
PROJECT_ROOT=${PROJECT_ROOT}
STARTED_AT=$(date -Iseconds 2>/dev/null || date)
EOF
}

is_debug_port_open() {
  curl -sf "http://127.0.0.1:${DEBUG_PORT}/json/version" >/dev/null 2>&1
}

has_attachable_pages() {
  local count
  count="$(curl -sf "http://127.0.0.1:${DEBUG_PORT}/json/list" 2>/dev/null \
    | "$PYTHON" -c "import sys,json; d=json.load(sys.stdin); print(sum(1 for t in d if t.get('type')=='page'))" 2>/dev/null \
    || echo 0)"
  [[ "${count:-0}" -gt 0 ]]
}

wait_for_debug_port() {
  local i
  for i in $(seq 1 90); do
    if is_debug_port_open && has_attachable_pages; then
      log "Chrome debug port ${DEBUG_PORT} is ready ($(board_label "$BOARD"))"
      return 0
    fi
    if is_debug_port_open; then
      log "Port ${DEBUG_PORT} open — waiting for a browser tab..."
    fi
    sleep 1
  done
  die "Chrome never became attachable on port ${DEBUG_PORT}"
}

any_chrome_running() {
  if [[ "$(uname -s)" == "Darwin" ]]; then
    pgrep -x "Google Chrome" >/dev/null 2>&1
  else
    pgrep -f "[g]oogle-chrome" >/dev/null 2>&1 \
      || pgrep -f "[c]hromium" >/dev/null 2>&1
  fi
}

find_chrome_pid_for_port() {
  local pid=""
  pid="$(lsof -nP -iTCP:"${DEBUG_PORT}" -sTCP:LISTEN -t 2>/dev/null | head -1 || true)"
  if [[ -n "$pid" ]]; then
    echo "$pid"
    return 0
  fi
  pid="$(pgrep -f "[c]hrome.*remote-debugging-port=${DEBUG_PORT}.*user-data-dir=${CHROME_PROFILE_DIR}" 2>/dev/null | head -1 || true)"
  if [[ -n "$pid" ]]; then
    echo "$pid"
    return 0
  fi
  pgrep -f "[c]hrome.*user-data-dir=${CHROME_PROFILE_DIR}.*remote-debugging-port=${DEBUG_PORT}" 2>/dev/null | head -1 || true
}

scraper_chrome_running() {
  if is_debug_port_open; then
    return 0
  fi
  if [[ -n "${CHROME_PID:-}" ]] && kill -0 "$CHROME_PID" 2>/dev/null; then
    return 0
  fi
  [[ -n "$(find_chrome_pid_for_port)" ]]
}

kill_chrome_process_tree() {
  local pid="$1"
  [[ -z "$pid" ]] && return 0
  if ! kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  if [[ "$(uname -s)" == "Darwin" ]]; then
    pkill -P "$pid" 2>/dev/null || true
  fi
  kill "$pid" 2>/dev/null || true
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    pkill -9 -P "$pid" 2>/dev/null || true
    kill -9 "$pid" 2>/dev/null || true
  fi
}

quit_chrome() {
  if [[ -z "${CHROME_PID:-}" ]] || ! kill -0 "$CHROME_PID" 2>/dev/null; then
    CHROME_PID="$(find_chrome_pid_for_port)"
  fi
  if [[ -z "${CHROME_PID:-}" ]]; then
    log "No $(board_label "$BOARD") Chrome on port ${DEBUG_PORT}"
    return 0
  fi
  log "Closing $(board_label "$BOARD") Chrome (PID ${CHROME_PID}, port ${DEBUG_PORT})..."
  kill_chrome_process_tree "$CHROME_PID"
  local i
  for i in $(seq 1 20); do
    if ! scraper_chrome_running; then
      log "Chrome closed"
      CHROME_PID=""
      return 0
    fi
    sleep 1
  done
  warn "Chrome may still be running"
}

chromedriver_pids() {
  pgrep -f "[c]hromedriver" 2>/dev/null || true
}

uc_driver_pids() {
  # SeleniumBase UC mode (INDEED_USE_UC=1) — not used in attach workflow
  pgrep -x "uc_driver" 2>/dev/null || true
}

selenium_driver_pids() {
  { chromedriver_pids; uc_driver_pids; } | awk 'NF' | sort -nu
}

kill_selenium_drivers() {
  local pids pid killed=0
  pids="$(selenium_driver_pids)"
  [[ -z "$pids" ]] && return 0
  while read -r pid; do
    [[ -z "$pid" ]] && continue
    log "Stopping Selenium driver PID ${pid}..."
    kill "$pid" 2>/dev/null || true
    sleep 0.5
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    killed=$((killed + 1))
  done <<< "$pids"
  [[ "$killed" -gt 0 ]] && log "Stopped ${killed} Selenium driver process(es) (chromedriver / uc_driver)"
}

report_selenium_cache() {
  log "Selenium / chromedriver / uc_driver / profile disk usage:"
  local p
  for p in \
    "$HOME/.cache/selenium" \
    "$HOME/Library/Caches/selenium" \
    "$HOME/.selenium" \
    "$PROJECT_ROOT/artifacts/chrome_profile" \
    "$PROJECT_ROOT/artifacts/chrome_profile_glassdoor" \
    "$PROJECT_ROOT/artifacts/chrome_profile_dice"
  do
    [[ -e "$p" ]] || continue
    du -sh "$p" 2>/dev/null | awk -v path="$p" '{print "  " $1 "\t" path}'
  done
  local chromedrivers uc_drivers
  chromedrivers="$(chromedriver_pids)"
  uc_drivers="$(uc_driver_pids)"
  if [[ -n "$chromedrivers" ]]; then
    warn "chromedriver still running: PIDs ${chromedrivers//$'\n'/, }"
  else
    log "chromedriver: not running"
  fi
  if [[ -n "$uc_drivers" ]]; then
    warn "uc_driver still running: PIDs ${uc_drivers//$'\n'/, } (orphaned UC mode — not used in attach)"
  else
    log "uc_driver: not running"
  fi
}

report_json_artifacts() {
  log "JSON artifacts in ${JSON_DIR}:"
  local count=0 f
  for f in "$JSON_DIR"/*.json; do
    [[ -f "$f" ]] || continue
    count=$((count + 1))
  done
  log "  total files: ${count}"
  "$PYTHON" - <<'PY' "$JSON_DIR" "$RUN_START_EPOCH"
import json, sys
from pathlib import Path
json_dir = Path(sys.argv[1])
run_start = int(sys.argv[2])
files = sorted(json_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
session_files = [p for p in files if p.stat().st_mtime >= run_start - 5]
def summarize(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    meta = data.get("metadata") or {}
    jobs = data.get("jobs") or []
    return meta.get("total_jobs", len(jobs)), (meta.get("search_params") or {}).get("query", "N/A"), meta.get("board") or "?"
if session_files:
    print(f"  session files ({len(session_files)}):")
    t = 0
    for path in session_files:
        total, query, board = summarize(path)
        t += total
        print(f"    - {path.name}  jobs={total}  board={board!r}  query={query!r}")
    print(f"  session job count: {t}")
elif files:
    total, query, board = summarize(files[0])
    print(f"  latest: {files[0].name}  jobs={total}  board={board!r}")
else:
    print("  no JSON files found")
PY
}

report_process_state() {
  log "Process summary ($(board_label "$BOARD")):"
  log "  BOARD=${BOARD}  port=${DEBUG_PORT}  profile=${CHROME_PROFILE_DIR}"
  log "  CHROME_PID=${CHROME_PID:-none}"
  log "  debug port: $(is_debug_port_open && echo open || echo closed)"
}

run_cache_cleanup() {
  [[ "$SKIP_CACHE_CLEANUP" == "true" ]] && return 0
  [[ -f "$CLEANUP_SCRIPT" ]] || return 0
  if [[ "$(uname -s)" != "Darwin" ]]; then
    report_selenium_cache
    return 0
  fi
  if [[ "$DRY_RUN_CLEANUP" != "true" && "$YES_CLEANUP" != "true" && "$CLEANUP_ONLY" != "true" ]]; then
    report_selenium_cache
    return 0
  fi
  if any_chrome_running; then
    [[ "$DRY_RUN_CLEANUP" == "true" ]] && sudo "$CLEANUP_SCRIPT" -d -a chrome || true
    report_selenium_cache
    return 0
  fi
  sudo "$CLEANUP_SCRIPT" -d -a chrome || true
  [[ "$YES_CLEANUP" == "true" ]] && sudo "$CLEANUP_SCRIPT" -y -a chrome || true
  report_selenium_cache
}

generate_html_reports() {
  [[ "$RUN_SCRAPER" != "true" && "$CLEANUP_ONLY" != "true" ]] && return 0
  log "Generating HTML reports..."
  if "$PYTHON" "$PROJECT_ROOT/modules/generate_job_reports.py" --import-json --variants index,dashboard,table,companies,cards,compare; then
    log "Reports: file://${PROJECT_ROOT}/artifacts/html/index.html"
  else
    warn "HTML report generation failed"
  fi
}

cleanup_all() {
  [[ "$CLEANUP_RAN" == "true" ]] && return 0
  CLEANUP_RAN=true
  log "=== POST-RUN: $(board_label "$BOARD") ==="
  kill_selenium_drivers
  if [[ "$QUIT_CHROME" == "true" ]]; then
    quit_chrome
  else
    log "Leaving Chrome open (--leave-chrome-open)"
  fi
  report_process_state
  report_json_artifacts
  run_cache_cleanup
  generate_html_reports
  write_state
}

board_ready_message() {
  case "$BOARD" in
    indeed) echo "Indeed job search results" ;;
    glassdoor) echo "Glassdoor job listings (NOT 'Humans only')" ;;
    dice) echo "Dice job listings" ;;
    *) echo "job listings" ;;
  esac
}

start_warm_detach() {
  cd "$PROJECT_ROOT"
  log "Launching $(board_label "$BOARD") Chrome (port ${DEBUG_PORT})..."
  local warm_out
  warm_out="$("$PYTHON" "$WARM_SCRIPT" --board "$BOARD" --debug-port "$DEBUG_PORT" --detach 2>&1 | tee /dev/stderr)"
  CHROME_PID="$(echo "$warm_out" | sed -n 's/^CHROME_PID=//p' | tail -1)"
  [[ -z "$CHROME_PID" ]] && CHROME_PID="$(find_chrome_pid_for_port)"
  write_state
  if ! is_debug_port_open || ! has_attachable_pages; then
    wait_for_debug_port
  fi
  local ready_msg
  ready_msg="$(board_ready_message)"
  log "Pass Cloudflare if prompted. Confirm ${ready_msg} are visible."
  if [[ -t 0 ]]; then
    read -r -p "Press ENTER when ${ready_msg} are visible... "
  else
    sleep 20
  fi
}

run_scraper() {
  cd "$PROJECT_ROOT"
  log "Starting $(board_label "$BOARD") scraper (attach mode)..."
  export INDEED_ATTACH="${INDEED_ATTACH:-1}"
  export INDEED_ORCHESTRATOR=1
  export SCRAPER_BOARD="$BOARD"
  if [[ "$QUIT_CHROME" == "true" ]]; then
    export INDEED_QUIT_CHROME=1
  else
    unset INDEED_QUIT_CHROME 2>/dev/null || true
  fi
  [[ -z "${CHROME_PID:-}" ]] || ! kill -0 "$CHROME_PID" 2>/dev/null && CHROME_PID="$(find_chrome_pid_for_port)"
  export INDEED_CHROME_PID="${CHROME_PID:-}"
  export INDEED_DEBUG_PORT="${DEBUG_PORT}"
  set +e
  "$PYTHON" "$MAIN_SCRIPT"
  SCRAPER_EXIT=$?
  set -e
  [[ "$SCRAPER_EXIT" -ne 0 ]] && warn "Scraper exited with code ${SCRAPER_EXIT}" || log "Scraper finished OK"
}

run_orchestrated() {
  setup_board_vars
  log "--- $(board_label "$BOARD") | port ${DEBUG_PORT} ---"
  if [[ "$RUN_WARM" == "true" ]]; then
    if is_debug_port_open && has_attachable_pages; then
      log "Reusing Chrome on port ${DEBUG_PORT}"
      CHROME_PID="$(find_chrome_pid_for_port)"
      write_state
    else
      start_warm_detach
    fi
  elif ! is_debug_port_open; then
    die "Port ${DEBUG_PORT} not open — run warm first or drop --scrape-only"
  fi
  [[ "$RUN_SCRAPER" == "true" ]] && run_scraper
}

open_dual_terminal_mac() {
  setup_board_vars
  osascript <<APPLESCRIPT
tell application "Terminal"
  do script "cd '$PROJECT_ROOT' && $PYTHON '$WARM_SCRIPT' --board $BOARD --debug-port $DEBUG_PORT --detach && sleep 999999"
  delay 2
  do script "cd '$PROJECT_ROOT' && sleep 8 && INDEED_ATTACH=1 INDEED_ORCHESTRATOR=1 SCRAPER_BOARD=$BOARD INDEED_DEBUG_PORT=$DEBUG_PORT $PYTHON '$MAIN_SCRIPT'"
end tell
APPLESCRIPT
  trap - EXIT INT TERM
  exit 0
}

open_dual_terminal_linux() {
  setup_board_vars
  command -v tmux >/dev/null 2>&1 || die "Install tmux for --dual-terminal"
  tmux new-session -d -s "warm_${BOARD}" "cd '$PROJECT_ROOT' && $PYTHON '$WARM_SCRIPT' --board $BOARD --debug-port $DEBUG_PORT --detach; sleep 999999"
  sleep 3
  tmux new-session -d -s "scrape_${BOARD}" "cd '$PROJECT_ROOT' && sleep 5 && INDEED_ATTACH=1 INDEED_ORCHESTRATOR=1 SCRAPER_BOARD=$BOARD INDEED_DEBUG_PORT=$DEBUG_PORT $PYTHON '$MAIN_SCRIPT'"
  trap - EXIT INT TERM
  exit 0
}

run_docker() {
  cd "$PROJECT_ROOT/build"
  ./build.sh interactive
  trap - EXIT INT TERM
  exit 0
}

attach_main() {
  local entry_script="${1:-$0}"
  [[ -x "$CLEANUP_SCRIPT" ]] || chmod +x "$CLEANUP_SCRIPT" 2>/dev/null || true
  log "$(board_label "$BOARD") attach — ${PROJECT_ROOT}"
  log "Post-run: quit_chrome=${QUIT_CHROME}  cache_cleanup=$(
    if [[ "$SKIP_CACHE_CLEANUP" == "true" ]]; then echo skip
    elif [[ "$DRY_RUN_CLEANUP" == "true" || "$YES_CLEANUP" == "true" || "$CLEANUP_ONLY" == "true" ]]; then echo scan
    else echo none; fi
  )"
  if [[ "$RUN_DOCKER" == "true" ]]; then
    run_docker
  fi
  if [[ "$DUAL_TERMINAL" == "true" ]]; then
    case "$(uname -s)" in
      Darwin) open_dual_terminal_mac ;;
      Linux) open_dual_terminal_linux ;;
      *) die "Unsupported OS for --dual-terminal" ;;
    esac
  fi
  if [[ "$CLEANUP_ONLY" == "true" ]]; then
    CHROME_PID="$(find_chrome_pid_for_port)"
    write_state
    cleanup_all
    trap - EXIT INT TERM
    exit 0
  fi
  trap cleanup_all EXIT INT TERM
  run_orchestrated
}
