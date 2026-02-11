#!/bin/bash
set -euo pipefail

ts=$(date +%Y%m%d_%H%M%S)
dest="/mnt/storage/parked/$ts"
mkdir -p "$dest"
echo "Destination: $dest"
shopt -s nullglob dotglob
patterns=(
  "/home/homelab/Win10PrinterVM.vdi"
  "/home/homelab/*.iso"
  "/home/homelab/actions-runner/*.tar.gz"
  "/home/homelab/archives/*"
  "/home/homelab/.cache/pip"
  "/home/homelab/.cache/huggingface"
  "/home/homelab/.cache/ms-playwright"
  "/home/homelab/.cache/pypoetry"
)
for pattern in "${patterns[@]}"; do
  for f in $pattern; do
    if [ -e "$f" ]; then
      echo "MOVING: $f -> $dest/"
      mv "$f" "$dest/"
      rc=$?
      echo "mv exit:$rc"
      sleep 1
      echo "Journal errors (last 2m):"
      journalctl -p err --since "2 minutes ago" -n 50 --no-pager || true
      echo "--- /var/log/syslog tail ---"
      tail -n 50 /var/log/syslog || true
      echo "----"
    fi
  done
done

echo "Move done. Destination contents:"
ls -lh "$dest"
df -h /mnt/storage
