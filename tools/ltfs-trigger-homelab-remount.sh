#!/bin/bash
set -euo pipefail

HOMELAB_HOST="${HOMELAB_HOST:-192.168.15.2}"
HOMELAB_USER="${HOMELAB_USER:-homelab}"
SSH_KEY="${SSH_KEY:-/root/.ssh/homelab_key}"
REMOTE_SCRIPT="${REMOTE_SCRIPT:-/usr/local/sbin/ltfs-nfs-remount.sh}"
TAPE_LOG_ROOT="${TAPE_LOG_ROOT:-/mnt/tape_sg0/logs}"
if [[ ! -d "$TAPE_LOG_ROOT" ]] || [[ ! -w "$TAPE_LOG_ROOT" ]]; then
    TAPE_LOG_ROOT="${TAPE_LOG_FALLBACK:-/var/log}"
fi
LOG="${LOG:-$TAPE_LOG_ROOT/ltfs-lto6.log}"

log() {
    echo "$(date -Iseconds) ltfs-trigger-homelab-remount: $*" | tee -a "$LOG"
}

if [[ ! -r "$SSH_KEY" ]]; then
    log "AVISO: chave SSH ausente em $SSH_KEY; remount homelab ignorado"
    exit 0
fi

log "Aguardando 10s para LTFS estabilizar antes de triggrar remount homelab..."
sleep 10

log "Triggando remount LTFS no homelab $HOMELAB_HOST..."
if ssh -i "$SSH_KEY" \
    -o StrictHostKeyChecking=no \
    -o BatchMode=yes \
    -o ConnectTimeout=15 \
    "${HOMELAB_USER}@${HOMELAB_HOST}" \
    "sudo -n ${REMOTE_SCRIPT}"
then
    log "Remount homelab OK"
else
    log "AVISO: remount homelab falhou (não crítico para LTFS local)"
fi

exit 0
