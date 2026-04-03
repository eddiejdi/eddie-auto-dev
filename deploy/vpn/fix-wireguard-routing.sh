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

# Limpar TODAS as regras wg (com e sem comment) antes de re-aplicar (idempotência total)
log "Limpando regras wg existentes (com e sem comment)..."
# MASQUERADE — sem e com comment
while iptables -t nat -D POSTROUTING -s "$VPN_CIDR" -o "$LAN_IFACE" -j MASQUERADE 2>/dev/null; do :; done
while iptables -t nat -D POSTROUTING -s "$VPN_CIDR" -o "$LAN_IFACE" -j MASQUERADE \
    -m comment --comment "wg-vpn-masquerade" 2>/dev/null; do :; done
# FORWARD -i wg0 — sem e com comment
while iptables -D FORWARD -i "$WG_IFACE" -j ACCEPT 2>/dev/null; do :; done
while iptables -D FORWARD -i "$WG_IFACE" -j ACCEPT \
    -m comment --comment "wg-forward-in" 2>/dev/null; do :; done
# FORWARD -o wg0 — sem e com comment
while iptables -D FORWARD -o "$WG_IFACE" -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null; do :; done
while iptables -D FORWARD -o "$WG_IFACE" -m state --state RELATED,ESTABLISHED -j ACCEPT \
    -m comment --comment "wg-forward-out-related" 2>/dev/null; do :; done
log "Regras wg removidas — aplicando conjunto limpo"

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

# ─────────────────────────────────────────────
# 6. Registrar peer eddie-desktop (10.66.66.4) — idempotente
# ─────────────────────────────────────────────
readonly PEER_PUBKEY="GSm6NSpcvAGj82SgpP9xojo9aArBgeDXj6YT5Log0VA="
readonly PEER_PSK="ul52173PqbHCsEyQyOv31H7rItfYkKQF8SGGRS80xUs="
readonly PEER_IP="10.66.66.4/32"
readonly WG_CONF="/etc/wireguard/${WG_IFACE}.conf"

log "Verificando peer eddie-desktop..."
if wg show "${WG_IFACE}" peers 2>/dev/null | grep -q "${PEER_PUBKEY}"; then
    log "Peer eddie-desktop já registrado em runtime. OK."
else
    log "Adicionando peer eddie-desktop (${PEER_IP})..."
    PSK_FILE=$(mktemp)
    chmod 600 "${PSK_FILE}"
    echo "${PEER_PSK}" > "${PSK_FILE}"
    wg set "${WG_IFACE}" peer "${PEER_PUBKEY}" \
        preshared-key "${PSK_FILE}" \
        allowed-ips "${PEER_IP}" \
        persistent-keepalive 25
    rm -f "${PSK_FILE}"
    log "Peer adicionado em runtime."
fi

if ! grep -q "${PEER_PUBKEY}" "${WG_CONF}" 2>/dev/null; then
    cat >> "${WG_CONF}" << PEEREOF

# eddie-desktop (LMDE 7) — adicionado $(date -Iseconds)
[Peer]
PublicKey = ${PEER_PUBKEY}
PresharedKey = ${PEER_PSK}
AllowedIPs = ${PEER_IP}
PersistentKeepalive = 25
PEEREOF
    log "Peer persistido em ${WG_CONF}"
fi

log "=== Estado final do WireGuard ==="
wg show "${WG_IFACE}" | grep -E "peer|endpoint|allowed|handshake|transfer" || true
log "✅ Peer eddie-desktop garantido. IP VPN: 10.66.66.4"

