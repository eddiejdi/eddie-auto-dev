#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${OUT_DIR:-/var/lib/prometheus/node-exporter}"
OUT_FILE="${OUT_FILE:-$OUT_DIR/lto6.prom}"
TMP_FILE="$(mktemp "${OUT_DIR}/lto6.prom.XXXXXX")"

MOUNTPOINT="${MOUNTPOINT:-/mnt/tape/lto6}"
SERVICE="${SERVICE:-ltfs-lto6.service}"
SGDEV="${SGDEV:-/dev/tape/by-id/scsi-HUL831AMRM-sg}"
DRIVE_ID="${DRIVE_ID:-HUL831AMRM}"

cleanup() {
  rm -f "$TMP_FILE"
}
trap cleanup EXIT

service_up=0
mount_up=0
read_only=0
size_bytes=0
used_bytes=0
avail_bytes=0
drive_ready=-1
medium_loaded=-1
compression_enabled=-1
write_timeouts_24h=0
fc_abort_events_24h=0

if systemctl is-active --quiet "$SERVICE"; then
  service_up=1
fi

if findmnt "$MOUNTPOINT" >/dev/null 2>&1; then
  mount_up=1
  read -r size_bytes used_bytes avail_bytes <<EOF || true
$(df -B1 --output=size,used,avail "$MOUNTPOINT" 2>/dev/null | awk 'NR == 2 {print $1, $2, $3}')
EOF
  size_bytes="${size_bytes:-0}"
  used_bytes="${used_bytes:-0}"
  avail_bytes="${avail_bytes:-0}"
fi

main_pid="$(systemctl show --property MainPID --value "$SERVICE" 2>/dev/null || echo 0)"
if [[ "${main_pid:-0}" =~ ^[0-9]+$ ]] && [ "$main_pid" -gt 0 ]; then
  if journalctl _PID="$main_pid" --grep='Dropping to read-only mode' -n 1 --no-pager >/dev/null 2>&1; then
    read_only=1
  fi
fi

write_timeouts_24h="$(journalctl -u "$SERVICE" --since '-24 hours' --no-pager 2>/dev/null | grep -c 'WRITE returns Command TIMEOUT' || true)"
fc_abort_events_24h="$(journalctl -k --since '-24 hours' --no-pager 2>/dev/null | grep -c 'qla2xxx .*Abort command issued' || true)"

mt_output="$(timeout 10 mt -f /dev/nst0 status 2>/dev/null || true)"
if grep -q ' ONLINE' <<<"$mt_output"; then
  drive_ready=1
  medium_loaded=1
elif grep -q ' DR_OPEN' <<<"$mt_output" || grep -q ' no tape loaded' <<<"$mt_output"; then
  drive_ready=0
  medium_loaded=0
fi

tapeinfo_output="$(timeout 3 tapeinfo -f "$SGDEV" 2>/dev/null || true)"
if grep -q 'DataCompEnabled: yes' <<<"$tapeinfo_output"; then
  compression_enabled=1
elif grep -q 'DataCompEnabled: no' <<<"$tapeinfo_output"; then
  compression_enabled=0
fi

cat >"$TMP_FILE" <<EOF
# HELP nas_ltfs_service_up LTFS systemd service state on the NAS.
# TYPE nas_ltfs_service_up gauge
nas_ltfs_service_up{service="${SERVICE}"} ${service_up}
# HELP nas_ltfs_mount_up LTFS mount availability on the NAS.
# TYPE nas_ltfs_mount_up gauge
nas_ltfs_mount_up{mountpoint="${MOUNTPOINT}"} ${mount_up}
# HELP nas_ltfs_read_only LTFS mount dropped to read-only mode in the current mount session.
# TYPE nas_ltfs_read_only gauge
nas_ltfs_read_only{mountpoint="${MOUNTPOINT}"} ${read_only}
# HELP nas_ltfs_size_bytes LTFS total capacity in bytes.
# TYPE nas_ltfs_size_bytes gauge
nas_ltfs_size_bytes{mountpoint="${MOUNTPOINT}"} ${size_bytes}
# HELP nas_ltfs_used_bytes LTFS used capacity in bytes.
# TYPE nas_ltfs_used_bytes gauge
nas_ltfs_used_bytes{mountpoint="${MOUNTPOINT}"} ${used_bytes}
# HELP nas_ltfs_avail_bytes LTFS available capacity in bytes.
# TYPE nas_ltfs_avail_bytes gauge
nas_ltfs_avail_bytes{mountpoint="${MOUNTPOINT}"} ${avail_bytes}
# HELP nas_tape_drive_ready Tape drive readiness according to tapeinfo.
# TYPE nas_tape_drive_ready gauge
nas_tape_drive_ready{device="${DRIVE_ID}"} ${drive_ready}
# HELP nas_tape_medium_loaded Tape medium presence according to tapeinfo.
# TYPE nas_tape_medium_loaded gauge
nas_tape_medium_loaded{device="${DRIVE_ID}"} ${medium_loaded}
# HELP nas_tape_compression_enabled Tape hardware compression state according to tapeinfo.
# TYPE nas_tape_compression_enabled gauge
nas_tape_compression_enabled{device="${DRIVE_ID}"} ${compression_enabled}
# HELP nas_ltfs_write_timeout_events_24h LTFS write timeout events seen in the last 24 hours.
# TYPE nas_ltfs_write_timeout_events_24h gauge
nas_ltfs_write_timeout_events_24h{service="${SERVICE}"} ${write_timeouts_24h}
# HELP nas_fc_abort_events_24h qla2xxx abort events seen in the last 24 hours.
# TYPE nas_fc_abort_events_24h gauge
nas_fc_abort_events_24h{driver="qla2xxx"} ${fc_abort_events_24h}
EOF

chmod 0644 "$TMP_FILE"
mv "$TMP_FILE" "$OUT_FILE"
