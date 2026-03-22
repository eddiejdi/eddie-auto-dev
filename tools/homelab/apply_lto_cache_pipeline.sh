#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 2
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)

PRIMARY_BUFFER_ROOT=${PRIMARY_BUFFER_ROOT:-/mnt/raid1/lto6-cache}
SPOOL_LINK=${SPOOL_LINK:-/var/spool/lto6-cache}
LEGACY_BUFFER_MOUNT=${LEGACY_BUFFER_MOUNT:-/mnt/lto6-cache-nas}
CACHE_MOUNT=${CACHE_MOUNT:-/mnt/lto6-cache}
NEXTCLOUD_CACHE_MOUNT=${NEXTCLOUD_CACHE_MOUNT:-/mnt/lto6-nextcloud}
TAPE_TARGET=${TAPE_TARGET:-/mnt/lto6}
SECONDARY_TAPE_TARGET=${SECONDARY_TAPE_TARGET:-/mnt/lto6b}
LOGICAL_ARCHIVE_MOUNT=${LOGICAL_ARCHIVE_MOUNT:-/mnt/lto-archive}

FLUSH_BIN=/usr/local/bin/ltfs-cache-flush
LOGICAL_MOUNT_BIN=/usr/local/bin/lto-logical-mount
ENV_DST=/etc/default/ltfs-cache-flush
LOGICAL_ENV_DST=/etc/default/lto-logical-mount
SERVICE_DST=/etc/systemd/system/ltfs-cache-flush.service
TIMER_DST=/etc/systemd/system/ltfs-cache-flush.timer
LOGICAL_SERVICE_DST=/etc/systemd/system/lto-logical-mount-refresh.service
LOGICAL_TIMER_DST=/etc/systemd/system/lto-logical-mount-refresh.timer
FSTAB=/etc/fstab
FSTAB_BACKUP="/etc/fstab.bak.$(date +%Y%m%d%H%M%S)"

SCRIPT_SRC="${REPO_ROOT}/tools/homelab/ltfs_cache_flush.py"
LOGICAL_SCRIPT_SRC="${REPO_ROOT}/tools/homelab/lto_logical_mount.sh"
SERVICE_SRC="${REPO_ROOT}/systemd/ltfs-cache-flush.service"
TIMER_SRC="${REPO_ROOT}/systemd/ltfs-cache-flush.timer"
ENV_SRC="${REPO_ROOT}/systemd/ltfs-cache-flush.env.example"
LOGICAL_SERVICE_SRC="${REPO_ROOT}/systemd/lto-logical-mount-refresh.service"
LOGICAL_TIMER_SRC="${REPO_ROOT}/systemd/lto-logical-mount-refresh.timer"
LOGICAL_ENV_SRC="${REPO_ROOT}/systemd/lto-logical-mount.env.example"

for file in \
  "$SCRIPT_SRC" \
  "$LOGICAL_SCRIPT_SRC" \
  "$SERVICE_SRC" \
  "$TIMER_SRC" \
  "$ENV_SRC" \
  "$LOGICAL_SERVICE_SRC" \
  "$LOGICAL_TIMER_SRC" \
  "$LOGICAL_ENV_SRC"; do
  [[ -f "$file" ]] || { echo "Missing required file: $file" >&2; exit 2; }
done

echo "Preparing directories"
install -d -m 2775 \
  "$PRIMARY_BUFFER_ROOT" \
  "$LEGACY_BUFFER_MOUNT" \
  "$CACHE_MOUNT" \
  "$NEXTCLOUD_CACHE_MOUNT" \
  "$TAPE_TARGET" \
  "$SECONDARY_TAPE_TARGET" \
  "$LOGICAL_ARCHIVE_MOUNT"
chmod 2775 "$PRIMARY_BUFFER_ROOT" "$CACHE_MOUNT" "$NEXTCLOUD_CACHE_MOUNT" "$LOGICAL_ARCHIVE_MOUNT"
chown homelab:homelab "$PRIMARY_BUFFER_ROOT" "$LOGICAL_ARCHIVE_MOUNT"
setfacl -m u:homelab:rwx,u:www-data:rwx,m:rwx "$PRIMARY_BUFFER_ROOT"
setfacl -d -m u:homelab:rwx,u:www-data:rwx,m:rwx "$PRIMARY_BUFFER_ROOT"
if [[ -e "$SPOOL_LINK" && ! -L "$SPOOL_LINK" ]]; then
  echo "Refusing to replace existing non-symlink spool path: $SPOOL_LINK" >&2
  exit 2
fi
ln -sfn "$PRIMARY_BUFFER_ROOT" "$SPOOL_LINK"

echo "Installing flush worker"
install -m 0755 "$SCRIPT_SRC" "$FLUSH_BIN"
install -m 0755 "$LOGICAL_SCRIPT_SRC" "$LOGICAL_MOUNT_BIN"
install -m 0644 "$SERVICE_SRC" "$SERVICE_DST"
install -m 0644 "$TIMER_SRC" "$TIMER_DST"
install -m 0644 "$LOGICAL_SERVICE_SRC" "$LOGICAL_SERVICE_DST"
install -m 0644 "$LOGICAL_TIMER_SRC" "$LOGICAL_TIMER_DST"

if [[ ! -f "$ENV_DST" ]]; then
  install -m 0644 "$ENV_SRC" "$ENV_DST"
fi
if [[ ! -f "$LOGICAL_ENV_DST" ]]; then
  install -m 0644 "$LOGICAL_ENV_SRC" "$LOGICAL_ENV_DST"
fi

