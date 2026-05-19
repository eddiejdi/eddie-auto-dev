#!/usr/bin/env python3
"""Ferramenta de diagnóstico e recuperação LTFS acionada por alertas."""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import shutil
import subprocess
import sys
import time as time_module
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger("ltfs-recovery")

# Modo debug: ativado por --debug ou LTFS_DEBUG=1; expõe streaming em tempo real
DEBUG: bool = os.getenv("LTFS_DEBUG", "0").lower() in {"1", "true", "yes", "on"}


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


for env_file in (Path("/etc/default/ltfs-recovery"), Path("/etc/ltfs-catalog.env")):
    _load_env_file(env_file)

LTFS_MOUNT_POINT = Path(os.getenv("LTFS_MOUNT_POINT", "/mnt/tape/lto6"))
LTFS_CURSOR_DIR = Path(os.getenv("LTFS_CURSOR_DIR", "/var/lib/ltfs/cursors"))
BACKUP_ROOT = Path(os.getenv("LTFS_BACKUP_ROOT", "/mnt/raid1/ltfs-cat-backups"))
CATALOG_DB = os.getenv("TAPE_CATALOG_DB", "")
RETENTION_DAYS = int(os.getenv("LTFS_BACKUP_RETENTION_DAYS", "14"))
LTFS_ALLOW_UNMOUNTED_OUTSIDE_WINDOW = os.getenv("LTFS_ALLOW_UNMOUNTED_OUTSIDE_WINDOW", "false").lower() in {"1", "true", "yes", "on"}
LTFS_USAGE_WINDOW_START = os.getenv("LTFS_USAGE_WINDOW_START", "02:00")
LTFS_USAGE_WINDOW_END = os.getenv("LTFS_USAGE_WINDOW_END", "04:00")
LTFS_SERVICE = os.getenv("LTFS_SERVICE", "ltfs-lto6.service")
LTFS_ENABLE_LEGACY_SELFHEAL_SCRIPT = os.getenv("LTFS_ENABLE_LEGACY_SELFHEAL_SCRIPT", "false").lower() in {"1", "true", "yes", "on"}
LTFS_LEGACY_SELFHEAL_SCRIPT = os.getenv("LTFS_LEGACY_SELFHEAL_SCRIPT", "/usr/local/sbin/ltfs-selfheal-remount.sh")
LTFS_DEVICE = os.getenv("LTFS_DEVICE", "/dev/sg0")
LTFS_TAPE_DEVICE = os.getenv("LTFS_TAPE_DEVICE", "/dev/nst0")
LTFS_JOURNAL_LINES = int(os.getenv("LTFS_JOURNAL_LINES", "160"))
LTFS_ORCH_LOCK = Path(os.getenv("LTFS_ORCH_LOCK", "/run/lock/ltfs-orchestrator.lock"))
LTFS_ORCH_LOCK_WAIT_SECONDS = int(os.getenv("LTFS_ORCH_LOCK_WAIT_SECONDS", "0"))
LTFS_SELF_HEAL_STATE_FILE = Path(os.getenv("LTFS_SELF_HEAL_STATE_FILE", "/var/lib/ltfs/self_heal_state.json"))
LTFS_SELF_HEAL_REMOUNT_COOLDOWN_SECONDS = int(os.getenv("LTFS_SELF_HEAL_REMOUNT_COOLDOWN_SECONDS", "300"))
LTFS_SELF_HEAL_LTFSCK_COOLDOWN_SECONDS = int(os.getenv("LTFS_SELF_HEAL_LTFSCK_COOLDOWN_SECONDS", "1800"))
LTFS_SELF_HEAL_DEEP_RECOVERY_COOLDOWN_SECONDS = int(os.getenv("LTFS_SELF_HEAL_DEEP_RECOVERY_COOLDOWN_SECONDS", "21600"))

LTFS_CONFLICT_SERVICES = [
    item.strip()
    for item in os.getenv(
        "LTFS_CONFLICT_SERVICES",
        "tape-safe-eject.service,ltfs-idle-unmount.timer,ltfs-idle-unmount.service,ltfs-cache-flush.timer,ltfs-cache-flush.service,ltfs-udev-mount.service",
    ).split(",")
    if item.strip()
]

LTFS_BACKGROUND_UNITS = [
    item.strip()
    for item in os.getenv(
        "LTFS_BACKGROUND_UNITS",
        "ltfs-cache-flush.timer,ltfs-cache-flush.service,ltfs-idle-unmount.timer,ltfs-idle-unmount.service,lto6-metrics-export.timer,lto6-metrics-export.service",
    ).split(",")
    if item.strip()
]

KNOWN_ISSUES: list[dict[str, Any]] = [
    {
        "id": "eod_missing_deep_recovery",
        "title": "Volume LTFS exige deep recovery",
        "patterns": (
            "EOD of DP(1) is missing",
            "deep recovery operation is required",
            "Use ltfsck with the --deep-recovery option",
        ),
        "recovery_action": "deep_recovery",
        "severity": "critical",
        "explanation": "O mount normal nao converge. A correcao segura e executar ltfsck --deep-recovery com exclusao mutua e timers auxiliares pausados.",
    },
    {
        "id": "media_index_inconsistent",
        "title": "Indice LTFS inconsistente na fita",
        "patterns": (
            "No index found in the index partition",
            "Medium check failed: extra blocks detected",
            "Run ltfsck",
        ),
        "recovery_action": "ltfsck",
        "severity": "critical",
        "explanation": "A fita foi lida, mas o indice LTFS nao bate com a midia. O caso conhecido e executar ltfsck e remontar.",
    },
    {
        "id": "partition_label_inconsistent",
        "title": "Labels LTFS inconsistentes ou truncados",
        "patterns": (
            "Cannot read ANSI label",
            "expected 80 bytes, but received",
            "failed to read partition labels",
            "Failed to read label (-1012)",
        ),
        "recovery_action": "ltfsck",
        "severity": "critical",
        "explanation": "O mount chegou a abrir o drive, mas os labels LTFS lidos da midia estao inconsistentes. O caminho seguro e executar ltfsck e escalar para deep recovery se o problema persistir.",
    },
    {
        "id": "stale_fuse_mount",
        "title": "Mount FUSE residual ou desconectado",
        "patterns": (
            "Transport endpoint is not connected",
            "stale fuse mount",
            "mountpoint LTFS inativo",
        ),
        "recovery_action": "selfheal_remount",
        "severity": "critical",
        "explanation": "O mount existe ou o service ficou num estado quebrado. O caso conhecido e limpar o mount e remontar.",
    },
    {
        "id": "invalid_sync_option",
        "title": "Opcao LTFS/FUSE invalida no wrapper",
        "patterns": (
            "unknown option 'sync_time=",
            'unknown option "sync_time=',
            "sync_time=300",
        ),
        "recovery_action": "manual_config_fix",
        "severity": "critical",
        "explanation": "A build atual do LTFS nao aceita a opcao antiga sync_time separada. Exige ajuste de wrapper, nao so restart.",
    },
    {
        "id": "mount_missing",
        "title": "LTFS desmontado",
        "patterns": (
            "Mountpoint LTFS inativo",
            "Mountpoint ausente",
            "is not mounted",
        ),
        "recovery_action": "selfheal_remount",
        "severity": "warning",
        "explanation": "O filesystem nao esta disponivel. O caso conhecido e tentar o self-heal de remount.",
    },
]


