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
COOKIE_PKL="$PROJECT_ROOT/indeed_cookies.pkl"
REPORT_LOG="$PROJECT_ROOT/artifacts/logs/report_server.log"
REPORT_PID_FILE="$PROJECT_ROOT/artifacts/logs/report_server.pid"
REPORT_SERVER_SH="$PROJECT_ROOT/scripts/start_report_server.sh"

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
INDEED_SKIP_COOKIE_INJECT=false

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

# ANSI colors (no-op when stdout is not a TTY)
if [[ -t 1 ]]; then
  CLR_RESET=$'\033[0m'
  CLR_BOLD=$'\033[1m'
  CLR_DIM=$'\033[2m'
  CLR_GREEN=$'\033[32m'
  CLR_YELLOW=$'\033[33m'
  CLR_BLUE=$'\033[34m'
  CLR_MAGENTA=$'\033[35m'
  CLR_CYAN=$'\033[36m'
  CLR_RED=$'\033[31m'
else
  CLR_RESET=; CLR_BOLD=; CLR_DIM=
  CLR_GREEN=; CLR_YELLOW=; CLR_BLUE=; CLR_MAGENTA=; CLR_CYAN=; CLR_RED=
fi

cprint() { printf '%b\n' "$*"; }
title()  { cprint "\n${CLR_BOLD}${CLR_MAGENTA}══════════════════════════════════════════════════════════════${CLR_RESET}"; cprint "${CLR_BOLD}${CLR_MAGENTA}  $*${CLR_RESET}"; cprint "${CLR_BOLD}${CLR_MAGENTA}══════════════════════════════════════════════════════════════${CLR_RESET}\n"; }
info()   { cprint "${CLR_CYAN}${CLR_BOLD}▸${CLR_RESET} $*"; }
ok()     { cprint "${CLR_GREEN}${CLR_BOLD}✓${CLR_RESET} $*"; }
note()   { cprint "${CLR_YELLOW}$*${CLR_RESET}"; }
hint()   { cprint "${CLR_DIM}  $*${CLR_RESET}"; }
bad()    { cprint "${CLR_RED}${CLR_BOLD}!${CLR_RESET} $*"; }

report_server_port() {
  echo "${REPORT_PORT:-8765}"
}

report_server_script() {
  echo "$REPORT_SERVER_SH"
}

report_server_port_in_use() {
  local port
  port="$(report_server_port)"
  lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
}

report_server_listener_pid() {
  local port
  port="$(report_server_port)"
  lsof -nP -iTCP:"${port}" -sTCP:LISTEN -t 2>/dev/null | head -1
}

is_report_server_up() {
  local port
  port="$(report_server_port)"
  # Bounded timeout — plain curl can hang on a stuck listener (blocks until Ctrl+C).
  if command -v curl >/dev/null 2>&1; then
    curl --connect-timeout 2 --max-time 3 -sf "http://127.0.0.1:${port}/api/health" >/dev/null 2>&1 && return 0
  fi
  PORT="$port" "$PYTHON" - <<'PY'
import os, urllib.request
port = os.environ["PORT"]
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=3) as resp:
        raise SystemExit(0 if resp.status == 200 else 1)
except Exception:
    raise SystemExit(1)
PY
}

stop_stale_report_server() {
  local port pid pids
  port="$(report_server_port)"

  if is_report_server_up; then
    return 0
  fi

  pkill -f "[g]enerate_job_reports.py --serve" 2>/dev/null || true
  sleep 1

  pids="$(lsof -nP -iTCP:"${port}" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    warn "Freeing port ${port} (stale listener)..."
    while read -r pid; do
      [[ -z "$pid" ]] && continue
      kill "$pid" 2>/dev/null || true
    done <<< "$pids"
    sleep 1
    while read -r pid; do
      [[ -z "$pid" ]] && continue
      if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
      fi
    done <<< "$pids"
    sleep 1
  fi

  if report_server_port_in_use && ! is_report_server_up; then
    pid="$(report_server_listener_pid)"
    bad "Port ${port} still in use (PID ${pid:-unknown})."
    hint "Run: lsof -nP -iTCP:${port} -sTCP:LISTEN"
    hint "Then: kill \$(lsof -t -iTCP:${port} -sTCP:LISTEN)"
    hint "Or set a different port: REPORT_PORT=8770 bash maintance/run_scraper_attach.sh"
    return 1
  fi

  rm -f "$REPORT_PID_FILE" 2>/dev/null || true
  return 0
}

