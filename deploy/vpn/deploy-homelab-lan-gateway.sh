#!/bin/bash
# deploy-homelab-lan-gateway.sh — Instala watchdog do gateway da LAN no homelab

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_HOST="${HOMELAB_HOST:-192.168.15.2}"
REMOTE_USER="${HOMELAB_USER:-homelab}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ $*" >&2; exit 1; }
success() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ $*"; }

log "🚀 Instalando watchdog do gateway da LAN no homelab..."

if ! ssh "$REMOTE_USER@$REMOTE_HOST" 'echo OK' >/dev/null 2>&1; then
    error "Não consegue conectar: $REMOTE_USER@$REMOTE_HOST"
fi

scp "$SCRIPT_DIR/homelab-lan-gateway.sh" "$REMOTE_USER@$REMOTE_HOST:/tmp/" || error "SCP do script falhou"
scp "$SCRIPT_DIR/homelab-lan-gateway.service" "$REMOTE_USER@$REMOTE_HOST:/tmp/" || error "SCP do service falhou"
scp "$SCRIPT_DIR/homelab-lan-gateway.timer" "$REMOTE_USER@$REMOTE_HOST:/tmp/" || error "SCP do timer falhou"

ssh "$REMOTE_USER@$REMOTE_HOST" bash <<'REMOTE_SCRIPT'
set -euo pipefail

sudo cp /tmp/homelab-lan-gateway.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/homelab-lan-gateway.sh
sudo cp /tmp/homelab-lan-gateway.service /etc/systemd/system/
sudo cp /tmp/homelab-lan-gateway.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now homelab-lan-gateway.timer
sudo /usr/local/bin/homelab-lan-gateway.sh --ensure
REMOTE_SCRIPT

success "✅ Watchdog do gateway da LAN instalado"
log "Verificar status: ssh $REMOTE_USER@$REMOTE_HOST systemctl status homelab-lan-gateway.timer"
log "Ver logs: ssh $REMOTE_USER@$REMOTE_HOST journalctl -u homelab-lan-gateway -f"
