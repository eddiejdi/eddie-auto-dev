#!/usr/bin/env python3
"""Orquestrador exclusivo de fitas LTO — ponto único de entrada.

Garante que NENHUMA operação de fita (mount, recovery, eject, selfheal)
seja executada em paralelo com outra. Usa flock POSIX para exclusividade
e para/bloqueia serviços concorrentes antes de liberar o device.

Uso:
    tape-orchestrator mount               # monta LTFS
    tape-orchestrator unmount             # desmonta LTFS
    tape-orchestrator recovery [--deep]   # ltfsck (basic ou deep-recovery)
    tape-orchestrator eject               # ejeção segura
    tape-orchestrator selfheal            # re-mount de recuperação
    tape-orchestrator status              # estado atual (sem lock)
    tape-orchestrator preflight           # verifica concorrência (sem executar)

Variáveis de ambiente reconhecidas:
    LTFS_DEVICE           /dev/sg0 (padrão)
    LTFS_TAPE_DEVICE      /dev/nst0 (padrão)
    LTFS_MOUNT_POINT      /mnt/tape/lto6 (padrão)
    LTFS_SERVICE          ltfs-lto6.service (padrão)
    LTFS_ORCH_LOCK        /run/lock/ltfs-tape-exclusive.lock (padrão)
    LTFS_ORCH_TIMEOUT     600  (segundos de espera pelo lock, 0=não espera)
    LTFS_CONFLICT_SERVICES  lista separada por vírgula
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Generator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [tape-orch] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tape-orchestrator")

# ── Configuração via ambiente ─────────────────────────────────────────
LTFS_DEVICE = os.getenv("LTFS_DEVICE", "/dev/sg0")
LTFS_TAPE_DEVICE = os.getenv("LTFS_TAPE_DEVICE", "/dev/nst0")
LTFS_MOUNT_POINT = Path(os.getenv("LTFS_MOUNT_POINT", "/mnt/tape/lto6"))
LTFS_SERVICE = os.getenv("LTFS_SERVICE", "ltfs-lto6.service")
ORCH_LOCK = Path(os.getenv("LTFS_ORCH_LOCK", "/run/lock/ltfs-tape-exclusive.lock"))
ORCH_TIMEOUT = int(os.getenv("LTFS_ORCH_TIMEOUT", "600"))
LTFS_START_SCRIPT = os.getenv("LTFS_START_SCRIPT", "/usr/local/sbin/ltfs-fc-stable-start")
LTFSCK_BIN = os.getenv("LTFSCK_BIN", "ltfsck")
LTFS_RECOVERY_SCRIPT = os.getenv("LTFS_RECOVERY_SCRIPT", "/usr/local/tools/ltfs_recovery.py")
LTFS_VOLSER = os.getenv("LTFS_VOLSER", "")           # ex: NC2508; descoberto no mount se vazio
LTFS_CURSOR_VOLSER_FILE = Path(os.getenv("LTFS_CURSOR_VOLSER_FILE", "/var/lib/ltfs/current_volser.txt"))

_DEFAULT_CONFLICTS = (
    "tape-safe-eject.service,"
    "lto6-selfheal.service,"
    "lto6-selfheal.timer,"
    "ltfs-idle-unmount.timer,"
    "ltfs-cache-flush.timer,"
    "ltfs-udev-mount.service,"
    "nextcloud-tape-backup.service,"
    "tape-backup.service,"
    "staged-tape-backup.service"
)
CONFLICT_SERVICES: list[str] = [
    s.strip()
    for s in os.getenv("LTFS_CONFLICT_SERVICES", _DEFAULT_CONFLICTS).split(",")
    if s.strip()
]


# ── Estruturas de resultado ────────────────────────────────────────────
@dataclass
class OpResult:
    """Resultado padronizado de uma operação do orquestrador."""

    success: bool
    operation: str
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    details: dict = field(default_factory=dict)

    def print_json(self) -> None:
        print(json.dumps(asdict(self), ensure_ascii=False, indent=2))

    def exit_code(self) -> int:
        return 0 if self.success else 1


# ── Utilitários internos ───────────────────────────────────────────────
def _run(cmd: list[str], timeout: int = 60, check: bool = False) -> subprocess.CompletedProcess[str]:
    """Executa subcomando capturando stdout/stderr."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )
    except subprocess.TimeoutExpired:
        logger.warning("Timeout ao executar: %s", " ".join(cmd))
        return subprocess.CompletedProcess(cmd, -1, "", "timeout")
    except FileNotFoundError:
        logger.debug("Comando não encontrado: %s", cmd[0])
        return subprocess.CompletedProcess(cmd, 127, "", f"command not found: {cmd[0]}")


