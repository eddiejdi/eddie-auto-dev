#!/usr/bin/env bash
set -euo pipefail

UNIT="mnt-lto6\\x2dsmb\\x2dproof.mount"
MOUNT_POINT="/mnt/lto6-smb-proof"
LOG="lto6-smb-proof-selfheal"

is_accessible() {
    timeout 5 ls "$MOUNT_POINT" &>/dev/null
}

if mountpoint -q "$MOUNT_POINT"; then
    if is_accessible; then
        logger -t "$LOG" "mount healthy, nothing to do"
        exit 0
    fi
    logger -t "$LOG" "stale mount detected — forcing unmount"
    umount -f -l "$MOUNT_POINT" 2>/dev/null || true
    sleep 2
fi

logger -t "$LOG" "mount is down — restarting $UNIT"
systemctl restart "$UNIT"

# Verify
sleep 3
if mountpoint -q "$MOUNT_POINT" && is_accessible; then
    logger -t "$LOG" "mount restored successfully"
else
    logger -t "$LOG" "ERROR: mount failed to come back up after restart"
    exit 1
fi
