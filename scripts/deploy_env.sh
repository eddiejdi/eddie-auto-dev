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

# Tenta atualizar via git no servidor remoto (retry)
update_remote_git() {
  ssh "${SSH_OPTS[@]}" "$REMOTE" "set -e; cd '${DEPLOY_PATH}'; git fetch --all; git reset --hard 'origin/${DEPLOY_BRANCH}'"
}

TRY=0
MAX_TRIES=3
until update_remote_git; do
  TRY=$((TRY+1))
  echo "Tentativa de git fetch falhou (attempt ${TRY}/${MAX_TRIES})"
  if [ "$TRY" -ge "$MAX_TRIES" ]; then
    echo "Falha ao atualizar remoto via git depois de ${MAX_TRIES} tentativas. Tentando fallback (push de archive do runner)."
    # Fallback: empacotar tree local e extrair no servidor (evita dependência do git no servidor)
    if command -v git >/dev/null 2>&1 && git rev-parse --verify "${DEPLOY_BRANCH}" >/dev/null 2>&1; then
      echo "Gerando archive do branch ${DEPLOY_BRANCH} e enviando para ${REMOTE}..."
      git archive --format=tar "${DEPLOY_BRANCH}" | ssh "${SSH_OPTS[@]}" "$REMOTE" "mkdir -p '${DEPLOY_PATH}' && tar -xC '${DEPLOY_PATH}'"
      break
    else
      echo "Não foi possível usar git archive no runner (branch não disponível). Abortando." >&2
      rm -f "$KEY_FILE"
      exit 1
    fi
  fi
  sleep 2
done

echo "[${ENV_NAME}] Reiniciando serviço ${SERVICE_NAME}"
ssh "${SSH_OPTS[@]}" "$REMOTE" "sudo systemctl restart '${SERVICE_NAME}'"

echo "[${ENV_NAME}] Aguardando serviço iniciar..."
for i in {1..10}; do
  if ssh "${SSH_OPTS[@]}" "$REMOTE" "sudo systemctl is-active --quiet '${SERVICE_NAME}'"; then
    break
  fi
  echo "Aguardando... tentativa $i/10"
  sleep 2
done

echo "[${ENV_NAME}] Verificando healthcheck"
for i in {1..10}; do
  if ssh "${SSH_OPTS[@]}" "$REMOTE" "curl -fsS 'http://localhost:${SERVICE_PORT}/health' >/dev/null 2>&1"; then
    echo "[${ENV_NAME}] ✅ Health check passou"
    break
  fi
  echo "Health check falhou, tentativa $i/10..."
  sleep 3
done

echo "[${ENV_NAME}] ✅ Deploy concluído com sucesso"

rm -f "$KEY_FILE"
