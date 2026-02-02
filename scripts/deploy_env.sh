#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="${1:-}"
if [[ -z "$ENV_NAME" ]]; then
  echo "Uso: $0 <dev|cer|prod>" >&2
  exit 1
fi

: "${DEPLOY_HOST:?DEPLOY_HOST não definido}"
: "${DEPLOY_USER:?DEPLOY_USER não definido}"
: "${DEPLOY_PATH:?DEPLOY_PATH não definido}"
: "${DEPLOY_BRANCH:?DEPLOY_BRANCH não definido}"
: "${SERVICE_NAME:?SERVICE_NAME não definido}"
: "${SERVICE_PORT:?SERVICE_PORT não definido}"
: "${DEPLOY_SSH_KEY:?DEPLOY_SSH_KEY não definido}"

KEY_FILE="/tmp/eddie_deploy_key_${ENV_NAME}"
rm -f "$KEY_FILE"
printf '%s\n' "$DEPLOY_SSH_KEY" > "$KEY_FILE"
chmod 600 "$KEY_FILE"

SSH_OPTS=(
  -o IdentitiesOnly=yes
  -o StrictHostKeyChecking=accept-new
  -i "$KEY_FILE"
)

REMOTE="${DEPLOY_USER}@${DEPLOY_HOST}"

echo "[${ENV_NAME}] Atualizando código em ${DEPLOY_PATH} (${DEPLOY_BRANCH})"
ssh "${SSH_OPTS[@]}" "$REMOTE" "set -e; cd '${DEPLOY_PATH}'; git fetch --all; git reset --hard 'origin/${DEPLOY_BRANCH}'"

echo "[${ENV_NAME}] Reiniciando serviço ${SERVICE_NAME}"
ssh "${SSH_OPTS[@]}" "$REMOTE" "sudo systemctl restart '${SERVICE_NAME}'"
ssh "${SSH_OPTS[@]}" "$REMOTE" "sudo systemctl is-active --quiet '${SERVICE_NAME}'"

echo "[${ENV_NAME}] Verificando healthcheck"
ssh "${SSH_OPTS[@]}" "$REMOTE" "curl -fsS 'http://localhost:${SERVICE_PORT}/health' >/dev/null"

echo "[${ENV_NAME}] ✅ Deploy concluído com sucesso"

rm -f "$KEY_FILE"
