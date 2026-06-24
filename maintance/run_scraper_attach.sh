#!/usr/bin/env bash
# =============================================================================
# Job scraper menu — pick a board or run all three (isolated scripts)
#
#   ./maintance/run_scraper_attach.sh              # interactive menu
#   ./maintance/run_scraper_attach.sh --board indeed
#   ./maintance/run_scraper_attach.sh --board all  # run each; failures isolated
#   ./maintance/run_scraper_attach.sh --help
#
# Per-board scripts (debug one board without touching others):
#   ./maintance/run_indeed_attach.sh
#   ./maintance/run_glassdoor_attach.sh
#   ./maintance/run_dice_attach.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="${PYTHON:-python3}"

INDEED_SH="$SCRIPT_DIR/run_indeed_attach.sh"
GLASSDOOR_SH="$SCRIPT_DIR/run_glassdoor_attach.sh"
DICE_SH="$SCRIPT_DIR/run_dice_attach.sh"

log()  { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
warn() { log "WARN: $*" >&2; }
die()  { log "ERROR: $*" >&2; exit 1; }

menu_usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS] [-- extra args passed to board script]

Interactive menu (no args): choose Indeed / Glassdoor / Dice / all / quit

Options:
  --board BOARD     indeed | glassdoor | dice | all  (skip menu)
  -h, --help        This help

Per-board scripts (same flags: --warm-only, --scrape-only, --cleanup-only, …):
  run_indeed_attach.sh      port ${INDEED_DEBUG_PORT:-9222}
  run_glassdoor_attach.sh   port ${GLASSDOOR_DEBUG_PORT:-9223}
  run_dice_attach.sh        port ${DICE_DEBUG_PORT:-9224}

Examples:
  $(basename "$0") --board glassdoor
  $(basename "$0") --board all --leave-chrome-open
  $(basename "$0") --board indeed --warm-only
EOF
}

run_board_script() {
  local script="$1"
  shift
  log "Running $(basename "$script") $*"
  set +e
  bash "$script" "$@"
  local code=$?
  set -e
  return "$code"
}

run_all_boards() {
  local script failed=0 name
  local scripts=("$INDEED_SH" "$GLASSDOOR_SH" "$DICE_SH")
  local names=("Indeed" "Glassdoor" "Dice")

  log "=== Running all boards (each in its own process — one failure won't stop others) ==="
  local i
  for i in 0 1 2; do
    script="${scripts[$i]}"
    name="${names[$i]}"
    if [[ -t 0 ]]; then
      read -r -p "Run ${name}? [Y/n]: " ans
      [[ "$ans" == "n" || "$ans" == "N" ]] && continue
    fi
    log "---------- ${name} ----------"
    if run_board_script "$script" "$@"; then
      log "${name}: OK"
    else
      local code=$?
      warn "${name}: FAILED (exit ${code})"
      failed=$((failed + 1))
    fi
  done
  log "=== All boards done: ${failed} failure(s) ==="
  [[ "$failed" -eq 0 ]]
}

show_menu() {
  echo ""
  echo "Job scraper attach — choose board"
  echo "  1) Indeed     (port ${INDEED_DEBUG_PORT:-9222})  → run_indeed_attach.sh"
  echo "  2) Glassdoor  (port ${GLASSDOOR_DEBUG_PORT:-9223})  → run_glassdoor_attach.sh"
  echo "  3) Dice       (port ${DICE_DEBUG_PORT:-9224})  → run_dice_attach.sh"
  echo "  4) Run all three (sequential; continue if one fails)"
  echo "  5) Quit"
  echo ""
}

interactive_menu() {
  local choice extra_args=()
  show_menu
  read -r -p "Choice [1-5]: " choice
  case "$choice" in
    1) run_board_script "$INDEED_SH" "${extra_args[@]}" ;;
    2) run_board_script "$GLASSDOOR_SH" "${extra_args[@]}" ;;
    3) run_board_script "$DICE_SH" "${extra_args[@]}" ;;
    4) run_all_boards "${extra_args[@]}" ;;
    5|q|Q) log "Bye"; exit 0 ;;
    *) die "Invalid choice: $choice" ;;
  esac
}

BOARD_CHOICE=""
PASS_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --board)
      BOARD_CHOICE="${2:-}"
      shift 2
      ;;
    --board=*)
      BOARD_CHOICE="${1#*=}"
      shift
      ;;
    -h|--help)
      menu_usage
      exit 0
      ;;
    --)
      shift
      PASS_ARGS+=("$@")
      break
      ;;
    *)
      PASS_ARGS+=("$1")
      shift
      ;;
  esac
done

chmod +x "$INDEED_SH" "$GLASSDOOR_SH" "$DICE_SH" 2>/dev/null || true

if [[ -n "$BOARD_CHOICE" ]]; then
  case "$BOARD_CHOICE" in
    indeed)   exec bash "$INDEED_SH" "${PASS_ARGS[@]}" ;;
    glassdoor) exec bash "$GLASSDOOR_SH" "${PASS_ARGS[@]}" ;;
    dice)     exec bash "$DICE_SH" "${PASS_ARGS[@]}" ;;
    all)      run_all_boards "${PASS_ARGS[@]}" ;;
    *)        die "Unknown board: $BOARD_CHOICE (indeed | glassdoor | dice | all)" ;;
  esac
fi

if [[ -t 0 ]]; then
  interactive_menu
else
  log "Non-interactive: defaulting to Indeed (use --board glassdoor|dice|all)"
  exec bash "$INDEED_SH" "${PASS_ARGS[@]}"
fi
