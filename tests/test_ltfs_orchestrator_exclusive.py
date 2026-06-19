from __future__ import annotations

from contextlib import contextmanager

from tools import ltfs_recovery


def test_parse_lsof_output_extracts_holders() -> None:
    raw = """COMMAND   PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
ltfsck  10600 root    4u   CHR  21,0      0t0  427 /dev/sg0
python3  858 root    5u   CHR  9,128     0t0  428 /dev/nst0
"""
    holders = ltfs_recovery._parse_lsof_output(raw)
    assert len(holders) == 2
    assert holders[0]["command"] == "ltfsck"
    assert holders[0]["pid"] == "10600"
    assert holders[1]["command"] == "python3"


def test_parse_lsof_output_ignores_warning_lines() -> None:
    raw = """lsof: WARNING: can't stat() fuse file system /srv/nextcloud/external/LTO
Output information may be incomplete.
COMMAND   PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
ltfsck  10600 root    4u   CHR  21,0      0t0  427 /dev/sg0
"""
    holders = ltfs_recovery._parse_lsof_output(raw)
    assert len(holders) == 1
    assert holders[0]["command"] == "ltfsck"
    assert holders[0]["pid"] == "10600"


def test_filter_unexpected_holders_ignores_allowed_pid_and_cmd() -> None:
    holders = [
        {"command": "ltfsck", "pid": "10", "user": "root", "line": "ltfsck 10 root"},
        {"command": "python3", "pid": "11", "user": "root", "line": "python3 11 root"},
        {"command": "mytool", "pid": "12", "user": "root", "line": "mytool 12 root"},
    ]

    unexpected = ltfs_recovery._filter_unexpected_holders(holders, allowed_pids={11})
    assert len(unexpected) == 1
    assert unexpected[0]["pid"] == "12"


def test_run_mode_orchestrated_mount_dispatch(monkeypatch) -> None:
    expected = {"success": True, "message": "ok", "details": {}}
    monkeypatch.setattr(ltfs_recovery, "orchestrated_mount", lambda: expected)
    assert ltfs_recovery.run_mode("orchestrated-mount") == expected


def test_run_exclusive_operation_blocks_on_unexpected_holder(monkeypatch) -> None:
    @contextmanager
    def fake_lock(*args, **kwargs):
        yield

    monkeypatch.setattr(ltfs_recovery, "_exclusive_tape_lock", fake_lock)
    monkeypatch.setattr(ltfs_recovery, "_stop_conflicting_services", lambda: {"stopped_services": []})
    monkeypatch.setattr(
        ltfs_recovery,
        "_list_tape_holders",
        lambda: [{"command": "rogue", "pid": "999", "user": "root", "line": "rogue 999 root"}],
    )

    response = ltfs_recovery._run_exclusive_operation("deep-recovery", ["ltfsck", "--deep-recovery", "/dev/sg0"])
    assert response["success"] is False
    assert "concorrência" in response["message"]
