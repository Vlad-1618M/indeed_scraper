#!/bin/bash
# =============================================================================
#       *** Job Scraper - Docker Build & Run Helper ***
# =============================================================================
#
# Boards: Dice + reports in Docker. Indeed → host only (Cloudflare).
#
# From repo root:
#   ./build/build.sh build
#   ./build/build.sh all dice              # dice scrape + reports + serve (default)
#   ./build/build.sh dice [query] [loc] [max]
#   ./build/build.sh reports && ./build/build.sh serve
#   ./build/build.sh auto                  # shows Indeed host redirect
#   ./build/build.sh help
#
# =============================================================================

set -e

# ___ Colors for output:
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ___ Script directory and project root:
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."
COMPOSE_FILE="$PROJECT_ROOT/build/docker-compose.yml"

# ___ Change to project root (works when invoked as ./build/build.sh from repo root):
cd "$PROJECT_ROOT"

# ___ Helper functions:
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ___ Check Docker is available:
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
}

# ___ Ensure .env is a file (Docker bake sometimes creates .env/ as a directory):
ensure_env_file() {
    local env_file="$PROJECT_ROOT/.env"
    local example="$PROJECT_ROOT/.env.example"

    if [ -d "$env_file" ]; then
        if [ -z "$(ls -A "$env_file" 2>/dev/null)" ]; then
            log_warn ".env is an empty directory — replacing with .env file (see docs/Scraper_Docker_Setup.md)"
            rmdir "$env_file"
        else
            log_error ".env is a directory, not a file. Move its contents aside, remove it, then: cp .env.example .env"
            exit 1
        fi
    fi

    if [ ! -f "$env_file" ]; then
        if [ -f "$example" ]; then
            log_warn ".env missing — creating from .env.example"
            cp "$example" "$env_file"
        else
            log_warn ".env missing — creating minimal .env"
            printf 'TZ=America/New_York\nREPORT_HOST=127.0.0.1\nREPORT_PORT=8765\n' > "$env_file"
        fi
    fi
}

# ___ Indeed is host-only (Cloudflare / manual challenges):
msg_indeed_use_host() {
    cat <<'EOF'

================================================================================
INDEED IS NOT SUPPORTED IN DOCKER
================================================================================

Indeed uses Cloudflare and session checks that need a real browser and
sometimes manual clicks. Container Chrome cannot reliably pass those
challenges — saved cookies alone often fail after the first page.

  Run Indeed on the HOST:

    bash maintance/run_indeed_attach.sh
    bash maintance/run_scraper_attach.sh          # menu: all boards

  One-time cookies (~30 days):
    python3 modules/get_cookies.py --auto

  All titles from config/job_titles.ini (interactive — type "all" at prompt):
    bash maintance/run_indeed_attach.sh

  Direct CLI — single query:
    python3 src/main.py --auto --board indeed \
      --query "DevOps Engineer" --location Remote --remote --days 7 --max 50

  Direct CLI — multiple queries:
    python3 src/main.py --auto --board indeed \
      --queries "DevOps Engineer,SDET,Site Reliability Engineer" \
      --location Remote --remote --days 7 --max 25

  Reports after host scrape (artifacts/ is shared with Docker):
    python3 modules/generate_job_reports.py --import-json
    python3 modules/generate_job_reports.py --serve
    # or: ./build/build.sh reports && ./build/build.sh serve

EOF
    msg_docker_capabilities
}

