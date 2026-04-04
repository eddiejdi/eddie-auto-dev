#!/usr/bin/env bash
set -euo pipefail

TARGET_HOST="${1:-${HOMELAB_HOST:-192.168.15.2}}"
TARGET_USER="${2:-${HOMELAB_USER:-homelab}}"
TARGET_DIR="${TARGET_DIR:-/home/homelab/eddie-auto-dev}"
SERVICE_NAME="clear-trading-agent.service"

if [[ -z "${TARGET_HOST}" || -z "${TARGET_USER}" ]]; then
  echo "HOST/USER ausentes" >&2
  exit 2
fi

echo "[1/5] Sincronizando codigo para ${TARGET_USER}@${TARGET_HOST}:${TARGET_DIR}"
ssh -o StrictHostKeyChecking=no "${TARGET_USER}@${TARGET_HOST}" "bash -s" <<SSH
set -euo pipefail
TARGET_DIR="${TARGET_DIR}"
if [[ -d "${TARGET_DIR}" ]]; then
  rm -rf /tmp/clear-trading-agent-backup
  mkdir -p /tmp/clear-trading-agent-backup
  rsync -a --delete \
    --exclude '.venv/' \
    --exclude '__pycache__/' \
    --exclude '.pytest_cache/' \
    "${TARGET_DIR}/" /tmp/clear-trading-agent-backup/
fi
SSH

rsync -az --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  ./ "${TARGET_USER}@${TARGET_HOST}:${TARGET_DIR}/"

echo "[2/5] Aplicando unit file do systemd"
scp systemd/clear-trading-agent.service "${TARGET_USER}@${TARGET_HOST}:/tmp/clear-trading-agent.service"

ssh -o StrictHostKeyChecking=no "${TARGET_USER}@${TARGET_HOST}" "TARGET_DIR='${TARGET_DIR}' bash -s" <<'SSH'
set -euo pipefail
TARGET_DIR="${TARGET_DIR:-/home/homelab/eddie-auto-dev}"
SERVICE_NAME="clear-trading-agent.service"

sudo install -m 0644 /tmp/clear-trading-agent.service /etc/systemd/system/clear-trading-agent.service
rm -f /tmp/clear-trading-agent.service

echo "[3/5] Preparando ambiente Python"
if [[ ! -x "${TARGET_DIR}/.venv/bin/python3" ]]; then
  python3 -m venv "${TARGET_DIR}/.venv"
fi

"${TARGET_DIR}/.venv/bin/pip" install --upgrade pip >/dev/null
"${TARGET_DIR}/.venv/bin/pip" install -r "${TARGET_DIR}/clear_trading_agent/requirements.txt" >/dev/null

echo "[4/5] Reiniciando servico ${SERVICE_NAME}"
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}

sleep 4
if ! sudo systemctl is-active --quiet ${SERVICE_NAME}; then
  echo "Servico falhou. Iniciando rollback..." >&2
  if [[ -d /tmp/clear-trading-agent-backup ]]; then
    rsync -a --delete /tmp/clear-trading-agent-backup/ "${TARGET_DIR}/"
  fi
  sudo systemctl restart ${SERVICE_NAME} || true
  sudo systemctl --no-pager -l status ${SERVICE_NAME} || true
  exit 1
fi

echo "[5/5] Healthcheck"
sudo systemctl --no-pager -l status ${SERVICE_NAME} | head -20
SSH

echo "Deploy concluido com sucesso"
