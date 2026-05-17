#!/bin/bash
set -euo pipefail

TAPE_LOG_ROOT="${TAPE_LOG_ROOT:-/mnt/tape_sg0/logs}"
if [ ! -d "$TAPE_LOG_ROOT" ] || [ ! -w "$TAPE_LOG_ROOT" ]; then
    TAPE_LOG_ROOT="${TAPE_LOG_FALLBACK:-/var/log}"
fi
LOG="${LOG:-$TAPE_LOG_ROOT/ltfs-nfs-remount.log}"
BASE_MOUNT="${BASE_MOUNT:-/mnt/lto6}"
BASE_SOURCE="${BASE_SOURCE:-192.168.15.4:/mnt/tape/lto6}"
BASE_OPTS="${BASE_OPTS:-rw,hard,nfsvers=4.2,actimeo=0,lookupcache=none,timeo=600,retrans=2,_netdev,nofail}"
NC_MOUNT="${NC_MOUNT:-/mnt/lto6-nc}"
NC_CONTAINER="${NC_CONTAINER:-nextcloud-app}"

log() {
    echo "$(date -Iseconds) ltfs-nfs-remount: $*" | tee -a "$LOG"
}

mount_usable() {
    local mp="$1"
    findmnt "$mp" >/dev/null 2>&1 && timeout 5 ls -d "$mp" >/dev/null 2>&1
}

mount_source_for() {
    local mp="$1"
    findmnt -rn -T "$mp" -o SOURCE 2>/dev/null | head -n1
}

fstab_uses_ltfs_for_nc() {
    grep -Eq '^[^#].*192\.168\.15\.4:/mnt/tape/lto6[[:space:]]+/mnt/lto6-nc[[:space:]]+nfs4' /etc/fstab
}

remount_nfs() {
    local source="$1"
    local target="$2"
    local opts="$3"

    umount -l "$target" 2>/dev/null || umount -f "$target" 2>/dev/null || true
    rm -rf "$target" 2>/dev/null || true
    mkdir -p "$target"
    mount -t nfs4 -o "$opts" "$source" "$target"
}

log "=== Disparado pelo NAS LTFS ==="

log "Remontando $BASE_MOUNT a partir de $BASE_SOURCE..."
if remount_nfs "$BASE_SOURCE" "$BASE_MOUNT" "$BASE_OPTS"; then
    log "$BASE_MOUNT remontado OK"
else
    log "ERRO: falha ao remontar $BASE_MOUNT"
    exit 1
fi

if ! mount_usable "$BASE_MOUNT"; then
    log "ERRO: $BASE_MOUNT montou mas permanece inacessível"
    exit 1
fi

if fstab_uses_ltfs_for_nc; then
    log "$NC_MOUNT está configurado para apontar direto ao LTFS; reiniciando consumer"
    nc_was_running=0
    if docker ps --format "{{.Names}}" | grep -q "^${NC_CONTAINER}$"; then
        log "Parando $NC_CONTAINER..."
        docker stop "$NC_CONTAINER" >> "$LOG" 2>&1
        nc_was_running=1
    fi

    if remount_nfs "$BASE_SOURCE" "$NC_MOUNT" "$BASE_OPTS"; then
        log "$NC_MOUNT remontado OK"
    else
        log "ERRO: falha ao remontar $NC_MOUNT"
        exit 1
    fi

    if [[ "$nc_was_running" == "1" ]]; then
        log "Iniciando $NC_CONTAINER..."
        docker start "$NC_CONTAINER" >> "$LOG" 2>&1 && log "$NC_CONTAINER iniciado OK" || \
            log "ERRO: falha ao iniciar $NC_CONTAINER"
    fi
else
    log "$NC_MOUNT permanece no pipeline local de staging; sem remount de Nextcloud"
fi

log "Remount concluído"