wait_for_report_server() {
  local port max_wait="${1:-25}" i
  port="$(report_server_port)"
  for i in $(seq 1 "$max_wait"); do
    if is_report_server_up; then
      return 0
    fi
    sleep 1
  done
  return 1
}

ensure_report_server_deps() {
  if ! "$PYTHON" -c "import uvicorn" 2>/dev/null; then
    bad "Report server needs Python packages from this project (uvicorn missing)."
    hint "  cd ${PROJECT_ROOT} && python3 -m venv .venv && source .venv/bin/activate"
    hint "  pip install -r requirements.txt"
    return 1
  fi
  return 0
}

show_report_server_log_tail() {
  local log="$REPORT_LOG" n=20
  [[ -f "$log" ]] || return 0
  cprint "${CLR_RED}Last ${n} lines from report server log:${CLR_RESET}"
  tail -n "$n" "$log" | while IFS= read -r line; do hint "$line"; done
}

open_url_in_browser() {
  local url="$1"
  local opened=false

  if command -v open >/dev/null 2>&1; then
    if open "$url" 2>/dev/null; then opened=true; fi
    if [[ "$opened" != "true" ]]; then
      open -a "Google Chrome" "$url" 2>/dev/null && opened=true
    fi
    if [[ "$opened" != "true" ]]; then
      open -a Safari "$url" 2>/dev/null && opened=true
    fi
  fi

  if [[ "$opened" != "true" ]]; then
    PROJECT_ROOT="$PROJECT_ROOT" OPEN_URL="$url" "$PYTHON" - <<'PY' 2>/dev/null || true
import os, webbrowser
webbrowser.open(os.environ["OPEN_URL"])
PY
    opened=true
  fi

  [[ "$opened" == "true" ]]
}

open_static_report_fallback() {
  local index_file="${PROJECT_ROOT}/artifacts/html/index.html"
  [[ -f "$index_file" ]] || return 1
  hint "Static preview only (no Jobs/Search API): file://${index_file}"
  return 0
}

open_report_http_in_browser() {
  local port url
  port="$(report_server_port)"
  url="http://127.0.0.1:${port}/index.html"

  if ! is_report_server_up; then
    bad "Report server is not responding on port ${port} yet."
    hint "Paste in your browser once the server terminal shows 'Uvicorn running':"
    hint "  ${url}"
    return 1
  fi

  if open_url_in_browser "$url"; then
    ok "Opened: ${CLR_BOLD}${url}${CLR_RESET}"
  else
    bad "Could not launch a browser automatically."
    hint "Paste in browser: ${url}"
  fi
  return 0
}

open_report_server_in_new_terminal() {
  local port script
  port="$(report_server_port)"
  script="$(report_server_script)"

  if [[ ! -f "$script" ]]; then
    bad "Report server script missing: ${script}"
    return 1
  fi
  chmod +x "$script" 2>/dev/null || true

  case "$(uname -s)" in
    Darwin)
      if ! osascript <<APPLESCRIPT
tell application "Terminal"
  do script "export DISABLE_UPDATE_PROMPT=true OMZ_DISABLE_AUTOUPDATE=true; exec bash '${script}' --port ${port}"
  activate
