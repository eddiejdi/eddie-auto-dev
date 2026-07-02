import json
import os
from pathlib import Path

import pytest

from tools import ltfs_recovery


@pytest.fixture(autouse=True)
def isolate_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(ltfs_recovery, "LTFS_ORCH_LOCK", tmp_path / "orchestrator.lock")
    monkeypatch.setattr(ltfs_recovery, "LTFS_EXTRA_LOCK_FILES", [tmp_path / "extra.lock"])
    monkeypatch.setattr(ltfs_recovery, "LTFS_SUSPEND_STATE_FILE", tmp_path / "suspended-units.json")
    monkeypatch.setattr(ltfs_recovery, "LTFS_SUSPEND_STATE_FILE_LEGACY", tmp_path / "run" / "suspended-units.json")
    monkeypatch.setattr(ltfs_recovery, "LTFS_RUNTIME_UNITS_DIR", tmp_path / "runtime-units")
    monkeypatch.setattr(ltfs_recovery, "LTFS_TEXTFILE_COLLECTOR_DIR", tmp_path / "textfile")
    monkeypatch.setattr(ltfs_recovery, "LTFS_CURSOR_DIR", tmp_path / "cursors")
    (tmp_path / "runtime-units").mkdir()
    yield


@pytest.fixture
def commands(monkeypatch):
    executed: list[list[str]] = []

    def fake_orchestration(cmd, **kwargs):
        executed.append(cmd)
        return {"command": cmd, "returncode": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr(ltfs_recovery, "_run_orchestration_command", fake_orchestration)
    return executed


@pytest.fixture
def telegram(monkeypatch):
    sent: list[str] = []
    monkeypatch.setattr(ltfs_recovery, "_telegram_send", lambda text: sent.append(text) or True)
    return sent


def test_boot_reconcile_clears_stale_lock(commands, telegram):
    dead_pid = 4000000  # acima de pid_max padrão — garantidamente inexistente
    ltfs_recovery.LTFS_ORCH_LOCK.write_text(f"pid={dead_pid} started_at=2026-07-02T16:00:00\n")

    result = ltfs_recovery.boot_reconcile()

    assert result["success"]
    assert str(ltfs_recovery.LTFS_ORCH_LOCK) in result["details"]["cleared_locks"]
    assert not ltfs_recovery.LTFS_ORCH_LOCK.exists()


def test_boot_reconcile_keeps_lock_of_live_pid(commands, telegram):
    ltfs_recovery.LTFS_ORCH_LOCK.write_text(f"pid={os.getpid()} started_at=2026-07-02T16:00:00\n")

    result = ltfs_recovery.boot_reconcile()

    assert result["success"]
    assert result["details"]["cleared_locks"] == []
    assert ltfs_recovery.LTFS_ORCH_LOCK.exists()


def test_boot_reconcile_resumes_suspended_units_from_state_file(commands, telegram):
    suspension = {
        "reason": "conflict-preflight",
        "suspended_at": "2026-07-02T16:19:55",
        "units": [
            {
                "unit": "ltfs-cache-flush.timer",
                "service": "ltfs-cache-flush.timer",
                "was_active": True,
                "was_masked": False,
                "is_timer": True,
                "mask_result": {"returncode": 0},
            }
        ],
    }
    ltfs_recovery.LTFS_SUSPEND_STATE_FILE.write_text(json.dumps(suspension))

    result = ltfs_recovery.boot_reconcile()

    assert result["success"]
    assert ["systemctl", "unmask", "ltfs-cache-flush.timer"] in commands
    assert ["systemctl", "start", "ltfs-cache-flush.timer"] in commands
    assert not ltfs_recovery.LTFS_SUSPEND_STATE_FILE.exists()


def test_boot_reconcile_reads_legacy_state_file(commands, telegram):
    suspension = {
        "reason": "conflict-preflight",
        "units": [
            {
                "unit": "ltfs-idle-unmount.timer",
                "service": "ltfs-idle-unmount.timer",
                "was_active": True,
                "was_masked": False,
                "is_timer": True,
            }
        ],
    }
    legacy = ltfs_recovery.LTFS_SUSPEND_STATE_FILE_LEGACY
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(json.dumps(suspension))

    result = ltfs_recovery.boot_reconcile()

    assert result["success"]
    assert ["systemctl", "start", "ltfs-idle-unmount.timer"] in commands
    assert not legacy.exists()


def test_boot_reconcile_unmasks_runtime_masked_service(commands, telegram):
    mask_link = ltfs_recovery.LTFS_RUNTIME_UNITS_DIR / ltfs_recovery.LTFS_SERVICE
    mask_link.symlink_to("/dev/null")

    result = ltfs_recovery.boot_reconcile()

    assert result["success"]
    assert ["systemctl", "unmask", "--runtime", ltfs_recovery.LTFS_SERVICE] in commands
    assert ["systemctl", "daemon-reload"] in commands
    unmasked = [entry["unit"] for entry in result["details"]["unmasked_units"]]
    assert ltfs_recovery.LTFS_SERVICE in unmasked


def test_boot_reconcile_alerts_orphan_cursor_without_touching_tape(commands, telegram, monkeypatch):
    orphan = {"volser": "SG0001", "status": "in_progress", "updated_at": "2026-07-01T07:54:42"}
    monkeypatch.setattr(ltfs_recovery, "_list_recovery_cursors", lambda: [orphan])

    result = ltfs_recovery.boot_reconcile()

    assert result["success"]
    assert result["details"]["orphan_cursors"] == [orphan]
    assert len(telegram) == 1
    assert "SG0001" in telegram[0]
    # reconcile nunca dispara comando de fita — só systemctl
    assert all(cmd[0] == "systemctl" for cmd in commands)


def test_boot_reconcile_writes_metrics(commands, telegram):
    result = ltfs_recovery.boot_reconcile()

    assert result["success"]
    prom = ltfs_recovery.LTFS_TEXTFILE_COLLECTOR_DIR / "ltfs_boot_reconcile.prom"
    content = prom.read_text()
    assert "ltfs_boot_reconcile_last_run_timestamp" in content
    assert "ltfs_orphan_cursor_count 0" in content


def test_run_mode_dispatches_boot_reconcile(monkeypatch):
    called = []
    monkeypatch.setattr(ltfs_recovery, "boot_reconcile", lambda: called.append(True) or {"success": True})
    assert ltfs_recovery.run_mode("boot-reconcile")["success"]
    assert called
