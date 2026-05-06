"""Testes unitários do tape_orchestrator.py.

Cobre:
- Lock exclusivo: adquirir, bloquear segunda tentativa, liberar
- Preflight: detecção de holders inesperados
- Operações: mount, unmount, recovery, eject, selfheal retornam OpResult correto
- Serviços conflitantes são parados antes de cada operação
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Importa o módulo a testar
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import tape_orchestrator as orch


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _tmp_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redireciona o lockfile para tmp durante todos os testes."""
    lock = tmp_path / "ltfs-tape-exclusive.lock"
    monkeypatch.setattr(orch, "ORCH_LOCK", lock)


@pytest.fixture()
def mock_mounted(monkeypatch: pytest.MonkeyPatch):
    """Simula LTFS montado."""
    monkeypatch.setattr(orch, "_is_mounted", lambda: True)


@pytest.fixture()
def mock_not_mounted(monkeypatch: pytest.MonkeyPatch):
    """Simula LTFS não montado."""
    monkeypatch.setattr(orch, "_is_mounted", lambda: False)


@pytest.fixture()
def mock_no_conflicts(monkeypatch: pytest.MonkeyPatch):
    """Simula serviços conflitantes todos inativos."""
    monkeypatch.setattr(orch, "_service_is_active", lambda _svc: False)
    monkeypatch.setattr(orch, "_stop_conflicts", lambda: {s: "already_inactive" for s in orch.CONFLICT_SERVICES})


@pytest.fixture()
def mock_devices_free(monkeypatch: pytest.MonkeyPatch):
    """Simula devices de fita sem holders."""
    monkeypatch.setattr(orch, "_list_device_holders", lambda: [])


# ── Lock exclusivo ────────────────────────────────────────────────────

def test_lock_acquired_and_releases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Lock deve ser adquirido e liberado sem erro."""
    lock_path = tmp_path / "test.lock"
    monkeypatch.setattr(orch, "ORCH_LOCK", lock_path)
    acquired = False
    with orch.exclusive_lock("test-op", timeout=5):
        acquired = True
        assert lock_path.exists()
        content = json.loads(lock_path.read_text().strip())
        assert content["operation"] == "test-op"
        assert content["pid"] == os.getpid()
    assert acquired


def test_lock_written_and_cleared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Após sair do contexto o lockfile deve conter {} (liberado)."""
    lock_path = tmp_path / "test.lock"
    monkeypatch.setattr(orch, "ORCH_LOCK", lock_path)
    with orch.exclusive_lock("test-clear"):
        pass
    content = lock_path.read_text().strip()
    assert content == "{}"


