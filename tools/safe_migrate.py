#!/usr/bin/env python3
"""
safe_migrate.py — Migração segura de pasta local para armazenamento remoto LTS.

Fluxo:
  1. Transfere via rsync com resume robusto (--partial --append-verify).
  2. Valida sucesso: exit code 0 + contagem de arquivos igual + bytes totais iguais.
  3. Apaga a cópia local SOMENTE após validação completa.
  4. Cria symlink no caminho original apontando para o destino remoto (arquivo virtual).

Uso:
  python3 tools/safe_migrate.py --src "~/Google Drive Pessoal"
      --dst homelab@192.168.15.2:/mnt/lto6-cache-nas/workstation-eddie/Google_Drive_Pessoal
      --dst-local /mnt/lto6-cache-nas/workstation-eddie/Google_Drive_Pessoal
      [--execute]   # sem --execute roda em dry-run

Variáveis de ambiente opcionais:
  SAFE_MIGRATE_SSH_KEY  — caminho para chave SSH (default: ~/.ssh/homelab_key)
  SAFE_MIGRATE_LOG      — caminho do log (default: /tmp/safe_migrate_<timestamp>.log)
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# ─────────────────────────── constantes ────────────────────────────────────

LOCK_PATH = Path("/tmp/safe_migrate.lock")
DEFAULT_SSH_KEY = Path.home() / ".ssh" / "homelab_key"
RSYNC_BIN = shutil.which("rsync") or "rsync"

# ─────────────────────────── logging ───────────────────────────────────────

def _build_logger(log_path: Path) -> logging.Logger:
    """Configura logger com saída para arquivo e stdout."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("safe_migrate")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


# ─────────────────────────── validação ────────────────────────────────────

def _count_files_local(path: Path) -> int:
    """Conta arquivos recursivamente no caminho local."""
    return sum(1 for _ in path.rglob("*") if _.is_file())


def _bytes_total_local(path: Path) -> int:
    """Soma bytes de todos os arquivos no caminho local."""
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _count_and_bytes_remote(dst_remote: str, ssh_key: Path | None, logger: logging.Logger) -> tuple[int, int]:
    """
    Retorna (n_files, n_bytes) do caminho remoto via SSH.

    dst_remote deve ser no formato user@host:/path/to/dir
    """
    if "@" not in dst_remote or ":" not in dst_remote:
        raise ValueError(f"dst_remote deve ter formato user@host:/path, recebido: {dst_remote!r}")
    user_host, remote_path = dst_remote.split(":", 1)
    ssh_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15"]
    if ssh_key and ssh_key.exists():
        ssh_cmd += ["-i", str(ssh_key)]
    ssh_cmd.append(user_host)
    # conta arquivos e soma bytes em um único comando remoto
    remote_script = (
        f"find {remote_path} -type f -printf '%s\\n' 2>/dev/null "
        "| awk 'BEGIN{c=0;b=0} {c++;b+=$1} END{print c\" \"b}'"
    )
    ssh_cmd.append(remote_script)
    logger.debug("SSH count cmd: %s", " ".join(ssh_cmd))
    result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"SSH falhou ao contar remoto: {result.stderr.strip()}")
    parts = result.stdout.strip().split()
    if len(parts) != 2:
        raise RuntimeError(f"Saída inesperada do SSH: {result.stdout.strip()!r}")
    return int(parts[0]), int(parts[1])


def validate_transfer(
    src: Path,
    dst_remote: str,
    ssh_key: Path | None,
    logger: logging.Logger,
) -> bool:
    """
    Valida que o destino remoto tem a mesma contagem de arquivos e total de bytes que a origem local.

    Retorna True se a validação passou, False caso contrário.
    """
    logger.info("Iniciando validação de transferência...")
    local_count = _count_files_local(src)
    local_bytes = _bytes_total_local(src)
    logger.info("Local:  %d arquivos, %d bytes", local_count, local_bytes)

    try:
        remote_count, remote_bytes = _count_and_bytes_remote(dst_remote, ssh_key, logger)
    except Exception as exc:
        logger.error("Falha ao consultar destino remoto: %s", exc)
        return False

    logger.info("Remoto: %d arquivos, %d bytes", remote_count, remote_bytes)

    if local_count != remote_count:
        logger.error(
            "VALIDAÇÃO FALHOU: contagem divergente (local=%d remoto=%d)",
            local_count,
            remote_count,
        )
        return False

    if local_bytes != remote_bytes:
        logger.error(
            "VALIDAÇÃO FALHOU: bytes divergentes (local=%d remoto=%d)",
            local_bytes,
            remote_bytes,
        )
        return False

    logger.info("VALIDAÇÃO OK: %d arquivos, %d bytes", local_count, local_bytes)
    return True


# ─────────────────────────── rsync ────────────────────────────────────────

def run_rsync(
    src: Path,
    dst_remote: str,
    ssh_key: Path | None,
    logger: logging.Logger,
) -> int:
    """Executa rsync com resume robusto. Retorna o exit code."""
    ssh_opts = "ssh -o BatchMode=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=6"
    if ssh_key and ssh_key.exists():
        ssh_opts += f" -i {ssh_key}"

    cmd = [
        RSYNC_BIN,
        "-avs",
        "--partial",
        "--append-verify",
        "--stats",
        "-e", ssh_opts,
        f"{src}/",
        f"{dst_remote}/",
    ]
    logger.info("rsync cmd: %s", " ".join(cmd))
    result = subprocess.run(cmd, text=True, timeout=None)
    logger.info("rsync exit code: %d", result.returncode)
    return result.returncode


