#!/usr/bin/env bash
set -euo pipefail

# Emergency snapshot script for rpa4all homelab
# Features:
# - Uses /mnt/storage/backups as default target
# - Checks available space before copying
# - Uses locking to prevent concurrent runs
# - Writes into a temporary dir and atomically renames on success
# - Keeps snapshots by days (KEEP_DAYS) and by count (KEEP_COUNT)
# - Supports DRY_RUN=1 for safe estimation

LOG=/var/log/create_snapshot.log
BACKUP_DIR="/mnt/storage/backups"
EXCLUDES=("/proc" "/sys" "/dev" "/tmp" "/run" "/mnt" "/media" "/lost+found" "/var/tmp" "/var/run")
KEEP_DAYS=${KEEP_DAYS:-14}
KEEP_COUNT=${KEEP_COUNT:-7}
MIN_FREE_BYTES=${MIN_FREE_BYTES:-1073741824} # 1 GiB safety margin

mkdir -p "$BACKUP_DIR"
chown homelab:homelab "$BACKUP_DIR" || true
mkdir -p $(dirname "$LOG") || true

# simple logging
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting snapshot (DRY_RUN=${DRY_RUN:-0})" >>"$LOG"

# Lock to avoid concurrent runs
LOCKFILE=/var/lock/create_snapshot.lock
exec 200>"$LOCKFILE"
flock -n 200 || { echo "Another snapshot is running, exiting" >>"$LOG"; exit 0; }

TS=$(date -u +%Y%m%dT%H%M%SZ)
TARGET="$BACKUP_DIR/rpa4all-snapshot-$TS"
TMP_TARGET="$TARGET.tmp.$$"

# build rsync excludes
RSYNC_EXCLUDES=()
DU_EXCLUDES=()
for e in "${EXCLUDES[@]}"; do
  RSYNC_EXCLUDES+=("--exclude=$e")
  DU_EXCLUDES+=("--exclude=$e")
done

# estimate source size (bytes)
set +e
DU_CMD=(sudo du -sx -B1)
for ex in "${DU_EXCLUDES[@]}"; do
  DU_CMD+=("$ex")
done
DU_CMD+=(/)
SIZE_BYTES=$("${DU_CMD[@]}" 2>/dev/null | awk '{print $1}')
set -e
if [[ -z "$SIZE_BYTES" ]]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] WARNING: could not estimate source size, proceeding" >>"$LOG"
  SIZE_BYTES=0
fi

AVAIL_BYTES=$(df --output=avail -B1 "$BACKUP_DIR" | tail -n1 | tr -d '[:space:]')
if [[ -z "$AVAIL_BYTES" ]]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: could not determine available space on $BACKUP_DIR" >>"$LOG"
  exit 2
fi

NEEDED=$((SIZE_BYTES + MIN_FREE_BYTES))
if (( SIZE_BYTES > 0 && AVAIL_BYTES < NEEDED )); then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: insufficient space on $BACKUP_DIR (avail=${AVAIL_BYTES}, need~=${NEEDED})" >>"$LOG"
  exit 2
fi

# perform rsync into temp dir; if DRY_RUN=1, use --dry-run and keep outputs
RSYNC_OPTS=(--archive --xattrs --acls --numeric-ids --one-file-system --delete --partial-dir=.rsync-part)
if [[ "${DRY_RUN:-0}" == "1" ]]; then
  RSYNC_OPTS+=(--dry-run --stats -v)
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Creating tmp snapshot at $TMP_TARGET" >>"$LOG"
sudo rsync "${RSYNC_OPTS[@]}" "${RSYNC_EXCLUDES[@]}" / "$TMP_TARGET" 2>>"$LOG" || {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: rsync failed" >>"$LOG"
  sudo rm -rf "$TMP_TARGET" || true
  exit 2
}

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] DRY_RUN complete" >>"$LOG"
  exit 0
fi

# add metadata
echo "$TS" | sudo tee "$TMP_TARGET/SNAPSHOT_TIMESTAMP.txt" >/dev/null
sudo df -h > "$TMP_TARGET/DF-INFO.txt"
sudo mount > "$TMP_TARGET/MOUNT-INFO.txt"

# atomically move into place
sudo mv "$TMP_TARGET" "$TARGET"
sudo chown -R homelab:homelab "$TARGET"

# Maintain retention by age
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Removing snapshots older than $KEEP_DAYS days" >>"$LOG"
find "$BACKUP_DIR" -maxdepth 1 -type d -name 'rpa4all-snapshot-*' -mtime +$KEEP_DAYS -print -exec sudo rm -rf {} + || true

# Maintain retention by count
SNAPS=( $(ls -1dt "$BACKUP_DIR"/rpa4all-snapshot-* 2>/dev/null || true) )
if (( ${#SNAPS[@]} > KEEP_COUNT )); then
  REMOVE=( "${SNAPS[@]:$KEEP_COUNT}" )
  for r in "${REMOVE[@]}"; do
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Removing old snapshot $r" >>"$LOG"
    sudo rm -rf "$r" || true
  done
fi

# Update 'latest' symlink
ln -sfn "$TARGET" "$BACKUP_DIR/latest"
chown -h homelab:homelab "$BACKUP_DIR/latest" || true

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Snapshot $TARGET created successfully" >>"$LOG"
sudo du -sh "$TARGET" >>"$LOG" || true

exit 0
