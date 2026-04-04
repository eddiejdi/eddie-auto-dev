#!/usr/bin/env bash
set -euo pipefail

# tools/ventoy_livegen.sh
# Simple helper to copy an existing ISO to a Ventoy USB, or to build
# a generic ISO from a directory (requires xorriso or genisoimage).
#
# Usage examples:
#   tools/ventoy_livegen.sh --iso ./ubuntu-22.04.iso --ventoy /media/usb
#   tools/ventoy_livegen.sh --dir ./my-live-tree --output mylive.iso --ventoy /media/usb
#   tools/ventoy_livegen.sh --iso image.iso --ventoy /media/usb --dry-run

PROGNAME=$(basename "$0")

die(){ echo "ERROR: $*" >&2; exit 1; }
info(){ echo "[INFO] $*" >&2; }

VENTOY_MOUNT=""
ISO_PATH=""
DIR_PATH=""
OUTPUT_ISO=""
LABEL="LIVE"
DRY_RUN=0
COPY_TARGET="root" # root or iso

show_help(){
  cat <<EOF
$PROGNAME -- Ventoy Live CD helper

Usage:
  $PROGNAME --iso PATH [--ventoy MOUNT] [--target-dir DIR] [--dry-run]
  $PROGNAME --dir PATH [--output FILENAME] [--label NAME] [--ventoy MOUNT] [--dry-run]

Options:
  --iso PATH         Copy existing ISO file to Ventoy USB.
  --dir PATH         Build a generic ISO from a directory (needs xorriso/genisoimage).
  --output FILE      Output ISO filename (when using --dir).
  --label NAME       Volume label for the generated ISO.
  --ventoy MOUNT     Path to Ventoy mountpoint (optional; script will try auto-detect).
  --target-dir DIR   Directory on Ventoy to copy ISO into (default: root).
  --dry-run          Show actions but do not modify the USB.
  --help             Show this help.

Notes:
  - Building a fully bootable linux live ISO from an arbitrary tree
    requires a proper layout (isolinux/syslinux or EFI files). This
    script builds a generic ISO only. For distro-specific ISO building
    follow that distro's documentation.
EOF
}

auto_detect_ventoy(){
  # Try common mount paths and look for an indicator file (ventoy.json) or name.
  local user=${SUDO_USER:-$USER}
  for d in /run/media/${user}/* /media/* /mnt/*; do
    [ -d "$d" ] || continue
    if [ -f "$d/ventoy.json" ] || [ -f "$d/Ventoy.json" ] || [[ "$(basename "$d")" =~ [Vv]entoy ]]; then
      echo "$d"
      return 0
    fi
  done
  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ventoy) VENTOY_MOUNT="$2"; shift 2;;
    --iso) ISO_PATH="$2"; shift 2;;
    --dir) DIR_PATH="$2"; shift 2;;
    --output) OUTPUT_ISO="$2"; shift 2;;
    --label) LABEL="$2"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    --target-dir) COPY_TARGET="$2"; shift 2;;
    --help) show_help; exit 0;;
    *) die "Unknown argument: $1";;
  esac
done

if [[ -z "$ISO_PATH" && -z "$DIR_PATH" ]]; then
  show_help
  die "Either --iso or --dir must be provided"
fi

if [[ -z "$VENTOY_MOUNT" ]]; then
  VENTOY_MOUNT=$(auto_detect_ventoy || true)
  if [[ -z "$VENTOY_MOUNT" ]]; then
    die "Ventoy mount not provided and auto-detect failed. Pass --ventoy /path/to/usb"
  fi
  info "Auto-detected Ventoy mount: $VENTOY_MOUNT"
fi

# ensure mount exists
if [[ ! -d "$VENTOY_MOUNT" ]]; then
  die "Ventoy mountpoint '$VENTOY_MOUNT' does not exist"
fi

if [[ -n "$DIR_PATH" ]]; then
  if [[ -z "$OUTPUT_ISO" ]]; then
    OUTPUT_ISO="$(pwd)/$(basename "$DIR_PATH").iso"
  fi
  info "Building ISO $OUTPUT_ISO from $DIR_PATH"
  if [[ $DRY_RUN -eq 1 ]]; then
    info "DRY RUN: would build ISO from $DIR_PATH to $OUTPUT_ISO"
  else
    if command -v xorriso >/dev/null 2>&1; then
      xorriso -as mkisofs -o "$OUTPUT_ISO" -V "$LABEL" -J -r "$DIR_PATH"
    elif command -v genisoimage >/dev/null 2>&1; then
      genisoimage -o "$OUTPUT_ISO" -V "$LABEL" -J -r "$DIR_PATH"
    else
      die "xorriso or genisoimage is required to build ISO from directory"
    fi
  fi
  ISO_PATH="$OUTPUT_ISO"
fi

if [[ ! -f "$ISO_PATH" ]]; then
  die "ISO file not found: $ISO_PATH"
fi

DEST_DIR="$VENTOY_MOUNT"
if [[ "$COPY_TARGET" != "root" ]]; then
  DEST_DIR="$VENTOY_MOUNT/$COPY_TARGET"
fi

info "Copying ISO to $DEST_DIR"
if [[ $DRY_RUN -eq 1 ]]; then
  info "DRY RUN: would copy $ISO_PATH -> $DEST_DIR"
  exit 0
fi

mkdir -p "$DEST_DIR"
cp -av -- "$ISO_PATH" "$DEST_DIR/"
sync

info "Done. ISO available at: $DEST_DIR/$(basename "$ISO_PATH")"
exit 0