# ─────────────────────────────────────────────
# 7. Exceções Pi-hole para NordVPN (bloqueia DNS privado)
# NordVPN adiciona regras OUTPUT que bloqueiam DNS para:
#   172.16.0.0/12 (inclui 172.18.x.x — rede Docker Pi-hole)
#   192.168.0.0/16 (inclui 192.168.15.2 — IP LAN do homelab)
# Precisa inserir ACCEPT NO INÍCIO (posição 1) das chains OUTPUT e FORWARD
# ─────────────────────────────────────────────
readonly PIHOLE_CIDR="172.18.0.0/16"    # rede Docker Pi-hole
readonly DOCKER_BRIDGE="br-1b94d522a7bc"  # bridge Docker do Pi-hole
readonly PIHOLE_HOST="192.168.15.2"     # IP LAN do homelab

log "Aplicando exceções Pi-hole contra bloqueio NordVPN..."

# Remover entradas antigas (idempotência)
while iptables -D OUTPUT -p udp --dport 53 -d "$PIHOLE_CIDR" -j ACCEPT \
    -m comment --comment "pihole-docker-dns-udp" 2>/dev/null; do :; done
while iptables -D OUTPUT -p tcp --dport 53 -d "$PIHOLE_CIDR" -j ACCEPT \
    -m comment --comment "pihole-docker-dns-tcp" 2>/dev/null; do :; done
while iptables -D FORWARD -o "$DOCKER_BRIDGE" -p udp --dport 53 -d "$PIHOLE_HOST" \
    -j ACCEPT -m comment --comment "pihole-lan-fwd-udp" 2>/dev/null; do :; done
while iptables -D FORWARD -o "$DOCKER_BRIDGE" -p tcp --dport 53 -d "$PIHOLE_HOST" \
    -j ACCEPT -m comment --comment "pihole-lan-fwd-tcp" 2>/dev/null; do :; done
while iptables -D FORWARD -o "$LAN_IFACE" -m conntrack --ctstate RELATED,ESTABLISHED \
    -j ACCEPT -m comment --comment "pihole-return-dns" 2>/dev/null; do :; done

# Inserir em posição 1 (antes das regras DROP do NordVPN)
iptables -I OUTPUT 1 -p udp --dport 53 -d "$PIHOLE_CIDR" -j ACCEPT \
    -m comment --comment "pihole-docker-dns-udp"
iptables -I OUTPUT 1 -p tcp --dport 53 -d "$PIHOLE_CIDR" -j ACCEPT \
    -m comment --comment "pihole-docker-dns-tcp"
iptables -I FORWARD 1 -o "$DOCKER_BRIDGE" -p udp --dport 53 -d "$PIHOLE_HOST" \
    -j ACCEPT -m comment --comment "pihole-lan-fwd-udp"
iptables -I FORWARD 1 -o "$DOCKER_BRIDGE" -p tcp --dport 53 -d "$PIHOLE_HOST" \
    -j ACCEPT -m comment --comment "pihole-lan-fwd-tcp"
iptables -I FORWARD 1 -o "$LAN_IFACE" -m conntrack --ctstate RELATED,ESTABLISHED \
    -j ACCEPT -m comment --comment "pihole-return-dns"

# Verificar INPUT para clientes VPN (DNS deve ser permitido de 10.66.66.0/24)
iptables -C INPUT -s "$VPN_CIDR" -p udp --dport 53 \
    -j ACCEPT -m comment --comment "pihole-dns-VPN" 2>/dev/null || \
iptables -A INPUT -s "$VPN_CIDR" -p udp --dport 53 \
    -j ACCEPT -m comment --comment "pihole-dns-VPN"
iptables -C INPUT -s "$VPN_CIDR" -p tcp --dport 53 \
    -j ACCEPT -m comment --comment "pihole-dns-tcp-VPN" 2>/dev/null || \
iptables -A INPUT -s "$VPN_CIDR" -p tcp --dport 53 \
    -j ACCEPT -m comment --comment "pihole-dns-tcp-VPN"

# Salvar regras persistidas
netfilter-persistent save 2>/dev/null || iptables-save > /etc/iptables/rules.v4

log "✅ Exceções Pi-hole aplicadas e persistidas."
