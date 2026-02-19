#!/usr/bin/env bash
# Instala as regras Prometheus para o Homelab Advisor (requer sudo)
set -euo pipefail
RULE_SRC_DIR="$(cd "$(dirname "$0")" && pwd)/prometheus-rules"
TARGET_DIR="/etc/prometheus/rules"
RULE_FILE="homelab-advisor-alerts.yml"

echo "📦 Instalando regra Prometheus: $RULE_FILE -> $TARGET_DIR"
if [ ! -f "$RULE_SRC_DIR/$RULE_FILE" ]; then
  echo "Arquivo de regra não encontrado: $RULE_SRC_DIR/$RULE_FILE" >&2
  exit 1
fi

sudo mkdir -p "$TARGET_DIR"
sudo cp "$RULE_SRC_DIR/$RULE_FILE" "$TARGET_DIR/"
# Ajustar permissões
sudo chown root:root "$TARGET_DIR/$RULE_FILE"
sudo chmod 644 "$TARGET_DIR/$RULE_FILE"

# Recarregar Prometheus (systemd) — se não existir, instruir usuário
if systemctl --quiet is-active prometheus; then
  echo "🔁 Recarregando prometheus.service"
  sudo systemctl reload prometheus || sudo systemctl restart prometheus
  echo "✅ Regra instalada e Prometheus recarregado"
else
  echo "⚠️ Prometheus service não ativo na máquina local. Copie $TARGET_DIR/$RULE_FILE para o servidor Prometheus e recarregue manualmente."
  echo "Exemplo (remote): sudo scp $RULE_SRC_DIR/$RULE_FILE homelab:/etc/prometheus/rules/ && ssh homelab 'sudo systemctl reload prometheus'"
fi
