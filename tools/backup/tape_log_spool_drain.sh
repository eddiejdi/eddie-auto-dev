#!/usr/bin/env bash
set -euo pipefail

RSYNC_BIN="${RSYNC_BIN:-/usr/bin/rsync}"
SPOOL_ROOT="${SPOOL_ROOT:-/var/spool/tape-log-buffer}"
ROUTE_NAME="${ROUTE_NAME:-tape_sg1}"
ROUTE_QUEUE_DIR="${ROUTE_QUEUE_DIR:-$SPOOL_ROOT/routes/$ROUTE_NAME}"
ROUTE_TARGET_ROOT="${ROUTE_TARGET_ROOT:-/mnt/tape_sg1/logs}"
REQUIRE_MOUNTPOINT="${REQUIRE_MOUNTPOINT:-}"

log() {
    printf '%s tape-log-drain: %s\n' "$(date -Iseconds)" "$*"
}

if [[ ! -x "$RSYNC_BIN" ]]; then
    log "rsync binary not found: $RSYNC_BIN"
    exit 1
fi

mkdir -p "$ROUTE_QUEUE_DIR"

if ! find "$ROUTE_QUEUE_DIR" -maxdepth 1 -type f ! -name '*.route' | grep -q .; then
    log "route queue empty: route=$ROUTE_NAME dir=$ROUTE_QUEUE_DIR"
    exit 0
fi

if ! timeout 10 ls -ld "$ROUTE_TARGET_ROOT" >/dev/null 2>&1; then
    log "route target not accessible: route=$ROUTE_NAME target=$ROUTE_TARGET_ROOT"
    exit 1
fi

if [[ -n "$REQUIRE_MOUNTPOINT" ]] && ! mountpoint -q "$REQUIRE_MOUNTPOINT"; then
    log "required mountpoint is not mounted: route=$ROUTE_NAME mountpoint=$REQUIRE_MOUNTPOINT target=$ROUTE_TARGET_ROOT"
    exit 1
fi

total_ok=0
total_fail=0

while IFS= read -r -d '' src; do
    base="$(basename "$src")"
    stamp="${src}.route"
    if [[ ! -f "$stamp" ]]; then
        log "missing route stamp for $base"
        (( total_fail++ )) || true
        continue
    fi

    stamped_route="$(tr -d '\n' < "$stamp" 2>/dev/null || true)"
    if [[ "$stamped_route" != "$ROUTE_NAME" ]]; then
        log "route mismatch for $base: stamp=$stamped_route expected=$ROUTE_NAME"
        (( total_fail++ )) || true
        continue
    fi

    log "syncing $base route=$ROUTE_NAME -> $ROUTE_TARGET_ROOT/"
    rsync_exit=0
    "$RSYNC_BIN" \
        --archive \
        --ignore-existing \
        --remove-source-files \
        --timeout=300 \
        "$src" "$ROUTE_TARGET_ROOT/" || rsync_exit=$?

    if [[ $rsync_exit -eq 0 ]]; then
        log "OK $base"
        rm -f "$stamp"
        (( total_ok++ )) || true
    else
        log "FAILED $base (rsync exit $rsync_exit)"
        (( total_fail++ )) || true
    fi
done < <(find "$ROUTE_QUEUE_DIR" -maxdepth 1 -type f ! -name '*.route' -print0 | sort -z)

log "drain complete: route=$ROUTE_NAME synced=$total_ok failed=$total_fail"
[[ $total_fail -eq 0 ]]
