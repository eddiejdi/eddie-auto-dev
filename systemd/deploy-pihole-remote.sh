#!/bin/bash
# Deploy do Pi-hole DNS Intercept para o homelab via SSH
# Execute a partir desta máquina (VS Code):
#   bash systemd/deploy-pihole-remote.sh
#
# Requerimento: SSH com chave configurada (ou será pedida senha)

set -euo pipefail

HOMELAB_IP="192.168.15.2"
HOMELAB_USER="${HOMELAB_USER:-$(whoami)}"
SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "=== Deploy Pi-hole DNS Intercept → ${HOMELAB_USER}@${HOMELAB_IP} ==="

# 1. Copiar arquivos para o homelab
log "Enviando arquivos via scp..."
scp $SSH_OPTS \
    "$SCRIPT_DIR/pihole-ipv6-dns-fix.sh" \
    "$SCRIPT_DIR/pihole-ipv6-dns-fix.service" \
    "$SCRIPT_DIR/radvd.conf" \
    "${HOMELAB_USER}@${HOMELAB_IP}:/tmp/"

log "Arquivos enviados. Executando instalação remota..."

# 2. Executar instalação remota como root
ssh $SSH_OPTS "${HOMELAB_USER}@${HOMELAB_IP}" bash -s << 'REMOTE'
set -euo pipefail
log() { echo "[HOMELAB $(date '+%H:%M:%S')] $*"; }

log "=== Instalando no homelab ==="

# Backup dos arquivos atuais, se existirem
[[ -f /usr/local/bin/pihole-ipv6-dns-fix.sh ]] && \
    cp /usr/local/bin/pihole-ipv6-dns-fix.sh /usr/local/bin/pihole-ipv6-dns-fix.sh.bak && \
    log "Backup: /usr/local/bin/pihole-ipv6-dns-fix.sh.bak"

[[ -f /etc/systemd/system/pihole-ipv6-dns-fix.service ]] && \
    cp /etc/systemd/system/pihole-ipv6-dns-fix.service /etc/systemd/system/pihole-ipv6-dns-fix.service.bak && \
    log "Backup: pihole-ipv6-dns-fix.service.bak"

# Instalar script
sudo cp /tmp/pihole-ipv6-dns-fix.sh /usr/local/bin/pihole-ipv6-dns-fix.sh
sudo chmod +x /usr/local/bin/pihole-ipv6-dns-fix.sh
log "Script instalado em /usr/local/bin/"

# Instalar service
sudo cp /tmp/pihole-ipv6-dns-fix.service /etc/systemd/system/pihole-ipv6-dns-fix.service
log "Service instalado em /etc/systemd/system/"

# radvd — apenas se instalado
if command -v radvd &>/dev/null; then
    [[ -f /etc/radvd.conf ]] && sudo cp /etc/radvd.conf /etc/radvd.conf.bak && log "Backup: /etc/radvd.conf.bak"
    sudo cp /tmp/radvd.conf /etc/radvd.conf
    sudo systemctl restart radvd
    sudo systemctl enable radvd
    log "radvd atualizado e habilitado"
fi

# Recarregar e reiniciar serviço
sudo systemctl daemon-reload
sudo systemctl enable pihole-ipv6-dns-fix.service
sudo systemctl restart pihole-ipv6-dns-fix.service

log "Aguardando serviço inicializar..."
sleep 5

# Status
sudo systemctl status pihole-ipv6-dns-fix --no-pager -l

log ""
log "=== VERIFICAÇÃO DAS REGRAS ==="
log "--- IPv4 iptables porta 53 ---"
sudo iptables -t nat -L PREROUTING -n --line-numbers 2>/dev/null | grep -E "dpt:53|pihole" || echo "  (nenhuma regra IPv4)"

log "--- IPv6 ip6tables porta 53 ---"
sudo ip6tables -t nat -L PREROUTING -n --line-numbers 2>/dev/null | grep -E "dpt:53|pihole" || echo "  (nenhuma regra IPv6)"

log ""
log "=== TESTE DNS ==="
if docker exec pihole pihole -q ads.google.com 2>/dev/null | head -3; then
    log "Pi-hole respondendo ✓"
fi

# Limpar arquivos temporários
rm -f /tmp/pihole-ipv6-dns-fix.sh /tmp/pihole-ipv6-dns-fix.service /tmp/radvd.conf
log "=== DEPLOY CONCLUÍDO === novos dispositivos usarão Pi-hole automaticamente"
REMOTE

log "Deploy finalizado com sucesso!"
