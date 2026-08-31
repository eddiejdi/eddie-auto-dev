#!/bin/bash
set -euo pipefail
LOG=/home/homelab/gh_rerun_24h.log
RUN_ID=21989960296
REPO=eddiejdi/eddie-auto-dev
for i in $(seq 1 24); do
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Iteration $i" >> "$LOG"
  gh run rerun "$RUN_ID" -R "$REPO" >> "$LOG" 2>&1 || echo "rerun command failed at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
  if [ "$i" -lt 24 ]; then sleep 3600; fi
 done
 echo "Completed 24 iterations" >> "$LOG"
