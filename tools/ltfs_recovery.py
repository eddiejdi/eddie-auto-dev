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
        return _respond(False, "Drive necessita intervenção", {"catalog": catalog_resp})

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

    export = _run_command(["ltfs-catalog", "export", "--file", str(export_file)])
    if export.returncode != 0:
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
    else:
        list_file.write_text("")

    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    cleaned = []
    for child in BACKUP_ROOT.iterdir():
        if not child.is_dir():
            continue
        if datetime.fromtimestamp(child.stat().st_mtime) < cutoff:
            shutil.rmtree(child, ignore_errors=True)
            cleaned.append(child.name)

    return _respond(
        True,
        "Backup concluído",
        {"dest": str(dest), "cleaned": cleaned, "export_file": str(export_file), "list_file": str(list_file)},
    )


def prepare_mirror() -> Dict[str, Any]:
    return _respond(
        True,
        "Fita secundária aguardando chegada",
        {"instructions": "Registre a nova fita no catálogo e reexecute python3 /usr/local/tools/ltfs_recovery.py --prepare-mirror quando disponível"},
    )


def run_mode(mode: str) -> Dict[str, Any]:
    if mode == "check":
        return check_catalog()
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
