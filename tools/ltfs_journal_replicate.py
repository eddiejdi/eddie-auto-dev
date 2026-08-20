#!/usr/bin/env python3
"""G13: Replica o journal LTFS (/var/lib/ltfs-journal) para NAS após cada sessão.

Motivação: se o homelab perder o disco local, o journal some e o recovery da
fita fica dependente só de SSH na NAS. Replicando para a NAS (e opcionalmente
um destino rsync extra), o recovery continua possível.

Uso (systemd):
    ltfs-journal-replicate.service  (After=ltfs-cache-flush.service, oneshot)

Variáveis de ambiente:
    LTFS_JOURNAL_DIR        Diretório do journal (padrão: /var/lib/ltfs-journal)
    JRNL_REPLICA_NAS        rsync:// ou user@host:path na NAS (obrigatório)
    JRNL_REPLICA_EXTRA      destino rsync opcional adicional (S3 mount etc.)
    JRNL_RSYNC_OPTS         opções rsync extras (padrão: -a --delete)
    JRNL_DRY_RUN            1 = só mostra o que seria replicado
"""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

JOURNAL_DIR = Path(os.environ.get("LTFS_JOURNAL_DIR", "/var/lib/ltfs-journal"))
REPLICA_NAS = os.environ.get("JRNL_REPLICA_NAS", "").strip()
REPLICA_EXTRA = os.environ.get("JRNL_REPLICA_EXTRA", "").strip()
RSYNC_OPTS = shlex.split(os.environ.get("JRNL_RSYNC_OPTS", "-a --delete"))
DRY_RUN = os.environ.get("JRNL_DRY_RUN", "0") == "1"

log = logging.getLogger("ltfs-journal-replicate")


def _run_rsync(source: Path, dest: str) -> tuple[int, str]:
    cmd = ["rsync", *RSYNC_OPTS, "--timeout=60"]
    if DRY_RUN:
        cmd.append("--dry-run")
    cmd += [str(source) + "/", dest]
    log.debug("rsync %s -> %s", source, dest)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, (proc.stdout or proc.stderr).strip()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if not JOURNAL_DIR.is_dir():
        log.error("Jornal %s não existe — nada a replicar", JOURNAL_DIR)
        return 1

    if not REPLICA_NAS and not REPLICA_EXTRA:
        log.error("Nenhum destino definido (JRNL_REPLICA_NAS ou JRNL_REPLICA_EXTRA)")
        return 2

    if not shutil.which("rsync"):
        log.error("rsync não instalado")
        return 3

    ok = True
    for label, dest in (("nas", REPLICA_NAS), ("extra", REPLICA_EXTRA)):
        if not dest:
            continue
        rc, out = _run_rsync(JOURNAL_DIR, dest)
        if rc == 0:
            log.info("Replicado para %s (%s)", label, "dry-run" if DRY_RUN else "ok")
        else:
            ok = False
            log.error("Falha replicando para %s (rc=%d): %s", label, rc, out)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
