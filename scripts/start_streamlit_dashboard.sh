#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"
# Activate virtualenv if present
if [ -f "$DIR/.venv/bin/activate" ]; then
  # shellcheck source=/dev/null
  source "$DIR/.venv/bin/activate"
fi
# Load .env if present
if [ -f "$DIR/.env" ]; then
  set -o allexport
  # shellcheck source=/dev/null
  source "$DIR/.env"
  set +o allexport
fi
export PYTHONUNBUFFERED=1
exec streamlit run specialized_agents/conversation_monitor.py --server.address 0.0.0.0 --server.port 8501
