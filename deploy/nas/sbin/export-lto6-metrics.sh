#!/usr/bin/env bash
_quick_mount_update() {
  local out_dir="${OUT_DIR:-/var/lib/prometheus/node-exporter}"
  local out_file="${out_dir}/lto6.prom"
  local mp="${MOUNTPOINT:-/mnt/tape/lto6}"
  local svc="${SERVICE:-ltfs-lto6.service}"
  [[ -f "$out_file" ]] || return 0
  local tmp; tmp="$(mktemp "${out_dir}/lto6.prom.quickXXXXXX")" || return 0
  local svc_val=0 mnt_val=0
  systemctl is-active --quiet "$svc" 2>/dev/null && svc_val=1
  findmnt "$mp" >/dev/null 2>&1 && mnt_val=1
  sed -e "s|^\(nas_ltfs_service_up[^}]*}\) [0-9]*$|\1 ${svc_val}|" \
      -e "s|^\(nas_ltfs_mount_up[^}]*}\) [0-9]*$|\1 ${mnt_val}|" \
      "$out_file" > "$tmp" && chmod 0644 "$tmp" && mv "$tmp" "$out_file" || rm -f "$tmp"
}
_quick_mount_update

# tape-access:
if [[ -z "${TAPE_ACCESS_ACTIVE:-}" ]]; then
    export TAPE_ACCESS_ACTIVE=1
    exec /usr/local/sbin/tape-access tryrun --name "export-lto6-metrics" -- "$0" "$@"
fi

set -euo pipefail

OUT_DIR="${OUT_DIR:-/var/lib/prometheus/node-exporter}"
OUT_FILE="${OUT_FILE:-$OUT_DIR/lto6.prom}"
TMP_FILE="$(mktemp "${OUT_DIR}/lto6.prom.XXXXXX")"

MOUNTPOINT="${MOUNTPOINT:-/mnt/tape/lto6}"
SERVICE="${SERVICE:-ltfs-lto6.service}"
RESOLVER="${RESOLVER:-/usr/local/sbin/lto6-resolve-device}"
DISCOVERER="${DISCOVERER:-/usr/local/sbin/discover-tape-volumes}"

if [ -x "$RESOLVER" ]; then
  if resolved="$($RESOLVER 2>/dev/null)"; then
    eval "$resolved"
  fi
fi

SGDEV="${SGDEV:-${LTO6_SG_DEV:-/dev/sg0}}"
TAPEDEV="${TAPEDEV:-${LTO6_NST_DEV:-/dev/nst0}}"
DRIVE_ID="${DRIVE_ID:-${LTO6_DRIVE_ID:-unknown}}"

cleanup() {
  rm -f "$TMP_FILE"
}
trap cleanup EXIT

esc() {
  local value="${1:-}"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/ }"
  printf '%s' "$value"
}

metric() {
  local name="$1"
  local labels="$2"
  local value="$3"
  if [[ -n "$labels" ]]; then
    printf '%s{%s} %s\n' "$name" "$labels" "$value" >>"$TMP_FILE"
  else
    printf '%s %s\n' "$name" "$value" >>"$TMP_FILE"
  fi
}

df_bytes_triplet() {
  local mountpoint="$1"
  local size="0"
  local used="0"
  local avail="0"

  # LTFS/FUSE can block indefinitely under heavy I/O; keep exporter responsive.
  read -r size used avail <<EOF || true
$(timeout 5 df -B1 --output=size,used,avail "$mountpoint" 2>/dev/null | awk 'NR == 2 {print $1, $2, $3}')
EOF

  printf '%s %s %s\n' "${size:-0}" "${used:-0}" "${avail:-0}"
}

mount_busy_by_foreign_process() {
  local mountpoint="$1"
  local pid args

  [[ -n "$mountpoint" ]] || return 1
  findmnt "$mountpoint" >/dev/null 2>&1 || return 1

  while read -r pid; do
    [[ -n "$pid" ]] || continue
    args="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    case "$args" in
      *"/usr/local/bin/ltfs "*"$mountpoint"* ) continue ;;
      *"/usr/local/sbin/tape-safe-eject.sh"* ) continue ;;
    esac
    return 0
  done < <(fuser -m "$mountpoint" 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+$' | sort -u)

  return 1
}

service_active() {
  local svc="$1"
  systemctl is-active --quiet "$svc" 2>/dev/null
}

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

if service_active "$SERVICE"; then
  service_up=1