end tell
APPLESCRIPT
      then
        bad "Could not open Terminal (AppleScript error)."
        hint "Run manually: bash '${script}' --port ${port}"
        return 1
      fi
      ok "Report server starting in a new Terminal window (port ${port})."
      hint "Script: ${script}"
      ;;
    Linux)
      if command -v gnome-terminal >/dev/null 2>&1; then
        gnome-terminal -- bash -lc "exec bash '${script}' --port ${port}; exec bash"
        ok "Report server starting in a new terminal (port ${port})."
      elif command -v xterm >/dev/null 2>&1; then
        xterm -e bash -lc "exec bash '${script}' --port ${port}; exec bash" &
        ok "Report server starting in xterm (port ${port})."
      else
        hint "Run: bash '${script}' --port ${port}"
        return 1
      fi
      ;;
    *)
      hint "Run: bash '${script}' --port ${port}"
      return 1
      ;;
  esac
}

ensure_report_server_running() {
  local port
  port="$(report_server_port)"
  mkdir -p "$(dirname "$REPORT_LOG")"

  ensure_report_server_deps || return 1

  if is_report_server_up; then
    ok "Report server already running: http://127.0.0.1:${port}/"
    return 0
  fi

  if report_server_port_in_use; then
    note "Port ${port} is in use but not responding — clearing stale process..."
  fi
  stop_stale_report_server || return 1

  if is_report_server_up; then
    ok "Report server is up: http://127.0.0.1:${port}/"
    return 0
  fi

  info "Starting report server in a new terminal (keeps running after this script exits)..."
  open_report_server_in_new_terminal || return 1

  info "Waiting for http://127.0.0.1:${port}/api/health ..."
  if wait_for_report_server 30; then
    ok "Report server ready: http://127.0.0.1:${port}/"
    return 0
  fi

  bad "Server did not become ready within 30s."
  hint "Check the new Terminal window — it should show 'Uvicorn running on http://127.0.0.1:${port}'"
  hint "Run manually: bash $(report_server_script) --port ${port}"
  return 1
}

indeed_cookie_exists() {
  [[ -f "$COOKIE_PKL" ]]
}

show_indeed_cookie_status() {
  PROJECT_ROOT="$PROJECT_ROOT" "$PYTHON" - <<'PY'
import os
import sys
from pathlib import Path

root = Path(os.environ["PROJECT_ROOT"])
sys.path.insert(0, str(root))
from modules import cookies_age as cookies
from modules import cfg

info = cookies.cookie_info()
if info:
    cfg.cprint(f"\n{cfg.clrd('Saved Indeed session:', 'cyan')} {cfg.clrd(info['artifact_name'], 'green')}")
    cfg.cprint(f"  Path: {cfg.clrd(info['artifact_path'], 'magenta')}")
    cfg.cprint(f"  Updated: {cfg.clrd(info['modified'], 'yellow')} ({cfg.clrd(info['age'], 'green')})")
    if info['is_expired']:
        cfg.cprint(f"  {cfg.clrd('Status: likely expired — refresh recommended', 'red')}")
    elif info['age_days'] > 20:
        days_left = 30 - info['age_days']
        cfg.cprint(f"  {cfg.clrd(f'Status: OK (~{days_left} days left)', 'yellow')}")
    else:
        cfg.cprint(f"  {cfg.clrd('Status: good', 'green')}")
else:
    cfg.cprint(f"\n{cfg.clrd('No saved cookies yet', 'yellow')} — file {cfg.clrd('indeed_cookies.pkl', 'magenta')} not found")
PY
}

print_indeed_auth_guide() {
  title "Indeed login — real Chrome opens next (not Selenium)"
  show_indeed_cookie_status
  cprint ""
  note "Your daily Chrome / Gmail session is separate. The scraper uses its own Chrome window"
  note "with profile: artifacts/chrome_profile — pass Cloudflare there once; it usually sticks."
  cprint ""
  cprint "${CLR_BOLD}${CLR_GREEN}Option A — Log in inside that Chrome window${CLR_RESET} ${CLR_DIM}(recommended, especially first run)${CLR_RESET}"
  hint "Pros: real Chrome beats Cloudflare; cf_clearance saved in the scraper profile;"
  hint "      you can export indeed_cookies.pkl after a successful scrape."
  hint "Cons: one manual login per new profile (unless you save the pickle afterward)."
  cprint ""
  cprint "${CLR_BOLD}${CLR_BLUE}Option B — Load saved indeed_cookies.pkl into warm Chrome${CLR_RESET}"
  hint "Pros: fastest repeat runs; best for daily / heavy scraping (~30 days per export)."
  hint "Cons: file must exist and be fresh; stale pickle → log in via Option A instead."
  cprint ""
  bad "Avoid: get_cookies.py --auto before attach — Selenium on the auth page often loops Cloudflare."
  cprint ""
}

