#!/bin/bash
# fix-wireguard-routing.sh — Corrige roteamento NAT/FORWARD para WireGuard
#
# Problema: Celular conecta ao WireGuard mas nenhum tráfego passa.
# O servidor tinha apenas regras de DNS (pihole-ipv6-dns-fix.sh) mas
# faltavam MASQUERADE e FORWARD para tráfego geral da VPN.
#
# Este script:
#   1. Habilita ip_forward (IPv4 + IPv6)
#   2. Adiciona MASQUERADE na POSTROUTING para VPN → internet
#   3. Adiciona FORWARD ACCEPT para wg0
#   4. Persiste via sysctl.d
#
# Uso: sudo bash fix-wireguard-routing.sh
# Idempotente — pode ser executado múltiplas vezes sem duplicar regras.

set -euo pipefail

readonly WG_IFACE="wg0"
readonly VPN_CIDR="10.66.66.0/24"
readonly LAN_IFACE="eth-onboard"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Verificar root
if [[ "$EUID" -ne 0 ]]; then
    echo "Execute como root: sudo $0" >&2
    exit 1
fi

# ─────────────────────────────────────────────
# 1. IP Forwarding (persistente)
# ─────────────────────────────────────────────
log "Habilitando IP forwarding..."

sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv6.conf.all.forwarding=1

# Persistir
cat > /etc/sysctl.d/99-wireguard-forward.conf << 'EOF'
# WireGuard VPN — habilita forwarding de pacotes
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
EOF

log "IP forwarding habilitado e persistido em /etc/sysctl.d/99-wireguard-forward.conf"

# ─────────────────────────────────────────────
# 2. NAT MASQUERADE — VPN → Internet
# Sem isso, pacotes saem com IP 10.66.66.x e
# são descartados pelo roteador/ISP
# ─────────────────────────────────────────────
log "Configurando NAT MASQUERADE..."

# Limpar regras legadas duplicadas (sem comment) antes de re-aplicar
log "Limpando regras legadas sem comment tag..."
while iptables -t nat -D POSTROUTING -s "$VPN_CIDR" -o "$LAN_IFACE" -j MASQUERADE 2>/dev/null; do :; done
while iptables -D FORWARD -i "$WG_IFACE" -j ACCEPT 2>/dev/null; do :; done
while iptables -D FORWARD -o "$WG_IFACE" -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null; do :; done
log "Regras legadas removidas"

# IPv4: VPN → LAN interface (para internet e rede local)
iptables -t nat -C POSTROUTING -s "$VPN_CIDR" -o "$LAN_IFACE" -j MASQUERADE \
    -m comment --comment "wg-vpn-masquerade" 2>/dev/null || \
iptables -t nat -A POSTROUTING -s "$VPN_CIDR" -o "$LAN_IFACE" -j MASQUERADE \
    -m comment --comment "wg-vpn-masquerade"

log "MASQUERADE: $VPN_CIDR → $LAN_IFACE"

# ─────────────────────────────────────────────
# 3. FORWARD — permite tráfego bidirecional wg0
# ─────────────────────────────────────────────
log "Configurando regras FORWARD..."

# Tráfego entrando pelo wg0 → pode sair para qualquer destino
iptables -C FORWARD -i "$WG_IFACE" -j ACCEPT \
    -m comment --comment "wg-forward-in" 2>/dev/null || \
iptables -A FORWARD -i "$WG_IFACE" -j ACCEPT \
    -m comment --comment "wg-forward-in"

# Tráfego de resposta voltando para wg0
iptables -C FORWARD -o "$WG_IFACE" -m state --state RELATED,ESTABLISHED -j ACCEPT \
    -m comment --comment "wg-forward-out-related" 2>/dev/null || \
iptables -A FORWARD -o "$WG_IFACE" -m state --state RELATED,ESTABLISHED -j ACCEPT \
    -m comment --comment "wg-forward-out-related"

log "FORWARD: wg0 ↔ bidirecional habilitado"

# ─────────────────────────────────────────────
# 4. Verificar que wg0 está ativo
# ─────────────────────────────────────────────
if ip link show "$WG_IFACE" &>/dev/null; then
    log "Interface $WG_IFACE está UP"
    wg show "$WG_IFACE" | grep -E "peer|endpoint|allowed|handshake|transfer" || true
else
    log "AVISO: Interface $WG_IFACE não encontrada. Iniciando..."
    if [[ -f "/etc/wireguard/${WG_IFACE}.conf" ]]; then
        wg-quick up "$WG_IFACE"
        log "wg0 iniciado"
    else
        log "ERRO: /etc/wireguard/${WG_IFACE}.conf não encontrado"
        exit 1
    fi
fi

# ─────────────────────────────────────────────
# 5. Resumo das regras aplicadas
# ─────────────────────────────────────────────
log "=== Resumo ==="
echo ""
echo "sysctl:"
sysctl net.ipv4.ip_forward net.ipv6.conf.all.forwarding
echo ""
echo "NAT POSTROUTING:"
iptables -t nat -L POSTROUTING -v -n | grep -E "wg|MASQ|${VPN_CIDR}" || echo "  (nenhuma regra VPN)"
echo ""
echo "FORWARD:"
iptables -L FORWARD -v -n | grep -E "wg|${WG_IFACE}" || echo "  (nenhuma regra wg0)"
echo ""

log "✅ Roteamento WireGuard corrigido. Teste no celular agora."
