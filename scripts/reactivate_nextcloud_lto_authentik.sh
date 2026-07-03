#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."
NEXTCLOUD_ENV_FILE="${REPO_ROOT}/.env"
CONFIGURE_SCRIPT="${REPO_ROOT}/tools/authentik_management/configure_authentik_nextcloud_oidc.py"
BOOTSTRAP_SCRIPT="${REPO_ROOT}/tools/authentik_management/bootstrap_nextcloud_oidc.sh"
NAS_HOST=""
NAS_USER="root"
NAS_SSH_PASS=""

usage() {
  cat <<EOF
Usage: bash scripts/reactivate_nextcloud_lto_authentik.sh [options]

Options:
  --nas-host HOST        Kept for compatibility; direct LTFS reactivation is skipped
  --nas-user USER        Kept for compatibility (default: root)
  --nas-pass PASS        Kept for compatibility (ignored)
  --env-file FILE        Nextcloud .env file to source before bootstrap
  --help                 Show this help and exit

This script now applies only the Authentik/OIDC bootstrap.
The old direct LTFS reactivation flow was retired after the
2026-04-23 storage incident. Use the staging runbook instead:
  - docs/NEXTCLOUD_LTO_STAGING_ARCHITECTURE_2026-04-23.md
  - docs/INCIDENTS/NEXTCLOUD_TANK_LTO_UPLOAD_2026-04-23.md

It assumes the repository checkout contains:
  - tools/authentik_management/bootstrap_nextcloud_oidc.sh
  - tools/authentik_management/configure_authentik_nextcloud_oidc.py
EOF
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --nas-host)
      NAS_HOST="$2"
      shift 2
      ;;
    --nas-user)
      NAS_USER="$2"
      shift 2
      ;;
    --nas-pass)
      NAS_SSH_PASS="$2"
      shift 2
      ;;
    --env-file)
      NEXTCLOUD_ENV_FILE="$2"
      shift 2
      ;;
    --help)
      usage
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      ;;
  esac
done

run_nextcloud_bootstrap() {
  if [[ ! -f "${CONFIGURE_SCRIPT}" ]]; then
    echo "ERROR: Nextcloud OIDC configure script not found: ${CONFIGURE_SCRIPT}" >&2
    exit 1
  fi

  if [[ ! -f "${BOOTSTRAP_SCRIPT}" ]]; then
    echo "ERROR: Nextcloud OIDC bootstrap script not found: ${BOOTSTRAP_SCRIPT}" >&2
    exit 1
  fi

  echo "[*] Aplicando configuração Authentik/OIDC no Nextcloud..."
  pushd "${REPO_ROOT}" >/dev/null

  if [[ -f "${NEXTCLOUD_ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${NEXTCLOUD_ENV_FILE}"
    set +a
  fi

  python3 "${CONFIGURE_SCRIPT}"
  bash "${BOOTSTRAP_SCRIPT}"
  popd >/dev/null
}

if [[ -n "${NAS_HOST}" ]]; then
  echo "[*] LTFS direto via NAS foi descontinuado após o incidente de 2026-04-23."
  echo "[*] Nenhuma ação remota será executada em ${NAS_HOST}."
  echo "[*] Revise o staging em disco usando docs/NEXTCLOUD_LTO_STAGING_ARCHITECTURE_2026-04-23.md."
else
  echo "[*] Fluxo de storage LTFS direto está descontinuado; seguindo apenas com o bootstrap Authentik/OIDC."
fi

run_nextcloud_bootstrap

echo "[*] Fluxo Authentik/OIDC concluído. O storage deve permanecer em staging, nunca direto em LTFS."
