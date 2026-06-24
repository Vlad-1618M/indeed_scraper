#!/usr/bin/env bash
# Start FastAPI report server (Jobs/Search API + interactive HTML).
# Usage: ./scripts/start_report_server.sh [--port 8765]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${REPORT_PORT:-8765}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="${2:?missing port after --port}"
      shift 2
      ;;
    --port=*)
      PORT="${1#*=}"
      shift
      ;;
    -h|--help)
      echo "Usage: $(basename "$0") [--port 8765]"
      echo "  Serves http://127.0.0.1:\${PORT}/ (default 8765)"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# Avoid oh-my-zsh update prompt when launched from Terminal attach flow
export DISABLE_UPDATE_PROMPT=true
export OMZ_DISABLE_AUTOUPDATE=true

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

if ! "$PYTHON" -c "import uvicorn" 2>/dev/null; then
  echo "[!] uvicorn not found — run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

echo "[*] Report server → http://127.0.0.1:${PORT}/"
echo "[*] Press Ctrl+C to stop"
exec "$PYTHON" "$ROOT/modules/generate_job_reports.py" --serve --port "$PORT"
