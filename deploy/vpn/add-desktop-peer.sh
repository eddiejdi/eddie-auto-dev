#!/bin/bash
# add-desktop-peer.sh — Adiciona peer eddie-desktop (10.66.66.4) ao servidor WireGuard
# Idempotente — verifica se o peer já existe antes de adicionar.
# Uso: sudo bash add-desktop-peer.sh

set -euo pipefail

readonly WG_IFACE="wg0"
readonly WG_CONF="/etc/wireguard/${WG_IFACE}.conf"
readonly PEER_PUBKEY="GSm6NSpcvAGj82SgpP9xojo9aArBgeDXj6YT5Log0VA="
readonly PEER_PSK="ul52173PqbHCsEyQyOv31H7rItfYkKQF8SGGRS80xUs="
readonly PEER_IP="10.66.66.4/32"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

if [[ "$EUID" -ne 0 ]]; then
    echo "Execute como root: sudo $0" >&2
    exit 1
fi

# Verificar se o peer já existe
if wg show "$WG_IFACE" peers 2>/dev/null | grep -q "$PEER_PUBKEY"; then
    log "Peer eddie-desktop já existe no wg0. Nada a fazer."
    wg show "$WG_IFACE" | grep -A4 "$PEER_PUBKEY"
    exit 0
fi

log "Adicionando peer eddie-desktop (${PEER_IP})..."

# Salvar PSK em arquivo temporário seguro
PSK_FILE=$(mktemp)
chmod 600 "$PSK_FILE"
echo "$PEER_PSK" > "$PSK_FILE"

# Adicionar peer em runtime
wg set "$WG_IFACE" peer "$PEER_PUBKEY" \
    preshared-key "$PSK_FILE" \
    allowed-ips "$PEER_IP" \
    persistent-keepalive 25

rm -f "$PSK_FILE"

# Persistir no arquivo de config (se não estiver lá)
if ! grep -q "$PEER_PUBKEY" "$WG_CONF" 2>/dev/null; then
    cat >> "$WG_CONF" << EOF

# eddie-desktop (LMDE 7) — adicionado $(date -Iseconds)
[Peer]
PublicKey = ${PEER_PUBKEY}
PresharedKey = ${PEER_PSK}
AllowedIPs = ${PEER_IP}
PersistentKeepalive = 25
EOF
    log "Peer persistido em ${WG_CONF}"
else
    log "Peer já estava no arquivo de config"
fi

log "=== Peer adicionado ==="
wg show "$WG_IFACE" | grep -A5 "$PEER_PUBKEY"
echo ""
log "eddie-desktop pode conectar com IP 10.66.66.4"
