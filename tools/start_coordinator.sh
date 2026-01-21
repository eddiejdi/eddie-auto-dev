#!/usr/bin/env bash
set -euo pipefail

# Start Coordinator Agent service using the workspace virtualenv if available.
VE=$(pwd)/.venv
PY=python3
export PYTHONPATH=$(pwd)
if [ -x "$VE/bin/python" ]; then
  PY="$VE/bin/python"
fi

echo "Starting CoordinatorAgent service with $PY"
exec "$PY" dev_agent/run_coordinator_service.py
