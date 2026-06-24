#!/usr/bin/env bash
# Run merge CI tests locally (same as .github/workflows/ci.yml python job).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV="$ROOT/.venv"
if [[ ! -x "$VENV/bin/python" ]]; then
  echo "[*] Creating .venv (keeps test deps isolated from system Python)..."
  python3 -m venv "$VENV"
fi
PYTHON="$VENV/bin/python"

echo "[*] Installing deps (if needed)..."
"$PYTHON" -m pip install -q --upgrade pip
"$PYTHON" -m pip install -q -r requirements.txt -r requirements-dev.txt

echo "[*] Running pytest..."
# exec "$PYTHON" -m pytest tests/ -q \
#   --cov=modules.job_store \
#   --cov=modules.job_report_api \
#   --cov-report=term-missing \
#   --cov-fail-under=60 \

exec "$PYTHON" -m pytest -v -r charts tests/ --cov=modules.job_store --cov=modules.job_report_api --cov-report=term-missing --cov-fail-under=60 "$@"