def _run_command(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    if DEBUG:
        LOGGER.debug("[CMD] %s", " ".join(str(c) for c in cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
        if DEBUG and result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                LOGGER.debug("[STDOUT] %s", line)
        if DEBUG and result.stderr.strip():
            for line in result.stderr.strip().splitlines():
                LOGGER.debug("[STDERR] %s", line)
        return result
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def _run_command_streaming(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """Executa comando com saída em tempo real via Popen; usa captura silenciosa quando DEBUG=False."""
    if not DEBUG:
        return _run_command(cmd, timeout=timeout)

    LOGGER.debug("[CMD-STREAM] %s", " ".join(str(c) for c in cmd))
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # mescla stderr no stdout para saída ordenada
            text=True,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\n")
            print(line, flush=True)  # saída em tempo real no terminal
            stdout_lines.append(line)
        proc.wait(timeout=timeout)
        return subprocess.CompletedProcess(cmd, proc.returncode, "\n".join(stdout_lines), "")
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        raise exc
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def _run_orchestration_command(cmd: list[str], streaming: bool = False) -> Dict[str, Any]:
    """Executa comando operacional e retorna payload padronizado."""
    proc = _run_command_streaming(cmd) if streaming else _run_command(cmd)
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }


def _parse_lsof_output(raw_output: str) -> list[Dict[str, str]]:
    """Converte saída do lsof em registros simples de posse de device."""
    holders: list[Dict[str, str]] = []
    for line in raw_output.splitlines():
        if not line.strip() or line.startswith("COMMAND"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        # Ignora warnings do lsof, que podem vir no stderr e não representam
        # processos segurando os devices de fita.
        if not parts[1].isdigit():
            continue
        holders.append(
            {
                "command": parts[0],
                "pid": parts[1],
                "user": parts[2],
                "line": line.strip(),
            }
        )
    return holders


def _list_tape_holders() -> list[Dict[str, str]]:
    """Lista processos com descritor aberto nos devices de fita."""
    proc = _run_command(["lsof", LTFS_DEVICE, LTFS_TAPE_DEVICE])
    output = "\n".join(
        part for part in ((proc.stdout or "").strip(), (proc.stderr or "").strip()) if part
    )
    return _parse_lsof_output(output)


def _filter_unexpected_holders(holders: list[Dict[str, str]], allowed_pids: set[int]) -> list[Dict[str, str]]:
    """Filtra holders que não pertencem ao processo atual/orquestrador."""
    allowed_cmd_tokens = (
        "ltfs_recovery.py",
        "ltfsck",
        "ltfs-fc-stable-start",
        "ltfs-lto6-stop",
    )
    unexpected: list[Dict[str, str]] = []
    for holder in holders:
        try:
            holder_pid = int(holder.get("pid", "0"))
        except ValueError:
            holder_pid = -1
        cmd = holder.get("command", "")
        if holder_pid in allowed_pids:
            continue
        if any(token in cmd for token in allowed_cmd_tokens):
            continue
        unexpected.append(holder)
    return unexpected


def _stop_conflicting_services() -> Dict[str, Any]:
    """Para serviços que podem competir com mount/recovery da fita."""
    return _toggle_systemd_units("stop", LTFS_CONFLICT_SERVICES)


def _toggle_systemd_units(action: str, units: list[str]) -> Dict[str, Any]:
    """Aplica ação em lote nos units systemd e retorna payload detalhado."""
    actions: list[Dict[str, Any]] = []
    for service_name in units:
        actions.append(
            {
                "service": service_name,
                "result": _run_orchestration_command(["systemctl", action, service_name]),
            }
        )
    return {f"{action}ped_services": actions}


def _pause_background_ltfs_units() -> Dict[str, Any]:
    """Pausa timers/units auxiliares enquanto recovery pesado está em curso."""
    return _toggle_systemd_units("stop", LTFS_BACKGROUND_UNITS)


def _resume_background_ltfs_units() -> Dict[str, Any]:
    """Religa timers/units auxiliares após LTFS voltar a um estado saudável."""
    return _toggle_systemd_units("start", LTFS_BACKGROUND_UNITS)


@contextmanager
def _exclusive_tape_lock(wait_seconds: int = LTFS_ORCH_LOCK_WAIT_SECONDS):
    """Garante exclusividade de operações de fita via lockfile."""
    LTFS_ORCH_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LTFS_ORCH_LOCK.open("w", encoding="utf-8") as lock_fd:
        start_time = time_module.time()
        while True:
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if wait_seconds <= 0 or time_module.time() - start_time >= wait_seconds:
                    raise RuntimeError("Lock de fita já está em uso por outro processo") from exc
                time_module.sleep(1)

        try:
            lock_fd.write(f"pid={os.getpid()} started_at={datetime.now().isoformat()}\n")
            lock_fd.flush()
            yield
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


def _run_exclusive_operation(operation: str, command: list[str], streaming: bool = False) -> Dict[str, Any]:
    """Executa operação exclusiva de fita com preflight anti-concorrência."""
    LOGGER.info("Iniciando operação exclusiva LTFS: %s", operation)
    if DEBUG:
        LOGGER.debug("[EXCL] device=%s tape=%s lock=%s", LTFS_DEVICE, LTFS_TAPE_DEVICE, LTFS_ORCH_LOCK)
    try:
        with _exclusive_tape_lock():
            service_actions = _stop_conflicting_services()
            current_holders = _list_tape_holders()
            unexpected = _filter_unexpected_holders(
                current_holders,
                allowed_pids={os.getpid(), os.getppid()},
            )
            if unexpected:
                return _respond(
                    False,
                    f"Operação '{operation}' bloqueada por concorrência no device",
                    {
                        "operation": operation,
                        "holders": current_holders,
                        "unexpected": unexpected,
                        **service_actions,
                    },
                )

            result = _run_orchestration_command(command, streaming=streaming)
            return _respond(
                result["returncode"] == 0,
                f"Operação '{operation}' executada",
                {
                    "operation": operation,
                    "command_result": result,
                    **service_actions,
                },
            )
    except RuntimeError as exc:
        return _respond(False, str(exc), {"operation": operation, "lock_file": str(LTFS_ORCH_LOCK)})


def _respond(success: bool, message: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = {
        "success": success,
        "message": message,
        "details": details or {},
        "timestamp": datetime.now().isoformat(),
    }
    print(json.dumps(payload, ensure_ascii=False))
    return payload


def _journal_tail() -> str:
    proc = _run_command(["journalctl", "-u", LTFS_SERVICE, "-n", str(LTFS_JOURNAL_LINES), "--no-pager"])
    return (proc.stdout or proc.stderr or "").strip()


def _load_self_heal_state() -> Dict[str, Any]:
    try:
        if LTFS_SELF_HEAL_STATE_FILE.exists():
            return json.loads(LTFS_SELF_HEAL_STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        LOGGER.warning("Falha ao ler state file do self-heal: %s", LTFS_SELF_HEAL_STATE_FILE)
    return {}


def _save_self_heal_state(state: Dict[str, Any]) -> None:
    try:
        LTFS_SELF_HEAL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        LTFS_SELF_HEAL_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    except OSError:
        LOGGER.warning("Falha ao gravar state file do self-heal: %s", LTFS_SELF_HEAL_STATE_FILE)


def _action_cooldown_seconds(action: str) -> int:
    return {
        "selfheal_remount": LTFS_SELF_HEAL_REMOUNT_COOLDOWN_SECONDS,
        "ltfsck": LTFS_SELF_HEAL_LTFSCK_COOLDOWN_SECONDS,
        "deep_recovery": LTFS_SELF_HEAL_DEEP_RECOVERY_COOLDOWN_SECONDS,
    }.get(action, 0)


def _action_in_cooldown(action: str, now: datetime | None = None) -> Dict[str, Any] | None:
    state = _load_self_heal_state()
    actions = state.get("actions", {})
    action_state = actions.get(action, {})
    last_attempt = action_state.get("last_attempt_at")
    if not last_attempt:
        return None

    try:
        last_attempt_at = datetime.fromisoformat(last_attempt)
    except ValueError:
        return None

    cooldown = _action_cooldown_seconds(action)
    elapsed = int(((now or datetime.now()) - last_attempt_at).total_seconds())
    if elapsed >= cooldown:
        return None

    return {
        "action": action,
        "last_attempt_at": last_attempt,
        "cooldown_seconds": cooldown,
        "elapsed_seconds": elapsed,
        "remaining_seconds": max(cooldown - elapsed, 0),
        "last_result_success": action_state.get("last_result_success"),
    }


def _record_action_attempt(action: str, success: bool, details: Dict[str, Any] | None = None, now: datetime | None = None) -> None:
    state = _load_self_heal_state()
    actions = state.setdefault("actions", {})
    actions[action] = {
        "last_attempt_at": (now or datetime.now()).isoformat(),
        "last_result_success": success,
        "details": details or {},
    }
    _save_self_heal_state(state)


def _collect_runtime_state(now: datetime | None = None) -> Dict[str, Any]:
    checked_at = (now or datetime.now()).isoformat()
    mount_expected = _is_mount_expected(now)
    mount_exists = LTFS_MOUNT_POINT.exists()
    mount_cmd = _run_command(["mountpoint", "-q", str(LTFS_MOUNT_POINT)]) if mount_exists else subprocess.CompletedProcess([], 1, "", "mountpoint absent")
    is_mounted = mount_exists and mount_cmd.returncode == 0

    systemctl_active = _run_command(["systemctl", "is-active", LTFS_SERVICE])
    service_state = (systemctl_active.stdout or systemctl_active.stderr).strip() or "unknown"

    journal = _journal_tail()
    df = _run_command(["df", "-h", str(LTFS_MOUNT_POINT)]) if is_mounted else subprocess.CompletedProcess([], 1, "", "")

    return {
        "checked_at": checked_at,
        "mountpoint": str(LTFS_MOUNT_POINT),
        "mount_expected": mount_expected,
        "mount_exists": mount_exists,
        "mounted": is_mounted,
        "mount_stderr": mount_cmd.stderr.strip() if hasattr(mount_cmd, "stderr") else "",
        "service": LTFS_SERVICE,
        "service_state": service_state,
        "ltfs_device": LTFS_DEVICE,
        "journal_excerpt": journal,
        "df": df.stdout.strip(),
    }


def _service_is_thrashing(state: Dict[str, Any]) -> bool:
    service_state = (state.get("service_state") or "").strip().lower()
    journal = state.get("journal_excerpt", "").lower()
    if service_state in {"failed", "activating", "deactivating", "auto-restart"}:
        return True
    # Só considera marcadores do journal se o serviço não está claramente parado/saudável.
    # "inactive" indica que o restart loop já esgotou ou foi interrompido — não é thrashing ativo.
    if service_state in {"inactive", "active"}:
        return False
    thrash_markers = (
        "cannot mount the volume",
        "failed to read partition labels",
        "cannot read ansi label",
        "scheduled restart job",
        "failed with result",
    )
    return any(marker in journal for marker in thrash_markers)


def _should_intervene_outside_window(state: Dict[str, Any]) -> bool:
    return not state.get("mount_expected", True) and _service_is_thrashing(state)


def diagnose_known_issue(now: datetime | None = None) -> Dict[str, Any]:
    state = _collect_runtime_state(now=now)
    if DEBUG:
        LOGGER.debug("[DIAGNOSE] service=%s mounted=%s expected=%s", state.get("service_state"), state.get("mounted"), state.get("mount_expected"))
        LOGGER.debug("[DIAGNOSE] journal_lines=%d", len((state.get("journal_excerpt") or "").splitlines()))
    corpus = "\n".join(
        [
            state.get("journal_excerpt", ""),
            state.get("mount_stderr", ""),
            state.get("service_state", ""),
        ]
    )

    matched: dict[str, Any] | None = None
    for issue in KNOWN_ISSUES:
        if any(pattern.lower() in corpus.lower() for pattern in issue["patterns"]):
            matched = issue
            break

    if matched is None and not state["mounted"] and state["mount_expected"]:
        matched = next(issue for issue in KNOWN_ISSUES if issue["id"] == "mount_missing")

    details = {
        "state": state,
        "issue": None,
        "known_issue": False,
    }
    if matched is None:
        return _respond(False, "Nenhuma assinatura conhecida de incidente LTFS encontrada", details)

    issue_details = {
        "id": matched["id"],
        "title": matched["title"],
        "severity": matched["severity"],
        "recovery_action": matched["recovery_action"],
        "explanation": matched["explanation"],
    }
    details["issue"] = issue_details
    details["known_issue"] = True
    return _respond(True, f"Incidente LTFS conhecido detectado: {matched['title']}", details)


def _run_selfheal_script() -> Dict[str, Any]:
    if LTFS_ENABLE_LEGACY_SELFHEAL_SCRIPT and Path(LTFS_LEGACY_SELFHEAL_SCRIPT).exists():
        proc = _run_command([LTFS_LEGACY_SELFHEAL_SCRIPT])
    else:
        proc = _run_command(["systemctl", "restart", LTFS_SERVICE])
    return {
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }


def _run_ltfsck() -> Dict[str, Any]:
    result = _run_exclusive_operation("ltfsck", ["ltfsck", "-f", LTFS_DEVICE], streaming=True)
    details = result.get("details", {})
    command_result = details.get("command_result", {})
    return {
        "returncode": command_result.get("returncode", 1),
        "stdout": command_result.get("stdout", ""),
        "stderr": command_result.get("stderr", ""),
        "details": details,
    }


def _run_deep_recovery() -> Dict[str, Any]:
    paused_units = _pause_background_ltfs_units()
    result = deep_recovery()
    details = result.get("details", {})
    command_result = details.get("command_result", {})
    return {
        "returncode": command_result.get("returncode", 1),
        "stdout": command_result.get("stdout", ""),
        "stderr": command_result.get("stderr", ""),
        "details": details,
        "paused_units": paused_units,
    }


def _execute_recovery_action(action: str) -> Dict[str, Any]:
    action_result: Dict[str, Any]
    resume_background_units = False

    if action == "selfheal_remount":
        action_result = _run_selfheal_script()
    elif action == "ltfsck":
        action_result = _run_ltfsck()
        if action_result["returncode"] == 0:
            restart_result = _run_command(["systemctl", "restart", LTFS_SERVICE])
            action_result["post_restart"] = {
                "returncode": restart_result.returncode,
                "stdout": (restart_result.stdout or "").strip(),
                "stderr": (restart_result.stderr or "").strip(),
            }
    elif action == "deep_recovery":
        action_result = _run_deep_recovery()
        if action_result["returncode"] == 0:
            reset_result = _run_command(["systemctl", "reset-failed", LTFS_SERVICE])
            start_result = _run_command(["systemctl", "start", LTFS_SERVICE])
            action_result["post_restart"] = {
                "reset_failed": {
                    "returncode": reset_result.returncode,
                    "stdout": (reset_result.stdout or "").strip(),
                    "stderr": (reset_result.stderr or "").strip(),
                },
                "start": {
                    "returncode": start_result.returncode,
                    "stdout": (start_result.stdout or "").strip(),
                    "stderr": (start_result.stderr or "").strip(),
                },
            }
            resume_background_units = start_result.returncode == 0
    else:
        return {
            "success": False,
            "returncode": 1,
            "message": f"Ação de recovery não suportada: {action}",
            "details": {},
        }

    _record_action_attempt(
        action,
        action_result.get("returncode", 1) == 0,
        {
            "stdout": action_result.get("stdout", ""),
            "stderr": action_result.get("stderr", ""),
        },
    )
    if resume_background_units:
        action_result["resume_background_units"] = True
    return action_result


def _choose_escalation_action(previous_action: str, diagnosis: Dict[str, Any]) -> str | None:
    issue = diagnosis.get("details", {}).get("issue") or {}
    suggested_action = issue.get("recovery_action")

    if previous_action == "selfheal_remount" and suggested_action in {"ltfsck", "deep_recovery"}:
        return suggested_action
    if previous_action == "ltfsck" and suggested_action == "deep_recovery":
        return suggested_action
    return None


def orchestrated_mount() -> Dict[str, Any]:
    """Monta LTFS via ltfs-fc-stable-start.

    NÃO usa _run_exclusive_operation: o próprio ltfs-fc-stable-start
    adquire flock exclusivo em LTFS_ORCH_LOCK. Envolver com
    _run_exclusive_operation causa deadlock — Python segura o flock
    enquanto o script filho tenta adquirir o mesmo arquivo via novo fd.
    Lição aprendida: 2026-05-18, sg1/sg2 mount timeout.
    """
    LOGGER.info("Iniciando operação exclusiva LTFS: mount")
    service_actions = _stop_conflicting_services()
    result = _run_orchestration_command(["/usr/local/sbin/ltfs-fc-stable-start"], streaming=True)
    return _respond(
        result["returncode"] == 0,
        "Operação 'mount' executada",
        {"operation": "mount", "command_result": result, **service_actions},
    )


def orchestrated_stop() -> Dict[str, Any]:
    """Desmonta LTFS de forma orquestrada e exclusiva."""
    # Pré-passo: fusermount gracioso ANTES de verificar holders.
    # O processo ltfs FUSE mantém /dev/sg0 aberto enquanto montado.
    # Verificar holders primeiro faz o ltfs aparecer como "unexpected holder",
    # bloqueando o stop e forçando o systemd a enviar SIGKILL na fita — causa
    # raiz do incidente NC2508L 2026-05-14 (VOL1 truncada, EOD destruído).
    mp = str(LTFS_MOUNT_POINT)
    if _run_command(["mountpoint", "-q", mp]).returncode == 0:
        LOGGER.info("orchestrated_stop: fusermount gracioso em %s", mp)
        r = _run_command(["fusermount", "-u", mp])
        if r.returncode != 0:
            LOGGER.warning("fusermount -u falhou (rc=%d), tentando -uz (lazy)", r.returncode)
            _run_command(["fusermount", "-u", "-z", mp])
        # Aguardar o processo ltfs liberar sg0 (até 15 s)
        for _ in range(15):
            if not _list_tape_holders():
                break
            time_module.sleep(1)
    return _run_exclusive_operation("stop", ["/usr/local/sbin/ltfs-lto6-stop"])


def deep_recovery() -> Dict[str, Any]:
    """Executa ltfsck --deep-recovery com lock exclusivo de fita."""
    return _run_exclusive_operation("deep-recovery", ["/usr/local/bin/ltfsck", "--deep-recovery", LTFS_DEVICE], streaming=True)


def self_heal(now: datetime | None = None) -> Dict[str, Any]:
    initial_check = check_catalog(now=now)
    if initial_check["success"]:
        runtime_state = _collect_runtime_state(now=now)
        if not _should_intervene_outside_window(runtime_state):
            return _respond(True, "LTFS já está saudável; sem ação corretiva", {"initial_check": initial_check, "runtime_state": runtime_state})

    diagnosis = diagnose_known_issue(now=now)
    diagnosis_issue = diagnosis.get("details", {}).get("issue")
    if not diagnosis.get("success") or not diagnosis_issue:
        return _respond(
            False,
            "Falha LTFS sem assinatura conhecida; escalonar com análise adicional",
            {"initial_check": initial_check, "diagnosis": diagnosis},
        )

    action = diagnosis_issue["recovery_action"]
    if action not in {"selfheal_remount", "ltfsck", "deep_recovery"}:
        return _respond(
            False,
            f"Incidente conhecido detectado, mas exige ajuste manual: {diagnosis_issue['title']}",
            {"initial_check": initial_check, "diagnosis": diagnosis},
        )

    cooldown_info = _action_in_cooldown(action, now=now)
    if cooldown_info:
        return _respond(
            False,
            f"Self-heal em cooldown para ação {action}",
            {
                "initial_check": initial_check,
                "diagnosis": diagnosis,
                "cooldown": cooldown_info,
            },
        )

    recovery_chain: list[Dict[str, Any]] = []
    action_result = _execute_recovery_action(action)
    recovery_chain.append({"action": action, "result": action_result})

    final_check = check_catalog(now=now)
    if not final_check["success"]:
        followup_diagnosis = diagnose_known_issue(now=now)
        escalated_action = _choose_escalation_action(action, followup_diagnosis)
        if escalated_action:
            cooldown_info = _action_in_cooldown(escalated_action, now=now)
            if cooldown_info:
                details = {
                    "initial_check": initial_check,
                    "diagnosis": diagnosis,
                    "action_result": action_result,
                    "recovery_chain": recovery_chain,
                    "final_check": final_check,
                    "followup_diagnosis": followup_diagnosis,
                    "cooldown": cooldown_info,
                }
                return _respond(
                    False,
                    f"Self-heal em cooldown para ação escalada {escalated_action}",
                    details,
                )
            escalated_result = _execute_recovery_action(escalated_action)
            recovery_chain.append({"action": escalated_action, "result": escalated_result})
            final_check = check_catalog(now=now)
            if escalated_result.get("resume_background_units") and final_check["success"]:
                escalated_result["background_units_resumed"] = _resume_background_ltfs_units()
        else:
            followup_diagnosis = None
    else:
        followup_diagnosis = None

    if action_result.get("resume_background_units") and final_check["success"]:
        action_result["background_units_resumed"] = _resume_background_ltfs_units()
    details = {
        "initial_check": initial_check,
        "diagnosis": diagnosis,
        "action_result": action_result,
        "recovery_chain": recovery_chain,
        "final_check": final_check,
    }
    if followup_diagnosis is not None:
        details["followup_diagnosis"] = followup_diagnosis
    if final_check["success"]:
        return _respond(True, f"Self-heal LTFS concluído: {diagnosis_issue['title']}", details)

    return _respond(
        False,
        f"Self-heal LTFS não recuperou o serviço: {diagnosis_issue['title']}",
        details,
    )


def _parse_window_time(raw_value: str) -> time | None:
    try:
        parsed = datetime.strptime(raw_value, "%H:%M")
    except ValueError:
        return None
    return parsed.time()


def _is_mount_expected(now: datetime | None = None) -> bool:
    if not LTFS_ALLOW_UNMOUNTED_OUTSIDE_WINDOW:
        return True

    start_time = _parse_window_time(LTFS_USAGE_WINDOW_START)
    end_time = _parse_window_time(LTFS_USAGE_WINDOW_END)
    if start_time is None or end_time is None:
        return True

    current = (now or datetime.now()).time()
    if start_time <= end_time:
        return start_time <= current < end_time
    return current >= start_time or current < end_time


def _expected_unmounted_response(now: datetime | None = None) -> Dict[str, Any]:
    return _respond(
        True,
        "LTFS desmontado fora da janela de utilização",
        {
            "mount_expected": False,
            "usage_window_start": LTFS_USAGE_WINDOW_START,
            "usage_window_end": LTFS_USAGE_WINDOW_END,
            "checked_at": (now or datetime.now()).isoformat(),
        },
    )


def check_catalog(now: datetime | None = None) -> Dict[str, Any]:
    if not LTFS_MOUNT_POINT.exists():
        if not _is_mount_expected(now):
            return _expected_unmounted_response(now)
        return _respond(False, f"Mountpoint ausente: {LTFS_MOUNT_POINT}")

    mount = _run_command(["mountpoint", "-q", str(LTFS_MOUNT_POINT)])
    if mount.returncode != 0:
        if not _is_mount_expected(now):
            return _expected_unmounted_response(now)
        return _respond(False, "Mountpoint LTFS inativo", {"stderr": mount.stderr.strip()})

    catalog = _run_command(["ltfs-catalog", "list"])
    if catalog.returncode != 0:
        return _respond(False, "ltfs-catalog list falhou", {"stderr": catalog.stderr.strip()})

    df = _run_command(["df", "-h", str(LTFS_MOUNT_POINT)])
    return _respond(True, "Catálogo LTFS acessível", {"df": df.stdout.strip()})


def _latest_backup_dir() -> Path | None:
    if not BACKUP_ROOT.exists():
        return None
    dirs = [p for p in BACKUP_ROOT.iterdir() if p.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda d: d.stat().st_mtime)


def catalog_restore() -> Dict[str, Any]:
    if not CATALOG_DB:
        return _respond(False, "TAPE_CATALOG_DB não configurado")

    backup_dir = _latest_backup_dir()
    if not backup_dir:
        return _respond(False, "Nenhum backup de catálogo disponível")

    dump_file = backup_dir / "catalog_dump.sql"
    if not dump_file.exists():
        return _respond(False, "Dump do catálogo não encontrado", {"backup_dir": str(backup_dir)})

    restore = _run_command(["psql", CATALOG_DB, "-f", str(dump_file)])
    if restore.returncode != 0:
        return _respond(False, "Restauração do catálogo falhou", {"stderr": restore.stderr.strip()})

    return check_catalog()


def drive_check(now: datetime | None = None) -> Dict[str, Any]:
    catalog_resp = check_catalog(now=now)
    if not catalog_resp["success"]:
        diagnosis = diagnose_known_issue(now=now)
        return _respond(False, "Drive necessita intervenção", {"catalog": catalog_resp, "diagnosis": diagnosis})

    if not catalog_resp["details"].get("mount_expected", True):
        return _respond(True, "Drive LTFS em estado seguro fora da janela", {"catalog": catalog_resp})

    dmesg = _run_command(["dmesg", "-T"])
    warnings = [
        line
        for line in dmesg.stdout.splitlines()
        if ("st0" in line.lower() or "lto" in line.lower()) and "error" in line.lower()
    ]
    if warnings:
        return _respond(True, "Drive reportou avisos importantes", {"warnings": warnings[:5]})

    return _respond(True, "Drive LTFS saudável")


def backup_catalog() -> Dict[str, Any]:
    if not CATALOG_DB:
        return _respond(False, "TAPE_CATALOG_DB indefinido")

    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_ROOT / timestamp
    dest.mkdir(parents=True)

    dump_file = dest / "catalog_dump.sql"
    export_file = dest / "ltfs_catalog_export.json"
    list_file = dest / "ltfs_catalog_list.txt"

    dump = _run_command(["pg_dump", CATALOG_DB, "--no-owner", "-f", str(dump_file)])
    if dump.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        return _respond(False, "pg_dump falhou", {"stderr": dump.stderr.strip()})

    # Tenta exportar o catálogo. Nem todas as versões do ltfs-catalog
    # implementam o subcomando `export`; nesse caso, usa o fallback `list`.
    export = _run_command(["ltfs-catalog", "export", "--file", str(export_file)])
    export_succeeded = export.returncode == 0
    if export_succeeded:
        # Se o comando escreveu no stdout em vez do arquivo, salvamos o conteúdo.
        try:
            if export_file.exists():
                pass
            elif export.stdout:
                export_file.write_text(export.stdout)
        except Exception:
            # Não falhar o backup por erro de escrita auxiliar; deixamos sem export_file.
            export_succeeded = False

    if not export_succeeded:
        # Algumas instalacoes do ltfs-catalog expõem apenas index/query/list.
        list_cmd = _run_command(["ltfs-catalog", "list"])
        if list_cmd.returncode != 0:
            shutil.rmtree(dest, ignore_errors=True)
            return _respond(
                False,
                "ltfs-catalog export falhou",
                {"stderr": export.stderr.strip(), "fallback_stderr": list_cmd.stderr.strip()},
            )
        list_file.write_text(list_cmd.stdout)

    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    cleaned = []
    for child in BACKUP_ROOT.iterdir():
        if not child.is_dir():
            continue
        if datetime.fromtimestamp(child.stat().st_mtime) < cutoff:
            shutil.rmtree(child, ignore_errors=True)
            cleaned.append(child.name)

    details: Dict[str, Any] = {"dest": str(dest), "cleaned": cleaned}
    if export_file.exists():
        details["export_file"] = str(export_file)
    if list_file.exists():
        details["list_file"] = str(list_file)

    return _respond(True, "Backup concluído", details)


# ─── Write Cursor — checkpoint de sessão de escrita ───────────────────────────

def _cursor_path(volser: str) -> Path:
    return LTFS_CURSOR_DIR / f"{volser}.json"


def _read_tape_block() -> int | None:
    """Lê posição atual do bloco na fita via mt tell (nst device)."""
    proc = _run_command(["mt", "-f", LTFS_TAPE_DEVICE, "tell"])
    for line in (proc.stdout or "").splitlines():
        line_l = line.lower()
        if "block" in line_l:
            for token in line.split():
                token_clean = token.rstrip(".")
                if token_clean.isdigit():
                    return int(token_clean)
    return None


def _cursor_write(path: Path, data: Dict[str, Any]) -> None:
    """Escrita atômica do cursor via rename."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    tmp.rename(path)


def _cursor_read(volser: str) -> tuple[Dict[str, Any] | None, str]:
    """Lê cursor; retorna (dados, erro). erro='' se ok."""
    path = _cursor_path(volser)
    if not path.exists():
        return None, f"Cursor não encontrado: {path}"
    try:
        return json.loads(path.read_text()), ""
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Erro ao ler cursor: {exc}"


def cursor_open(volser: str, session_id: str | None = None) -> Dict[str, Any]:
    """
    Abre uma sessão de escrita na fita e registra o bloco inicial.
    Deve ser chamado ANTES de qualquer write na sessão.
    """
    LTFS_CURSOR_DIR.mkdir(parents=True, exist_ok=True)
    sid = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    block = _read_tape_block()
    now = datetime.now().isoformat()
    cursor: Dict[str, Any] = {
        "volser": volser,
        "session_id": sid,
        "device": LTFS_DEVICE,
        "tape_device": LTFS_TAPE_DEVICE,
        "opened_at": now,
        "updated_at": now,
        "start_block": block,
        "last_block": block,
        "last_file": None,
        "files_written": [],
        "files_pending": [],
        "status": "in_progress",
    }
    _cursor_write(_cursor_path(volser), cursor)
    return _respond(True, f"Cursor aberto: sessão {sid} a partir do bloco {block}", {
        "cursor": cursor,
        "cursor_file": str(_cursor_path(volser)),
    })


def cursor_update(volser: str, file_path: str, block: int | None = None) -> Dict[str, Any]:
    """
    Atualiza o cursor após gravar um arquivo com sucesso.
    Se block não for passado, lê a posição atual via mt tell.
    """
    data, err = _cursor_read(volser)
    if err:
        return _respond(False, err, {"volser": volser})
    now = datetime.now().isoformat()
    current_block = block if block is not None else _read_tape_block()
    data["last_block"] = current_block
    data["last_file"] = file_path
    data["updated_at"] = now
    data["files_written"].append({
        "path": file_path,
        "block": current_block,
        "written_at": now,
    })
    _cursor_write(_cursor_path(volser), data)
    return _respond(True, f"Cursor atualizado: bloco {current_block} — {file_path}", {
        "cursor_file": str(_cursor_path(volser)),
        "last_block": current_block,
        "files_written_count": len(data["files_written"]),
    })


def cursor_close(volser: str) -> Dict[str, Any]:
    """
    Encerra a sessão de escrita com status 'clean'.
    Indica que a fita está consistente e não precisa de recovery.
    """
    data, err = _cursor_read(volser)
    if err:
        return _respond(False, err, {"volser": volser})
    block = _read_tape_block()
    now = datetime.now().isoformat()
    data["status"] = "clean"
    data["closed_at"] = now
    data["final_block"] = block
    _cursor_write(_cursor_path(volser), data)
    return _respond(True, f"Sessão encerrada limpa: {data['session_id']} — bloco final {block}", {
        "cursor": data,
        "files_written_count": len(data["files_written"]),
    })


def cursor_status(volser: str) -> Dict[str, Any]:
    """Exibe estado atual do cursor de escrita para um volser."""
    data, err = _cursor_read(volser)
    if err:
        return _respond(False, err, {"volser": volser})
    return _respond(True, f"Cursor {volser}: {data.get('status')} — bloco {data.get('last_block')}", {
        "cursor": data,
        "files_written_count": len(data.get("files_written", [])),
        "files_pending_count": len(data.get("files_pending", [])),
    })


def cursor_recover(volser: str) -> Dict[str, Any]:
    """
    Recovery a partir do cursor de escrita:
      1. Lê o checkpoint salvo (last_block + arquivos confirmados)
      2. Pausa units auxiliares
      3. Executa ltfsck para reconstruir o índice LTFS
      4. Reinicia o serviço LTFS
      5. Reporta arquivos confirmados e pendentes (para re-fila)

    Analogia: download manager que retoma do byte onde parou.
    Os arquivos em files_written foram confirmados ANTES da falha.
    Os arquivos em files_pending estavam "em voo" — precisam ser re-escritos.
    """
    data, err = _cursor_read(volser)
    if err:
        return _respond(False, err, {"volser": volser})

    if data.get("status") == "clean":
        return _respond(True, f"Cursor {volser} já está limpo — nenhum recovery necessário", {"cursor": data})

    last_block = data.get("last_block")
    files_written = data.get("files_written", [])
    files_pending = data.get("files_pending", [])

    LOGGER.info("cursor_recover: volser=%s last_block=%s files_confirmed=%d", volser, last_block, len(files_written))

    paused = _pause_background_ltfs_units()

    ltfsck_result = _run_exclusive_operation(
        "ltfsck-cursor-recover",
        ["/usr/local/bin/ltfsck", "-f", LTFS_DEVICE],
        streaming=True,
    )

    now = datetime.now().isoformat()
    data["status"] = "recovered" if ltfsck_result["success"] else "recover_failed"
    data["recovered_at"] = now
    data["recovered_block"] = last_block
    data["ltfsck_rc"] = ltfsck_result.get("details", {}).get("command_result", {}).get("returncode", -1)
    _cursor_write(_cursor_path(volser), data)

    if ltfsck_result["success"]:
        reset = _run_command(["systemctl", "reset-failed", LTFS_SERVICE])
        start = _run_command(["systemctl", "start", LTFS_SERVICE])
        if start.returncode == 0:
            _resume_background_ltfs_units()

    return _respond(
        ltfsck_result["success"],
        f"Recovery do cursor {volser}: {len(files_written)} arquivos recuperados, {len(files_pending)} para re-fila",
        {
            "volser": volser,
            "last_block": last_block,
            "files_recovered": files_written,
            "files_to_requeue": files_pending,
            "ltfsck_result": ltfsck_result,
            "paused_units": paused,
            "cursor_file": str(_cursor_path(volser)),
        },
    )


def cursor_list() -> Dict[str, Any]:
    """Lista todos os cursores ativos no LTFS_CURSOR_DIR."""
    if not LTFS_CURSOR_DIR.exists():
        return _respond(True, "Nenhum cursor encontrado (diretório ausente)", {"cursors": []})
    cursors = []
    for p in sorted(LTFS_CURSOR_DIR.glob("*.json")):
        try:
            c = json.loads(p.read_text())
            cursors.append({
                "volser": c.get("volser"),
                "status": c.get("status"),
                "session_id": c.get("session_id"),
                "last_block": c.get("last_block"),
                "updated_at": c.get("updated_at"),
                "files_written_count": len(c.get("files_written", [])),
                "files_pending_count": len(c.get("files_pending", [])),
            })
        except (OSError, json.JSONDecodeError):
            cursors.append({"file": p.name, "error": "leitura falhou"})
    return _respond(True, f"{len(cursors)} cursor(es) encontrado(s)", {"cursors": cursors})


def prepare_mirror() -> Dict[str, Any]:
    return _respond(
        True,
        "Fita secundária aguardando chegada",
        {"instructions": "Registre a nova fita no catálogo e reexecute python3 /usr/local/tools/ltfs_recovery.py --prepare-mirror quando disponível"},
    )


def run_mode(mode: str, volser: str = "", file_path: str = "", block: int | None = None, session_id: str | None = None) -> Dict[str, Any]:
    if mode == "check":
        return check_catalog()
    if mode == "diagnose":
        return diagnose_known_issue()
    if mode == "self-heal":
        return self_heal()
    if mode == "catalog-restore":
        return catalog_restore()
    if mode == "drive-check":
        return drive_check()
    if mode == "backup-catalog":
        return backup_catalog()
    if mode == "prepare-mirror":
        return prepare_mirror()
    if mode == "orchestrated-mount":
        return orchestrated_mount()
    if mode == "orchestrated-stop":
        return orchestrated_stop()
    if mode == "deep-recovery":
        return deep_recovery()
    # ── cursor ──
    if mode == "cursor-open":
        if not volser:
            return _respond(False, "--cursor-open requer --volser VOLSER")
        return cursor_open(volser, session_id=session_id)
    if mode == "cursor-update":
        if not volser or not file_path:
            return _respond(False, "--cursor-update requer --volser VOLSER --file CAMINHO")
        return cursor_update(volser, file_path, block=block)
    if mode == "cursor-close":
        if not volser:
            return _respond(False, "--cursor-close requer --volser VOLSER")
        return cursor_close(volser)
    if mode == "cursor-status":
        if not volser:
            return _respond(False, "--cursor-status requer --volser VOLSER")
        return cursor_status(volser)
    if mode == "cursor-recover":
        if not volser:
            return _respond(False, "--cursor-recover requer --volser VOLSER")
        return cursor_recover(volser)
    if mode == "cursor-list":
        return cursor_list()
    return _respond(False, f"Modo desconhecido: {mode}")


def main() -> None:
    global DEBUG
    parser = argparse.ArgumentParser(description="LTFS recovery acionado por alertas")
    parser.add_argument(
        "--debug",
        action="store_true",
        default=DEBUG,
        help="Modo debug: streaming em tempo real + logs detalhados (equivale a LTFS_DEBUG=1)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Valida mountpoint e catalogo LTFS")
    group.add_argument("--diagnose", action="store_true", help="Classifica o incidente LTFS por assinatura conhecida")
    group.add_argument("--self-heal", action="store_true", help="Tenta auto-correção para incidentes conhecidos")
    group.add_argument("--catalog-restore", action="store_true", help="Restaura o catalogo a partir do backup mais recente")
    group.add_argument("--drive-check", action="store_true", help="Inspeciona drive e logs do LTFS")
    group.add_argument("--backup-catalog", action="store_true", help="Gera dump diario do catalogo LTFS")
    group.add_argument("--prepare-mirror", action="store_true", help="Registra preparo para futura fita secundaria")
    group.add_argument("--orchestrated-mount", action="store_true", help="Monta LTFS com lock exclusivo e bloqueio de concorrentes")
    group.add_argument("--orchestrated-stop", action="store_true", help="Desmonta LTFS com lock exclusivo")
    group.add_argument("--deep-recovery", action="store_true", help="Executa ltfsck --deep-recovery com lock exclusivo")
    # cursor — write checkpoint / resume
    group.add_argument("--cursor-open", action="store_true", help="Abre sessão de escrita e registra bloco inicial (requer --volser)")
    group.add_argument("--cursor-update", action="store_true", help="Atualiza cursor após gravar arquivo (requer --volser --file)")
    group.add_argument("--cursor-close", action="store_true", help="Encerra sessão de escrita com status limpo (requer --volser)")
    group.add_argument("--cursor-status", action="store_true", help="Exibe estado do cursor de escrita (requer --volser)")
    group.add_argument("--cursor-recover", action="store_true", help="Recovery a partir do cursor: ltfsck + lista de re-fila (requer --volser)")
    group.add_argument("--cursor-list", action="store_true", help="Lista todos os cursores ativos no servidor")

    parser.add_argument("--volser", default="", help="Volser da fita (ex: NC2508) — obrigatório para modos cursor-*")
    parser.add_argument("--file", dest="file_path", default="", help="Caminho do arquivo gravado — usado com --cursor-update")
    parser.add_argument("--block", type=int, default=None, help="Bloco de fita explícito — usado com --cursor-update")
    parser.add_argument("--session-id", default=None, help="ID da sessão de escrita — usado com --cursor-open")

    args = parser.parse_args()
    if args.debug:
        DEBUG = True
        LOGGER.setLevel(logging.DEBUG)
        LOGGER.debug("Modo debug ativado — device=%s tape=%s mount=%s", LTFS_DEVICE, LTFS_TAPE_DEVICE, LTFS_MOUNT_POINT)

    mode = next(
        flag.replace("_", "-")
        for flag, enabled in vars(args).items()
        if isinstance(enabled, bool) and enabled and flag not in {"debug"}
    )
    result = run_mode(mode, volser=args.volser, file_path=args.file_path, block=args.block, session_id=args.session_id)
    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
