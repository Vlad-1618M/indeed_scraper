#!/bin/bash
# =============================================================================
#       *** Job Scraper - Docker Entrypoint ***
# =============================================================================
set -e

echo "[*] Starting Xvfb virtual display..."

# ___ Start Xvfb in background
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# ___ Export DISPLAY
export DISPLAY=:99

# ___ Wait for Xvfb to be ready
sleep 2

# ___ Verify Xvfb started
if xdpyinfo -display :99 > /dev/null 2>&1; then
    echo "[+] Virtual display ready on :99"
else
    echo "[!] ERROR: Xvfb failed to start"
    kill $XVFB_PID 2>/dev/null || true
    exit 1
fi

# ___ cleanup function
cleanup() {
    echo "[*] Shutting down Xvfb..."
    kill $XVFB_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ___ run scraper
exec "$@"
