#!/usr/bin/env bash
set -euo pipefail

LOGROTATE_BIN="${LOGROTATE_BIN:-/usr/sbin/logrotate}"
LOGROTATE_CONF="${LOGROTATE_CONF:-/usr/local/etc/logrotate-tape.conf}"
LOGROTATE_STATE="${LOGROTATE_STATE:-/var/lib/logrotate/tape.status}"
SPOOL_ROOT="${SPOOL_ROOT:-/var/spool/tape-log-buffer}"
SPOOL_INCOMING_DIR="${SPOOL_INCOMING_DIR:-$SPOOL_ROOT/incoming}"
SPOOL_ROUTES_DIR="${SPOOL_ROUTES_DIR:-$SPOOL_ROOT/routes}"
DEFAULT_ROUTE="${DEFAULT_ROUTE:-tape_sg1}"

log() {
    printf '%s tape-logrotate: %s\n' "$(date -Iseconds)" "$*"
}

if [[ ! -x "$LOGROTATE_BIN" ]]; then
    log "logrotate binary not found: $LOGROTATE_BIN"
    exit 1
fi

if [[ ! -f "$LOGROTATE_CONF" ]]; then
    log "logrotate config not found: $LOGROTATE_CONF"
    exit 1
fi

mkdir -p "$SPOOL_INCOMING_DIR" "$SPOOL_ROUTES_DIR/$DEFAULT_ROUTE"

mkdir -p "$(dirname "$LOGROTATE_STATE")"
log "running logrotate with state=$LOGROTATE_STATE conf=$LOGROTATE_CONF incoming=$SPOOL_INCOMING_DIR default_route=$DEFAULT_ROUTE"
"$LOGROTATE_BIN" -s "$LOGROTATE_STATE" "$LOGROTATE_CONF"

while IFS= read -r -d '' src; do
    base="$(basename "$src")"
    dst="$SPOOL_ROUTES_DIR/$DEFAULT_ROUTE/$base"
    stamp="${dst}.route"
    mv "$src" "$dst"
    printf '%s\n' "$DEFAULT_ROUTE" > "$stamp"
    log "stamped $base route=$DEFAULT_ROUTE"
done < <(find "$SPOOL_INCOMING_DIR" -maxdepth 1 -type f -print0 | sort -z)
