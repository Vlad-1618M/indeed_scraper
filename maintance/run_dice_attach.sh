#!/usr/bin/env bash
# Dice attach workflow (port 9224)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SCRAPER_BOARD=dice
# shellcheck source=lib/attach_common.sh
source "$SCRIPT_DIR/lib/attach_common.sh"
attach_init
attach_parse_args "$0" "$@"
attach_main "$0"