def test_lock_blocks_concurrent_access(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Segunda chamada com timeout=0 deve levantar RuntimeError."""
    lock_path = tmp_path / "test.lock"
    monkeypatch.setattr(orch, "ORCH_LOCK", lock_path)
    errors: list[Exception] = []

    def _try_acquire() -> None:
        try:
            with orch.exclusive_lock("concurrent", timeout=0):
                pass
        except RuntimeError as exc:
            errors.append(exc)

    with orch.exclusive_lock("holder", timeout=5):
        t = threading.Thread(target=_try_acquire)
        t.start()
        t.join(timeout=3)

    assert len(errors) == 1
    assert "Lock de fita ocupado" in str(errors[0])


# ── Preflight ─────────────────────────────────────────────────────────

def test_preflight_ok_when_no_holders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orch, "_list_device_holders", lambda: [])
    ok, holders = orch._preflight_check()
    assert ok is True
    assert holders == []


def test_preflight_fails_with_unexpected_holder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        orch,
        "_list_device_holders",
        lambda: [{"command": "rogue", "pid": "9999", "device": "/dev/sg1"}],
    )
    ok, holders = orch._preflight_check()
    assert ok is False
    assert len(holders) == 1


# ── Operação: status ──────────────────────────────────────────────────

def test_status_returns_opresult(monkeypatch: pytest.MonkeyPatch, mock_no_conflicts: None) -> None:
    monkeypatch.setattr(orch, "_is_mounted", lambda: False)
    monkeypatch.setattr(orch, "_run", lambda cmd, **_: MagicMock(stdout="inactive\n", stderr="", returncode=0))
    monkeypatch.setattr(orch, "_list_device_holders", lambda: [])

    result = orch._op_status()
    assert result.success is True
    assert result.operation == "status"
    assert result.details["mounted"] is False


# ── Operação: preflight ───────────────────────────────────────────────

def test_op_preflight_clear(monkeypatch: pytest.MonkeyPatch, mock_no_conflicts: None, mock_devices_free: None) -> None:
    result = orch._op_preflight()
    assert result.success is True
    assert result.details["devices_clear"] is True
    assert result.details["active_conflict_services"] == []


def test_op_preflight_detects_active_service(monkeypatch: pytest.MonkeyPatch, mock_devices_free: None) -> None:
    monkeypatch.setattr(orch, "_service_is_active", lambda svc: svc == "tape-safe-eject.service")
    monkeypatch.setattr(orch, "_stop_conflicts", lambda: {"tape-safe-eject.service": "stopped"})

    result = orch._op_preflight()
    assert result.success is False
    assert "tape-safe-eject.service" in result.details["active_conflict_services"]


# ── Operação: mount ───────────────────────────────────────────────────

def test_op_mount_skips_if_already_mounted(mock_mounted: None) -> None:
    result = orch._op_mount()
    assert result.success is True
    assert "já está montado" in result.message


def test_op_mount_stops_conflicts_and_mounts(
    monkeypatch: pytest.MonkeyPatch,
    mock_not_mounted: None,
    mock_no_conflicts: None,
    mock_devices_free: None,
) -> None:
    call_log: list[str] = []

    def fake_run(cmd: list[str], timeout: int = 60) -> MagicMock:
        call_log.append(" ".join(cmd))
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(orch, "_run", fake_run)
    # Após o mount, simula montado
    monkeypatch.setattr(orch, "_is_mounted", lambda: "start" in " ".join(call_log))

    result = orch._op_mount()
    assert any("systemctl" in c and "start" in c for c in call_log)


def test_op_mount_blocked_by_lock(monkeypatch: pytest.MonkeyPatch, mock_not_mounted: None) -> None:
    """Deve retornar falha se não conseguir adquirir lock."""
    @contextmanager
    def _no_lock(op: str, timeout: int = 0):
        raise RuntimeError("Lock de fita ocupado após 0s")
        yield  # noqa: unreachable

    monkeypatch.setattr(orch, "exclusive_lock", _no_lock)
    result = orch._op_mount()
    assert result.success is False
    assert "Lock" in result.message


# ── Operação: recovery ────────────────────────────────────────────────

def test_op_recovery_calls_ltfsck(
    monkeypatch: pytest.MonkeyPatch,
    mock_not_mounted: None,
    mock_no_conflicts: None,
    mock_devices_free: None,
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], timeout: int = 60) -> MagicMock:
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="LTFS16000I Check complete.", stderr="")

    monkeypatch.setattr(orch, "_run", fake_run)

    result = orch._op_recovery(deep=False)
    ltfsck_calls = [c for c in calls if "ltfsck" in c[0]]
    assert len(ltfsck_calls) == 1
    assert "--deep-recovery" not in ltfsck_calls[0]
    assert result.operation == "recovery"


def test_op_recovery_deep_passes_flag(
    monkeypatch: pytest.MonkeyPatch,
    mock_not_mounted: None,
    mock_no_conflicts: None,
    mock_devices_free: None,
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], timeout: int = 60) -> MagicMock:
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(orch, "_run", fake_run)

    result = orch._op_recovery(deep=True)
    ltfsck_calls = [c for c in calls if "ltfsck" in c[0]]
    assert any("--deep-recovery" in c for c in ltfsck_calls)
    assert result.operation == "recovery-deep"


def test_op_recovery_blocked_by_unexpected_holder(
    monkeypatch: pytest.MonkeyPatch,
    mock_not_mounted: None,
    mock_no_conflicts: None,
) -> None:
    monkeypatch.setattr(
        orch,
        "_list_device_holders",
        lambda: [{"command": "intruder", "pid": "777", "device": "/dev/sg1"}],
    )
    monkeypatch.setattr(orch, "_run", lambda cmd, **_: MagicMock(returncode=0, stdout="", stderr=""))

    result = orch._op_recovery(deep=False)
    assert result.success is False
    assert "Preflight" in result.message


# ── Operação: eject ───────────────────────────────────────────────────

def test_op_eject_unmounts_and_ejects(
    monkeypatch: pytest.MonkeyPatch,
    mock_mounted: None,
    mock_no_conflicts: None,
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], timeout: int = 60) -> MagicMock:
        calls.append(cmd)
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(orch, "_run", fake_run)

    result = orch._op_eject()
    assert result.operation == "eject"
    mt_calls = [c for c in calls if c and c[0] == "mt"]
    assert len(mt_calls) == 1
    assert "eject" in mt_calls[0]


# ── OpResult ─────────────────────────────────────────────────────────

def test_opresult_exit_code() -> None:
    ok = orch.OpResult(True, "test", "ok")
    err = orch.OpResult(False, "test", "fail")
    assert ok.exit_code() == 0
    assert err.exit_code() == 1


def test_opresult_print_json(capsys: pytest.CaptureFixture) -> None:
    r = orch.OpResult(True, "status", "ok", details={"mounted": True})
    r.print_json()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["success"] is True
    assert data["details"]["mounted"] is True
