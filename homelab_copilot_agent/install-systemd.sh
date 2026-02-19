#!/usr/bin/env bash
# Instala o unit systemd para o Homelab Copilot Agent
set -euo pipefail
UNIT_SRC_DIR="$(cd "$(dirname "$0")" && pwd)/systemd"
UNIT_FILE="homelab_copilot_agent.service"

if [ ! -f "$UNIT_SRC_DIR/$UNIT_FILE" ]; then
  echo "Arquivo unit não encontrado: $UNIT_SRC_DIR/$UNIT_FILE" >&2
  exit 1
fi

echo "📦 Instalando systemd unit: $UNIT_FILE -> /etc/systemd/system/"
sudo cp "$UNIT_SRC_DIR/$UNIT_FILE" /etc/systemd/system/
sudo chown root:root /etc/systemd/system/$UNIT_FILE
sudo chmod 644 /etc/systemd/system/$UNIT_FILE
sudo systemctl daemon-reload
sudo systemctl enable --now $UNIT_FILE || true

echo "✅ Unit instalado. Status:"
sudo systemctl status $UNIT_FILE --no-pager || true

echo "Dica: use 'sudo systemctl restart homelab_copilot_agent' para reiniciar com segurança."