#!/usr/bin/env bash
# Deploy grafana-selfheal + atualiza rss-sentiment-exporter no homelab
set -euo pipefail

HOMELAB="${1:-homelab@192.168.15.2}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Deploy grafana-selfheal → ${HOMELAB} ==="

# 1. Copia script
echo "[1/4] Copiando grafana-selfheal..."
scp "${REPO_DIR}/tools/grafana-selfheal" "${HOMELAB}:/tmp/grafana-selfheal"
ssh "$HOMELAB" "sudo install -m 755 /tmp/grafana-selfheal /usr/local/bin/grafana-selfheal"

# 2. Instala service
echo "[2/4] Instalando unit grafana-selfheal.service..."
scp "${REPO_DIR}/systemd/grafana-selfheal.service" "${HOMELAB}:/tmp/grafana-selfheal.service"
ssh "$HOMELAB" "
  sudo cp /tmp/grafana-selfheal.service /etc/systemd/system/grafana-selfheal.service
  sudo mkdir -p /var/lib/grafana-selfheal
  sudo systemctl daemon-reload
  sudo systemctl enable grafana-selfheal.service
  sudo systemctl restart grafana-selfheal.service
"

# 3. Atualiza rss-sentiment-exporter (modelo qwen3:1.7b)
echo "[3/4] Atualizando rss-sentiment-exporter.service (qwen3:1.7b)..."
scp "${REPO_DIR}/systemd/rss-sentiment-exporter.service" "${HOMELAB}:/tmp/rss-sentiment-exporter.service"
ssh "$HOMELAB" "
  sudo cp /tmp/rss-sentiment-exporter.service /etc/systemd/system/rss-sentiment-exporter.service
  sudo systemctl daemon-reload
  sudo systemctl restart rss-sentiment-exporter.service
"

# 4. Verifica
echo "[4/4] Verificando serviços..."
sleep 5
ssh "$HOMELAB" "
  echo '--- grafana-selfheal ---'
  systemctl is-active grafana-selfheal.service
  sudo /usr/local/bin/grafana-selfheal --test

  echo ''
  echo '--- rss-sentiment-exporter ---'
  systemctl is-active rss-sentiment-exporter.service
  sudo journalctl -u rss-sentiment-exporter.service -n 5 --no-pager
"

echo ""
echo "Deploy concluído."
echo "Métricas Prometheus em: /var/lib/prometheus/node-exporter/grafana_selfheal.prom"
echo "Logs: sudo journalctl -u grafana-selfheal.service -f"
