from __future__ import annotations

from pathlib import Path


def _read_text(relative_path: str) -> str:
    return Path(relative_path).read_text(encoding="utf-8")


def test_iso_builders_write_to_tape_archive_root() -> None:
    host_script = _read_text("create_live_iso_from_host.sh")
    snapshot_script = _read_text("create_live_iso_from_snapshot.sh")

    assert 'TAPE_ARCHIVE_ROOT="${TAPE_ARCHIVE_ROOT:-/mnt/tape_sg0}"' in host_script
    assert 'ISO_OUTPUT_DIR="${ISO_OUTPUT_DIR:-$TAPE_ARCHIVE_ROOT/isos}"' in host_script
    assert 'LOG_DIR="${LOG_DIR:-$TAPE_ARCHIVE_ROOT/logs}"' in host_script
    assert 'cp -v "$ISO_PATH" "$ARCHIVE_DEST"' in host_script

    assert 'TAPE_ARCHIVE_ROOT="${TAPE_ARCHIVE_ROOT:-/mnt/tape_sg0}"' in snapshot_script
    assert 'ISO_OUTPUT_DIR="${ISO_OUTPUT_DIR:-$TAPE_ARCHIVE_ROOT/isos}"' in snapshot_script
    assert 'LOG_DIR="${LOG_DIR:-$TAPE_ARCHIVE_ROOT/logs}"' in snapshot_script
    assert 'cp -v "$BUILD_DIR/custom-live-${TIMESTAMP}.iso" "$ARCHIVE_DEST"' in snapshot_script


def test_ltfs_backup_catalog_uses_tape_log_root() -> None:
    script = _read_text("tools/ltfs_backup_catalog.sh")
    trigger_script = _read_text("tools/ltfs-trigger-homelab-remount.sh")
    nfs_script = _read_text("tools/ltfs-nfs-remount.sh")
    selfheal_script = _read_text("tools/ltfs-selfheal-remount.sh")

    assert 'TAPE_ARCHIVE_ROOT="${TAPE_ARCHIVE_ROOT:-/mnt/tape_sg0}"' in script
    assert 'LOG_DIR="${LTFS_LOG_DIR:-$TAPE_ARCHIVE_ROOT/logs}"' in script
    assert 'LOG_FILE="$LOG_DIR/ltfs_backup_catalog.log"' in script
    assert 'ERR_FILE="$LOG_DIR/ltfs_export.err"' in script

    assert 'TAPE_LOG_ROOT="${TAPE_LOG_ROOT:-/mnt/tape_sg0/logs}"' in trigger_script
    assert 'LOG="${LOG:-$TAPE_LOG_ROOT/ltfs-lto6.log}"' in trigger_script

    assert 'TAPE_LOG_ROOT="${TAPE_LOG_ROOT:-/mnt/tape_sg0/logs}"' in nfs_script
    assert 'LOG="${LOG:-$TAPE_LOG_ROOT/ltfs-nfs-remount.log}"' in nfs_script

    assert 'TAPE_LOG_ROOT="${TAPE_LOG_ROOT:-/mnt/tape_sg0/logs}"' in selfheal_script
    assert 'LOG="${LTFS_SELFHEAL_LOG:-$TAPE_LOG_ROOT/ltfs-selfheal.log}"' in selfheal_script