def _is_mounted() -> bool:
    """Verifica se o mountpoint LTFS está ativo."""
    r = _run(["mountpoint", "-q", str(LTFS_MOUNT_POINT)])
    return r.returncode == 0


def _service_is_active(svc: str) -> bool:
    r = _run(["systemctl", "is-active", "--quiet", svc])
    return r.returncode == 0


def _list_device_holders() -> list[dict]:
    """Retorna processos com FDs abertos nos devices de fita."""
    holders: list[dict] = []
    for dev in (LTFS_DEVICE, LTFS_TAPE_DEVICE):
        r = _run(["lsof", dev])
        for line in (r.stdout or "").splitlines():
            if not line.strip() or line.startswith("COMMAND"):
                continue
            parts = line.split()
            if len(parts) >= 3:
                holders.append({"command": parts[0], "pid": parts[1], "device": dev})
    return holders


def _stop_conflicts() -> dict[str, str]:
    """Para todos os serviços que podem concorrer com operações de fita."""
    results: dict[str, str] = {}
    for svc in CONFLICT_SERVICES:
        if _service_is_active(svc):
            logger.info("Parando serviço concorrente: %s", svc)
            r = _run(["systemctl", "stop", svc], timeout=30)
            results[svc] = "stopped" if r.returncode == 0 else f"stop_failed({r.returncode})"
        else:
            results[svc] = "already_inactive"
    return results


def _restart_stopped_timers(stopped: dict[str, str]) -> None:
    """Reinicia os timers de conflito que foram parados pela operação."""
    for unit, result in stopped.items():
        if result == "stopped" and unit.endswith(".timer"):
            logger.info("Reiniciando timer %s após operação", unit)
            _run(["systemctl", "start", unit], timeout=10)


def _preflight_check() -> tuple[bool, list[dict]]:
    """Verifica se há processos segurando o device. Retorna (ok, holders)."""
    holders = _list_device_holders()
    own_pid = str(os.getpid())
    # filtra o próprio processo (lsof do preflight)
    unexpected = [h for h in holders if h.get("pid") != own_pid]
    return len(unexpected) == 0, unexpected


# ── Lock exclusivo ─────────────────────────────────────────────────────
@contextmanager
def exclusive_lock(operation: str, timeout: int = ORCH_TIMEOUT) -> Generator[None, None, None]:
    """Adquire lock exclusivo de fita. Bloqueia até `timeout` segundos.

    Raises:
        RuntimeError: se o lock não puder ser adquirido dentro do timeout.
    """
    ORCH_LOCK.parent.mkdir(parents=True, exist_ok=True)
    mode = "r+" if ORCH_LOCK.exists() else "w"
    with ORCH_LOCK.open(mode, encoding="utf-8") as fd:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    try:
                        current = ORCH_LOCK.read_text()
                    except OSError:
                        current = "(ilegível)"
                    raise RuntimeError(
                        f"Lock de fita ocupado após {timeout}s. "
                        f"Operação em andamento: {current!r}"
                    )
                logger.info("Lock ocupado, aguardando... (op=%s)", operation)
                time.sleep(5)

        # escreve metadados no lockfile
        fd.seek(0)
        fd.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "operation": operation,
                    "started_at": datetime.now().isoformat(),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        fd.flush()
        fd.truncate()

        logger.info("Lock adquirido (op=%s, pid=%d)", operation, os.getpid())
        try:
            yield
        finally:
            fd.seek(0)
            fd.truncate(0)
            fd.write("{}\n")
            fd.flush()
            fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            logger.info("Lock liberado (op=%s)", operation)


