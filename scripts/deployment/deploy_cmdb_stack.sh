#!/usr/bin/env bash

set -euo pipefail

USAGE="Usage: $0 --host HOST --user USER [--remote-dir DIR] [--apply]

Copies deploy/cmdb and scripts/cmdb/generate_cmdb_baseline.py to a remote staging path.
Default mode only stages files for review. Use --apply to validate compose and start the stack remotely."

HOST=""
USER=""
REMOTE_DIR="/opt/cmdb"
APPLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --user) USER="$2"; shift 2 ;;
    --remote-dir) REMOTE_DIR="$2"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    -h|--help) printf '%s\n' "$USAGE"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; printf '%s\n' "$USAGE" >&2; exit 2 ;;
  esac
done

if [[ -z "$HOST" || -z "$USER" ]]; then
  printf '%s\n' "$USAGE" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REMOTE_STAGE="/tmp/cmdb-stack-${STAMP}"
REMOTE="${USER}@${HOST}"

echo "[INFO] Creating remote staging directory ${REMOTE_STAGE}"
ssh "${REMOTE}" "mkdir -p '${REMOTE_STAGE}/deploy' '${REMOTE_STAGE}/scripts/cmdb'"

echo "[INFO] Copying stack artifacts"
scp -r "${REPO_ROOT}/deploy/cmdb" "${REMOTE}:${REMOTE_STAGE}/deploy/"
scp "${REPO_ROOT}/scripts/cmdb/generate_cmdb_baseline.py" "${REMOTE}:${REMOTE_STAGE}/scripts/cmdb/"

if [[ "${APPLY}" -eq 0 ]]; then
  echo "[INFO] Files staged at ${REMOTE_STAGE}"
  echo "[INFO] Review remotely, create ${REMOTE_STAGE}/deploy/cmdb/.env, then rerun with --apply if desired."
  exit 0
fi

echo "[INFO] Applying stack to ${REMOTE_DIR}"
ssh "${REMOTE}" "set -euo pipefail
  test -f '${REMOTE_STAGE}/deploy/cmdb/.env' || {
    echo '[ERROR] Missing remote .env in staging directory. Copy .env.example to .env and adjust secrets before apply.' >&2
    exit 2
  }
  COMPOSE_CMD='docker compose'
  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD='docker-compose'
  elif ! docker compose version >/dev/null 2>&1; then
    echo '[ERROR] Docker Compose not available on remote host.' >&2
    exit 2
  fi
  mkdir -p '${REMOTE_DIR}'
  cp -a '${REMOTE_STAGE}/deploy/cmdb/.' '${REMOTE_DIR}/'
  cd '${REMOTE_DIR}'
  \$COMPOSE_CMD --env-file .env -f docker-compose.yml config >/dev/null
  \$COMPOSE_CMD --env-file .env -f docker-compose.yml up -d
"

echo "[INFO] Stack applied to ${REMOTE_DIR}"
