#!/usr/bin/env bash
# Auditoria rápida de boot + systemd
# Gera arquivos em /tmp/boot_audit/

set -euo pipefail

OUTDIR=/tmp/boot_audit
mkdir -p "$OUTDIR"

echo "Collecting systemd-analyze blame..."
systemd-analyze blame > "$OUTDIR/blame.txt" 2>&1 || true
echo "Collected: $OUTDIR/blame.txt"

echo "Collecting critical chain..."
systemd-analyze critical-chain > "$OUTDIR/critical-chain.txt" 2>&1 || true

echo "Collecting boot errors (priority err or worse)..."
journalctl -b -p err --no-pager > "$OUTDIR/boot-errors.txt" 2>&1 || true

echo "Searching unit files for suspicious directives..."
TMP_UNITS="$OUTDIR/units_list.txt"
grep -EH "ExecStartPost|Type=oneshot|Restart=always|After=network.target|After=network-online.target|OnBootSec" /etc/systemd/system/*.service /lib/systemd/system/*.service 2>/dev/null || true

# Build a unique list of unit names that match common slow/blocked patterns
grep -EH "ExecStartPost|Type=oneshot|Restart=always|After=network.target|After=network-online.target|OnBootSec" /etc/systemd/system/*.service /lib/systemd/system/*.service 2>/dev/null \
  | sed -E 's#^.*/([^/]+\.service):.*#\1#' | sort -u > "$TMP_UNITS" || true

echo "Units found:" 
cat "$TMP_UNITS" || true

while read -r unit; do
  [ -z "$unit" ] && continue
  echo "--- Collecting status and logs for $unit"
  systemctl status "$unit" -n 200 --no-pager > "$OUTDIR/status-$unit.txt" 2>&1 || true
  journalctl -u "$unit" -n 200 --no-pager > "$OUTDIR/journal-$unit.txt" 2>&1 || true
done < "$TMP_UNITS"

echo "Summary saved to $OUTDIR"
echo "Top slow units (from blame):"
head -n 30 "$OUTDIR/blame.txt" || true

echo "Done"
