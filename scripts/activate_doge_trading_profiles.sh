#!/usr/bin/env bash
# Ativa perfis DOGE-USDT live na conta TRADE master (kucoin/homelab).
# Executar NO HOMELAB com sudo, após sync dos configs do repositório.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${TARGET_DIR:-/apps/crypto-trader/trading/btc_trading_agent}"
ENVDIR="${ENVDIR:-/apps/crypto-trader/envfiles}"
PROMETHEUS_CONFIG="${PROMETHEUS_CONFIG:-/home/homelab/monitoring/prometheus.yml}"
REPO_PROMETHEUS="${REPO_ROOT}/monitoring/prometheus.yml"

declare -a PROFILES=(
  "DOGE_USDT_shadow:9112:8522"
  "DOGE_USDT_conservative:9113:8523"
  "DOGE_USDT_aggressive:9114:8524"
)

echo "=== Ativação DOGE-USDT (master TRADE, live) ==="

mkdir -p "${ENVDIR}"
for entry in "${PROFILES[@]}"; do
  IFS=':' read -r inst metrics_port api_port <<< "$entry"
  cat > "${ENVDIR}/${inst}.env" <<EOF
TRADING_TELEGRAM_CHAT_ID=-1004434951297
METRICS_PORT=${metrics_port}
BTC_ENGINE_API_PORT=${api_port}
EOF
  echo "  envfile ${inst}.env (metrics:${metrics_port})"
done

for cfg in config_DOGE_USDT_shadow.json config_DOGE_USDT_conservative.json config_DOGE_USDT_aggressive.json; do
  install -o btc-trading -g btc-trading -m 0644 \
    "${REPO_ROOT}/btc_trading_agent/${cfg}" "${TARGET_DIR}/${cfg}"
  echo "  config ${cfg}"
done

if [[ -f "${REPO_PROMETHEUS}" ]]; then
  if grep -q "crypto-exporter-doge_usdt_shadow" "${REPO_PROMETHEUS}"; then
    cp "${PROMETHEUS_CONFIG}" "${PROMETHEUS_CONFIG}.bak.$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
    cp "${REPO_PROMETHEUS}" "${PROMETHEUS_CONFIG}"
    systemctl reload prometheus 2>/dev/null || kill -HUP "$(pgrep -xo prometheus)" 2>/dev/null || true
    echo "  prometheus.yml atualizado"
  fi
fi

systemctl daemon-reload
for entry in "${PROFILES[@]}"; do
  inst="${entry%%:*}"
  systemctl enable "crypto-agent@${inst}.service" "crypto-exporter@${inst}.service"
  systemctl restart "crypto-agent@${inst}.service" "crypto-exporter@${inst}.service"
  echo "  started crypto-agent@${inst} + crypto-exporter@${inst}"
done

sleep 3
for entry in "${PROFILES[@]}"; do
  inst="${entry%%:*}"
  systemctl is-active "crypto-agent@${inst}.service" "crypto-exporter@${inst}.service" || true
done

echo "=== DOGE-USDT ativo (live). Capital alvo ~\$150 USDT na TRADE master (\$50 × 3 perfis). ==="