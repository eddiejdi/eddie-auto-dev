#!/usr/bin/env python3
"""
fix-staging-perms — Garante permissões corretas do staging Nextcloud LTO no boot.

Executa como systemd oneshot antes do Nextcloud e do ltfs-cache-flush.
Corrige: uid=33 (www-data), gid=33, mode=770 em /mnt/raid1/lto6-cache
e garante que o bind mount /mnt/lto6-nc está ativo.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [fix-staging-perms] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("fix-staging-perms")

STAGING_DIR = Path("/mnt/raid1/lto6-cache")
BIND_MOUNT = Path("/mnt/lto6-nc")
EXPECTED_UID = 33  # www-data
EXPECTED_GID = 33  # www-data
EXPECTED_MODE = 0o770
FSTAB_ENTRY = "/mnt/raid1/lto6-cache /mnt/lto6-nc none bind 0 0"


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    log.debug("[CMD] %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def ensure_staging_dir() -> bool:
    """Cria diretório de staging se não existir."""
    if not STAGING_DIR.exists():
        log.info("Criando diretório de staging: %s", STAGING_DIR)
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
    return True


def fix_permissions() -> bool:
    """Ajusta owner, group e mode do staging."""
    try:
        current = STAGING_DIR.stat()
        changes = []

        if current.st_uid != EXPECTED_UID or current.st_gid != EXPECTED_GID:
            log.info("Ajustando owner: %d:%d -> %d:%d", current.st_uid, current.st_gid, EXPECTED_UID, EXPECTED_GID)
            os.chown(STAGING_DIR, EXPECTED_UID, EXPECTED_GID)
            changes.append("owner")

        current_mode = current.st_mode & 0o777
        if current_mode != EXPECTED_MODE:
            log.info("Ajustando mode: %o -> %o", current_mode, EXPECTED_MODE)
            os.chmod(STAGING_DIR, EXPECTED_MODE)
            changes.append("mode")

        if changes:
            log.info("Permissões corrigidas: %s", ", ".join(changes))
        else:
            log.debug("Permissões já corretas: uid=%d gid=%d mode=%o", EXPECTED_UID, EXPECTED_GID, EXPECTED_MODE)
        return True
    except Exception as e:
        log.error("Falha ao ajustar permissões: %s", e)
        return False


def ensure_bind_mount() -> bool:
    """Garante que o bind mount está ativo."""
    # Verifica se já está montado
    result = run_cmd(["mountpoint", "-q", str(BIND_MOUNT)], check=False)
    if result.returncode == 0:
        log.debug("Bind mount já ativo: %s", BIND_MOUNT)
        return True

    # Tenta montar via systemd (fstab)
    log.info("Montando bind mount: %s -> %s", STAGING_DIR, BIND_MOUNT)
    BIND_MOUNT.parent.mkdir(parents=True, exist_ok=True)

    # Verifica entrada no fstab
    fstab_check = run_cmd(["grep", "-q", str(STAGING_DIR), "/etc/fstab"], check=False)
    if fstab_check.returncode != 0:
        log.warning("Entrada fstab não encontrada, adicionando: %s", FSTAB_ENTRY)
        try:
            with open("/etc/fstab", "a") as f:
                f.write(f"\n{FSTAB_ENTRY}\n")
        except Exception as e:
            log.error("Falha ao escrever fstab: %s", e)
            return False

    # Monta
    mount_result = run_cmd(["mount", str(BIND_MOUNT)], check=False)
    if mount_result.returncode != 0:
        log.error("Falha no mount: %s", mount_result.stderr)
        return False

    log.info("Bind mount ativado: %s", BIND_MOUNT)
    return True


def validate_write_as_www_data() -> bool:
    """Valida escrita como www-data no container Nextcloud (se rodando)."""
    # Tenta detectar container Nextcloud
    try:
        result = run_cmd(["docker", "ps", "--format", "{{.Names}}"], check=False)
        containers = result.stdout.strip().split("\n")
        nc_container = None
        for c in containers:
            if "nextcloud" in c.lower():
                nc_container = c
                break

        if not nc_container:
            log.info("Container Nextcloud não encontrado, pulando validação de escrita")
            return True

        # Testa escrita via docker exec
        test_file = "/var/www/html/external/LTO/.perm_test"
        cmd = [
            "docker", "exec", "-u", "www-data", nc_container,
            "sh", "-c", f'date > "{test_file}" && cat "{test_file}" && rm -f "{test_file}"'
        ]
        result = run_cmd(cmd, check=False)
        if result.returncode == 0:
            log.info("Validação de escrita como www-data: OK")
            return True
        else:
            log.warning("Validação de escrita como www-data falhou: %s", result.stderr)
            return False

    except Exception as e:
        log.warning("Erro na validação de escrita: %s", e)
        return True  # Não falha o boot por isso


def main() -> int:
    log.info("=== Fix Staging Perms iniciado ===")

    ok = True
    ok &= ensure_staging_dir()
    ok &= fix_permissions()
    ok &= ensure_bind_mount()
    ok &= validate_write_as_www_data()

    if ok:
        log.info("=== Fix Staging Perms concluído com sucesso ===")
        return 0
    else:
        log.error("=== Fix Staging Perms FALHOU ===")
        return 1


if __name__ == "__main__":
    sys.exit(main())