# ── Operações ──────────────────────────────────────────────────────────
def _op_mount() -> OpResult:
    """Monta LTFS garantindo exclusividade."""
    if _is_mounted():
        return OpResult(True, "mount", "LTFS já está montado", details={"mountpoint": str(LTFS_MOUNT_POINT)})

    try:
        stopped: dict[str, str] = {}
        with exclusive_lock("mount"):
            stopped = _stop_conflicts()
            ok, holders = _preflight_check()
            if not ok:
                _restart_stopped_timers(stopped)
                return OpResult(
                    False, "mount",
                    "Preflight falhou: device em uso por processo inesperado",
                    details={"holders": holders, "stopped_services": stopped},
                )

        # O próprio serviço LTFS reentra no lock exclusivo durante o start.
        # Segurar o lock aqui causaria deadlock entre o orchestrator e o unit.
        logger.info("Iniciando mount LTFS via systemctl start %s", LTFS_SERVICE)
        r = _run(["systemctl", "start", LTFS_SERVICE], timeout=480)
        success = r.returncode == 0 and _is_mounted()
        _restart_stopped_timers(stopped)
        if success:
            _cursor_open()
        return OpResult(
            success, "mount",
            "Mount concluído" if success else "Mount falhou",
            details={
                "returncode": r.returncode,
                "stderr": r.stderr.strip(),
                "mounted": _is_mounted(),
                "stopped_services": stopped,
                "cursor_volser": _volser() if success else None,
            },
        )
    except RuntimeError as exc:
        return OpResult(False, "mount", str(exc))


def _op_unmount() -> OpResult:
    """Desmonta LTFS garantindo exclusividade."""
    if not _is_mounted():
        return OpResult(True, "unmount", "LTFS já estava desmontado")

    try:
        with exclusive_lock("unmount"):
            stopped = _stop_conflicts()
            logger.info("Desmontando LTFS...")
            _cursor_close()   # fecha cursor ANTES do unmount — fita ainda acessível
            r = _run(["systemctl", "stop", LTFS_SERVICE], timeout=180)
            still_mounted = _is_mounted()
            success = r.returncode == 0 and not still_mounted
            _restart_stopped_timers(stopped)
            return OpResult(
                success, "unmount",
                "Unmount concluído" if success else "Unmount parcialmente falhou",
                details={
                    "returncode": r.returncode,
                    "still_mounted": still_mounted,
                    "stopped_services": stopped,
                },
            )
    except RuntimeError as exc:
        return OpResult(False, "unmount", str(exc))


def _op_recovery(deep: bool = False) -> OpResult:
    """Executa ltfsck com ou sem --deep-recovery."""
    operation = "recovery-deep" if deep else "recovery"
    cmd = [LTFSCK_BIN]
    if deep:
        cmd.append("--deep-recovery")
    cmd.append(LTFS_DEVICE)

    try:
        with exclusive_lock(operation, timeout=max(ORCH_TIMEOUT, 3600)):
            # Para LTFS se montado
            if _is_mounted():
                logger.info("Desmontando LTFS antes do ltfsck...")
                _run(["systemctl", "stop", LTFS_SERVICE], timeout=180)

            stopped = _stop_conflicts()

            ok, holders = _preflight_check()
            if not ok:
                _restart_stopped_timers(stopped)
                return OpResult(
                    False, operation,
                    "Preflight falhou: device em uso antes do ltfsck",
                    details={"holders": holders, "stopped_services": stopped},
                )

            logger.info("Executando: %s", " ".join(cmd))
            r = _run(cmd, timeout=7200)  # 2h máximo
            success = r.returncode == 0
            cursor_result: dict = {}
            if success:
                cursor_result = _cursor_recover_after_ltfsck()
                logger.info("Cursor recover: %s", cursor_result.get("message", ""))
            _restart_stopped_timers(stopped)
            return OpResult(
                success, operation,
                "ltfsck concluído com sucesso" if success else f"ltfsck saiu com código {r.returncode}",
                details={
                    "command": " ".join(cmd),
                    "returncode": r.returncode,
                    "stdout_tail": r.stdout[-2000:] if r.stdout else "",
                    "stopped_services": stopped,
                    "cursor_recover": cursor_result,
                },
            )
    except RuntimeError as exc:
        return OpResult(False, operation, str(exc))


