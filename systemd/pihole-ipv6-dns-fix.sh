#!/bin/bash
# Força redirecionamento de TODO DNS para Pi-hole (IPv4 + IPv6)
# Garante que novos dispositivos na rede NUNCA bypass o Pi-hole
#
# Problema 1: IPv4 — dispositivos com DNS manual (ex: 8.8.8.8) ou que recebem
#   DNS do roteador VIVOFIBRA bypassam o Pi-hole.
# Problema 2: IPv6 — dispositivos usam DNS IPv6 do roteador via Router
#   Advertisement (RA), bypassando o Pi-hole.
# Problema 3: Serviço pode iniciar antes do container pihole estar pronto.
#
# Solução: iptables + ip6tables DNAT intercepta TODO tráfego DNS (porta 53)
#   na interface LAN e redireciona para o Pi-hole, independente do DNS
#   configurado no dispositivo. Zero configuração necessária no cliente.
#
# Criado em 2026-03-04 | Atualizado em 2026-03-29: adicionado IPv4 DNAT

set -euo pipefail

readonly PIHOLE_IPV4="192.168.15.2"
readonly PIHOLE_IPV6="2804:7f0:9342:bca1:2e0:4cff:feb6:3d5e"
readonly PIHOLE_IPV6_LL="fe80::2e0:4cff:feb6:3d5e"
readonly LAN_IFACE="eth-onboard"
readonly VPN_CIDR="10.66.66.0/24"
readonly LAN_CIDR="192.168.15.0/24"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Aguardar container pihole estar healthy (máx 60s)
wait_pihole_ready() {
    local retries=0
    while [[ $retries -lt 12 ]]; do
        local status
        status=$(docker inspect --format='{{.State.Health.Status}}' pihole 2>/dev/null || echo "absent")
        if [[ "$status" == "healthy" ]]; then
            log "Pi-hole container saudável"
            return 0
        fi
        log "Aguardando Pi-hole ($status)... tentativa $((retries+1))/12"
        sleep 5
        retries=$((retries + 1))
    done
    log "AVISO: Pi-hole não ficou healthy em 60s, aplicando regras mesmo assim"
}

wait_pihole_ready

# =============================================================================
# IPv4 DNAT — força TODO DNS da LAN para o Pi-hole
# Novos dispositivos com DNS manual (8.8.8.8, 1.1.1.1, etc.) são interceptados
# =============================================================================
add4() {
    local proto="$1" pos="$2"
    iptables -t nat -C PREROUTING -i "$LAN_IFACE" -p "$proto" --dport 53 \
        ! -d "$PIHOLE_IPV4" -j DNAT --to-destination "${PIHOLE_IPV4}:53" 2>/dev/null || \
    iptables -t nat -I PREROUTING "$pos" -i "$LAN_IFACE" -p "$proto" --dport 53 \
        ! -d "$PIHOLE_IPV4" -j DNAT --to-destination "${PIHOLE_IPV4}:53" \
        -m comment --comment "pihole-force-dns-${proto}"
}
add4 udp 1
add4 tcp 2

# VPN WireGuard também interceptada
add4vpn() {
    local proto="$1" pos="$2"
    iptables -t nat -C PREROUTING -s "$VPN_CIDR" -p "$proto" --dport 53 \
        ! -d "$PIHOLE_IPV4" -j DNAT --to-destination "${PIHOLE_IPV4}:53" 2>/dev/null || \
    iptables -t nat -I PREROUTING "$pos" -s "$VPN_CIDR" -p "$proto" --dport 53 \
        ! -d "$PIHOLE_IPV4" -j DNAT --to-destination "${PIHOLE_IPV4}:53" \
        -m comment --comment "pihole-force-dns-vpn-${proto}"
}
add4vpn udp 3
add4vpn tcp 4

log "IPv4 DNS DNAT aplicado — toda porta 53 LAN/VPN → ${PIHOLE_IPV4}"

# =============================================================================
# IPv6 DNAT — intercepta DNS IPv6 (resolve DNS leak via Router Advertisement)
# =============================================================================
add6() {
    local proto="$1" dest="$2" pos="$3"
    ip6tables -t nat -C PREROUTING -p "$proto" --dport 53 \
        ! -d "$dest" -j DNAT --to-destination "[${dest}]:53" 2>/dev/null || \
    ip6tables -t nat -I PREROUTING "$pos" -p "$proto" --dport 53 \
        ! -d "$dest" -j DNAT --to-destination "[${dest}]:53" \
        -m comment --comment "pihole-force-dns6-${proto}"
}

# Endereço global
add6 udp "$PIHOLE_IPV6" 1
add6 tcp "$PIHOLE_IPV6" 2

# Link-local (fallback estável para alguns dispositivos)
add6 udp "$PIHOLE_IPV6_LL" 3
add6 tcp "$PIHOLE_IPV6_LL" 4

# MASQUERADE IPv6 para respostas voltarem corretamente
ip6tables -t nat -C POSTROUTING -p udp --dport 53 -j MASQUERADE 2>/dev/null || \
ip6tables -t nat -A POSTROUTING -p udp --dport 53 -j MASQUERADE

ip6tables -t nat -C POSTROUTING -p tcp --dport 53 -j MASQUERADE 2>/dev/null || \
ip6tables -t nat -A POSTROUTING -p tcp --dport 53 -j MASQUERADE

log "IPv6 DNS DNAT aplicado — toda porta 53 → [${PIHOLE_IPV6}]"

# =============================================================================
# DoT (DNS-over-TLS porta 853) — libera entrada para Pi-hole receber
# Necessário para Android "Private DNS" apontar para Pi-hole
# =============================================================================
iptables -C INPUT -p tcp --dport 853 -s "$LAN_CIDR" -j ACCEPT 2>/dev/null || \
iptables -I INPUT 1 -p tcp --dport 853 -s "$LAN_CIDR" -j ACCEPT \
  -m comment --comment "pihole-DoT-LAN"

iptables -C INPUT -p tcp --dport 853 -s "$VPN_CIDR" -j ACCEPT 2>/dev/null || \
iptables -I INPUT 2 -p tcp --dport 853 -s "$VPN_CIDR" -j ACCEPT \
  -m comment --comment "pihole-DoT-VPN"

log "DoT firewall rules aplicadas"
log "=== TODAS AS REGRAS DNS ATIVAS — novos dispositivos usarão Pi-hole automaticamente ==="
