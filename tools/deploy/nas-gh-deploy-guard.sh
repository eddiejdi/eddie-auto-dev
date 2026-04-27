#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-unspecified}"
TOKEN_FILE="/etc/nas-gh-deploy/token"
LOG_FILE="/var/log/nas-gh-deploy-guard.log"

explain_block() {
  local reason="$1"
  cat >&2 <<EOF
[DEPLOY BLOQUEADO] Tentativa fora do fluxo autorizado (motivo: ${reason}).
Este servidor NAS aceita alteracoes de deploy somente via GitHub Actions.

Fluxo correto:
1) Commit/push no repositorio eddiejdi/eddie-auto-dev
2) Disparar workflow de deploy no GitHub
3) O workflow envia GH_DEPLOY_TOKEN + metadados da execucao

Esta tentativa foi negada para proteger o ambiente contra alteracoes manuais/acidentais.
EOF
}

log() {
  local msg="$1"
  printf '[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$msg" >> "$LOG_FILE"
}

if [[ ! -r "$TOKEN_FILE" ]]; then
  log "DENY action=$ACTION reason=token_file_missing user=$(id -un)"
  explain_block "token_file_missing"
  exit 1
fi

EXPECTED_TOKEN="$(<"$TOKEN_FILE")"
PRESENTED_TOKEN="${GH_DEPLOY_TOKEN:-}"

if [[ -z "$PRESENTED_TOKEN" ]]; then
  log "DENY action=$ACTION reason=missing_env_token user=$(id -un) repo=${GH_DEPLOY_REPOSITORY:-na} run=${GH_DEPLOY_RUN_ID:-na} actor=${GH_DEPLOY_ACTOR:-na}"
  explain_block "missing_env_token"
  exit 1
fi

if [[ "$PRESENTED_TOKEN" != "$EXPECTED_TOKEN" ]]; then
  log "DENY action=$ACTION reason=invalid_token user=$(id -un) repo=${GH_DEPLOY_REPOSITORY:-na} run=${GH_DEPLOY_RUN_ID:-na} actor=${GH_DEPLOY_ACTOR:-na}"
  explain_block "invalid_token"
  exit 1
fi

if [[ -z "${GH_DEPLOY_REPOSITORY:-}" || -z "${GH_DEPLOY_RUN_ID:-}" ]]; then
  log "DENY action=$ACTION reason=missing_run_metadata user=$(id -un)"
  explain_block "missing_run_metadata"
  exit 1
fi

log "ALLOW action=$ACTION user=$(id -un) repo=${GH_DEPLOY_REPOSITORY} run=${GH_DEPLOY_RUN_ID} actor=${GH_DEPLOY_ACTOR:-na}"
exit 0
