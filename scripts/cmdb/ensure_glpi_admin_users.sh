#!/usr/bin/env bash

set -euo pipefail

USAGE="Usage: $0 [--env-file FILE] [--container NAME] [--db-container NAME] [--users CSV]

Ensures the selected GLPI users exist and hold the Super-Admin profile on the root entity."

ENV_FILE="/workspace/eddie-auto-dev/deploy/cmdb/.env"
CONTAINER="cmdb-glpi"
DB_CONTAINER=""
USERS_CSV="edenilson.paschoa,edenilson,akadmin"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --container) CONTAINER="$2"; shift 2 ;;
    --db-container) DB_CONTAINER="$2"; shift 2 ;;
    --users) USERS_CSV="$2"; shift 2 ;;
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

random_password() {
  python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(24)[:28])
PY
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

PROFILE_ID="$(run_sql "SELECT id FROM glpi_profiles WHERE name='Super-Admin' LIMIT 1;")"
if [[ -z "$PROFILE_ID" ]]; then
  echo "Super-Admin profile not found in GLPI." >&2
  exit 1
fi

IFS=',' read -r -a USERS <<<"$USERS_CSV"
for raw_user in "${USERS[@]}"; do
  user="$(printf '%s' "$raw_user" | xargs)"
  [[ -n "$user" ]] || continue

  user_id="$(run_sql "SELECT id FROM glpi_users WHERE name='$(sql_escape "$user")' LIMIT 1;")"
  if [[ -z "$user_id" ]]; then
    password="$(random_password)"
    docker exec "$CONTAINER" php bin/console user:create "$user" --password="$password" --no-interaction >/dev/null
    user_id="$(run_sql "SELECT id FROM glpi_users WHERE name='$(sql_escape "$user")' LIMIT 1;")"
  fi

  if [[ -z "$user_id" ]]; then
    echo "Unable to resolve GLPI user id for $user" >&2
    exit 1
  fi

  run_sql "UPDATE glpi_profiles_users SET is_default_profile=0 WHERE users_id=${user_id};" >/dev/null
  run_sql "UPDATE glpi_profiles_users SET is_recursive=1, is_dynamic=0, is_default_profile=1 WHERE users_id=${user_id} AND profiles_id=${PROFILE_ID} AND entities_id=0;" >/dev/null
  run_sql "INSERT INTO glpi_profiles_users (users_id, profiles_id, entities_id, is_recursive, is_dynamic, is_default_profile) SELECT ${user_id}, ${PROFILE_ID}, 0, 1, 0, 1 FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM glpi_profiles_users WHERE users_id=${user_id} AND profiles_id=${PROFILE_ID} AND entities_id=0);" >/dev/null
  printf 'ensured glpi admin: %s\n' "$user"
done
