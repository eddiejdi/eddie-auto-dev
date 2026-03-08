#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

# Install only what this script needs, quietly.
if ! "$VENV_DIR/bin/python" -c "import httpx" >/dev/null 2>&1; then
  "$VENV_DIR/bin/pip" -q install httpx
fi

"$VENV_DIR/bin/python" "$SCRIPT_DIR/openwebui_director_function.py"
