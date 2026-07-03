#!/usr/bin/env bash
set -euo pipefail

NEXTCLOUD_CONTAINER="${NEXTCLOUD_CONTAINER:-nextcloud-app}"
NEXTCLOUD_EXEC_USER="${NEXTCLOUD_EXEC_USER:-www-data}"
NEXTCLOUD_OCC="${NEXTCLOUD_OCC:-php occ}"
NEXTCLOUD_PROVIDER_URL="${NEXTCLOUD_PROVIDER_URL:-https://auth.rpa4all.com/application/o/nextcloud/}"
NEXTCLOUD_CLIENT_ID="${AUTHENTIK_NEXTCLOUD_CLIENT_ID:-authentik-nextcloud}"
NEXTCLOUD_CLIENT_SECRET="${AUTHENTIK_NEXTCLOUD_CLIENT_SECRET:-nextcloud-sso-secret-2026}"

occ() {
  docker exec -u "${NEXTCLOUD_EXEC_USER}" "${NEXTCLOUD_CONTAINER}" ${NEXTCLOUD_OCC} "$@"
}

echo "[*] Habilitando apps necessários do Nextcloud..."
occ app:enable oidc_login
occ app:enable groupfolders

echo "[*] Aplicando configuração OIDC do Nextcloud..."
occ config:system:set oidc_login_provider_url --value="${NEXTCLOUD_PROVIDER_URL}"
occ config:system:set oidc_login_client_id --value="${NEXTCLOUD_CLIENT_ID}"
occ config:system:set oidc_login_client_secret --value="${NEXTCLOUD_CLIENT_SECRET}"
occ config:system:set oidc_login_scope --value="openid profile email groups"
occ config:system:set oidc_login_button_text --value="Log in with Authentik"
occ config:system:set oidc_login_hide_password_form --value=false --type=boolean
occ config:system:set oidc_login_auto_redirect --value=false --type=boolean
occ config:system:set oidc_login_use_access_token_payload --value=false --type=boolean
occ config:system:set oidc_login_default_group --value="users"
occ config:system:set oidc_create_groups --value=true --type=boolean
occ config:system:set oidc_login_logout_url --value="${NEXTCLOUD_PROVIDER_URL}end-session/"

echo "[*] Bootstrap OIDC do Nextcloud concluído para o container ${NEXTCLOUD_CONTAINER}."
