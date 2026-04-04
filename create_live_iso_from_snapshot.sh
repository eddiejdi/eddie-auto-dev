#!/usr/bin/env bash
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BUILD_DIR="/var/tmp/live-iso-snapshot-${TIMESTAMP}"
VENTOY_MOUNT="/media/edenilson/Ventoy"
LOG="$BUILD_DIR/build.log"

ORIG_ARGS=("$@")
PREPARE_ONLY=false
for _a in "${ORIG_ARGS[@]:-}"; do
  if [ "$_a" = "--prepare-only" ]; then
    PREPARE_ONLY=true
    break
  fi
done

if [ "$EUID" -ne 0 ]; then
  if [ "$PREPARE_ONLY" = true ]; then
    echo "Running in prepare-only mode without root; some actions may require root later." >&2
  else
    if [ -n "${SUDO_PASS:-}" ]; then
      printf "%s\n" "$SUDO_PASS" | sudo -S --preserve-env=PATH bash "$0" "${ORIG_ARGS[@]}"
      exit $?
    else
      echo "Re-run as root... invoking sudo"
      exec sudo --preserve-env=PATH bash "$0" "${ORIG_ARGS[@]}"
    fi
  fi
fi

mkdir -p "$BUILD_DIR"
mkdir -p "$BUILD_DIR/chroot"
mkdir -p "$BUILD_DIR/iso/live"
mkdir -p "$BUILD_DIR/tmp"
export TMPDIR="$BUILD_DIR/tmp"
chmod 1777 "$BUILD_DIR"
cd "$BUILD_DIR"

echo "Log: $LOG"
exec 3>&1 1>>"$LOG" 2>&1

echo "Starting snapshot ISO build: $TIMESTAMP"

# Exclude typical runtime and large locations; preserve /boot so kernels are available
EXCLUDES=(--exclude=/dev --exclude=/proc --exclude=/sys --exclude=/tmp --exclude=/run \
  --exclude=/mnt --exclude=/media --exclude=/lost+found --exclude=/home --exclude=/var/tmp \
  --exclude=/var/cache/apt/archives --exclude=/var/lib/apt/lists --exclude=/swapfile)

if [ "${PREPARE_ONLY}" != "true" ]; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends rsync squashfs-tools grub-pc-bin grub-efi-amd64-bin xorriso || true
else
  echo "Prepare-only: skipping package installation (run full script as root to install build deps)."
fi

echo "Starting rsync snapshot (this may take a while)..."
set +e
rsync -aAXH --numeric-ids -x "${EXCLUDES[@]}" / "$BUILD_DIR/chroot" --delete
RSYNC_STATUS=$?
set -e
if [ $RSYNC_STATUS -ne 0 ]; then
  echo "rsync exited with $RSYNC_STATUS (permissions or open files may have caused non-zero exit)."
fi

# Create squashfs for live usage if available and not prepare-only
if command -v mksquashfs >/dev/null 2>&1 && [ "${PREPARE_ONLY}" != "true" ]; then
  echo "Creating filesystem.squashfs..."
  mksquashfs "$BUILD_DIR/chroot" "$BUILD_DIR/iso/live/filesystem.squashfs" -comp xz -b 1048576 -Xdict-size 100% -noappend
else
  echo "mksquashfs not available or prepare-only; skipping squashfs creation. The chroot tree is at $BUILD_DIR/chroot"
fi

# Copy kernel and initrd (best-effort)
KERNEL=$(ls -1t /boot/vmlinuz-* 2>/dev/null | head -n1 || true)
INITRD=$(ls -1t /boot/initrd.img-* 2>/dev/null | head -n1 || true)
if [ -n "$KERNEL" ] && [ -n "$INITRD" ]; then
  cp -a "$KERNEL" "$BUILD_DIR/iso/live/vmlinuz" 2>/dev/null || true
  cp -a "$INITRD" "$BUILD_DIR/iso/live/initrd.img" 2>/dev/null || true
else
  echo "No vmlinuz/initrd found in /boot; you may need to install kernel packages or copy kernels into the iso tree manually."
fi

mkdir -p "$BUILD_DIR/iso/boot/grub"
cat > "$BUILD_DIR/iso/boot/grub/grub.cfg" <<'EOF'
set default=0
set timeout=5

menuentry "Custom Live Snapshot" {
  linux /live/vmlinuz boot=live components quiet splash
  initrd /live/initrd.img
}
EOF

if command -v grub-mkrescue >/dev/null 2>&1 && [ "${PREPARE_ONLY}" != "true" ]; then
  echo "Creating ISO with grub-mkrescue..."
  grub-mkrescue -o "$BUILD_DIR/custom-live-${TIMESTAMP}.iso" "$BUILD_DIR/iso" || true
else
  echo "grub-mkrescue not available or prepare-only; ISO creation skipped. ISO tree is at $BUILD_DIR/iso"
fi

if [ -f "$BUILD_DIR/custom-live-${TIMESTAMP}.iso" ]; then
  if [ -d "$VENTOY_MOUNT" ] && mountpoint -q "$VENTOY_MOUNT"; then
    DEST="$VENTOY_MOUNT/custom-live-${TIMESTAMP}.iso"
    cp -v "$BUILD_DIR/custom-live-${TIMESTAMP}.iso" "$DEST" >&3 || { echo "Failed to copy ISO to Ventoy" >&3; exit 1; }
    sync
    echo "ISO copied to $DEST" >&3
  else
    echo "Ventoy mount $VENTOY_MOUNT not found; ISO at $BUILD_DIR/custom-live-${TIMESTAMP}.iso" >&3
  fi
else
  echo "No ISO produced. See $BUILD_DIR/iso for the prepared tree." >&3
fi

echo "Snapshot prepare complete. Build dir: $BUILD_DIR" >&3
exit 0
