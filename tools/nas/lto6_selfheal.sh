#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${STATE_DIR:-/var/lib/lto6-selfheal}"
STATE_FILE="${STATE_FILE:-$STATE_DIR/state.env}"
ATTEMPTS_FILE="${ATTEMPTS_FILE:-$STATE_DIR/attempts.log}"
OUT_DIR="${OUT_DIR:-/var/lib/prometheus/node-exporter}"
OUT_FILE="${OUT_FILE:-$OUT_DIR/lto6_selfheal.prom}"
TMP_FILE="$(mktemp "${OUT_DIR}/lto6_selfheal.prom.XXXXXX")"

MOUNTPOINT="${MOUNTPOINT:-/mnt/tape/lto6}"
SERVICE="${SERVICE:-ltfs-lto6.service}"
EXPORT_METRICS_CMD="${EXPORT_METRICS_CMD:-/usr/local/sbin/export-lto6-metrics.sh}"
COOLDOWN_SECONDS="${COOLDOWN_SECONDS:-1800}"
MAX_ATTEMPTS_24H="${MAX_ATTEMPTS_24H:-6}"

cleanup() {
  rm -f "$TMP_FILE"
}
trap cleanup EXIT

mkdir -p "$STATE_DIR" "$OUT_DIR"
touch "$ATTEMPTS_FILE"

last_attempt=0
last_success=0
last_result_code=0
consecutive_failures=0

if [ -f "$STATE_FILE" ]; then
  # shellcheck disable=SC1090
  . "$STATE_FILE"
fi

now="$(date +%s)"
cutoff="$((now - 86400))"
tmp_attempts="$(mktemp "${STATE_DIR}/attempts.XXXXXX")"
awk -v cutoff="$cutoff" '$1 >= cutoff {print $1}' "$ATTEMPTS_FILE" >"$tmp_attempts"
mv "$tmp_attempts" "$ATTEMPTS_FILE"
attempts_24h="$(wc -l < "$ATTEMPTS_FILE" | tr -d ' ')"

if [ -x "$EXPORT_METRICS_CMD" ]; then
  "$EXPORT_METRICS_CMD" >/dev/null 2>&1 || true
fi

read_only="$(awk '/^nas_ltfs_read_only/ {print $NF}' /var/lib/prometheus/node-exporter/lto6.prom 2>/dev/null | tail -n 1)"
read_only="${read_only:-0}"
selfheal_active=0

verify_rw() {
  local probe_dir="${MOUNTPOINT}/.selfheal"
  local probe_file="${probe_dir}/rw-probe"
  mkdir -p "$probe_dir"
  : >"$probe_file"
  rm -f "$probe_file"
}

if [ "$read_only" = "1" ]; then
  selfheal_active=1

  if [ "$((now - last_attempt))" -lt "$COOLDOWN_SECONDS" ]; then
    last_result_code=3
  elif [ "$attempts_24h" -ge "$MAX_ATTEMPTS_24H" ]; then
    last_result_code=4
  else
    last_attempt="$now"
    printf '%s\n' "$now" >>"$ATTEMPTS_FILE"
    attempts_24h="$((attempts_24h + 1))"

    systemctl stop "$SERVICE" || true
    systemctl start "$SERVICE" || true
    sleep 8

    if findmnt "$MOUNTPOINT" >/dev/null 2>&1 && verify_rw >/dev/null 2>&1; then
      last_success="$now"
      last_result_code=1
      consecutive_failures=0
      selfheal_active=0
      if [ -x "$EXPORT_METRICS_CMD" ]; then
        "$EXPORT_METRICS_CMD" >/dev/null 2>&1 || true
      fi
    else
      last_result_code=2
      consecutive_failures="$((consecutive_failures + 1))"
    fi
  fi
else
  last_result_code=0
  consecutive_failures=0
fi

cat >"$STATE_FILE" <<EOF
last_attempt=${last_attempt}
last_success=${last_success}
last_result_code=${last_result_code}
consecutive_failures=${consecutive_failures}
EOF

cat >"$TMP_FILE" <<EOF
# HELP nas_ltfs_selfheal_active LTFS self-heal is currently needed because the mount is read-only.
# TYPE nas_ltfs_selfheal_active gauge
nas_ltfs_selfheal_active{mountpoint="${MOUNTPOINT}"} ${selfheal_active}
# HELP nas_ltfs_selfheal_last_result_code Last LTFS self-heal result code (0=healthy, 1=recovered, 2=failed, 3=cooldown, 4=rate_limited).
# TYPE nas_ltfs_selfheal_last_result_code gauge
nas_ltfs_selfheal_last_result_code{mountpoint="${MOUNTPOINT}"} ${last_result_code}
# HELP nas_ltfs_selfheal_last_attempt_timestamp_seconds Last LTFS self-heal attempt timestamp.
# TYPE nas_ltfs_selfheal_last_attempt_timestamp_seconds gauge
nas_ltfs_selfheal_last_attempt_timestamp_seconds{mountpoint="${MOUNTPOINT}"} ${last_attempt}
# HELP nas_ltfs_selfheal_last_success_timestamp_seconds Last successful LTFS self-heal timestamp.
# TYPE nas_ltfs_selfheal_last_success_timestamp_seconds gauge
nas_ltfs_selfheal_last_success_timestamp_seconds{mountpoint="${MOUNTPOINT}"} ${last_success}
# HELP nas_ltfs_selfheal_attempts_24h LTFS self-heal attempts in the last 24 hours.
# TYPE nas_ltfs_selfheal_attempts_24h gauge
nas_ltfs_selfheal_attempts_24h{mountpoint="${MOUNTPOINT}"} ${attempts_24h}
# HELP nas_ltfs_selfheal_consecutive_failures Consecutive LTFS self-heal failures.
# TYPE nas_ltfs_selfheal_consecutive_failures gauge
nas_ltfs_selfheal_consecutive_failures{mountpoint="${MOUNTPOINT}"} ${consecutive_failures}
EOF

chmod 0644 "$TMP_FILE"
mv "$TMP_FILE" "$OUT_FILE"
