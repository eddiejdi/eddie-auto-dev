#!/usr/bin/env bash
set -euo pipefail

# Start Coordinator Agent service using the workspace virtualenv if available.
VE=$(pwd)/.venv
PY=python3
export PYTHONPATH=$(pwd)
if [ -x "$VE/bin/python" ]; then
  PY="$VE/bin/python"
fi

VER="${COORDINATOR_VERSION:-v1}"
echo "Starting CoordinatorAgent service with $PY (version=$VER)"

if [ "$VER" = "v2" ]; then
  exec "$PY" -m specialized_agents.coordinator_langgraph
else
  exec "$PY" dev_agent/run_coordinator_service.py
fi
