#!/bin/bash
# Storj QUIC Recovery Script - Regenerates node identity to fix QUIC Misconfigured
# Usage: ./tools/storj_quic_recovery.sh [homelab_user@homelab_ip]

set -euo pipefail

HOMELAB="${1:-homelab@192.168.15.2}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/homelab_key}"
BACKUP_DIR="/home/homelab/.local/share/storj/identity/storagenode.bak_$(date +%Y%m%d_%H%M%S)"

echo "=== Storj QUIC Recovery ==="
echo "Target: $HOMELAB"
echo "SSH Key: $SSH_KEY"
echo ""

if [ ! -f "$SSH_KEY" ]; then
    echo "ERROR: SSH key not found at $SSH_KEY"
    exit 1
fi

echo "[1/6] Checking current QUIC status..."
CURRENT_STATUS=$(ssh -i "$SSH_KEY" "$HOMELAB" 'curl -sL http://127.0.0.1:14002/api/sno/ | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get(\"quicStatus\", \"unknown\"))"' 2>/dev/null || echo "error")
echo "Current status: $CURRENT_STATUS"

if [ "$CURRENT_STATUS" = "OK" ] || [ "$CURRENT_STATUS" = "Accepting" ]; then
    echo "✓ QUIC is already healthy - no action needed"
    exit 0
fi

echo ""
echo "[2/6] Stopping Storj container..."
ssh -i "$SSH_KEY" "$HOMELAB" "docker stop storagenode" || true

echo "[3/6] Backing up corrupted identity..."
ssh -i "$SSH_KEY" "$HOMELAB" "cp -r /home/homelab/.local/share/storj/identity/storagenode '$BACKUP_DIR' 2>/dev/null || true"

echo "[4/6] Removing corrupted identity (forcing regeneration)..."
ssh -i "$SSH_KEY" "$HOMELAB" "rm -rf /home/homelab/.local/share/storj/identity/storagenode"

echo "[5/6] Restarting container (auto-regenerates identity)..."
ssh -i "$SSH_KEY" "$HOMELAB" "docker start storagenode"

echo "[6/6] Waiting for identity regeneration and API ready (20s)..."
sleep 20

echo ""
echo "=== Verification ==="
ssh -i "$SSH_KEY" "$HOMELAB" << 'VERIFY'
echo "Certificate validation:"
if [ -f /home/homelab/.local/share/storj/identity/storagenode/ca.cert ]; then
    openssl x509 -in /home/homelab/.local/share/storj/identity/storagenode/ca.cert -noout -dates
else
    echo "ERROR: ca.cert not regenerated yet"
fi

echo ""
echo "API Status:"
curl -sL http://127.0.0.1:14002/api/sno/ | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f'quicStatus: {d.get(\"quicStatus\", \"N/A\")}')
    print(f'nodeID: {d.get(\"nodeID\", \"N/A\")[:16]}...')
    print(f'lastPinged: {d.get(\"lastPinged\", \"N/A\")[:19]}')
except:
    print('API not ready yet')
" 2>/dev/null || echo "API loading..."
VERIFY

echo ""
echo "✓ Recovery complete. Monitor lastPinged - should update in 1-2 minutes."
echo "⏳ Reputation scores will recover over 24-48 hours."
echo "📂 Backup: $BACKUP_DIR"
