#!/usr/bin/env bash
# Glassdoor attach workflow (port 9223) — pass "Humans only" in real Chrome
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SCRAPER_BOARD=glassdoor
# shellcheck source=lib/attach_common.sh
source "$SCRIPT_DIR/lib/attach_common.sh"
attach_init
attach_parse_args "$0" "$@"
attach_main "$0"
