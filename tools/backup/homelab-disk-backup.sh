#!/bin/bash
# Backup do RAID completo (mergerfs /mnt/raid1) para Nextcloud via WebDAV.
# Usa localhost:8880 (bypass Cloudflare) — sem limite de tamanho de arquivo.
# Histórico: --max-size 35M era necessário via nextcloud.rpa4all.com (Cloudflare 100s timeout/HTTP 524).
set -euo pipefail

LOG=/var/log/homelab-disk-backup.log
CFG=/etc/rclone/nextcloud-backup.conf

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }

log "=== Iniciando backup /mnt/raid1 → Nextcloud ==="

rclone sync /mnt/raid1 nextcloud:raid1 \
  --config "$CFG" \
  --exclude 'lost+found/**' \
  --transfers 4 \
  --checkers 8 \
  --retries 3 \
  --retries-sleep 10s \
  --low-level-retries 5 \
  --log-file "$LOG" \
  --log-level INFO \
  --stats 60s

log "=== Backup concluído ==="
