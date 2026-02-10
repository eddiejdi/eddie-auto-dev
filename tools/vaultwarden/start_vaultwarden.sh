#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$ROOT_DIR/vaultwarden"

if [ -z "${VAULTWARDEN_ADMIN_TOKEN:-}" ]; then
  echo "WARNING: VAULTWARDEN_ADMIN_TOKEN not set; container will start with default 'changeme' admin token."
  echo "Set VAULTWARDEN_ADMIN_TOKEN env var before running for security."
fi

docker compose up -d
echo "Vaultwarden starting (http://localhost:8080). Admin token from VAULTWARDEN_ADMIN_TOKEN or default 'changeme'."
