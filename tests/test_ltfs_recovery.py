from pathlib import Path
from subprocess import CompletedProcess
from datetime import datetime

import os
import pytest

from tools import ltfs_recovery


@pytest.fixture(autouse=True)
def isolate_paths(tmp_path, monkeypatch):
    backup_root = tmp_path / "backups"
    monkeypatch.setenv("LTFS_BACKUP_ROOT", str(backup_root))
    monkeypatch.setenv("TAPE_CATALOG_DB", "postgresql://user:pass@localhost/tape_catalog")
    monkeypatch.setenv("LTFS_BACKUP_RETENTION_DAYS", "1")
    ltfs_recovery.CATALOG_DB = "postgresql://user:pass@localhost/tape_catalog"
    ltfs_recovery.BACKUP_ROOT = backup_root
    yield


def test_check_catalog_success(tmp_path, monkeypatch):
    temp_mount = tmp_path / "tape"
    temp_mount.mkdir()
    ltfs_recovery.LTFS_MOUNT_POINT = temp_mount

    def fake_run(cmd, **kwargs):
        if cmd[0] == "mountpoint":
            return CompletedProcess(cmd, 0, "", "")
        if cmd[:2] == ["ltfs-catalog", "list"]:
            return CompletedProcess(cmd, 0, "OK", "")
        if cmd[0] == "df":
            return CompletedProcess(cmd, 0, "space", "")
        raise AssertionError(f"unexpected command {cmd}")

    monkeypatch.setattr(ltfs_recovery, "_run_command", fake_run)
    result = ltfs_recovery.check_catalog()
    assert result["success"]
    assert "df" in result["details"]


def test_check_catalog_mount_missing(monkeypatch):
    ltfs_recovery.LTFS_ALLOW_UNMOUNTED_OUTSIDE_WINDOW = False
    ltfs_recovery.LTFS_MOUNT_POINT = Path("/does-not-exist")
    res = ltfs_recovery.check_catalog()
    assert not res["success"]
    assert "Mountpoint ausente" in res["message"]


def test_check_catalog_allows_unmounted_outside_window(monkeypatch):
    ltfs_recovery.LTFS_ALLOW_UNMOUNTED_OUTSIDE_WINDOW = True
    ltfs_recovery.LTFS_USAGE_WINDOW_START = "02:00"
    ltfs_recovery.LTFS_USAGE_WINDOW_END = "04:00"
    ltfs_recovery.LTFS_MOUNT_POINT = Path("/does-not-exist")

    res = ltfs_recovery.check_catalog(now=datetime(2026, 4, 1, 1, 0))
    assert res["success"]
    assert res["details"]["mount_expected"] is False
    assert "fora da janela" in res["message"]


def test_check_catalog_requires_mount_inside_window(monkeypatch):
    ltfs_recovery.LTFS_ALLOW_UNMOUNTED_OUTSIDE_WINDOW = True
    ltfs_recovery.LTFS_USAGE_WINDOW_START = "02:00"
    ltfs_recovery.LTFS_USAGE_WINDOW_END = "04:00"
    ltfs_recovery.LTFS_MOUNT_POINT = Path("/does-not-exist")

    res = ltfs_recovery.check_catalog(now=datetime(2026, 4, 1, 3, 0))
    assert not res["success"]
    assert "Mountpoint ausente" in res["message"]


def test_catalog_restore(monkeypatch, tmp_path):
    backup_dir = tmp_path / "latest"
    backup_dir.mkdir(parents=True)
    (backup_dir / "catalog_dump.sql").write_text("SELECT 1;")

    monkeypatch.setenv("LTFS_BACKUP_ROOT", str(tmp_path))
    monkeypatch.setattr(ltfs_recovery, "_latest_backup_dir", lambda: backup_dir)
    monkeypatch.setattr(ltfs_recovery, "LTFS_MOUNT_POINT", tmp_path / "mount")
    (ltfs_recovery.LTFS_MOUNT_POINT).mkdir(parents=True)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[0] == "psql":
            return CompletedProcess(cmd, 0, "", "")
        if cmd[0] == "mountpoint":
            return CompletedProcess(cmd, 0, "", "")
        if cmd[:2] == ["ltfs-catalog", "list"]:
            return CompletedProcess(cmd, 0, "OK", "")
        if cmd[0] == "df":
            return CompletedProcess(cmd, 0, "space", "")
        raise AssertionError(cmd)

    monkeypatch.setattr(ltfs_recovery, "_run_command", fake_run)
    res = ltfs_recovery.catalog_restore()
    assert res["success"]
    assert any(cmd[0] == "psql" for cmd in calls)


def test_backup_catalog_cleanup(monkeypatch, tmp_path):
    old_dir = tmp_path / "old"
    old_dir.mkdir()
    (old_dir / "catalog_dump.sql").write_text("old")
    new_dir = tmp_path / "new"
    new_dir.mkdir()
    (new_dir / "catalog_dump.sql").write_text("new")

    monkeypatch.setenv("LTFS_BACKUP_ROOT", str(tmp_path))
    ltfs_recovery.BACKUP_ROOT = tmp_path
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return CompletedProcess(cmd, 0, "", "")

    os.utime(old_dir, (0, 0))
    monkeypatch.setattr(ltfs_recovery, "_run_command", fake_run)
    res = ltfs_recovery.backup_catalog()
    assert res["success"]
    assert "old" in res["details"]["cleaned"]


def test_backup_catalog_falls_back_to_list(monkeypatch, tmp_path):
    monkeypatch.setenv("LTFS_BACKUP_ROOT", str(tmp_path))
    ltfs_recovery.BACKUP_ROOT = tmp_path

    def fake_run(cmd, **kwargs):
        if cmd[0] == "pg_dump":
            return CompletedProcess(cmd, 0, "", "")
        if cmd[:2] == ["ltfs-catalog", "export"]:
            return CompletedProcess(cmd, 2, "", "invalid choice: 'export'")
        if cmd[:2] == ["ltfs-catalog", "list"]:
            return CompletedProcess(cmd, 0, "tape inventory", "")
        raise AssertionError(cmd)

    monkeypatch.setattr(ltfs_recovery, "_run_command", fake_run)
    res = ltfs_recovery.backup_catalog()
    assert res["success"]
    assert Path(res["details"]["list_file"]).read_text() == "tape inventory"


def test_run_command_handles_missing_binary():
    res = ltfs_recovery._run_command(["command-that-does-not-exist-codex"])
    assert res.returncode == 127