save_indeed_cookies_from_warm() {
  set +e
  "$PYTHON" "$PROJECT_ROOT/modules/get_cookies.py" --from-warm "$DEBUG_PORT"
  local code=$?
  set -e
  [[ "$code" -eq 0 ]]
}

prompt_save_indeed_cookies_after_run() {
  [[ "${ATTACH_SKIP_PROMPTS:-}" == "1" ]] && return 0
  [[ ! -t 0 ]] && return 0
  [[ "$BOARD" != "indeed" ]] && return 0
  [[ "$RUN_SCRAPER" != "true" ]] && return 0
  is_debug_port_open || return 0

  local default_ans="Y" ans
  if indeed_cookie_exists; then
    default_ans="n"
  fi

  cprint ""
  title "Save Indeed session for next time?"
  info "Export cookies from the warm Chrome you just used → ${CLR_BOLD}indeed_cookies.pkl${CLR_RESET}"
  hint "Makes future attach runs faster (injected before warm). Profile also keeps cf_clearance."
  cprint ""
  if [[ "$default_ans" == "Y" ]]; then
    read -r -p "$(printf '%b' "${CLR_BOLD}Save indeed_cookies.pkl now? [Y/n]: ${CLR_RESET}")" ans
    ans="${ans:-Y}"
  else
    read -r -p "$(printf '%b' "${CLR_BOLD}Update indeed_cookies.pkl from this session? [y/N]: ${CLR_RESET}")" ans
    ans="${ans:-N}"
  fi

  if [[ "$ans" == "y" || "$ans" == "Y" || "$ans" == "yes" || "$ans" == "Yes" ]]; then
    if save_indeed_cookies_from_warm; then
      ok "Saved indeed_cookies.pkl — next run can use Option B (load saved cookies)."
      show_indeed_cookie_status
    else
      bad "Could not save cookies — log in to Indeed in the Chrome window and retry:"
      hint "python3 modules/get_cookies.py --from-warm ${DEBUG_PORT}"
    fi
  else
    hint "Skip saving. Manual export while Chrome is still open:"
    hint "python3 modules/get_cookies.py --from-warm ${DEBUG_PORT}"
  fi
  cprint ""
}