msg_docker_capabilities() {
    cat <<'EOF'
--------------------------------------------------------------------------------
WHAT DOCKER IS FOR
--------------------------------------------------------------------------------

  Board       Docker?   Notes
  ---------   --------  -----
  Dice        Yes       Best unattended board (default pipeline)
  Reports     Yes       import JSON → SQLite + HTML
  Serve       Yes       http://localhost:8765
  Glassdoor   Maybe     Often hits "Humans only" — prefer host attach
  Indeed      No        Use host commands above

  Default pipeline (one Dice query + reports + serve):
    ./build/build.sh all dice
    # defaults: "DevOps Engineer" · Remote · max 25 · days 7

  Custom Dice query:
    ./build/build.sh dice "Python Developer" Remote 50
    ./build/build.sh all dice "Site Reliability Engineer" Remote 30

  Multiple queries in Docker (--queries, comma-separated):
    docker-compose -f build/docker-compose.yml run --rm scraper-dice \
      python src/main.py --auto --board dice \
      --queries "DevOps Engineer,SDET,Platform Engineer" \
      --location Remote --remote --days 7 --max 25

  Glassdoor in Docker (best-effort — may fail):
    ./build/build.sh glassdoor "Software Engineer" Remote 25
    # prefer host: bash maintance/run_glassdoor_attach.sh

  Reports only:
    ./build/build.sh reports

  Report server only:
    ./build/build.sh serve

  Docs: docs/Scraper_Docker_Setup.md
================================================================================
EOF
}

block_indeed_in_docker() {
    msg_indeed_use_host
    exit 1
}

msg_glassdoor_host_hint() {
    log_warn "Glassdoor in Docker often fails on 'Humans only' pages."
    log_info "Prefer host: bash maintance/run_glassdoor_attach.sh"
}

# ___ Build the Docker image:
cmd_build() {
    log_info "Building Docker image..."
    docker-compose -f "$COMPOSE_FILE" build
    log_success "Docker image built successfully"
}

# ___ Run automated scrape (Indeed — blocked in Docker, use host):
cmd_auto() {
    block_indeed_in_docker
}

# ___ Run Dice scrape (no cookies):
cmd_dice() {
    local query="${1:-DevOps Engineer}"
    local location="${2:-Remote}"
    local max="${3:-25}"
    log_info "Running Dice automated scrape: '$query' in '$location' (max: $max)"
    docker-compose -f "$COMPOSE_FILE" run --rm scraper-dice python src/main.py \
        --auto --board dice \
        --query "$query" --location "$location" --remote --days 7 --max "$max"
    log_success "Scrape completed. Check ./artifacts/json/ for results."
    log_info "View reports: ./build.sh serve  →  http://localhost:${REPORT_PORT:-8765}"
}

# ___ Run Glassdoor scrape (best-effort in Docker):
cmd_glassdoor() {
    msg_glassdoor_host_hint
    local query="${1:-Software Engineer}"
    local location="${2:-Remote}"
    local max="${3:-25}"
    log_info "Running Glassdoor automated scrape: '$query' in '$location' (max: $max)"
    docker-compose -f "$COMPOSE_FILE" run --rm scraper-glassdoor python src/main.py \
        --auto --board glassdoor \
        --query "$query" --location "$location" --remote --days 7 --max "$max"
    log_success "Scrape completed. Check ./artifacts/json/ for results."
    log_info "View reports: ./build.sh serve  →  http://localhost:${REPORT_PORT:-8765}"
}

# ___ Run interactive mode (Indeed/Glassdoor need host attach):
cmd_interactive() {
    block_indeed_in_docker
}

# ___ Run scheduled scrapes (Dice-only in Docker):
cmd_scheduled() {
    log_info "Running scheduled Dice scrape (Indeed/Glassdoor → use host attach)..."
    docker-compose -f "$COMPOSE_FILE" run --rm scraper-scheduled
    log_success "Scheduled scrape completed."
    log_info "Import + view: ./build/build.sh reports && ./build/build.sh serve"
}

# ___ Import JSON and rebuild HTML reports (same as host generate_job_reports.py):
cmd_reports() {
    log_info "Importing JSON into SQLite and rebuilding HTML..."
    docker-compose -f "$COMPOSE_FILE" run --rm --no-deps report-server \
        python3 modules/generate_job_reports.py --import-json
    log_success "Reports updated in ./artifacts/html/"
    log_info "Start server: ./build.sh serve  →  http://localhost:${REPORT_PORT:-8765}"
}

