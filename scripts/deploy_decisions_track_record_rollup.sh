#!/usr/bin/env bash
# Deploy do rollup horário de track_record_trs/track_record_boost no homelab.
#
# Cria/atualiza btc.decisions_track_record_hourly e o timer que a mantém
# atualizada, evitando que o painel Grafana "Track Record" precise agregar
# sobre milhões de linhas JSONB de btc.decisions a cada carregamento.
set -euo pipefail

HOMELAB="${1:-homelab@192.168.15.2}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKFILL_HOURS="${BACKFILL_HOURS:-2200}"  # ~91 dias, cobre o range usado no dashboard

echo "=== Deploy decisions-track-record-rollup → ${HOMELAB} ==="

echo "[1/4] Copiando script de rollup..."
scp "${REPO_DIR}/scripts/decisions_track_record_rollup.py" "${HOMELAB}:/tmp/decisions_track_record_rollup.py"
ssh "$HOMELAB" "
  sudo install -o btc-trading -g btc-trading -m 755 /tmp/decisions_track_record_rollup.py \
    /apps/crypto-trader/trading/scripts/decisions_track_record_rollup.py
"

echo "[2/4] Instalando unit + timer..."
scp "${REPO_DIR}/systemd/decisions-track-record-rollup.service" "${HOMELAB}:/tmp/decisions-track-record-rollup.service"
scp "${REPO_DIR}/systemd/decisions-track-record-rollup.timer" "${HOMELAB}:/tmp/decisions-track-record-rollup.timer"
ssh "$HOMELAB" "
  sudo cp /tmp/decisions-track-record-rollup.service /etc/systemd/system/decisions-track-record-rollup.service
  sudo cp /tmp/decisions-track-record-rollup.timer /etc/systemd/system/decisions-track-record-rollup.timer
  sudo systemctl daemon-reload
"

echo "[3/4] Backfill único (${BACKFILL_HOURS}h) — pode levar alguns minutos..."
ssh "$HOMELAB" "
  sudo systemd-run --uid=btc-trading --gid=btc-trading \
    --working-directory=/apps/crypto-trader/trading \
    --property=EnvironmentFile=-/apps/crypto-trader/envfiles/trading-database.env \
    --setenv=PYTHONPATH=/apps/crypto-trader/trading \
    --wait --pipe \
    /apps/crypto-trader/.venv/bin/python /apps/crypto-trader/trading/scripts/decisions_track_record_rollup.py --backfill ${BACKFILL_HOURS}
"

echo "[4/4] Habilitando timer de refresh incremental..."
ssh "$HOMELAB" "
  sudo systemctl enable --now decisions-track-record-rollup.timer
  systemctl is-active decisions-track-record-rollup.timer
"

echo ""
echo "Deploy concluído. Refresh incremental a cada 20min via timer."
echo "Logs: sudo journalctl -u decisions-track-record-rollup.service -f"
