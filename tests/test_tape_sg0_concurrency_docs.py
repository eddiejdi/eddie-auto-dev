from __future__ import annotations

from pathlib import Path


def _read_text(relative_path: str) -> str:
    return Path(relative_path).read_text(encoding="utf-8")


def test_sg0_concurrency_guards_and_timer_dropins_are_documented_in_code() -> None:
    guard = _read_text("tools/tape_session_guard.sh")
    tape_access = _read_text("tools/tape-access")
    nextcloud_no_overlap = _read_text("systemd/nextcloud-tape-backup.service.d/30-no-overlap.conf")
    nvme_no_overlap = _read_text("systemd/nvme-tape-drain.service.d/30-no-overlap.conf")
    legacy_gate = _read_text("systemd/lto6-drain-backups.service.d/50-tape-gate.conf")
    nextcloud_timer = _read_text("systemd/nextcloud-tape-backup.timer.d/20-no-ltfs-require.conf")
    nvme_timer = _read_text("systemd/nvme-tape-drain.timer.d/20-no-ltfs-require.conf")
    flush_rearm = _read_text("systemd/ltfs-cache-flush.service.d/70-rearm-timer-on-exit.conf")
    sg0_scope = _read_text("systemd/ltfs-lto6.service.d/65-sg0-tape-access-scope.conf")
    nextcloud_scope = _read_text("systemd/nextcloud-tape-backup.service.d/35-sg0-tape-access-scope.conf")
    nvme_scope = _read_text("systemd/nvme-tape-drain.service.d/35-sg0-tape-access-scope.conf")
    tape_paths_doc = _read_text("docs/tape-archive-paths.md")
    incident_doc = _read_text("docs/INCIDENTS/LTO_SG0_CONCURRENCY_AND_TIMER_RECOVERY_2026-05-21.md")

    assert "active|activating|deactivating|reloading" in guard
    assert "[OBS] sessão anterior ainda ativa" in guard
    assert 'LOCKFILE="${TAPE_ACCESS_LOCKFILE:-/run/lock/tape-access.lock}"' in tape_access
    assert 'QUEUE_DIR="${TAPE_ACCESS_QUEUE_DIR:-/run/tape-queue}"' in tape_access
    assert 'HOLDER_FILE="${TAPE_ACCESS_HOLDER_FILE:-$QUEUE_DIR/current}"' in tape_access

    assert "tape-session-guard --name nextcloud-tape-backup" in nextcloud_no_overlap
    assert "--busy-unit ltfs-cache-flush.service" in nextcloud_no_overlap
    assert "tape-session-guard --name nvme-tape-drain" in nvme_no_overlap
    assert "--busy-unit ltfs-cache-flush.service" in nvme_no_overlap
    assert "tape-session-guard --name lto6-drain-backups" in legacy_gate

    assert "After=" in nextcloud_timer
    assert "Requires=" in nextcloud_timer
    assert "After=" in nvme_timer
    assert "Requires=" in nvme_timer
    assert "restart ltfs-cache-flush.timer" in flush_rearm

    for scoped in (sg0_scope, nextcloud_scope, nvme_scope):
        assert "TAPE_ACCESS_LOCKFILE=/run/lock/tape-access-sg0.lock" in scoped
        assert "TAPE_ACCESS_QUEUE_DIR=/run/tape-queue-sg0" in scoped
        assert "TAPE_ACCESS_HOLDER_FILE=/run/tape-queue-sg0/current" in scoped

    assert "Guardas de concorrência e timers do sg0" in tape_paths_doc
    assert "tape_session_guard.sh" in tape_paths_doc
    assert "tape-access-sg0.lock" in tape_paths_doc
    assert "docs/INCIDENTS/LTO_SG0_CONCURRENCY_AND_TIMER_RECOVERY_2026-05-21.md" in tape_paths_doc

    assert "timers mortos e backlog longo" in incident_doc
    assert "TAPE_ACCESS_LOCKFILE=/run/lock/tape-access-sg0.lock" in incident_doc
    assert "ltfs-cache-flush.service (state=activating)" in incident_doc
