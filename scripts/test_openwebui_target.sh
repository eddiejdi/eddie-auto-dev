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
    # Return key (may be empty) — caller will handle unauthenticated fallback
    if not k:
      # print nothing and exit 0 so caller sees empty KEY
      print("")
    else:
      print(k)
  except Exception:
    # If loader fails altogether, return empty to allow non-auth tests
    print("")
PY
}

KEY="$(get_key 2>/tmp/_get_key.err || true)"
# If runner has a local homelab token file, prefer it when key not found in vault
if [ -z "$KEY" ] && [ -f "$HOME/.openwebui_token" ]; then
  KEY="$(cat "$HOME/.openwebui_token" 2>/dev/null || true)"
fi
if [ -z "$KEY" ]; then
  echo "WARNING: OpenWebUI API key not available — proceeding with unauthenticated checks." >&2
fi

echo "Testing OpenWebUI host: $HOST"

echo "-> /api/status (no auth)"
status=$(curl -sS -o /tmp/ow_status.json -w "%{http_code}" "$HOST/api/status")
echo "HTTP $status"

echo "-> /api/v1/models (auth)"
status=$(curl -sS -o /tmp/ow_models.json -H "X-API-Key: $KEY" -H "Authorization: Bearer $KEY" -w "%{http_code}" "$HOST/api/v1/models")
echo "HTTP $status"

echo "-> /api/chat/completions (auth) - quick test"
PAYLOAD='{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Teste breve"}]}'
status=$(curl -sS -X POST -H "Content-Type: application/json" -H "X-API-Key: $KEY" -H "Authorization: Bearer $KEY" -d "$PAYLOAD" -o /tmp/ow_post.json -w "%{http_code}" "$HOST/api/chat/completions")
echo "HTTP $status"

echo "Saved responses: /tmp/ow_status.json /tmp/ow_models.json /tmp/ow_post.json"

echo "Done."
