#!/bin/bash
# =============================================================================
#       *** Indeed Scraper - Docker Build & Run Helper ***
# =============================================================================
#
# Usage:
#   ./build.sh build              # Build the Docker image
#   ./build.sh auto               # Run automated scrape (default search)
#   ./build.sh auto "Python Developer" "New York"  # Custom search
#   ./build.sh interactive        # Run interactive mode
#   ./build.sh scheduled          # Run scheduled multi-search
#   ./build.sh shell              # Open shell in container
#   ./build.sh logs               # View container logs
#   ./build.sh clean              # Remove containers and images
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

# ___ Run automated scrape:
cmd_auto() {
    local query="${1:-DevOps Engineer}"
    local location="${2:-Remote}"
    local max="${3:-25}"
    
    log_info "Running automated scrape: '$query' in '$location' (max: $max)"
    docker-compose -f "$COMPOSE_FILE" run --rm scraper-auto python src/main.py \
        --auto \
        --scraper seleniumbase \
        --query "$query" \
        --location "$location" \
        --remote \
        --days 7 \
        --max "$max"
    log_success "Scrape completed. Check ./artifacts/json/ for results."
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
    log_warn "This will remove all Indeed scraper containers and images."
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
    echo "Indeed Scraper - Docker Helper"
    echo ""
    echo "Usage: ./build.sh <command> [args]"
    echo ""
    echo "Commands:"
    echo "  build                          Build the Docker image"
    echo "  auto [query] [location] [max]  Run automated scrape"
    echo "  interactive                    Run interactive mode"
    echo "  scheduled                      Run scheduled multi-search"
    echo "  proxy                          Run with proxy (requires .env)"
    echo "  shell                          Open shell in container"
    echo "  logs                           View container logs"
    echo "  clean                          Remove containers and images"
    echo "  help                           Show this help"
    echo ""
    echo "Examples:"
    echo "  ./build.sh build"
    echo "  ./build.sh auto"
    echo "  ./build.sh auto 'Python Developer' 'San Francisco' 50"
    echo "  ./build.sh interactive"
    echo ""
    echo "Environment Variables (for proxy):"
    echo "  PROXY_SERVER  - Proxy server URL (e.g., http://proxy:8080)"
    echo "  PROXY_USER    - Proxy username"
    echo "  PROXY_PASS    - Proxy password"
}

# ___ Main:
check_docker

case "${1:-help}" in
    build)       cmd_build ;;
    auto)        shift; cmd_auto "$@" ;;
    interactive) cmd_interactive ;;
    scheduled)   cmd_scheduled ;;
    proxy)       cmd_proxy ;;
    shell)       cmd_shell ;;
    logs)        cmd_logs ;;
    clean)       cmd_clean ;;
    help|*)      cmd_help ;;
esac
