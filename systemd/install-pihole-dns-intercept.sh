#!/bin/bash
# Instala/atualiza o serviço de interceptação DNS do Pi-hole no homelab
# Execute como root no servidor homelab:
#   sudo bash install-pihole-dns-intercept.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="pihole-ipv6-dns-fix"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
err() { echo "[ERRO] $*" >&2; exit 1; }

[[ "$EUID" -eq 0 ]] || err "Execute como root: sudo bash $0"

log "=== Instalando Pi-hole DNS Intercept (IPv4 + IPv6) ==="

# 1. Copiar script
log "Copiando script para /usr/local/bin/..."
cp -v "$SCRIPT_DIR/pihole-ipv6-dns-fix.sh" /usr/local/bin/pihole-ipv6-dns-fix.sh
chmod +x /usr/local/bin/pihole-ipv6-dns-fix.sh

# 2. Copiar unit file
log "Copiando serviço systemd..."
cp -v "$SCRIPT_DIR/pihole-ipv6-dns-fix.service" /etc/systemd/system/${SERVICE_NAME}.service

# 3. radvd: garantir Pi-hole como DNS IPv6 via Router Advertisement
if command -v radvd &>/dev/null; then
    log "Atualizando /etc/radvd.conf..."
    cp -v "$SCRIPT_DIR/radvd.conf" /etc/radvd.conf
    systemctl restart radvd
    systemctl enable radvd
    log "radvd reiniciado e habilitado"
else
    log "AVISO: radvd não instalado. IPv6 via RA não será anunciado."
    log "  Para instalar: apt install radvd"
fi

# 4. Habilitar e (re)iniciar serviço
log "Habilitando e iniciando ${SERVICE_NAME}..."
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
systemctl restart "${SERVICE_NAME}.service"

sleep 2
systemctl status "${SERVICE_NAME}.service" --no-pager -l

# 5. Verificação das regras ativas
log ""
log "=== VERIFICAÇÃO ==="
log "--- IPv4 iptables (porta 53) ---"
iptables -t nat -L PREROUTING -n -v --line-numbers | grep -E "dpt:53|pihole" || echo "  NENHUMA regra IPv4 ativa"

log "--- IPv6 ip6tables (porta 53) ---"
ip6tables -t nat -L PREROUTING -n -v --line-numbers | grep -E "dpt:53|pihole" || echo "  NENHUMA regra IPv6 ativa"

log ""
log "=== TESTE DE DNS ==="
if docker exec pihole pihole -q ads.google.com 2>/dev/null | head -3; then
    log "Pi-hole respondendo queries ✓"
else
    log "AVISO: não foi possível testar query no Pi-hole"
fi

log ""
log "=== CONCLUÍDO ==="
log "Novos dispositivos na rede usarão Pi-hole automaticamente (sem configuração manual)"
log "IPv4: iptables DNAT força porta 53 → 192.168.15.2"
log "IPv6: ip6tables DNAT força porta 53 → Pi-hole IPv6 + radvd anuncia via RA"
