#!/usr/bin/env bash
# Resolve o token da API do Authentik sem hardcodar segredo.
# Ordem: env AUTHENTIK_TOKEN → override.conf do secrets_agent (homelab) → secrets_agent API.
#
# Uso:
#   source "$(dirname "${BASH_SOURCE[0]}")/authentik_token.sh"
#   TOKEN="$(authentik_token)"

authentik_token() {
    if [ -n "${AUTHENTIK_TOKEN:-}" ]; then
        printf '%s' "$AUTHENTIK_TOKEN"
        return 0
    fi

    local override="/etc/systemd/system/secrets_agent.service.d/override.conf"
    if [ -f "$override" ]; then
        sed -n 's/.*AUTHENTIK_TOKEN="*\([^"]*\)"*.*/\1/p' "$override" | head -1
        return 0
    fi

    curl -sf "http://localhost:8088/secrets/authentik/api_token" 2>/dev/null |
        python3 -c 'import sys, json
try:
    d = json.load(sys.stdin).get("data") or {}
    v = d.get("value") or ""
    print(v, end="")
except Exception:
    pass' 2>/dev/null
    return 0
}