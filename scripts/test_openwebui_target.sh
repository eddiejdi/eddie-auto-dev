#!/usr/bin/env bash
set -euo pipefail

# Test OpenWebUI endpoints on a target host.
# Usage: ./scripts/test_openwebui_target.sh [HOST]
# Default HOST: http://192.168.15.2:3000

HOST=${1:-http://192.168.15.2:3000}

get_key() {
  # REQUIRED: obtain key only from the repository cofre via the python secrets loader
  python3 - <<'PY'
from importlib import import_module
try:
    m = import_module('tools.secrets_loader')
    k = m.get_openwebui_api_key()
    if not k:
        raise SystemExit(2)
    print(k)
except Exception:
    # ensure we exit non-zero so caller knows the cofre is required
    raise
PY
}

KEY=""
if ! KEY=$(get_key 2>/tmp/_get_key.err); then
  echo "ERROR: failed to read OpenWebUI API key from cofre (usage is mandatory)." >&2
  echo "--- cofre loader error ---" >&2
  sed -n '1,200p' /tmp/_get_key.err >&2 || true
  exit 2
fi

echo "Testing OpenWebUI host: $HOST"

echo "-> /api/status (no auth)"
curl -sS -o /tmp/ow_status.json -w "%{http_code}" "$HOST/api/status" | { read code; echo "HTTP $code"; }

echo "-> /api/v1/models (auth X-API-Key)"
curl -sS -o /tmp/ow_models.json -H "X-API-Key: $KEY" -w "%{http_code}" "$HOST/api/v1/models" | { read code; echo "HTTP $code"; }

echo "-> /api/chat/completions (auth) - quick test"
PAYLOAD='{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Teste breve"}]}'
curl -sS -X POST -H "Content-Type: application/json" -H "X-API-Key: $KEY" -d "$PAYLOAD" -o /tmp/ow_post.json -w "%{http_code}" "$HOST/api/chat/completions" | { read code; echo "HTTP $code"; }

echo "Saved responses: /tmp/ow_status.json /tmp/ow_models.json /tmp/ow_post.json"

echo "Done."
