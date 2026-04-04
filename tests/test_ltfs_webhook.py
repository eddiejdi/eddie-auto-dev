from pathlib import Path
from subprocess import CompletedProcess

import pytest

from tools.alerting import ltfs_alert_handler


@pytest.fixture(autouse=True)
def configure_state(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setenv("LTFS_ALERT_STATE_FILE", str(state_file))
    monkeypatch.setenv("LTFS_ALERT_THROTTLE", "1")
    monkeypatch.setattr(ltfs_alert_handler, "LTFS_RECOVERY_SCRIPT", Path("tools/ltfs_recovery.py").resolve())
    ltfs_alert_handler.STATE_FILE = state_file
    ltfs_alert_handler.THROTTLE_SECONDS = 1
    yield


def test_handle_catalog_alert(monkeypatch):
    seq = [
        CompletedProcess(["python3"], 1, "", "check failed"),
        CompletedProcess(["python3"], 0, "restored", ""),
        CompletedProcess(["python3"], 0, "check ok", ""),
    ]

    def fake_run(cmd, **kwargs):
        return seq.pop(0)

    monkeypatch.setattr(ltfs_alert_handler.subprocess, "run", fake_run)
    msg = ltfs_alert_handler.handle_ltfs_alert("ltfs-catalog")
    assert "Catálogo restaurado" in msg


def test_handle_drive_alert(monkeypatch):
    monkeypatch.setattr(
        ltfs_alert_handler.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(["python3"], 0, "drive healthy", ""),
    )
    msg = ltfs_alert_handler.handle_ltfs_alert("ltfs-drive")
    assert "Drive LTFS" in msg


def test_handle_catalog_alert_restore_but_mount_still_down(monkeypatch):
    seq = [
        CompletedProcess(["python3"], 1, "", "check failed"),
        CompletedProcess(["python3"], 1, '{"success": false, "message": "Mountpoint LTFS inativo"}', ""),
    ]

    def fake_run(cmd, **kwargs):
        return seq.pop(0)

    monkeypatch.setattr(ltfs_alert_handler.subprocess, "run", fake_run)
    msg = ltfs_alert_handler.handle_ltfs_alert("ltfs-catalog")
    assert "mount LTFS segue indisponível" in msg


def test_throttle(monkeypatch):
    monkeypatch.setattr(
        ltfs_alert_handler.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(["python3"], 0, "ok", ""),
    )
    first = ltfs_alert_handler.handle_ltfs_alert("ltfs-catalog")
    second = ltfs_alert_handler.handle_ltfs_alert("ltfs-catalog")
    assert "Esperando throttle" in second


def test_remote_command_with_ssh_password(monkeypatch):
    monkeypatch.setenv("LTFS_RECOVERY_SSH_TARGET", "root@192.168.15.4")
    monkeypatch.setenv("LTFS_RECOVERY_SSH_PASSWORD", "secret")
    cmd = ltfs_alert_handler._build_ltfs_command("check")
    assert cmd[:3] == ["sshpass", "-p", "secret"]
    assert "BatchMode=yes" not in cmd
    assert cmd[-3:] == ["python3", "/usr/local/tools/ltfs_recovery.py", "--check"]
