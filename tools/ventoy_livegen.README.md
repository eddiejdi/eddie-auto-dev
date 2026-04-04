# Ventoy Livegen helper

Small helper script to copy or build an ISO and place it on a Ventoy USB.

Quick usage:

1. Copy an existing ISO to Ventoy (auto-detect mount):

```bash
tools/ventoy_livegen.sh --iso ~/Downloads/ubuntu-22.04.iso --ventoy /media/usb
```

2. Build a generic ISO from a directory and copy it to Ventoy:

```bash
tools/ventoy_livegen.sh --dir mylive-tree --output mylive.iso --ventoy /media/usb
```

3. Dry-run to see actions without modifying the USB:

```bash
tools/ventoy_livegen.sh --iso image.iso --ventoy /media/usb --dry-run
```

Notes and caveats:
- This script performs a generic ISO creation; building a fully functional
  distro live ISO requires following the distribution-specific layout
  (EFI files, isolinux/syslinux, squashfs, etc.).
- The script will try to auto-detect Ventoy mounts under `/run/media/$USER`,
  `/media` or `/mnt` if `--ventoy` is not provided.
- When building (`--dir`) the host must have `xorriso` or `genisoimage`.

Support and improvements:
- Add validation of Ventoy JSON and available space.
- Add options to generate persistent data.json for Ventoy if needed.
