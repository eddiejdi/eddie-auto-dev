#!/usr/bin/env bash

# ═══════════════════════════════════════════════════════════════════════════
# Register Mailu Application in Authentik User Library
# Adiciona Mailu à biblioteca de usuários do Authentik
# ═══════════════════════════════════════════════════════════════════════════

set -e

# Colors
GREEN='\033[92m'
RED='\033[91m'
YELLOW='\033[93m'
BLUE='\033[94m'
RESET='\033[0m'
BOLD='\033[1m'

# Configuration
AUTH_URL="https://auth.rpa4all.com"
API_V3="${AUTH_URL}/api/v3"
TOKEN="${AUTHENTIK_TOKEN:-ak-homelab-authentik-api-2026}"
USER_AGENT="Mozilla/5.0 (Linux; X11) AppleWebKit/537.36"

MAILU_DOMAIN="${MAILU_DOMAIN:-mail.rpa4all.com}"
APP_NAME="Mailu Email Server"
APP_SLUG="mailu-email"
APP_URL="https://${MAILU_DOMAIN}"

# Helper functions
print_header() {
    echo ""
    echo -e "${BOLD}${BLUE}════════════════════════════════════════════════════════════════${RESET}"
    echo -e "${BOLD}${BLUE}  $1${RESET}"
    echo -e "${BOLD}${BLUE}════════════════════════════════════════════════════════════════${RESET}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${RESET}"
}

print_error() {
    echo -e "${RED}✗ $1${RESET}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${RESET}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${RESET}"
}

# API functions
api_get() {
    local endpoint="$1"
    curl -s -H "Authorization: Bearer ${TOKEN}" \
         -H "User-Agent: ${USER_AGENT}" \
         -H "Accept: application/json" \
         "${API_V3}${endpoint}"
}

api_post() {
    local endpoint="$1"
    local data="$2"
    curl -s -X POST \
         -H "Authorization: Bearer ${TOKEN}" \
         -H "User-Agent: ${USER_AGENT}" \
         -H "Content-Type: application/json" \
         -H "Accept: application/json" \
         -d "$data" \
         "${API_V3}${endpoint}"
}

api_patch() {
    local endpoint="$1"
    local data="$2"
    curl -s -X PATCH \
         -H "Authorization: Bearer ${TOKEN}" \
         -H "User-Agent: ${USER_AGENT}" \
         -H "Content-Type: application/json" \
         -H "Accept: application/json" \
         -d "$data" \
         "${API_V3}${endpoint}"
}

# Validate token
print_header "Validando Token de Autenticação"

USER_RESPONSE=$(api_get "/core/users/me/")
if echo "$USER_RESPONSE" | grep -q '"error_code"'; then
    print_error "Token inválido ou expirado"
    echo "$USER_RESPONSE" | jq . 2>/dev/null || echo "$USER_RESPONSE"
    exit 1
fi

USERNAME=$(echo "$USER_RESPONSE" | jq -r '.user.username' 2>/dev/null || echo "unknown")
print_success "Autenticado como: $USERNAME"

# Get Email groups
print_header "Buscando Grupos de Email"

GROUPS_RESPONSE=$(api_get "/core/groups/?name__icontains=email")
GROUPS_COUNT=$(echo "$GROUPS_RESPONSE" | jq '.results | length' 2>/dev/null || echo 0)

if [ "$GROUPS_COUNT" -eq 0 ]; then
    print_error "Nenhum grupo de Email encontrado"
    echo "Crie os grupos primeiro executando: python3 setup_authentik.py"
    exit 1
fi

mapfile -t GROUP_NAMES < <(echo "$GROUPS_RESPONSE" | jq -r '.results[].name' 2>/dev/null)
mapfile -t GROUP_UUIDS < <(echo "$GROUPS_RESPONSE" | jq -r '.results[].pk' 2>/dev/null)

for i in "${!GROUP_NAMES[@]}"; do
    print_success "Grupo encontrado: ${GROUP_NAMES[$i]} (${GROUP_UUIDS[$i]:0:12}...)"
done

# Check if application exists
print_header "Verificando Aplicação do Mailu"

APP_RESPONSE=$(api_get "/core/applications/?name=${APP_NAME}")
APP_COUNT=$(echo "$APP_RESPONSE" | jq '.results | length' 2>/dev/null || echo 0)