fi

if findmnt "$MOUNTPOINT" >/dev/null 2>&1; then
  mount_up=1
  read -r size_bytes used_bytes avail_bytes < <(df_bytes_triplet "$MOUNTPOINT")
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

# mt/tapeinfo bloqueiam quando LTFS segura /dev/nst exclusivamente.
# Quando montado, inferir estado pelo mount ativo; ler compressao do journal de startup.
if [ "$mount_up" -eq 1 ]; then
  drive_ready=1
  medium_loaded=1
  # LTFS16028I (ltfsck) nao aparece no journal de mount — usar args do processo.
  ltfs_pid="$(pgrep -f 'ltfs-patched.*ltfs ' | head -1 || true)"
  if [[ -n "$ltfs_pid" ]]; then
    if tr '\0' ' ' </proc/"$ltfs_pid"/cmdline 2>/dev/null | grep -q 'no-compression'; then
      compression_enabled=0
    else
      compression_enabled=1
    fi
  fi
else
  mt_output="$(timeout 10 mt -f "$TAPEDEV" status 2>/dev/null || true)"
  if grep -q ' ONLINE' <<<"$mt_output"; then
    drive_ready=1
    medium_loaded=1
  elif grep -q ' DR_OPEN' <<<"$mt_output" || grep -q ' no tape loaded' <<<"$mt_output"; then
    drive_ready=0
    medium_loaded=0
  fi
  tapeinfo_output="$(timeout 5 tapeinfo -f "$SGDEV" 2>/dev/null || true)"
  if grep -q 'DataCompEnabled: yes' <<<"$tapeinfo_output"; then
    compression_enabled=1
  elif grep -q 'DataCompEnabled: no' <<<"$tapeinfo_output"; then
    compression_enabled=0
  fi
fi

cat >"$TMP_FILE" <<EOF2
# HELP nas_ltfs_service_up LTFS systemd service state on the NAS.
# TYPE nas_ltfs_service_up gauge
# HELP nas_ltfs_mount_up LTFS mount availability on the NAS.
# TYPE nas_ltfs_mount_up gauge
# HELP nas_ltfs_read_only LTFS mount dropped to read-only mode in the current mount session.
# TYPE nas_ltfs_read_only gauge
# HELP nas_ltfs_size_bytes LTFS total capacity in bytes.
# TYPE nas_ltfs_size_bytes gauge
# HELP nas_ltfs_used_bytes LTFS used capacity in bytes.
# TYPE nas_ltfs_used_bytes gauge
# HELP nas_ltfs_avail_bytes LTFS available capacity in bytes.
# TYPE nas_ltfs_avail_bytes gauge
# HELP nas_tape_drive_ready Tape drive readiness according to tapeinfo.
# TYPE nas_tape_drive_ready gauge
# HELP nas_tape_medium_loaded Tape medium presence according to tapeinfo.
# TYPE nas_tape_medium_loaded gauge
# HELP nas_tape_compression_enabled Tape hardware compression state according to tapeinfo.
# TYPE nas_tape_compression_enabled gauge
# HELP nas_ltfs_write_timeout_events_24h LTFS write timeout events seen in the last 24 hours.
# TYPE nas_ltfs_write_timeout_events_24h gauge
# HELP nas_fc_abort_events_24h qla2xxx abort events seen in the last 24 hours.
# TYPE nas_fc_abort_events_24h gauge
# HELP nas_tape_volume_info Current discovered tape volume on the NAS.
# TYPE nas_tape_volume_info gauge
# HELP nas_tape_volume_mounted Tape mount availability for each discovered tape.
# TYPE nas_tape_volume_mounted gauge
# HELP nas_tape_volume_ready Tape drive readiness for each discovered tape.
# TYPE nas_tape_volume_ready gauge
# HELP nas_tape_safe_to_eject Tape can be ejected safely now (1=yes, 0=blocked).
# TYPE nas_tape_safe_to_eject gauge
# HELP nas_tape_used_bytes Used bytes for each mounted LTFS volume.
# TYPE nas_tape_used_bytes gauge
# HELP nas_tape_avail_bytes Available bytes for each mounted LTFS volume.
# TYPE nas_tape_avail_bytes gauge
# HELP nas_tape_size_bytes Total bytes for each mounted LTFS volume.
# TYPE nas_tape_size_bytes gauge
EOF2

