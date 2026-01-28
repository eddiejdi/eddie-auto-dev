#!/usr/bin/env bash
# Serve a pasta tools (inclui monitor_bus.html) na porta 3002
# Uso: ./tools/serve_monitor.sh [port]
PORT=${1:-3002}
DIR="$(dirname "$0")"
echo "Serving $DIR on http://0.0.0.0:$PORT (ctrl-c to stop)"
cd "$DIR" || exit 1
python3 -m http.server "$PORT"
