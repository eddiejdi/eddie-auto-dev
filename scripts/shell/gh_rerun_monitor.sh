#!/bin/bash
set -euo pipefail
LOG=/home/homelab/gh_rerun_24h.log
OUT=/home/homelab/gh_rerun_24h.status
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$OUT"
echo "Last 50 lines of $LOG:" >> "$OUT"
if [ -f "$LOG" ]; then tail -n 50 "$LOG" >> "$OUT"; else echo "Log not found: $LOG" >> "$OUT"; fi