grep -q '^TARGET_ROOTS=' "$ENV_DST" || printf 'TARGET_ROOTS=%s:%s\n' "$TAPE_TARGET" "$SECONDARY_TAPE_TARGET" >>"$ENV_DST"
grep -q '^PLACEMENT_FILE=' "$ENV_DST" || echo 'PLACEMENT_FILE=/var/lib/ltfs-cache-flush/placements.json' >>"$ENV_DST"
grep -q '^CATALOG_FILE=' "$ENV_DST" || echo 'CATALOG_FILE=/var/lib/ltfs-cache-flush/catalog.jsonl' >>"$ENV_DST"
grep -q '^MIN_TARGET_FREE_BYTES=' "$ENV_DST" || echo 'MIN_TARGET_FREE_BYTES=0' >>"$ENV_DST"
grep -q '^PLACEMENT_POLICY=' "$ENV_DST" || echo 'PLACEMENT_POLICY=most-free' >>"$ENV_DST"

grep -q '^LOGICAL_ROOT=' "$LOGICAL_ENV_DST" || printf 'LOGICAL_ROOT=%s\n' "$LOGICAL_ARCHIVE_MOUNT" >>"$LOGICAL_ENV_DST"
grep -q '^CACHE_BRANCH=' "$LOGICAL_ENV_DST" || printf 'CACHE_BRANCH=%s\n' "$PRIMARY_BUFFER_ROOT" >>"$LOGICAL_ENV_DST"
grep -q '^TAPE_BRANCHES=' "$LOGICAL_ENV_DST" || printf 'TAPE_BRANCHES=%s:%s\n' "$TAPE_TARGET" "$SECONDARY_TAPE_TARGET" >>"$LOGICAL_ENV_DST"
grep -q '^MIN_TARGET_TOTAL_BYTES=' "$LOGICAL_ENV_DST" || echo 'MIN_TARGET_TOTAL_BYTES=1099511627776' >>"$LOGICAL_ENV_DST"
grep -q '^MERGERFS_BIN=' "$LOGICAL_ENV_DST" || echo 'MERGERFS_BIN=/usr/bin/mergerfs' >>"$LOGICAL_ENV_DST"
grep -q '^MERGERFS_OPTIONS=' "$LOGICAL_ENV_DST" || echo 'MERGERFS_OPTIONS=allow_other,use_ino,cache.files=off,dropcacheonclose=true,category.create=ff,func.getattr=newest,fsname=lto-logical' >>"$LOGICAL_ENV_DST"
grep -q '^STATE_FILE=' "$LOGICAL_ENV_DST" || echo 'STATE_FILE=/run/lto-logical-mount.branches' >>"$LOGICAL_ENV_DST"

if ! grep -q "BEGIN LTFS CACHE PIPELINE" "$FSTAB"; then
  cp "$FSTAB" "$FSTAB_BACKUP"
  python3 - "$FSTAB" <<'PY'
from pathlib import Path
import sys

fstab_path = Path(sys.argv[1])
lines = fstab_path.read_text(encoding="utf-8").splitlines()
result = []
for line in lines:
    stripped = line.strip()
    if stripped.startswith("//192.168.15.4/LTO6_CACHE /mnt/lto6-cache ") or stripped.startswith("//192.168.15.4/LTO6_CACHE /mnt/lto6-nextcloud "):
        result.append(f"# disabled by ltfs-cache-pipeline: {line}")
    else:
        result.append(line)

block = [
    "# BEGIN LTFS CACHE PIPELINE",
    "//192.168.15.4/LTO6_CACHE /mnt/lto6-cache-nas cifs credentials=/root/.smb-lto6-cache-credentials,vers=3.1.1,iocharset=utf8,uid=1000,gid=1000,file_mode=0664,dir_mode=0775,_netdev,nofail 0 0",
    "/mnt/raid1/lto6-cache /mnt/lto6-cache none bind 0 0",
    "/mnt/raid1/lto6-cache /mnt/lto6-nextcloud none bind 0 0",
    "# END LTFS CACHE PIPELINE",
]
result.append("")
result.extend(block)
fstab_path.write_text("\n".join(result) + "\n", encoding="utf-8")
PY
fi

echo "Reloading mount layout"
systemctl daemon-reload
mountpoint -q "$NEXTCLOUD_CACHE_MOUNT" && umount "$NEXTCLOUD_CACHE_MOUNT"
mountpoint -q "$CACHE_MOUNT" && umount "$CACHE_MOUNT"
mountpoint -q "$LEGACY_BUFFER_MOUNT" || mount "$LEGACY_BUFFER_MOUNT"
mountpoint -q "$CACHE_MOUNT" || mount "$CACHE_MOUNT"
mountpoint -q "$NEXTCLOUD_CACHE_MOUNT" || mount "$NEXTCLOUD_CACHE_MOUNT"

echo "Enabling logical single-mount refresher"
systemctl enable --now lto-logical-mount-refresh.timer
systemctl start lto-logical-mount-refresh.service

echo "Enabling flush timer"
systemctl enable --now ltfs-cache-flush.timer

echo "Running an immediate flush pass"
systemctl start ltfs-cache-flush.service

echo "Done."
echo "Primary buffer root: $PRIMARY_BUFFER_ROOT"
echo "Legacy buffer mount: $LEGACY_BUFFER_MOUNT"
echo "Logical tape target: $TAPE_TARGET"
echo "Secondary tape target: $SECONDARY_TAPE_TARGET"
echo "Logical archive mount: $LOGICAL_ARCHIVE_MOUNT"