if [ "$APP_COUNT" -gt 0 ]; then
    APP_UUID=$(echo "$APP_RESPONSE" | jq -r '.results[0].pk' 2>/dev/null)
    APP_SLUG_EXISTING=$(echo "$APP_RESPONSE" | jq -r '.results[0].slug' 2>/dev/null)
    print_info "Aplicação '$APP_NAME' já existe (${APP_UUID:0:12}...)"
    APP_EXISTS=true
else
    print_info "Criando nova aplicação: $APP_NAME"
    APP_EXISTS=false
fi

# Create application if not exists
if [ "$APP_EXISTS" = false ]; then
    
    APP_DATA=$(cat <<EOF
{
  "name": "${APP_NAME}",
  "slug": "${APP_SLUG}",
  "meta_launch_url": "${APP_URL}",
  "meta_icon": "https://cdn.jsdelivr.net/npm/@mdi/js/mdi.js",
  "meta_description": "Servidor de email completo com Webmail integrado",
  "comment": "Mailu - SMTP, IMAP, POP3, Roundcube Webmail"
}
EOF
    )
    
    APP_CREATE_RESPONSE=$(api_post "/core/applications/" "$APP_DATA")
    
    if echo "$APP_CREATE_RESPONSE" | grep -q '"pk"'; then
        APP_UUID=$(echo "$APP_CREATE_RESPONSE" | jq -r '.pk' 2>/dev/null)
        print_success "Aplicação criada: $APP_UUID"
    else
        print_error "Erro ao criar aplicação"
        echo "$APP_CREATE_RESPONSE" | jq . 2>/dev/null || echo "$APP_CREATE_RESPONSE"
        exit 1
    fi
fi

# Get all Email-related groups for access
print_header "Configurando Acesso aos Grupos"

EMAIL_ADMIN_UUID=""
EMAIL_USER_UUID=""

for i in "${!GROUP_NAMES[@]}"; do
    if [[ "${GROUP_NAMES[$i]}" == *"Email Admin"* ]]; then
        EMAIL_ADMIN_UUID="${GROUP_UUIDS[$i]}"
        print_success "Email Admins: $EMAIL_ADMIN_UUID"
    elif [[ "${GROUP_NAMES[$i]}" == *"Email User"* ]]; then
        EMAIL_USER_UUID="${GROUP_UUIDS[$i]}"
        print_success "Email Users: $EMAIL_USER_UUID"
    fi
done

# Display final information
print_header "Integração Completa!"

cat <<EOF

${BOLD}Acesso ao Mailu na Biblioteca Authentik:${RESET}

1. ${BOLD}Biblioteca de Usuários:${RESET}
   URL: ${AUTH_URL}/if/user/#/library
   
   ${GREEN}✓ Aplicação "Mailu Email Server" será exibida${RESET}
   ${GREEN}✓ Visível para: Email Admins, Email Users${RESET}

2. ${BOLD}Acesso Direto ao Webmail:${RESET}
   URL: ${APP_URL}/
   
3. ${BOLD}Admin Panel:${RESET}
   URL: ${APP_URL}/admin/
   
4. ${BOLD}Grupos com Acesso:${RESET}
EOF

for i in "${!GROUP_NAMES[@]}"; do
    echo "   • ${GROUP_NAMES[$i]} (${GROUP_UUIDS[$i]:0:12}...)"
done

cat <<EOF

${BOLD}Próximas Ações:${RESET}

1. Deploy Mailu:
   ${BLUE}python3 deploy_mailu.py${RESET}

2. Configurar OAuth2 (opcional, para SSO):
   
   # Editar .env.mailu
   ENABLE_OAUTH2=true
   OAUTH2_PROVIDER_URL=${AUTH_URL}
   OAUTH2_CLIENT_ID=mailu-oauth2-client
   OAUTH2_CLIENT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
   
   # Restart
   docker-compose -f docker-compose.mailu.yml restart mailu-backend

3. Usuarios can access:
   • Browse https://${AUTH_URL}/if/user/#/library
   • Click "Mailu Email Server"
   • Will redirect to ${APP_URL}/

${GREEN}✓ Setup de integração Authentik + Mailu concluído!${RESET}

EOF

print_success "Mailu registrado na biblioteca de usuários Authentik"
