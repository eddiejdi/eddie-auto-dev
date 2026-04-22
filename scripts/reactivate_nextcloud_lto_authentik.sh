#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAS_SCRIPT="${SCRIPT_DIR}/nas_ltfs_nextcloud_reactivate.sh"
NEXTCLOUD_DIR="${SCRIPT_DIR}/../forks/rpa4all-nextcloud-authentik"
NEXTCLOUD_ENV_FILE="${NEXTCLOUD_DIR}/.env"
NAS_HOST=""
NAS_USER="root"
NAS_SSH_PASS=""

usage() {
  cat <<EOF
Usage: bash scripts/reactivate_nextcloud_lto_authentik.sh [options]

Options:
  --nas-host HOST        NAS hostname or IP for LTFS reativation via SSH
  --nas-user USER        NAS SSH user (default: root)
  --nas-pass PASS        NAS SSH password (requires sshpass)
  --env-file FILE        Nextcloud .env file to source before bootstrap
  --help                 Show this help and exit

This script runs the complete reativation flow:
  1) reativa LTFS no NAS (opcional via SSH)
  2) configura o Authentik/OIDC no Nextcloud
  3) habilita os apps necessários no Nextcloud

It assumes the repository checkout contains:
  - scripts/nas_ltfs_nextcloud_reactivate.sh
  - forks/rpa4all-nextcloud-authentik/scripts/bootstrap_nextcloud_oidc.sh
  - forks/rpa4all-nextcloud-authentik/scripts/configure_authentik_nextcloud_oidc.py
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

run_remote_nas() {
  if [[ -z "${NAS_HOST}" ]]; then
    return
  fi

  echo "[*] Reativando LTFS no NAS ${NAS_HOST}..."
  if [[ -n "${NAS_SSH_PASS}" ]]; then
    command -v sshpass >/dev/null 2>&1 || {
      echo "ERROR: sshpass is required when using --nas-pass" >&2
      exit 1
    }
    sshpass -p "${NAS_SSH_PASS}" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "${NAS_USER}@${NAS_HOST}" "bash -s" < "${NAS_SCRIPT}"
  else
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "${NAS_USER}@${NAS_HOST}" "bash -s" < "${NAS_SCRIPT}"
  fi
}

run_local_nas() {
  echo "[*] Reativando LTFS localmente no host atual..."
  bash "${NAS_SCRIPT}"
}

run_nextcloud_bootstrap() {
  if [[ ! -d "${NEXTCLOUD_DIR}" ]]; then
    echo "ERROR: Nextcloud bootstrap directory not found: ${NEXTCLOUD_DIR}" >&2
    exit 1
  fi

  echo "[*] Aplicando configuração Authentik/OIDC no Nextcloud..."
  pushd "${NEXTCLOUD_DIR}" >/dev/null

  if [[ -f "${NEXTCLOUD_ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${NEXTCLOUD_ENV_FILE}"
    set +a
  fi

  python3 scripts/configure_authentik_nextcloud_oidc.py
  bash scripts/bootstrap_nextcloud_oidc.sh
  popd >/dev/null
}

if [[ -n "${NAS_HOST}" ]]; then
  run_remote_nas
else
  echo "[*] No NAS host configured, pulando reativação de fita. Use --nas-host se quiser reativar o NAS remotamente."
fi

run_nextcloud_bootstrap

echo "[*] Fluxo Nextcloud + LTFS + Authentik concluído."
