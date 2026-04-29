#!/usr/bin/env bash
# ltfs-selfheal-remount.sh
# Runs on homelab (192.168.15.2). Manages LTFS on NAS (192.168.15.4) via SSH.
#
# Handles three failure modes introduced by sync_type=time,sync_time=300:
#
#   CASE 1 – Mount absent, no LTFS process
#     Normal down (crash, reboot). Action: restart ltfs-lto6.service.
#
#   CASE 2 – Stale fuse mount (findmnt ok, but process dead)
#     LTFS process died mid-sync; the fuse mount is a zombie.
#     Action: lazy unmount → restart service.
#
#   CASE 3 – Hung mid-sync (process alive, mount present, I/O timeout)
#     The periodic sync (every sync_time=300s) blocked the fuse layer.
#     Action: SIGTERM → wait grace period → SIGKILL → lazy unmount → restart.
#
#   CASE 4 – Mount present, I/O responsive
#     Healthy. Record metrics and exit 0.
#
# Result codes written to nas_ltfs_selfheal_last_result_code:
#   0 = healthy
#   1 = recovered (was unmounted, remounted OK)
#   2 = failed (all retries exhausted)
#   5 = stale fuse mount recovered
#   6 = hung mid-sync recovered

set -euo pipefail

NAS_HOST="${NAS_HOST:-root@192.168.15.4}"
MOUNTPOINT="${LTFS_MOUNT_POINT:-/mnt/tape/lto6}"
LTFS_SERVICE="${LTFS_SERVICE:-ltfs-lto6.service}"
LOG="${LTFS_SELFHEAL_LOG:-/var/log/ltfs-selfheal.log}"
NAS_TEXTFILE_DIR="${NAS_TEXTFILE_DIR:-/var/lib/prometheus/node-exporter}"
METRICS_FILE="${NAS_TEXTFILE_DIR}/ltfs_selfheal.prom"

IO_CHECK_TIMEOUT=15     # seconds before declaring I/O hung
SYNC_GRACE_PERIOD=60    # seconds to wait for in-flight sync before SIGKILL
MAX_RETRIES=3
RETRY_DELAY=5
FAILURES_FILE="/run/ltfs-selfheal-failures"

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
nas()  { ssh -o BatchMode=yes -o ConnectTimeout=10 "$NAS_HOST" "$@"; }

# ── Metrics ─────────────────────────────────────────────────────────────────

write_metrics() {
    local mount_up=$1 consecutive=$2 result_code=$3 io_hung=${4:-0}
    nas "mkdir -p ${NAS_TEXTFILE_DIR} && cat > ${METRICS_FILE}.tmp" <<EOF
# HELP nas_ltfs_mount_up 1 if LTFS is mounted and I/O responsive.
# TYPE nas_ltfs_mount_up gauge
nas_ltfs_mount_up{mountpoint="${MOUNTPOINT}"} ${mount_up}
# HELP nas_ltfs_io_hung 1 when LTFS mount exists but I/O did not respond within ${IO_CHECK_TIMEOUT}s.
# TYPE nas_ltfs_io_hung gauge
nas_ltfs_io_hung{mountpoint="${MOUNTPOINT}"} ${io_hung}
# HELP nas_ltfs_selfheal_consecutive_failures Number of consecutive failed recovery attempts.
# TYPE nas_ltfs_selfheal_consecutive_failures gauge
nas_ltfs_selfheal_consecutive_failures{mountpoint="${MOUNTPOINT}"} ${consecutive}
# HELP nas_ltfs_selfheal_last_result_code Last selfheal result: 0=ok 1=recovered 2=failed 5=stale 6=hung
# TYPE nas_ltfs_selfheal_last_result_code gauge
nas_ltfs_selfheal_last_result_code{mountpoint="${MOUNTPOINT}"} ${result_code}
EOF
    nas "mv ${METRICS_FILE}.tmp ${METRICS_FILE}" 2>/dev/null || true
}

read_failures() {
    [[ -f "$FAILURES_FILE" ]] && cat "$FAILURES_FILE" || echo 0
}

write_failures() { echo "$1" > "$FAILURES_FILE"; }

# ── Recovery ─────────────────────────────────────────────────────────────────

