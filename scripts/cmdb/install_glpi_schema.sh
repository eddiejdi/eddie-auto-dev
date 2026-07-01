#!/usr/bin/env bash

set -euo pipefail

USAGE="Usage: $0 [--env-file FILE] [--container NAME]

Reads GLPI database settings from an env file and runs a clean schema install
through the official GLPI CLI."

ENV_FILE="/workspace/eddie-auto-dev/deploy/cmdb/.env"
CONTAINER="cmdb-glpi"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --container) CONTAINER="$2"; shift 2 ;;
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

GLPI_DB_NAME="$(read_env_value GLPI_DB_NAME)"
GLPI_DB_USER="$(read_env_value GLPI_DB_USER)"
GLPI_DB_PASSWORD="$(read_env_value GLPI_DB_PASSWORD)"

docker exec "$CONTAINER" php bin/console database:install \
  --db-host=glpi-db \
  --db-port=3306 \
  --db-name="$GLPI_DB_NAME" \
  --db-user="$GLPI_DB_USER" \
  --db-password="$GLPI_DB_PASSWORD" \
  --default-language=pt_BR \
  --no-interaction \
  --no-telemetry \
  --reconfigure \
  --force
