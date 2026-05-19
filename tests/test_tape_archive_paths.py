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


def test_logrotate_archives_to_tape_logs() -> None:
    snapshot_rotate = _read_text("scripts/create_snapshot.logrotate")
    service_rotate = _read_text("tools/backup/homelab-service-logs.logrotate")
    app_var_rotate = _read_text("tools/backup/homelab-app-var-logs.logrotate")
    app_home_rotate = _read_text("tools/backup/homelab-app-home-logs.logrotate")
    runner_rotate = _read_text("tools/backup/homelab-actions-runner-diag.logrotate")
    tape_conf = _read_text("tools/backup/logrotate-tape.conf")
    tape_runner = _read_text("tools/backup/tape_logrotate_runner.sh")
    tape_drain = _read_text("tools/backup/tape_log_spool_drain.sh")
    tape_drain_sg1_service = _read_text("systemd/homelab-tape-log-drain-sg1.service")
    tape_drain_sg1_timer = _read_text("systemd/homelab-tape-log-drain-sg1.timer")
    tape_drain_nextcloud_service = _read_text("systemd/homelab-tape-log-drain-nextcloud.service")
    tape_drain_nextcloud_timer = _read_text("systemd/homelab-tape-log-drain-nextcloud.timer")
    tape_sg1_mount = _read_text("systemd/mnt-tape_sg1.mount")
    tape_sg1_automount = _read_text("systemd/mnt-tape_sg1.automount")
    nas_sg1_service = _read_text("systemd/ltfs-lto6-sg1.service")
    nas_sg1_env = _read_text("systemd/ltfs-lto6-sg1.env")
    ltfs_start = _read_text("tools/ltfs-lto6-start")

    assert "olddir /var/spool/tape-log-buffer/incoming" in snapshot_rotate
    assert "su root root" in snapshot_rotate
    assert "createolddir 1777 root root" in snapshot_rotate
    assert "dateformat -%Y%m%d-%H%M%S" in snapshot_rotate

    assert "/var/log/cloudflared.log" in service_rotate
    assert "/var/log/dnsproxy.log" in service_rotate
    assert "/var/log/homelab-disk-backup.log" in service_rotate
    assert "/var/log/ltfs-nfs-remount.log" in service_rotate
    assert "/var/log/ltfs-selfheal.log" in service_rotate
    assert "olddir /var/spool/tape-log-buffer/incoming" in service_rotate
    assert "createolddir 1777 root root" in service_rotate
    assert "dateformat -%Y%m%d-%H%M%S" in service_rotate
    assert "nocompress" in service_rotate

    assert "/var/log/iot-bypass-autodetect.log" in app_var_rotate
    assert "/var/log/eddie-expurgo-error.log" in app_var_rotate
    assert "/var/log/alertmanager-telegram.log" in app_var_rotate
    assert "/var/log/openwebui_roster.log" in app_var_rotate
    assert "olddir /var/spool/tape-log-buffer/incoming" in app_var_rotate
    assert "createolddir 1777 root root" in app_var_rotate
    assert "dateformat -%Y%m%d-%H%M%S" in app_var_rotate
    assert "nocompress" in app_var_rotate

    assert "/home/homelab/monitor_status.log" in app_home_rotate
    assert "/home/homelab/nextcloud/data_local/nextcloud.log" in app_home_rotate
    assert "/home/homelab/myClaude/btc_trading_agent/logs/*.log" in app_home_rotate
    assert "/opt/homeassistant/config/home-assistant.log" in app_home_rotate
    assert "olddir /var/spool/tape-log-buffer/incoming" in app_home_rotate
    assert "createolddir 1777 root root" in app_home_rotate
    assert "dateformat -%Y%m%d-%H%M%S" in app_home_rotate
    assert "nocompress" in app_home_rotate

    assert "/home/homelab/actions-runner/_diag/*.log" in runner_rotate
    assert "maxsize 5M" in runner_rotate
    assert "olddir /var/spool/tape-log-buffer/incoming" in runner_rotate
    assert "createolddir 1777 root root" in runner_rotate
    assert "dateformat -%Y%m%d-%H%M%S" in runner_rotate
    assert "nocompress" in runner_rotate

    assert "include /usr/local/etc/logrotate-tape.d" in tape_conf
    assert 'LOGROTATE_STATE="${LOGROTATE_STATE:-/var/lib/logrotate/tape.status}"' in tape_runner
    assert 'SPOOL_ROOT="${SPOOL_ROOT:-/var/spool/tape-log-buffer}"' in tape_runner
    assert 'SPOOL_INCOMING_DIR="${SPOOL_INCOMING_DIR:-$SPOOL_ROOT/incoming}"' in tape_runner
    assert 'DEFAULT_ROUTE="${DEFAULT_ROUTE:-tape_sg1}"' in tape_runner
    assert 'printf \'%s\\n\' "$DEFAULT_ROUTE" > "$stamp"' in tape_runner
    assert 'ROUTE_NAME="${ROUTE_NAME:-tape_sg1}"' in tape_drain
    assert 'ROUTE_QUEUE_DIR="${ROUTE_QUEUE_DIR:-$SPOOL_ROOT/routes/$ROUTE_NAME}"' in tape_drain
    assert 'ROUTE_TARGET_ROOT="${ROUTE_TARGET_ROOT:-/mnt/tape_sg1/logs}"' in tape_drain
    assert 'REQUIRE_MOUNTPOINT="${REQUIRE_MOUNTPOINT:-}"' in tape_drain
    assert 'mountpoint -q "$REQUIRE_MOUNTPOINT"' in tape_drain
    assert "--remove-source-files" in tape_drain
    assert 'stamped_route="$(tr -d \'\\n\' < "$stamp" 2>/dev/null || true)"' in tape_drain
    assert "RequiresMountsFor=/mnt/tape_sg1/logs" in tape_drain_sg1_service
    assert "Environment=ROUTE_NAME=tape_sg1" in tape_drain_sg1_service
    assert "Environment=ROUTE_TARGET_ROOT=/mnt/tape_sg1/logs" in tape_drain_sg1_service
    assert "Environment=REQUIRE_MOUNTPOINT=/mnt/tape_sg1" in tape_drain_sg1_service
    assert "Unit=homelab-tape-log-drain-sg1.service" in tape_drain_sg1_timer
    assert "Environment=ROUTE_NAME=nextcloud" in tape_drain_nextcloud_service
    assert "Environment=ROUTE_TARGET_ROOT=/mnt/raid1/lto6-cache/logs" in tape_drain_nextcloud_service
    assert "Unit=homelab-tape-log-drain-nextcloud.service" in tape_drain_nextcloud_timer
    assert "What=//192.168.15.4/LTO6_SG1" in tape_sg1_mount
    assert "Where=/mnt/tape_sg1" in tape_sg1_mount
    assert "Type=cifs" in tape_sg1_mount
    assert "TimeoutSec=20" in tape_sg1_mount
    assert "Where=/mnt/tape_sg1" in tape_sg1_automount
    assert "TimeoutIdleSec=10min" in tape_sg1_automount
    assert "EnvironmentFile=-/etc/default/ltfs-lto6-sg1" in nas_sg1_service
    assert "/usr/local/tools/ltfs_recovery.py --orchestrated-mount" in nas_sg1_service
    assert "/usr/local/tools/ltfs_recovery.py --orchestrated-stop" in nas_sg1_service
    assert "mount --bind /mnt/tape/lto6-sg1 /run/ltfs-export/lto6-sg1" in nas_sg1_service
    assert "LTFS_SERVICE=ltfs-lto6-sg1.service" in nas_sg1_env
    assert "LTFS_MOUNT_POINT=/mnt/tape/lto6-sg1" in nas_sg1_env
    assert "LTFS_DEVICE=/dev/sg2" in nas_sg1_env
    assert "LTFS_TAPE_DEVICE=/dev/nst2" in nas_sg1_env
    assert "LTO6_ST_DEV=/dev/st2" in nas_sg1_env
    assert "LTFS_SELF_HEAL_STATE_FILE=/var/lib/ltfs/self_heal_state_sg1.json" in nas_sg1_env
    assert "LTFS_CURSOR_DIR=/var/lib/ltfs/cursors" in nas_sg1_env
    assert "exec 9>&-" in ltfs_start
    assert "nohup sh -c 'exec 9>&-; exec \"$@\"' sh \"$@\"" in ltfs_start
