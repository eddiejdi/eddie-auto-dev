#!/usr/bin/env bash

set -euo pipefail

USAGE="Usage: $0 [--env-file FILE] [--db-container NAME] [--sso-variable NAME] [--email-field NAME] [--name-field NAME] [--logout-url URL] [--url-base URL]

Configures GLPI to trust the upstream auth_request identity provided by Authentik."

ENV_FILE="/workspace/eddie-auto-dev/deploy/cmdb/.env"
DB_CONTAINER=""
SSO_VARIABLE="HTTP_X_AUTHENTIK_USERNAME"
EMAIL_FIELD="HTTP_X_AUTHENTIK_EMAIL"
NAME_FIELD="HTTP_X_AUTHENTIK_NAME"
LOGOUT_URL="https://auth.rpa4all.com/outpost.goauthentik.io/sign_out"
URL_BASE="https://auth.rpa4all.com/cmdb/glpi"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --db-container) DB_CONTAINER="$2"; shift 2 ;;
    --sso-variable) SSO_VARIABLE="$2"; shift 2 ;;
    --email-field) EMAIL_FIELD="$2"; shift 2 ;;
    --name-field) NAME_FIELD="$2"; shift 2 ;;
    --logout-url) LOGOUT_URL="$2"; shift 2 ;;
    --url-base) URL_BASE="$2"; shift 2 ;;
    -h|--help) printf '%s\n' "$USAGE"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; printf '%s\n' "$USAGE" >&2; exit 2 ;;
  esac
done

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 2
fi

read_env_value() {
  local key="$1"
  local value
  value="$(grep -E "^${key}=" "$ENV_FILE" | head -n 1 | cut -d= -f2- || true)"
  if [[ -z "$value" ]]; then
    echo "Missing ${key} in ${ENV_FILE}" >&2
    exit 2
  fi
  printf '%s' "$value"
}

sql_escape() {
  printf "%s" "$1" | sed "s/'/''/g"
}

if [[ -z "$DB_CONTAINER" ]]; then
  DB_CONTAINER="$(docker ps --filter label=com.docker.compose.service=glpi-db --format '{{.Names}}' | head -n 1)"
fi

if [[ -z "$DB_CONTAINER" ]]; then
  echo "GLPI database container not found." >&2
  exit 1
fi

GLPI_DB_NAME="$(read_env_value GLPI_DB_NAME)"
GLPI_DB_USER="$(read_env_value GLPI_DB_USER)"
GLPI_DB_PASSWORD="$(read_env_value GLPI_DB_PASSWORD)"

run_sql() {
  docker exec "$DB_CONTAINER" mariadb \
    -u"$GLPI_DB_USER" \
    -p"$GLPI_DB_PASSWORD" \
    "$GLPI_DB_NAME" \
    -N -s \
    -e "$1"
}

set_config() {
  local name="$1"
  local value="$2"
  local escaped
  escaped="$(sql_escape "$value")"
  run_sql "UPDATE glpi_configs SET value='${escaped}' WHERE context='core' AND name='${name}'; INSERT INTO glpi_configs (context, name, value) SELECT 'core', '${name}', '${escaped}' FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM glpi_configs WHERE context='core' AND name='${name}');" >/dev/null
}

SSO_ID="$(run_sql "SELECT id FROM glpi_ssovariables WHERE name='$(sql_escape "$SSO_VARIABLE")' LIMIT 1;")"
if [[ -z "$SSO_ID" ]]; then
  run_sql "INSERT INTO glpi_ssovariables (name) VALUES ('$(sql_escape "$SSO_VARIABLE")');" >/dev/null
  SSO_ID="$(run_sql "SELECT id FROM glpi_ssovariables WHERE name='$(sql_escape "$SSO_VARIABLE")' LIMIT 1;")"
fi

set_config "ssovariables_id" "$SSO_ID"
set_config "email1_ssofield" "$EMAIL_FIELD"
set_config "realname_ssofield" "$NAME_FIELD"
set_config "is_users_auto_add" "1"
set_config "noAUTO" "0"
set_config "ssologout_url" "$LOGOUT_URL"
set_config "url_base" "$URL_BASE"

printf 'configured glpi sso: variable=%s id=%s url_base=%s\n' "$SSO_VARIABLE" "$SSO_ID" "$URL_BASE"