metric "nas_ltfs_service_up" "service=\"$(esc "$SERVICE")\"" "$service_up"
metric "nas_ltfs_mount_up" "mountpoint=\"$(esc "$MOUNTPOINT")\"" "$mount_up"
metric "nas_ltfs_read_only" "mountpoint=\"$(esc "$MOUNTPOINT")\"" "$read_only"
metric "nas_ltfs_size_bytes" "mountpoint=\"$(esc "$MOUNTPOINT")\"" "${size_bytes:-0}"
metric "nas_ltfs_used_bytes" "mountpoint=\"$(esc "$MOUNTPOINT")\"" "${used_bytes:-0}"
metric "nas_ltfs_avail_bytes" "mountpoint=\"$(esc "$MOUNTPOINT")\"" "${avail_bytes:-0}"
metric "nas_tape_drive_ready" "device=\"$(esc "$DRIVE_ID")\"" "$drive_ready"
metric "nas_tape_medium_loaded" "device=\"$(esc "$DRIVE_ID")\"" "$medium_loaded"
metric "nas_tape_compression_enabled" "device=\"$(esc "$DRIVE_ID")\"" "$compression_enabled"
metric "nas_ltfs_write_timeout_events_24h" "service=\"$(esc "$SERVICE")\"" "$write_timeouts_24h"
metric "nas_fc_abort_events_24h" "driver=\"qla2xxx\"" "$fc_abort_events_24h"


# Backward-compat fixed device label used by older panel filters.
if [[ "$DRIVE_ID" != "HUL831AMRM" ]]; then
  metric "nas_tape_drive_ready" "device=\"HUL831AMRM\"" "$drive_ready"
  metric "nas_tape_medium_loaded" "device=\"HUL831AMRM\"" "$medium_loaded"
  metric "nas_tape_compression_enabled" "device=\"HUL831AMRM\"" "$compression_enabled"
fi

backup_busy=0
for svc in nextcloud-tape-backup.service tape-backup.service staged-tape-backup.service lto6-selfheal.service ltfs-cache-flush.service; do
  if service_active "$svc"; then
    backup_busy=1
    break
  fi
done

if [ -x "$DISCOVERER" ]; then
  while IFS=$'\t' read -r barcode label sg_dev st_dev nst_dev serial mountpoint state; do
    [[ -n "$sg_dev" ]] || continue
    [[ -n "$barcode" || -n "$label" || -n "$serial" ]] || continue

    local_barcode="${barcode:-unknown}"
    local_label="${label:-$local_barcode}"
    local_serial="${serial:-unknown}"
    local_mount="${mountpoint:-}"
    mounted=0
    ready=0
    safe_eject=0
    local_size=0
    local_used=0
    local_avail=0

    if [[ "$state" == "mounted" ]] && [[ -n "$local_mount" ]] && findmnt "$local_mount" >/dev/null 2>&1; then
      mounted=1
      read -r local_size local_used local_avail < <(df_bytes_triplet "$local_mount")
      local_size="${local_size:-0}"
      local_used="${local_used:-0}"
      local_avail="${local_avail:-0}"
    fi

    if timeout 8 mt -f "$nst_dev" status 2>/dev/null | grep -q ' ONLINE'; then
      ready=1
    fi

    if [[ "$backup_busy" -eq 0 ]] && [[ "$ready" -eq 1 ]] && ! mount_busy_by_foreign_process "$local_mount"; then
      safe_eject=1
    fi

    labels="barcode=\"$(esc "$local_barcode")\",label=\"$(esc "$local_label")\",sg=\"$(esc "$sg_dev")\",st=\"$(esc "$st_dev")\",nst=\"$(esc "$nst_dev")\",drive_serial=\"$(esc "$local_serial")\",mountpoint=\"$(esc "$local_mount")\",state=\"$(esc "$state")\""
    metric "nas_tape_volume_info" "$labels" 1
    metric "nas_tape_volume_mounted" "$labels" "$mounted"
    metric "nas_tape_volume_ready" "$labels" "$ready"
    metric "nas_tape_safe_to_eject" "$labels" "$safe_eject"
    metric "nas_tape_size_bytes" "$labels" "${local_size:-0}"
    metric "nas_tape_used_bytes" "$labels" "${local_used:-0}"
    metric "nas_tape_avail_bytes" "$labels" "${local_avail:-0}"
  done < <("$DISCOVERER" 2>/dev/null)
fi

chmod 0644 "$TMP_FILE"
mv "$TMP_FILE" "$OUT_FILE"