# ─────────────────────────── cleanup ─────────────────────────────────────

def remove_local_source(src: Path, logger: logging.Logger) -> None:
    """Remove a pasta local de origem de forma progressiva e segura."""
    logger.info("Removendo cópia local: %s", src)
    shutil.rmtree(src)
    logger.info("Cópia local removida com sucesso: %s", src)


# ─────────────────────────── symlink ─────────────────────────────────────

def create_virtual_symlink(src: Path, dst_local: Path, logger: logging.Logger) -> None:
    """
    Cria symlink no caminho original (src) apontando para dst_local.

    dst_local é o caminho local para o mount remoto LTS (ex: montado via CIFS/NFS).
    """
    if src.exists() or src.is_symlink():
        logger.error(
            "Não é possível criar symlink: caminho ainda existe em %s (remoção incompleta?)", src
        )
        raise FileExistsError(f"Caminho origem ainda existe: {src}")

    src.symlink_to(dst_local)
    logger.info("Symlink virtual criado: %s -> %s", src, dst_local)

    # Validação imediata: o symlink resolve e o destino é acessível
    if not dst_local.exists():
        logger.warning(
            "Destino do symlink não está acessível agora: %s (mount pode estar offline)", dst_local
        )
    else:
        logger.info("Symlink validado: destino acessível")


# ─────────────────────────── fluxo principal ──────────────────────────────

def migrate(
    src: Path,
    dst_remote: str,
    dst_local: Path,
    ssh_key: Path | None,
    dry_run: bool,
    logger: logging.Logger,
) -> int:
    """
    Orquestra o fluxo completo de migração segura.

    Retorna 0 em sucesso, != 0 em falha.
    """
    logger.info("=" * 60)
    logger.info("INÍCIO DA MIGRAÇÃO")
    logger.info("  src       : %s", src)
    logger.info("  dst_remote: %s", dst_remote)
    logger.info("  dst_local : %s", dst_local)
    logger.info("  dry_run   : %s", dry_run)
    logger.info("=" * 60)

    if not src.exists():
        logger.error("Origem não existe: %s", src)
        return 1

    if dry_run:
        local_count = _count_files_local(src)
        local_bytes = _bytes_total_local(src)
        logger.info("[DRY-RUN] Origem: %d arquivos, %d bytes", local_count, local_bytes)
        logger.info("[DRY-RUN] rsync seria executado para: %s", dst_remote)
        logger.info("[DRY-RUN] Após validação, %s seria removido", src)
        logger.info("[DRY-RUN] Symlink %s -> %s seria criado", src, dst_local)
        logger.info("[DRY-RUN] Nenhuma alteração foi feita.")
        return 0

    # ── Fase 1: transferir ──
    rsync_rc = run_rsync(src, dst_remote, ssh_key, logger)
    if rsync_rc != 0:
        logger.error("FALHA NO RSYNC (exit=%d). Cópia local preservada.", rsync_rc)
        return rsync_rc

    # ── Fase 2: validar ──
    if not validate_transfer(src, dst_remote, ssh_key, logger):
        logger.error("VALIDAÇÃO FALHOU. Cópia local preservada. Verifique o destino remoto.")
        return 2

    # ── Fase 3: remover local ──
    try:
        remove_local_source(src, logger)
    except Exception as exc:
        logger.error("Erro ao remover cópia local: %s", exc)
        return 3

    # ── Fase 4: criar symlink virtual ──
    try:
        create_virtual_symlink(src, dst_local, logger)
    except Exception as exc:
        logger.error(
            "Erro ao criar symlink: %s. Origem removida mas sem representação virtual!", exc
        )
        return 4

    logger.info("=" * 60)
    logger.info("MIGRAÇÃO CONCLUÍDA COM SUCESSO")
    logger.info("  Virtual: %s -> %s", src, dst_local)
    logger.info("=" * 60)
    return 0


# ─────────────────────────── CLI ─────────────────────────────────────────

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Migração segura de pasta local para LTS com symlink virtual."
    )
    p.add_argument("--src", required=True, type=Path, help="Caminho local de origem (ex: ~/Google Drive Pessoal)")
    p.add_argument(
        "--dst",
        required=True,
        help="Destino remoto rsync no formato user@host:/path",
    )
    p.add_argument(
        "--dst-local",
        required=True,
        type=Path,
        help="Caminho local para o mount do destino (usado no symlink)",
    )
    p.add_argument(
        "--ssh-key",
        type=Path,
        default=Path(os.environ.get("SAFE_MIGRATE_SSH_KEY", str(DEFAULT_SSH_KEY))),
        help="Chave SSH para conexão remota",
    )
    p.add_argument(
        "--log",
        type=Path,
        default=Path(
            os.environ.get(
                "SAFE_MIGRATE_LOG",
                f"/tmp/safe_migrate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            )
        ),
    )
    p.add_argument(
        "--execute",
        action="store_true",
        help="Executa de verdade (sem --execute roda em dry-run)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada principal."""
    args = _parse_args(argv)
    src = args.src.expanduser().resolve()
    dst_local = args.dst_local.expanduser()
    dry_run = not args.execute
    ssh_key: Path | None = args.ssh_key if args.ssh_key.exists() else None

    logger = _build_logger(args.log)

    # lock para evitar execuções concorrentes
    lock_fd = LOCK_PATH.open("w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logging.error("Outra instância já está rodando (lock: %s). Abortando.", LOCK_PATH)
        lock_fd.close()
        return 10

    try:
        return migrate(src, args.dst, dst_local, ssh_key, dry_run, logger)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
        try:
            LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
