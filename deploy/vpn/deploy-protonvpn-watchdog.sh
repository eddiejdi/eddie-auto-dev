#!/bin/bash
# deploy-protonvpn-watchdog.sh — Instala watchdog imutável no homelab
# Garante que ProtonVPN nunca será revertido acidentalmente

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_HOST="${HOMELAB_HOST:-192.168.15.2}"
REMOTE_USER="${HOMELAB_USER:-homelab}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ $*" >&2; exit 1; }
success() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ $*"; }

log "🚀 Instalando ProtonVPN Routing Watchdog no homelab..."

# Valida SSH
if ! ssh "$REMOTE_USER@$REMOTE_HOST" 'echo OK' &>/dev/null; then
    error "Não consegue conectar: $REMOTE_USER@$REMOTE_HOST"
fi

log "📋 Copiando arquivos..."
scp "$SCRIPT_DIR/protonvpn-routing-watchdog.sh" "$REMOTE_USER@$REMOTE_HOST:/tmp/" || error "SCP falhou"
scp "$SCRIPT_DIR/99-force-protonvpn-routing.network" "$REMOTE_USER@$REMOTE_HOST:/tmp/" || error "SCP falhou"
scp "$SCRIPT_DIR/protonvpn-routing-watchdog.service" "$REMOTE_USER@$REMOTE_HOST:/tmp/" || error "SCP falhou"
scp "$SCRIPT_DIR/protonvpn-routing-watchdog.timer" "$REMOTE_USER@$REMOTE_HOST:/tmp/" || error "SCP falhou"
scp "$SCRIPT_DIR/protonvpn-routing-watchdog-fix.service" "$REMOTE_USER@$REMOTE_HOST:/tmp/" || error "SCP falhou"

log "🔧 Instalando..."
ssh "$REMOTE_USER@$REMOTE_HOST" bash << 'REMOTE_SCRIPT'
set -euo pipefail

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ $*" >&2; exit 1; }
success() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ $*"; }

# 1. Copia script para bin
sudo cp /tmp/protonvpn-routing-watchdog.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/protonvpn-routing-watchdog.sh
log "✓ Script instalado em /usr/local/bin"

# 2. Copia systemd units
sudo cp /tmp/protonvpn-routing-watchdog.service /etc/systemd/system/
sudo cp /tmp/protonvpn-routing-watchdog.timer /etc/systemd/system/
sudo cp /tmp/protonvpn-routing-watchdog-fix.service /etc/systemd/system/
log "✓ Systemd units instaladas"

# 3. Copia NetworkD drop-in
sudo mkdir -p /etc/systemd/network
sudo cp /tmp/99-force-protonvpn-routing.network /etc/systemd/network/
sudo chmod 644 /etc/systemd/network/99-force-protonvpn-routing.network
log "✓ NetworkD config instalada"

# 4. Recarrega systemd
sudo systemctl daemon-reload
log "✓ Systemd daemon recarregado"

# 5. Ativa e inicia o timer
sudo systemctl enable protonvpn-routing-watchdog.timer
sudo systemctl start protonvpn-routing-watchdog.timer
log "✓ Timer ativado"

# 6. Primeira verificação
sleep 2
sudo /usr/local/bin/protonvpn-routing-watchdog.sh --health-check

success "✅ Watchdog instalado com sucesso!"
log "Monitorando a cada 5 minutos..."
log "Ver status: systemctl status protonvpn-routing-watchdog.timer"
log "Ver logs: journalctl -u protonvpn-routing-watchdog -f"

REMOTE_SCRIPT

success "✅ ProtonVPN Watchdog instalado e ativo!"
log ""
log "Próximos passos:"
log "  1. Verificar status: ssh homelab@192.168.15.2 systemctl status protonvpn-routing-watchdog.timer"
log "  2. Ver logs: ssh homelab@192.168.15.2 journalctl -u protonvpn-routing-watchdog -f"
log "  3. Testar: ssh homelab@192.168.15.2 /usr/local/bin/protonvpn-routing-watchdog.sh --health-check"
log "  4. Aplicar gateway da LAN: bash deploy/vpn/deploy-homelab-lan-gateway.sh"
log ""
log "🔒 Agora ProtonVPN está PROTEGIDO:"
log "   ✓ Monitora a cada 5 minutos"
log "   ✓ Auto-corrige se quebrar"
log "   ✓ Drop-in persistente atualizado sem reiniciar a rede"
log "   ✓ Alerta se problema persistir"
