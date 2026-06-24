#!/bin/bash
# =============================================================================
#       *** Job Scraper - Docker Build & Run Helper ***
# =============================================================================
#
# Boards: Indeed (cookies required), Dice, Glassdoor (no cookies)
#
# Usage:
#   ./build.sh build                    # Build the Docker image
#   ./build.sh auto                     # Indeed automated (needs indeed_cookies.pkl)
#   ./build.sh auto "Python Developer" "New York" 50  # Custom Indeed search
#   ./build.sh dice                     # Dice automated (no cookies)
#   ./build.sh glassdoor                # Glassdoor automated (no cookies)
#   ./build.sh interactive              # Interactive mode (board selection)
#   ./build.sh scheduled                # Multi-board scheduled scrape
#   ./build.sh reports                  # Import JSON + rebuild HTML in container
#   ./build.sh serve                    # Start report server (http://localhost:8765)
#   ./build.sh all                      # scheduled + reports + serve (full pipeline)
#   ./build.sh all dice                 # dice scrape + reports + serve
#   ./build.sh shell                    # Open shell in container
#   ./build.sh logs                     # View container logs
#   ./build.sh clean                    # Remove containers and images
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

# ___ Change to project root:
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

# ___ Build the Docker image:
cmd_build() {
    log_info "Building Docker image..."
    docker-compose -f "$COMPOSE_FILE" build
    log_success "Docker image built successfully"
}

# ___ Run automated scrape (Indeed - requires cookies):
cmd_auto() {
    local query="${1:-DevOps Engineer}"
    local location="${2:-Remote}"
    local max="${3:-25}"
    
    if [ ! -f "$PROJECT_ROOT/indeed_cookies.pkl" ]; then
        log_warn "indeed_cookies.pkl not found. Indeed requires cookies."
        log_info "Run locally: python modules/get_cookies.py --auto"
        log_info "Or use: ./build.sh dice  (Dice, no cookies)"
        exit 1
    fi
    log_info "Running Indeed automated scrape: '$query' in '$location' (max: $max)"
    docker-compose -f "$COMPOSE_FILE" run --rm scraper-auto python src/main.py \
        --auto --board indeed \
        --query "$query" --location "$location" --remote --days 7 --max "$max"
    log_success "Scrape completed. Check ./artifacts/json/ for results."
    log_info "View reports: ./build.sh serve  →  http://localhost:${REPORT_PORT:-8765}"
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

# ___ Run Glassdoor scrape (no cookies):
cmd_glassdoor() {
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

# ___ Run interactive mode:
cmd_interactive() {
    log_info "Starting interactive mode..."
    docker-compose -f "$COMPOSE_FILE" run --rm scraper-interactive
}

# ___ Run scheduled scrapes:
cmd_scheduled() {
    log_info "Running scheduled multi-search..."
    docker-compose -f "$COMPOSE_FILE" run --rm scraper-scheduled
    log_success "Scheduled scrapes completed."
    log_info "Import + view: ./build.sh reports && ./build.sh serve"
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
    local board="${1:-scheduled}"
    shift || true

    case "$board" in
        scheduled)
            cmd_scheduled
            ;;
        auto|indeed)
            cmd_auto "$@"
            ;;
        dice)
            cmd_dice "$@"
            ;;
        glassdoor)
            cmd_glassdoor "$@"
            ;;
        *)
            log_error "Unknown board '$board'. Use: scheduled, auto, dice, glassdoor"
            exit 1
            ;;
    esac

    cmd_reports
    cmd_serve
}

# ___ Run with proxy:
cmd_proxy() {
    if [ -z "$PROXY_SERVER" ]; then
        log_warn "PROXY_SERVER not set. Create .env file or export variables."
        log_info "Example: export PROXY_SERVER=http://proxy.example.com:8080"
        exit 1
    fi
    
    log_info "Running with proxy: $PROXY_SERVER"
    docker-compose -f "$COMPOSE_FILE" run --rm scraper-proxy
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
    echo "Job Scraper - Docker Helper (Indeed, Dice, Glassdoor)"
    echo ""
    echo "Usage: ./build.sh <command> [args]"
    echo ""
    echo "Commands:"
    echo "  build                          Build the Docker image"
    echo "  auto [query] [location] [max]  Indeed automated (needs cookies)"
    echo "  dice [query] [location] [max]  Dice automated (no cookies)"
    echo "  glassdoor [query] [loc] [max]  Glassdoor automated (no cookies)"
    echo "  interactive                    Interactive mode (board selection)"
    echo "  scheduled                      Multi-board scheduled scrape"
    echo "  reports                        Import JSON + rebuild HTML (container)"
    echo "  serve                          Start report server on localhost:8765"
    echo "  all [board] [query] [loc] [max] Scrape + reports + serve (default: scheduled)"
    echo "  proxy                          Indeed with proxy (requires .env)"
    echo "  shell                          Open shell in container"
    echo "  logs                           View container logs"
    echo "  clean                          Remove containers and images"
    echo "  help                           Show this help"
    echo ""
    echo "Examples:"
    echo "  ./build.sh build"
    echo "  ./build.sh auto                              # Indeed (needs indeed_cookies.pkl)"
    echo "  ./build.sh dice 'Python Developer' Remote 50 # Dice, no cookies"
    echo "  ./build.sh glassdoor 'DevOps' Remote 25      # Glassdoor"
    echo "  ./build.sh all                                 # scheduled + reports + serve"
    echo "  ./build.sh all dice 'Python Developer' Remote 50"
    echo "  ./build.sh interactive"
    echo ""
    echo "Indeed cookies: Run 'python modules/get_cookies.py --auto' locally first."
    echo "Proxy: Set PROXY_SERVER, PROXY_USER, PROXY_PASS in .env"
}

# ___ Main:
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
