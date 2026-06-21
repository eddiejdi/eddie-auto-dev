#!/usr/bin/env bash
# Registra o portal do CMDB na biblioteca do Authentik.

set -euo pipefail

AUTH_URL="https://auth.rpa4all.com"
API_V3="${AUTHENTIK_API_BASE:-http://127.0.0.1:9000/api/v3}"
TOKEN="${AUTHENTIK_TOKEN:-ak-homelab-authentik-api-2026}"

APP_NAME="CMDB Portal"
APP_SLUG="cmdb-portal"
APP_URL="${AUTH_URL}/cmdb/"
APP_ICON="fa://fa-network-wired"
APP_DESC="Portal do inventario corporativo com NetBox e GLPI protegidos pelo Authentik"

api_get() {
    curl -sf -H "Authorization: Bearer ${TOKEN}" \
         -H "Accept: application/json" \
         "${API_V3}${1}"
}

api_post() {
    curl -sf -X POST \
         -H "Authorization: Bearer ${TOKEN}" \
         -H "Content-Type: application/json" \
         -H "Accept: application/json" \
         -d "$2" "${API_V3}${1}"
}

api_patch() {
    curl -sf -X PATCH \
         -H "Authorization: Bearer ${TOKEN}" \
         -H "Content-Type: application/json" \
         -H "Accept: application/json" \
         -d "$2" "${API_V3}${1}"
}

api_get "/core/users/me/" >/dev/null

PAYLOAD="$(cat <<JSON
{
  "name": "${APP_NAME}",
  "slug": "${APP_SLUG}",
  "meta_launch_url": "${APP_URL}",
  "meta_icon": "${APP_ICON}",
  "meta_description": "${APP_DESC}",
  "open_in_new_tab": false,
  "policy_engine_mode": "any"
}
JSON
)"

if api_get "/core/applications/${APP_SLUG}/" >/dev/null 2>&1; then
    api_patch "/core/applications/${APP_SLUG}/" "${PAYLOAD}" >/dev/null
    echo "updated:${APP_SLUG}:${APP_URL}"
else
    api_post "/core/applications/" "${PAYLOAD}" >/dev/null
    echo "created:${APP_SLUG}:${APP_URL}"
fi
