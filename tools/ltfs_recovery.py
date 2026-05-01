#!/usr/bin/env python3
"""Ferramenta de diagnóstico e recuperação LTFS acionada por alertas."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict


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
BACKUP_ROOT = Path(os.getenv("LTFS_BACKUP_ROOT", "/mnt/raid1/ltfs-cat-backups"))
CATALOG_DB = os.getenv("TAPE_CATALOG_DB", "")
RETENTION_DAYS = int(os.getenv("LTFS_BACKUP_RETENTION_DAYS", "14"))
LTFS_ALLOW_UNMOUNTED_OUTSIDE_WINDOW = os.getenv("LTFS_ALLOW_UNMOUNTED_OUTSIDE_WINDOW", "false").lower() in {"1", "true", "yes", "on"}
LTFS_USAGE_WINDOW_START = os.getenv("LTFS_USAGE_WINDOW_START", "02:00")
LTFS_USAGE_WINDOW_END = os.getenv("LTFS_USAGE_WINDOW_END", "04:00")
LTFS_SERVICE = os.getenv("LTFS_SERVICE", "ltfs-lto6.service")
LTFS_SELFHEAL_SCRIPT = os.getenv("LTFS_SELFHEAL_SCRIPT", "/usr/local/sbin/ltfs-selfheal-remount.sh")
LTFS_DEVICE = os.getenv("LTFS_DEVICE", "/dev/sg1")
LTFS_JOURNAL_LINES = int(os.getenv("LTFS_JOURNAL_LINES", "160"))

KNOWN_ISSUES: list[dict[str, Any]] = [
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
    try:
        return subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


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


def diagnose_known_issue(now: datetime | None = None) -> Dict[str, Any]:
    state = _collect_runtime_state(now=now)
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
    if Path(LTFS_SELFHEAL_SCRIPT).exists():
        proc = _run_command([LTFS_SELFHEAL_SCRIPT])
    else:
        proc = _run_command(["systemctl", "restart", LTFS_SERVICE])
    return {
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }


def _run_ltfsck() -> Dict[str, Any]:
    proc = _run_command(["ltfsck", "-f", LTFS_DEVICE])
    return {
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }


def self_heal(now: datetime | None = None) -> Dict[str, Any]:
    initial_check = check_catalog(now=now)
    if initial_check["success"]:
        return _respond(True, "LTFS já está saudável; sem ação corretiva", {"initial_check": initial_check})

    diagnosis = diagnose_known_issue(now=now)
    diagnosis_issue = diagnosis.get("details", {}).get("issue")
    if not diagnosis.get("success") or not diagnosis_issue:
        return _respond(
            False,
            "Falha LTFS sem assinatura conhecida; escalonar com análise adicional",
            {"initial_check": initial_check, "diagnosis": diagnosis},
        )

    action = diagnosis_issue["recovery_action"]
    action_result: Dict[str, Any]
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
    else:
        return _respond(
            False,
            f"Incidente conhecido detectado, mas exige ajuste manual: {diagnosis_issue['title']}",
            {"initial_check": initial_check, "diagnosis": diagnosis},
        )

    final_check = check_catalog(now=now)
    details = {
        "initial_check": initial_check,
        "diagnosis": diagnosis,
        "action_result": action_result,
        "final_check": final_check,
    }
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


def prepare_mirror() -> Dict[str, Any]:
    return _respond(
        True,
        "Fita secundária aguardando chegada",
        {"instructions": "Registre a nova fita no catálogo e reexecute python3 /usr/local/tools/ltfs_recovery.py --prepare-mirror quando disponível"},
    )


def run_mode(mode: str) -> Dict[str, Any]:
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
    return _respond(False, f"Modo desconhecido: {mode}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LTFS recovery acionado por alertas")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Valida mountpoint e catalogo LTFS")
    group.add_argument("--diagnose", action="store_true", help="Classifica o incidente LTFS por assinatura conhecida")
    group.add_argument("--self-heal", action="store_true", help="Tenta auto-correção para incidentes conhecidos")
    group.add_argument("--catalog-restore", action="store_true", help="Restaura o catalogo a partir do backup mais recente")
    group.add_argument("--drive-check", action="store_true", help="Inspeciona drive e logs do LTFS")
    group.add_argument("--backup-catalog", action="store_true", help="Gera dump diario do catalogo LTFS")
    group.add_argument("--prepare-mirror", action="store_true", help="Registra preparo para futura fita secundaria")

    args = parser.parse_args()
    mode = next(
        flag.replace("_", "-")
        for flag, enabled in vars(args).items()
        if enabled
    )
    result = run_mode(mode)
    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