def _op_eject() -> OpResult:
    """Ejeção segura: desmonta + ejecta via mt."""
    try:
        with exclusive_lock("eject"):
            stopped = _stop_conflicts()
            if _is_mounted():
                logger.info("Desmontando antes do eject...")
                _run(["systemctl", "stop", LTFS_SERVICE], timeout=180)
                time.sleep(3)

            logger.info("Ejetando fita de %s", LTFS_TAPE_DEVICE)
            r = _run(["mt", "-f", LTFS_TAPE_DEVICE, "eject"], timeout=120)
            success = r.returncode == 0
            # Não reinicia timers após eject: fita foi removida, flush não faz sentido.
            return OpResult(
                success, "eject",
                "Eject concluído" if success else f"Eject falhou (rc={r.returncode})",
                details={
                    "device": LTFS_TAPE_DEVICE,
                    "returncode": r.returncode,
                    "stderr": r.stderr.strip(),
                    "stopped_services": stopped,
                },
            )
    except RuntimeError as exc:
        return OpResult(False, "eject", str(exc))


def _op_selfheal() -> OpResult:
    """Re-mount de recuperação via selfheal."""
    try:
        stopped: dict[str, str] = {}
        with exclusive_lock("selfheal"):
            stopped = _stop_conflicts()

            if _is_mounted():
                logger.info("Desmontando LTFS para re-mount...")
                _run(["systemctl", "stop", LTFS_SERVICE], timeout=180)
                time.sleep(5)

            ok, holders = _preflight_check()
            if not ok:
                _restart_stopped_timers(stopped)
                return OpResult(
                    False, "selfheal",
                    "Preflight falhou: device ainda em uso",
                    details={"holders": holders, "stopped_services": stopped},
                )

        logger.info("Re-montando LTFS via systemctl start %s", LTFS_SERVICE)
        r = _run(["systemctl", "start", LTFS_SERVICE], timeout=480)
        mounted = _is_mounted()
        _restart_stopped_timers(stopped)
        return OpResult(
            mounted, "selfheal",
            "Selfheal: LTFS remontado" if mounted else "Selfheal: mount falhou",
            details={
                "returncode": r.returncode,
                "mounted": mounted,
                "stopped_services": stopped,
            },
        )
    except RuntimeError as exc:
        return OpResult(False, "selfheal", str(exc))


def _op_status() -> OpResult:
    """Retorna estado atual da fita e serviços (sem lock, read-only)."""
    mounted = _is_mounted()
    service_state_r = _run(["systemctl", "is-active", LTFS_SERVICE])
    service_state = service_state_r.stdout.strip() or "unknown"

    # Lê lockfile se existir
    lock_info: dict = {}
    try:
        lock_info = json.loads(ORCH_LOCK.read_text().strip())
    except Exception:
        pass

    # Processos nos devices
    holders = _list_device_holders()

    # Estado dos serviços concorrentes
    conflict_states = {s: ("active" if _service_is_active(s) else "inactive") for s in CONFLICT_SERVICES}

    # df se montado
    df_output = ""
    if mounted:
        r = _run(["df", "-h", str(LTFS_MOUNT_POINT)])
        df_output = r.stdout.strip()

    return OpResult(
        True, "status", "Estado atual da fita",
        details={
            "mounted": mounted,
            "mountpoint": str(LTFS_MOUNT_POINT),
            "service": LTFS_SERVICE,
            "service_state": service_state,
            "lock_file": str(ORCH_LOCK),
            "lock_info": lock_info,
            "device_holders": holders,
            "conflict_services": conflict_states,
            "df": df_output,
        },
    )


# ── Write Cursor — integração com ltfs_recovery.py ────────────────────
def _volser() -> str:
    """Descobre o volser atual: env > arquivo de estado > UNKNOWN."""
    if LTFS_VOLSER:
        return LTFS_VOLSER
    try:
        v = LTFS_CURSOR_VOLSER_FILE.read_text().strip()
        if v:
            return v
    except OSError:
        pass
    return "UNKNOWN"


def _cursor_call(mode: str, extra: list[str] | None = None) -> dict:
    """Chama ltfs_recovery.py no modo cursor indicado; retorna payload JSON."""
    cmd = ["python3", LTFS_RECOVERY_SCRIPT, f"--{mode}", "--volser", _volser()]
    if extra:
        cmd.extend(extra)
    try:
        r = _run(cmd, timeout=30)
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    pass
        return {"success": r.returncode == 0, "raw": r.stdout.strip()}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _cursor_open() -> None:
    result = _cursor_call("cursor-open")
    if result.get("success"):
        logger.info("Cursor de escrita aberto: volser=%s", _volser())
    else:
        logger.warning("Falha ao abrir cursor: %s", result)