# ___ Start FastAPI report server (background, port mapped to host):
cmd_serve() {
    log_info "Starting report server on http://localhost:${REPORT_PORT:-8765} ..."
    docker-compose -f "$COMPOSE_FILE" up -d report-server
    log_success "Report server running. Open http://localhost:${REPORT_PORT:-8765}/"
    log_info "Stop with: docker-compose -f build/docker-compose.yml stop report-server"
}

# ___ Scrape + import/rebuild + serve (one command):
cmd_all() {
    local board="${1:-dice}"
    shift || true

    case "$board" in
        scheduled)
            cmd_scheduled
            ;;
        auto|indeed)
            block_indeed_in_docker
            ;;
        dice)
            cmd_dice "$@"
            ;;
        glassdoor)
            cmd_glassdoor "$@"
            ;;
        *)
            log_error "Unknown board '$board'. Use: dice, glassdoor, scheduled"
            log_info "Indeed: run on host — ./build/build.sh auto  (shows redirect)"
            exit 1
            ;;
    esac

    cmd_reports
    cmd_serve
}

# ___ Run with proxy (Indeed — blocked in Docker):
cmd_proxy() {
    block_indeed_in_docker
}

# ___ Open shell in container:
cmd_shell() {
    log_info "Opening shell in container..."
    docker-compose -f "$COMPOSE_FILE" run --rm scraper-auto /bin/bash
}

# ___ View logs:
cmd_logs() {
    log_info "Viewing container logs..."
    docker-compose -f "$COMPOSE_FILE" logs -f
}

# ___ Clean up:
cmd_clean() {
    log_warn "This will remove all job scraper containers and images."
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Removing containers..."
        docker-compose -f "$COMPOSE_FILE" down --rmi all --volumes --remove-orphans 2>/dev/null || true
        log_success "Cleanup completed"
    else
        log_info "Cleanup cancelled"
    fi
}

# ___ Show help:
cmd_help() {
    echo "Job Scraper - Docker Helper"
    echo ""
    echo "Usage: ./build/build.sh <command> [args]   (from repo root)"
    echo ""
    echo "Indeed is HOST-ONLY (Cloudflare). Run: ./build/build.sh auto  for full redirect."
    echo ""
    echo "Docker commands:"
    echo "  build                          Build the Docker image"
    echo "  dice [query] [location] [max]  Dice scrape (default: DevOps Engineer, Remote, 25)"
    echo "  glassdoor [query] [loc] [max]  Glassdoor scrape (best-effort; prefer host attach)"
    echo "  scheduled                      Dice-only scheduled scrape"
    echo "  reports                        Import JSON + rebuild HTML"
    echo "  serve                          Report server on http://localhost:8765"
    echo "  all [board] [query] [loc] [max]  Scrape + reports + serve (default board: dice)"
    echo "  shell / logs / clean / help"
    echo ""
    echo "Blocked in Docker (shows host redirect): auto, proxy, interactive"
    echo ""
    echo "Examples:"
    echo "  ./build/build.sh build"
    echo "  ./build/build.sh all dice"
    echo "  ./build/build.sh dice 'Python Developer' Remote 50"
    echo "  ./build/build.sh reports && ./build/build.sh serve"
    echo ""
    msg_docker_capabilities
}

# ___ Main:
ensure_env_file

_pre_cmd="${1:-help}"
if [[ "$_pre_cmd" == "auto" || "$_pre_cmd" == "proxy" || "$_pre_cmd" == "interactive" ]]; then
    block_indeed_in_docker
fi

check_docker

case "${1:-help}" in
    build)       cmd_build ;;
    auto)        shift; cmd_auto "$@" ;;
    dice)        shift; cmd_dice "$@" ;;
    glassdoor)   shift; cmd_glassdoor "$@" ;;
    interactive) cmd_interactive ;;
    scheduled)   cmd_scheduled ;;
    reports)     cmd_reports ;;
    serve)       cmd_serve ;;
    all)         shift; cmd_all "$@" ;;
    proxy)       cmd_proxy ;;
    shell)       cmd_shell ;;
    logs)        cmd_logs ;;
    clean)       cmd_clean ;;
    help|*)      cmd_help ;;
esac
