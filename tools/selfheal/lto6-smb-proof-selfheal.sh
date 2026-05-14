#!/usr/bin/env bash
set -euo pipefail

UNIT="mnt-lto6\\x2dsmb\\x2dproof.mount"
MOUNT_POINT="/mnt/lto6-smb-proof"
NAS_IP="192.168.15.4"
DRAIN_SCRIPT="/usr/local/sbin/lto6-drain-backups"
LOG="lto6-smb-proof-selfheal"

is_accessible() {
    timeout 5 ls "$MOUNT_POINT" &>/dev/null
}

if mountpoint -q "$MOUNT_POINT"; then
    if is_accessible; then
        logger -t "$LOG" "mount healthy, nothing to do"
        exit 0
    fi
    logger -t "$LOG" "stale mount detected — forcing unmount"
    umount -f -l "$MOUNT_POINT" 2>/dev/null || true
    sleep 2
fi

logger -t "$LOG" "mount is down — clearing stale processes"

# Matar drain e rsync que podem estar em D< sobre o mount stale.
# SIGKILL em D< não é processado até o kernel liberar o I/O — por isso
# também reiniciamos smbd na NAS para fechar a TCP e desbloquear o kernel.
pkill -9 -f "$DRAIN_SCRIPT" 2>/dev/null || true
pkill -9 -f "rsync.*lto6-smb-proof" 2>/dev/null || true
pkill -9 -f "mount\.cifs.*LTO6_CACHE" 2>/dev/null || true

# Fechar sessão SMB da NAS para desbloquear processos D< no kernel CIFS.
# Sem isso, mount.cifs fica em D< indefinidamente e impede o remount.
if ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
       root@"$NAS_IP" "systemctl restart smbd" 2>/dev/null; then
    logger -t "$LOG" "smbd reiniciado na NAS para liberar sessão stale"
else
    logger -t "$LOG" "WARN: não foi possível reiniciar smbd na NAS via SSH"
fi

# Aguardar processos D< serem liberados pelo kernel (até 15s)
for i in $(seq 1 15); do
    if ! pgrep -f "mount\.cifs.*LTO6_CACHE" > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

systemctl reset-failed "$UNIT" 2>/dev/null || true
logger -t "$LOG" "remontando $UNIT"
systemctl restart "$UNIT"

# Verificar
sleep 5
if mountpoint -q "$MOUNT_POINT" && is_accessible; then
    logger -t "$LOG" "mount restaurado com sucesso"
    # Reiniciar drain se houver snapshots pendentes
    if [[ -x "$DRAIN_SCRIPT" ]]; then
        nohup "$DRAIN_SCRIPT" >> /tmp/lto6-drain-selfheal.log 2>&1 &
        logger -t "$LOG" "drain reiniciado (PID $!)"
    fi
else
    logger -t "$LOG" "ERROR: mount não voltou após restart"
    exit 1
fi