def _cursor_close() -> None:
    result = _cursor_call("cursor-close")
    if result.get("success"):
        logger.info("Cursor de escrita fechado: volser=%s", _volser())
    else:
        logger.warning("Falha ao fechar cursor: %s", result)


def _cursor_recover_after_ltfsck() -> dict:
    """Atualiza status do cursor para 'recovered' após ltfsck bem-sucedido."""
    result = _cursor_call("cursor-status")
    cursor_data = result.get("details", {}).get("cursor", {})
    status = cursor_data.get("status", "")
    if status == "in_progress":
        recover = _cursor_call("cursor-recover")
        logger.info("Cursor recover após ltfsck: %s", recover.get("message", ""))
        return recover
    return result


def _op_cursor_update(file_path: str, block: int | None = None) -> OpResult:
    """
    Atualiza o cursor de escrita após gravar um arquivo na fita.
    Chamado pelo flush script após cada cópia bem-sucedida.
    """
    volser = _volser()
    extra = ["--file", file_path]
    if block is not None:
        extra += ["--block", str(block)]
    result = _cursor_call("cursor-update", extra)
    return OpResult(
        result.get("success", False),
        "cursor-update",
        result.get("message", "cursor-update concluído"),
        details={"volser": volser, "file": file_path, "block": block, **result},
    )


def _op_cursor_status() -> OpResult:
    """Exibe estado atual do cursor de escrita."""
    result = _cursor_call("cursor-status")
    return OpResult(
        result.get("success", False),
        "cursor-status",
        result.get("message", ""),
        details=result.get("details", result),
    )


def _op_preflight() -> OpResult:
    """Verifica concorrência sem executar nenhuma operação."""
    stopped_candidates = {
        s: ("active" if _service_is_active(s) else "inactive") for s in CONFLICT_SERVICES
    }
    ok, holders = _preflight_check()
    active_conflicts = [s for s, st in stopped_candidates.items() if st == "active"]

    all_clear = ok and len(active_conflicts) == 0
    return OpResult(
        all_clear, "preflight",
        "Devices livres, sem conflitos" if all_clear else "Conflitos detectados",
        details={
            "devices_clear": ok,
            "unexpected_holders": holders,
            "active_conflict_services": active_conflicts,
            "all_conflict_services": stopped_candidates,
        },
    )


# ── CLI ────────────────────────────────────────────────────────────────
_OPS = {
    "mount": _op_mount,
    "unmount": _op_unmount,
    "eject": _op_eject,
    "selfheal": _op_selfheal,
    "status": _op_status,
    "preflight": _op_preflight,
    "cursor-status": _op_cursor_status,
}


def main() -> int:
    """Entry point principal."""
    parser = argparse.ArgumentParser(
        description="Orquestrador exclusivo de operações de fita LTO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "operation",
        choices=list(_OPS) + ["recovery", "cursor-update"],
        help="Operação a executar",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Para 'recovery': usa --deep-recovery no ltfsck",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="Saída em JSON (padrão)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=ORCH_TIMEOUT,
        help=f"Timeout de espera pelo lock em segundos (padrão: {ORCH_TIMEOUT})",
    )
    parser.add_argument(
        "--file",
        dest="file_path",
        default="",
        help="Para 'cursor-update': caminho do arquivo gravado na fita",
    )
    parser.add_argument(
        "--block",
        type=int,
        default=None,
        help="Para 'cursor-update': bloco de fita explícito (opcional; lido via mt tell se omitido)",
    )

    args = parser.parse_args()

    if args.timeout != ORCH_TIMEOUT:
        os.environ["LTFS_ORCH_TIMEOUT"] = str(args.timeout)

    if args.operation == "recovery":
        result = _op_recovery(deep=args.deep)
    elif args.operation == "cursor-update":
        if not args.file_path:
            print(json.dumps({"success": False, "message": "cursor-update requer --file CAMINHO"}))
            return 1
        result = _op_cursor_update(args.file_path, block=args.block)
    else:
        result = _OPS[args.operation]()

    result.print_json()
    return result.exit_code()


if __name__ == "__main__":
    sys.exit(main())
