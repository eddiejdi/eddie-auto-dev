#!/bin/bash
# homelab-lan-gateway.sh — Mantém o homelab como gateway/DNS da LAN

set -euo pipefail

readonly LAN_NETWORK="${LAN_NETWORK:-192.168.15.0/24}"
readonly LAN_INTERFACE="${LAN_INTERFACE:-eth-onboard}"
readonly LAN_GATEWAY_IP="${LAN_GATEWAY_IP:-192.168.15.2}"
readonly VPN_INTERFACE="${VPN_INTERFACE:-nordlynx}"
readonly CHECK_CLIENT_IP="${CHECK_CLIENT_IP:-192.168.15.114}"
readonly NAT_COMMENT="homelab-lan-gateway-nat-vpn"
readonly FWD_OUT_COMMENT="homelab-lan-gateway-forward-out"
readonly FWD_IN_COMMENT="homelab-lan-gateway-forward-in"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ ERROR: $*" >&2; }
warn() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  WARNING: $*" >&2; }
success() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ $*"; }

require_root() {
    if [[ "$EUID" -ne 0 ]]; then
        error "Precisa ser root. Execute: sudo $0"
        exit 1
    fi
}

iptables_has() {
    local table="$1"
    shift
    iptables -t "$table" -C "$@" >/dev/null 2>&1
}

ensure_nat_rule() {
    if ! iptables_has nat POSTROUTING -s "$LAN_NETWORK" -o "$VPN_INTERFACE" -m comment --comment "$NAT_COMMENT" -j MASQUERADE; then
        iptables -t nat -A POSTROUTING -s "$LAN_NETWORK" -o "$VPN_INTERFACE" -m comment --comment "$NAT_COMMENT" -j MASQUERADE
        log "✓ NAT LAN->$VPN_INTERFACE aplicado"
    fi
}

ensure_forward_rules() {
    if ! iptables_has filter FORWARD -i "$LAN_INTERFACE" -o "$VPN_INTERFACE" -s "$LAN_NETWORK" -m comment --comment "$FWD_OUT_COMMENT" -j ACCEPT; then
        iptables -A FORWARD -i "$LAN_INTERFACE" -o "$VPN_INTERFACE" -s "$LAN_NETWORK" -m comment --comment "$FWD_OUT_COMMENT" -j ACCEPT
        log "✓ FORWARD LAN->$VPN_INTERFACE aplicado"
    fi

    if ! iptables_has filter FORWARD -i "$VPN_INTERFACE" -o "$LAN_INTERFACE" -d "$LAN_NETWORK" -m conntrack --ctstate ESTABLISHED,RELATED -m comment --comment "$FWD_IN_COMMENT" -j ACCEPT; then
        iptables -A FORWARD -i "$VPN_INTERFACE" -o "$LAN_INTERFACE" -d "$LAN_NETWORK" -m conntrack --ctstate ESTABLISHED,RELATED -m comment --comment "$FWD_IN_COMMENT" -j ACCEPT
        log "✓ FORWARD retorno $VPN_INTERFACE->LAN aplicado"
    fi
}

apply_gateway() {
    require_root

    sysctl -w net.ipv4.ip_forward=1 >/dev/null
    sysctl -w net.ipv4.conf.all.rp_filter=2 >/dev/null
    sysctl -w "net.ipv4.conf.${LAN_INTERFACE}.rp_filter=2" >/dev/null 2>&1 || true
    sysctl -w "net.ipv4.conf.${VPN_INTERFACE}.rp_filter=2" >/dev/null 2>&1 || true

    ensure_nat_rule
    ensure_forward_rules
}

check_interfaces() {
    if ! ip link show "$LAN_INTERFACE" >/dev/null 2>&1; then
        warn "Interface LAN $LAN_INTERFACE não encontrada"
        return 1
    fi

    if ! ip link show "$VPN_INTERFACE" >/dev/null 2>&1; then
        warn "Interface VPN $VPN_INTERFACE não encontrada"
        return 1
    fi

    return 0
}

check_lan_route() {
    if ! ip route show "$LAN_NETWORK" | grep -q "$LAN_INTERFACE"; then
        warn "LAN $LAN_NETWORK não está conectada em $LAN_INTERFACE"
        return 1
    fi

    return 0
}

check_client_path() {
    local route_output

    route_output="$(ip route get 1.1.1.1 from "$CHECK_CLIENT_IP" iif "$LAN_INTERFACE" 2>/dev/null || true)"
    if [[ "$route_output" != *"dev $VPN_INTERFACE"* ]]; then
        warn "Caminho da LAN para internet não está saindo por $VPN_INTERFACE"
        return 1
    fi

    return 0
}

check_nat_rules() {
    if ! iptables_has nat POSTROUTING -s "$LAN_NETWORK" -o "$VPN_INTERFACE" -m comment --comment "$NAT_COMMENT" -j MASQUERADE; then
        warn "NAT da LAN para $VPN_INTERFACE está ausente"
        return 1
    fi

    return 0
}

check_dns() {
    local public_dns local_dns

    public_dns="$(timeout 5 dig +time=2 +tries=1 @"$LAN_GATEWAY_IP" google.com +short 2>/dev/null | head -n1 || true)"
    local_dns="$(timeout 5 dig +time=2 +tries=1 @"$LAN_GATEWAY_IP" pi.hole +short 2>/dev/null | head -n1 || true)"

    if [[ -z "$public_dns" || -z "$local_dns" ]]; then
        warn "DNS do gateway não respondeu corretamente"
        return 1
    fi

    return 0
}

health_check() {
    log "=== HEALTH CHECK HOMELAB LAN GATEWAY ==="

    local status=0

    if check_interfaces; then
        success "✅ Interfaces LAN/VPN disponíveis"
    else
        status=1
    fi

    if check_lan_route; then
        success "✅ LAN $LAN_NETWORK presente em $LAN_INTERFACE"
    else
        status=1
    fi

    if check_client_path; then
        success "✅ Tráfego da LAN sai por $VPN_INTERFACE"
    else
        status=1
    fi

    if check_nat_rules; then
        success "✅ NAT LAN->$VPN_INTERFACE presente"
    else
        status=1
    fi

    if check_dns; then
        success "✅ DNS da LAN via $LAN_GATEWAY_IP operacional"
    else
        status=1
    fi

    return "$status"
}

ensure_gateway() {
    apply_gateway
    health_check
}

main() {
    local cmd="${1:---ensure}"

    case "$cmd" in
        --apply|--fix)
            apply_gateway
            health_check
            ;;
        --health-check|--check)
            health_check
            ;;
        --ensure)
            ensure_gateway
            ;;
        *)
            cat <<'EOF'
Uso: sudo ./homelab-lan-gateway.sh <comando>

Comandos:
  --ensure          Reaplica regras e valida gateway da LAN
  --apply           Aplica regras e valida
  --health-check    Apenas valida interfaces, NAT, caminho e DNS
EOF
            exit 1
            ;;
    esac
}

main "$@"
