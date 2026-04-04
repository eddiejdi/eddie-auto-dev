#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# Registra Wallpapers Manager como aplicacao na biblioteca do Authentik
# Adiciona atalho em auth.rpa4all.com → Wallpapers Manager
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

GREEN='\033[92m'
RED='\033[91m'
BLUE='\033[94m'
BOLD='\033[1m'
RESET='\033[0m'

AUTH_URL="https://auth.rpa4all.com"
API_V3="${AUTH_URL}/api/v3"
TOKEN="${AUTHENTIK_TOKEN:-ak-homelab-authentik-api-2026}"

APP_NAME="Wallpapers Manager"
APP_SLUG="wallpapers-manager"
APP_URL="${AUTH_URL}/wallpapers/"
APP_ICON="fa://fa-paint-brush"
APP_DESC="Catálogo de wallpapers corporativos, calendário de feriados e geração de temas via Ollama"

print_ok()   { echo -e "${GREEN}✓ $1${RESET}"; }
print_err()  { echo -e "${RED}✗ $1${RESET}"; }
print_info() { echo -e "${BLUE}ℹ $1${RESET}"; }

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

echo -e "\n${BOLD}${BLUE}══ Registrando ${APP_NAME} no Authentik ══${RESET}\n"

# 1. Valida token
ME=$(api_get "/core/users/me/" 2>/dev/null) || { print_err "Token inválido"; exit 1; }
USERNAME=$(echo "$ME" | python3 -c "import sys,json;print(json.load(sys.stdin)['user']['username'])" 2>/dev/null || echo "?")
print_ok "Autenticado como: $USERNAME"

# 2. Verifica se app já existe
EXISTING=$(api_get "/core/applications/?slug=${APP_SLUG}" 2>/dev/null) || EXISTING='{"results":[]}'
COUNT=$(echo "$EXISTING" | python3 -c "import sys,json;print(len(json.load(sys.stdin).get('results',[])))" 2>/dev/null || echo 0)

if [ "$COUNT" -gt 0 ]; then
    print_info "Aplicação '${APP_NAME}' já existe — atualizando..."
    SLUG_PK=$(echo "$EXISTING" | python3 -c "import sys,json;print(json.load(sys.stdin)['results'][0]['slug'])" 2>/dev/null)

    RESULT=$(api_patch "/core/applications/${SLUG_PK}/" "$(cat <<JSON
{
  "name": "${APP_NAME}",
  "meta_launch_url": "${APP_URL}",
  "meta_icon": "${APP_ICON}",
  "meta_description": "${APP_DESC}",
  "open_in_new_tab": true
}
JSON
    )" 2>&1)

    if echo "$RESULT" | grep -q '"slug"'; then
        print_ok "Aplicação atualizada"
    else
        print_err "Erro ao atualizar: $RESULT"
        exit 1
    fi
else
    print_info "Criando aplicação: ${APP_NAME}"

    RESULT=$(api_post "/core/applications/" "$(cat <<JSON
{
  "name": "${APP_NAME}",
  "slug": "${APP_SLUG}",
  "meta_launch_url": "${APP_URL}",
  "meta_icon": "${APP_ICON}",
  "meta_description": "${APP_DESC}",
  "open_in_new_tab": true,
  "policy_engine_mode": "any"
}
JSON
    )" 2>&1)

    if echo "$RESULT" | grep -q '"pk"'; then
        UUID=$(echo "$RESULT" | python3 -c "import sys,json;print(json.load(sys.stdin)['pk'])" 2>/dev/null)
        print_ok "Aplicação criada: ${UUID}"
    else
        print_err "Erro ao criar: $RESULT"
        exit 1
    fi
fi

echo ""
print_ok "Atalho disponível em: ${AUTH_URL}/if/user/#/library"
print_ok "Launch URL: ${APP_URL}"
echo ""
