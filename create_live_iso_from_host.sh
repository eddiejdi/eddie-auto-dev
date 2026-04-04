#!/usr/bin/env bash
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
# Use /var/tmp so device nodes can be created (some systems mount /tmp nodev)
BUILD_DIR="/var/tmp/live-iso-from-host-${TIMESTAMP}"
VENTOY_MOUNT="/media/edenilson/Ventoy"
DISTRO="trixie"
ARCH="amd64"
LB_CONFIG_ARGS=(--distribution "$DISTRO" --architecture "$ARCH" --binary-images iso-hybrid --archive-areas "main contrib non-free non-free-firmware" --bootappend-live "boot=live components")
LOG="$BUILD_DIR/build.log"

# Allow a prepare-only mode (no build) and optional non-interactive sudo via SUDO_PASS.
# Collect original args and detect --prepare-only without consuming positional args.
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
mkdir -p "$BUILD_DIR/tmp"
export TMPDIR="$BUILD_DIR/tmp"
chmod 1777 "$BUILD_DIR"
cd "$BUILD_DIR"

echo "Log: $LOG"
exec 3>&1 1>>"$LOG" 2>&1

echo "Starting live ISO build: $TIMESTAMP"

# Install prerequisites (skip when in prepare-only mode)
if [ "${PREPARE_ONLY:-false}" != "true" ]; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends live-build squashfs-tools xorriso rsync mtools syslinux-utils debootstrap xz-utils grub-pc-bin grub-efi-amd64-bin || true
else
  echo "Prepare-only: skipping package installation (run full script as root to install build deps)."
fi

# Prepare live-build tree
mkdir -p config/includes.chroot/etc/apt/sources.list.d
mkdir -p config/includes.chroot/etc/apt/trusted.gpg.d
mkdir -p config/includes.chroot/usr/share/keyrings
mkdir -p config/package-lists

# Usar sources Debian Trixie limpos no chroot — NÃO copiar fontes Mint do host
# (Mint-specific sources causam 'Unable to locate package mint-*' no lb build)
cat > config/includes.chroot/etc/apt/sources.list <<'TRIXIE_EOF'
deb https://deb.debian.org/debian trixie main contrib non-free non-free-firmware
deb https://deb.debian.org/debian trixie-updates main contrib non-free non-free-firmware
deb http://security.debian.org/ trixie-security main contrib non-free non-free-firmware
deb https://deb.debian.org/debian trixie-backports main contrib non-free non-free-firmware
TRIXIE_EOF
# Copiar apenas fontes não-Mint do host (github-cli, vscode, etc.)
for _src in /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do
  [ -f "$_src" ] || continue
  _base=$(basename "$_src")
  case "$_base" in
    official-package-repositories* | linuxmint* | mint*) continue ;;
    *) cp -a "$_src" config/includes.chroot/etc/apt/sources.list.d/ 2>/dev/null || true ;;
  esac