prompt_indeed_auth_before_run() {
  [[ "${ATTACH_SKIP_PROMPTS:-}" == "1" ]] && return 0
  [[ ! -t 0 ]] && return 0
  [[ "$BOARD" != "indeed" ]] && return 0
  [[ "$RUN_SCRAPER" != "true" ]] && return 0

  print_indeed_auth_guide

  local choice
  if indeed_cookie_exists; then
    cprint "${CLR_BOLD}What would you like to do?${CLR_RESET}"
    cprint "  ${CLR_GREEN}1${CLR_RESET}) ${CLR_BOLD}Load saved cookies into warm Chrome${CLR_RESET} ${CLR_DIM}(default — regular use)${CLR_RESET}"
    cprint "  ${CLR_CYAN}2${CLR_RESET}) Fresh login in warm Chrome ${CLR_DIM}(ignore pickle this run)${CLR_RESET}"
    cprint "  ${CLR_YELLOW}3${CLR_RESET}) Log in in warm Chrome ${CLR_DIM}(same as 2; use if cookies expired)${CLR_RESET}"
    cprint ""
    read -r -p "$(printf '%b' "${CLR_BOLD}Choice [1/2/3] (default 1): ${CLR_RESET}")" choice
    choice="${choice:-1}"
    case "$choice" in
      1)
        INDEED_SKIP_COOKIE_INJECT=false
        ok "Will inject indeed_cookies.pkl when warm Chrome opens."
        ;;
      2|3)
        INDEED_SKIP_COOKIE_INJECT=true
        note "Skipping pickle — log in to Indeed in the warm Chrome window when it opens."
        hint "After scrape you'll be asked to save indeed_cookies.pkl for next time."
        ;;
      *)
        warn "Unknown choice '$choice' — loading saved cookies."
        INDEED_SKIP_COOKIE_INJECT=false
        ;;
    esac
  else
    cprint "${CLR_BOLD}What would you like to do?${CLR_RESET}"
    cprint "  ${CLR_GREEN}1${CLR_RESET}) ${CLR_BOLD}Log in in warm Chrome when it opens${CLR_RESET} ${CLR_DIM}(default — recommended)${CLR_RESET}"
    cprint "  ${CLR_CYAN}2${CLR_RESET}) Load indeed_cookies.pkl ${CLR_DIM}(only if you copied one into the project root)${CLR_RESET}"
    cprint ""
    read -r -p "$(printf '%b' "${CLR_BOLD}Choice [1/2] (default 1): ${CLR_RESET}")" choice
    choice="${choice:-1}"
    case "$choice" in
      1)
        INDEED_SKIP_COOKIE_INJECT=true
        ok "Real Chrome opens next — pass Cloudflare and log in to Indeed there."
        hint "You'll be asked to save indeed_cookies.pkl after scraping (for heavy use)."
        ;;
      2)
        if indeed_cookie_exists; then
          INDEED_SKIP_COOKIE_INJECT=false
          ok "Will inject indeed_cookies.pkl when warm Chrome opens."
        else
          INDEED_SKIP_COOKIE_INJECT=true
          bad "indeed_cookies.pkl still not found — you'll log in in warm Chrome."
          hint "Copy a pickle to: ${COOKIE_PKL}"
        fi
        ;;
      *)
        INDEED_SKIP_COOKIE_INJECT=true
        note "Continuing — log in in warm Chrome when it opens."
        ;;
    esac
  fi
  cprint ""
}

show_report_server_log_help() {
  local port script
  port="$(report_server_port)"
  script="$(report_server_script)"

  cprint ""
  title "Report server — logs and control"
  info "Server URL: ${CLR_BOLD}http://127.0.0.1:${port}/${CLR_RESET}"
  info "Start script: ${CLR_BOLD}${script}${CLR_RESET}"
  cprint ""
  cprint "${CLR_BOLD}Start / restart server:${CLR_RESET}"
  hint "bash ${script} --port ${port}"
  cprint ""
  cprint "${CLR_BOLD}Or foreground in this terminal:${CLR_RESET}"
  hint "cd ${PROJECT_ROOT} && ${PYTHON} modules/generate_job_reports.py --serve --port ${port}"
  cprint ""
  cprint "${CLR_BOLD}Stop report server:${CLR_RESET}"
  hint "Close the Terminal window running --serve, or:"
  hint "pkill -f 'generate_job_reports.py --serve'"
  cprint ""
  note "Use http://127.0.0.1:${port}/ — not file:// — for Jobs, Search, and Apply/Skip."
}

show_report_server_manual_help() {
  local port script import_cmd static_url
  port="$(report_server_port)"
  script="$(report_server_script)"
  import_cmd="cd ${PROJECT_ROOT} && ${PYTHON} modules/generate_job_reports.py --import-json"
  static_url="file://${PROJECT_ROOT}/artifacts/html/index.html"

  cprint ""
  title "View reports later"
  cprint "${CLR_BOLD}${CLR_GREEN}Recommended — interactive reports in browser:${CLR_RESET}"
  hint "bash ${script} --port ${port}"
  hint "Then open: http://127.0.0.1:${port}/"
  cprint ""
  cprint "${CLR_BOLD}Other useful commands:${CLR_RESET}"
  hint "Re-import JSON into database:  ${import_cmd}"
  hint "Rebuild HTML only:             ${PYTHON} modules/generate_job_reports.py --import-json --variants index,dashboard,search"
  hint "Static preview (limited):      ${static_url}"
  cprint ""
  note "Use --serve for full Jobs search, dashboard live data, and Apply/Skip cards."
}

