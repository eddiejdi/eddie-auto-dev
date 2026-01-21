#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH=$(pwd)
VE=$(pwd)/.venv
PY=python3
if [ -x "$VE/bin/python" ]; then
  PY="$VE/bin/python"
fi

echo "Starting Diretor service with $PY"
exec "$PY" dev_agent/run_diretor_service.py
