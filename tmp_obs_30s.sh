#!/bin/bash
tmpj=/tmp/obs_journal.log
tmpr=/tmp/obs_recent.log
tmpe=/tmp/obs_err.log
sudo rm -f "$tmpj" "$tmpr" "$tmpe"
sudo journalctl -u specialized-agents-api.service -n0 --no-pager -f >> "$tmpj" 2>&1 &
j=$!
tail -n0 -F /home/homelab/eddie-auto-dev/monitor_bridge_recent.log >> "$tmpr" 2>&1 &
r=$!
tail -n0 -F /home/homelab/eddie-auto-dev/monitor_bridge.log >> "$tmpe" 2>&1 &
e=$!
sleep 30
kill $j $r $e 2>/dev/null || true
echo "=== journal (last 200 lines) ==="
sudo sed -n '1,200p' "$tmpj" || true
echo "=== monitor_recent (last 200 lines) ==="
sed -n '1,200p' "$tmpr" || true
echo "=== monitor_errors (last 200 lines) ==="
sed -n '1,200p' "$tmpe" || true
sudo rm -f "$tmpj" "$tmpr" "$tmpe"