start_report_server_background() {
  # Legacy helper — prefer ensure_report_server_running (new Terminal + health wait).
  ensure_report_server_running
}

prompt_report_server_after_run() {
  [[ "${ATTACH_SKIP_PROMPTS:-}" == "1" ]] && return 0
  [[ ! -t 0 ]] && return 0

  local ans port
  port="$(report_server_port)"

  cprint ""
  title "View your scraped jobs"
  info "HTML reports were built under ${CLR_BOLD}artifacts/html/${CLR_RESET}"
  note "Jobs, Search, and Apply/Skip need the FastAPI server at http://127.0.0.1:${port}/"
  note "Do not use file:// for those tabs — it will look broken."
  cprint ""
  read -r -p "$(printf '%b' "${CLR_BOLD}Start report server and open http://127.0.0.1:${port}/ in browser? [Y/n]: ${CLR_RESET}")" ans
  ans="${ans:-Y}"

  if [[ "$ans" == "y" || "$ans" == "Y" || "$ans" == "yes" || "$ans" == "Yes" ]]; then
    if ensure_report_server_running; then
      open_report_http_in_browser || true
    else
      hint "Run manually in a terminal:"
      hint "  bash $(report_server_script) --port ${port}"
      hint "Then open: http://127.0.0.1:${port}/index.html"
      open_static_report_fallback || true
    fi
    show_report_server_log_help
  else
    show_report_server_manual_help
    open_static_report_fallback || true
  fi
}

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

Workflow: Indeed auth guide → real Chrome warm → attach scrape → optional cookie export → HTML reports → optional report server

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
  if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
  fi
  mkdir -p "$STATE_DIR" "$JSON_DIR" "$(dirname "$REPORT_LOG")"
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
  report_process_state
  report_json_artifacts
  run_cache_cleanup
  generate_html_reports
  prompt_save_indeed_cookies_after_run
  if [[ "$QUIT_CHROME" == "true" ]]; then
    quit_chrome
  else
    log "Leaving Chrome open (--leave-chrome-open)"
  fi
  prompt_report_server_after_run
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
  local warm_extra=() warm_out
  if [[ "$INDEED_SKIP_COOKIE_INJECT" == "true" && "$BOARD" == "indeed" ]]; then
    warm_extra+=(--skip-cookie-inject)
  fi
  warm_out="$("$PYTHON" "$WARM_SCRIPT" --board "$BOARD" --debug-port "$DEBUG_PORT" --detach "${warm_extra[@]}" 2>&1 | tee /dev/stderr)"
  CHROME_PID="$(echo "$warm_out" | sed -n 's/^CHROME_PID=//p' | tail -1)"
  [[ -z "$CHROME_PID" ]] && CHROME_PID="$(find_chrome_pid_for_port)"
  write_state
  if ! is_debug_port_open || ! has_attachable_pages; then
    wait_for_debug_port
  fi
  local ready_msg
  ready_msg="$(board_ready_message)"
  if [[ "$BOARD" == "indeed" && "$INDEED_SKIP_COOKIE_INJECT" == "true" ]]; then
    log "Pass Cloudflare if prompted. Log in to Indeed in this Chrome window if needed."
  else
    log "Pass Cloudflare if prompted. Confirm ${ready_msg} are visible."
  fi
  if [[ -t 0 ]]; then
    read -r -p "Press ENTER when ${ready_msg} are visible (logged in if Indeed)... "
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
  prompt_indeed_auth_before_run
  run_orchestrated
}