force_unmount_nas() {
    local pid=$1

    if [[ -n "$pid" ]]; then
        log "SIGTERM → LTFS pid=${pid} (aguardando ${SYNC_GRACE_PERIOD}s para sync finalizar)..."
        nas "kill -TERM ${pid}" 2>/dev/null || true
        local waited=0
        while [[ $waited -lt $SYNC_GRACE_PERIOD ]]; do
            sleep 5
            waited=$((waited + 5))
            if ! nas "kill -0 ${pid}" 2>/dev/null; then
                log "LTFS encerrou após ${waited}s (sync concluído normalmente)"
                break
            fi
        done
        if nas "kill -0 ${pid}" 2>/dev/null; then
            log "LTFS ainda vivo após ${SYNC_GRACE_PERIOD}s → SIGKILL"
            nas "kill -KILL ${pid}" 2>/dev/null || true
            sleep 2
        fi
    fi

    nas "
        if findmnt ${MOUNTPOINT} >/dev/null 2>&1; then
            fusermount -u -z ${MOUNTPOINT} 2>/dev/null || umount -l ${MOUNTPOINT} 2>/dev/null || true
        fi
        systemctl reset-failed ${LTFS_SERVICE} 2>/dev/null || true
    " || true
    sleep 2
}

do_remount() {
    local attempt=0
    while [[ $attempt -lt $MAX_RETRIES ]]; do
        attempt=$((attempt + 1))
        log "Tentativa ${attempt}/${MAX_RETRIES} — iniciando ${LTFS_SERVICE}..."
        nas "systemctl reset-failed ${LTFS_SERVICE} 2>/dev/null; systemctl start ${LTFS_SERVICE}" || true

        local t=0
        while [[ $t -lt 60 ]]; do
            sleep 4
            t=$((t + 4))
            if nas "findmnt ${MOUNTPOINT} >/dev/null 2>&1"; then
                log "✓ LTFS remontado (tentativa ${attempt}, ${t}s)"
                return 0
            fi
        done

        log "Tentativa ${attempt} falhou. Aguardando ${RETRY_DELAY}s..."
        sleep "$RETRY_DELAY"
    done
    log "✗ Falha ao remontar após ${MAX_RETRIES} tentativas"
    return 1
}

# ── Main ──────────────────────────────────────────────────────────────────────

log "=== LTFS Self-Heal (sync_type=time) — $(date) ==="

failures=$(read_failures)

# Reachability check
if ! nas "true" 2>/dev/null; then
    log "NAS ${NAS_HOST} inacessível via SSH — abortando"
    exit 0
fi

# Gather NAS state
is_mounted=false
ltfs_pid=""
nas "findmnt ${MOUNTPOINT} >/dev/null 2>&1" && is_mounted=true || true
ltfs_pid=$(nas "pgrep -f 'ltfs ${MOUNTPOINT}' 2>/dev/null | head -1" || true)

if $is_mounted; then
    # Check I/O responsiveness
    io_ok=false
    if nas "timeout ${IO_CHECK_TIMEOUT} ls ${MOUNTPOINT} >/dev/null 2>&1"; then
        io_ok=true
    fi

    if $io_ok; then
        log "LTFS OK — montado e I/O responsivo"
        write_failures 0
        write_metrics 1 0 0 0
        exit 0
    fi

    # I/O hung — classify
    if [[ -z "$ltfs_pid" ]]; then
        # CASE 2: Stale fuse mount
        log "AVISO: stale fuse mount — mount presente mas processo LTFS ausente"
        force_unmount_nas ""
        if do_remount; then
            write_failures 0
            write_metrics 1 0 5 0
        else
            failures=$((failures + 1))
            write_failures "$failures"
            write_metrics 0 "$failures" 2 0
        fi
    else
        # CASE 3: Hung mid-sync (sync_type=time hang)
        proc_age=$(nas "ps -o etimes= -p ${ltfs_pid} 2>/dev/null | tr -d ' '" || echo "?")
        log "AVISO: I/O travado — LTFS pid=${ltfs_pid} ativo há ${proc_age}s (sync hang)"
        force_unmount_nas "$ltfs_pid"
        if do_remount; then
            write_failures 0
            write_metrics 1 0 6 0
        else
            failures=$((failures + 1))
            write_failures "$failures"
            write_metrics 0 "$failures" 2 1
        fi
    fi
else
    if [[ -n "$ltfs_pid" ]]; then
        # Process alive but not mounted yet (rare — still starting up)
        log "LTFS processo ${ltfs_pid} em execução mas mount ausente — aguardando 30s"
        sleep 30
        if nas "findmnt ${MOUNTPOINT} >/dev/null 2>&1"; then
            log "LTFS montou enquanto aguardávamos — OK"
            write_failures 0
            write_metrics 1 0 0 0
            exit 0
        fi
        nas "kill -KILL ${ltfs_pid}" 2>/dev/null || true
        nas "systemctl reset-failed ${LTFS_SERVICE} 2>/dev/null" || true
    fi

    # CASE 1: Normal unmounted
    log "LTFS não montado — tentando remount"
    if do_remount; then
        write_failures 0
        write_metrics 1 0 1 0
    else
        failures=$((failures + 1))
        write_failures "$failures"
        write_metrics 0 "$failures" 2 0
    fi
fi

log "=== Self-Heal concluído. Falhas consecutivas: ${failures} ==="
[[ $failures -eq 0 ]] && exit 0 || exit 1