done
cp -a /etc/apt/trusted.gpg.d/* config/includes.chroot/etc/apt/trusted.gpg.d/ 2>/dev/null || true
cp -a /usr/share/keyrings/* config/includes.chroot/usr/share/keyrings/ 2>/dev/null || true

# Generate package list from host and filter packages that have candidates in apt
# Write the raw host list outside of live-build's config to avoid lb reading it
RAW_HOST_LIST="$BUILD_DIR/host.raw.list"
apt-mark showmanual | sort > "$RAW_HOST_LIST"

echo "Filtering package list (this may take a while)..."
> config/package-lists/host.list.chroot

# Create a temporary apt environment pointing to Debian trixie to
# determine which packages are available in the target mirror. This
# avoids including Linux Mint-specific packages that won't exist in
# a Debian-based live chroot.
TMP_APT_DIR="$BUILD_DIR/apt-filter"
mkdir -p "$TMP_APT_DIR/lists" "$TMP_APT_DIR/archives" "$TMP_APT_DIR/state"
cat > "$TMP_APT_DIR/sources.list" <<EOF
deb https://deb.debian.org/debian trixie main contrib non-free non-free-firmware
deb https://deb.debian.org/debian trixie-updates main contrib non-free non-free-firmware
deb http://security.debian.org/ trixie-security main contrib non-free non-free-firmware
deb https://deb.debian.org/debian trixie-backports main contrib non-free non-free-firmware
EOF

# Populate lists for the temporary apt environment
APT_OPTS=(
  -o Dir::Etc::sourcelist="$TMP_APT_DIR/sources.list"
  -o Dir::Etc::sourceparts="-"
  -o Dir::State::lists="$TMP_APT_DIR/lists"
  -o Dir::Cache::archives="$TMP_APT_DIR/archives"
  -o APT::Cache-Limit=100000000
)
apt-get "${APT_OPTS[@]}" update >/dev/null 2>&1 || true

while IFS= read -r pkg; do
  cand=$(apt-cache "${APT_OPTS[@]}" policy "$pkg" 2>/dev/null | awk -F: '/Candidate:/ {gsub(/^[ \t]+/,"",$2); print $2; exit}') || true
  if [ -n "$cand" ] && [ "$cand" != "(none)" ]; then
    echo "$pkg" >> config/package-lists/host.list.chroot
  fi
# Read from the raw host list stored outside the live-build config
done < "$RAW_HOST_LIST"

# Clean temporary apt env
rm -rf "$TMP_APT_DIR" || true
# Remove the raw host list so lb won't pick it up accidentally
rm -f "$RAW_HOST_LIST" || true

# Provide a minimal live list if filtering removed everything
if [ ! -s config/package-lists/host.list.chroot ]; then
  cat > config/package-lists/host.list.chroot <<EOF
locales
keyboard-configuration
live-boot
live-config
systemd-sysv
sudo
openssh-client
openssh-server
rsync
curl
ca-certificates
initramfs-tools
EOF
fi

# Copy some host customizations (safe selected paths)
mkdir -p config/includes.chroot/etc/skel
cp -a /etc/skel/. config/includes.chroot/etc/skel/ 2>/dev/null || true
cp -a /etc/hostname config/includes.chroot/etc/hostname 2>/dev/null || true
cp -a /etc/hosts config/includes.chroot/etc/hosts 2>/dev/null || true

# Ensure ownership/permissions
chown -R root:root config || true
umask 022

# Clean previous builds, then create lb config (use 'noauto' to avoid
# live-build's auto-redirect issues when stdout/stderr are redirected)
lb clean --purge || true
lb config noauto --distribution "$DISTRO" --architecture "$ARCH" --binary-images iso-hybrid --archive-areas "main contrib non-free non-free-firmware" --bootappend-live "boot=live components" || true
# Ensure /dev/pts is mounted (fix common chroot pty errors)
if ! mountpoint -q /dev/pts; then
  mount -t devpts devpts /dev/pts || true
fi

# Run build (may take long)
if [ "${PREPARE_ONLY:-false}" = "true" ]; then
  echo "Prepare-only: skipping lb build. Configuration and package lists are prepared in $BUILD_DIR." >&3
  echo "To perform the full build as root, run: sudo bash $0" >&3
  exit 0
else
  echo "Running lb build (logs are in $LOG)"
  set +e
  lb build --verbose
  STATUS=$?
  set -e

  if [ $STATUS -ne 0 ]; then
    echo "live-build failed with status $STATUS. Check $LOG for details." >&3
    echo "You can inspect $LOG or run the script again after adjustments." >&3
    exit $STATUS
  fi
fi

# Find generated ISO
ISO_PATH=$(find "$BUILD_DIR" -maxdepth 3 -type f -iname "*.iso" -o -iname "*.hybrid*" | head -n1 || true)
if [ -z "$ISO_PATH" ]; then
  # Try common names
  ISO_PATH=$(ls -1t *.iso 2>/dev/null | head -n1 || true)
fi

if [ -z "$ISO_PATH" ]; then
  echo "No ISO found in $BUILD_DIR" >&3
  exit 1
fi

echo "ISO created: $ISO_PATH" >&3

# Copy to Ventoy (verify mount)
if [ -d "$VENTOY_MOUNT" ] && mountpoint -q "$VENTOY_MOUNT"; then
  DEST="$VENTOY_MOUNT/custom-live-${TIMESTAMP}.iso"
  cp -v "$ISO_PATH" "$DEST" >&3 || { echo "Failed to copy ISO to Ventoy" >&3; exit 1; }
  sync
  echo "ISO copied to $DEST" >&3
else
  echo "Ventoy mount $VENTOY_MOUNT not found or not mounted. ISO remains at $ISO_PATH" >&3
fi

# Print short summary
echo "Build complete. ISO: $ISO_PATH" >&3

exit 0
