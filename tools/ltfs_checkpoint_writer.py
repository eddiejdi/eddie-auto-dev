#!/usr/bin/env python3
"""
ltfs_checkpoint_writer.py — Drain para fita LTO com journal de recuperação por arquivo.

Mantém um journal JSON por sessão no disco local para permitir retomada segura
após falha de energia durante a gravação em fita.

Fluxo normal (run):
  1. Escaneia snapshots completos em BACKUPS_SRC
  2. Cria sessão no journal com manifest de arquivos por snapshot
  3. Para cada snapshot: rsync → SHA256 verify por arquivo → marca done
  4. Unmount seguro do CIFS + stop ltfs-lto6 na NAS (flush LTFS → fita)
  5. Start ltfs-lto6 na NAS + remount CIFS local + verificação
  6. Marca sessão como completed

Fluxo de recovery (recover):
  1. Detecta sessão incompleta no journal
  2. Arquivos "writing" são resetados para "pending" (escrita interrompida)
  3. Executa ltfsck --full-recovery na NAS se fita inconsistente
  4. Remonta fita + CIFS
  5. Resincrona apenas arquivos não-done (rsync --files-from)
  6. Verifica SHA256 de cada arquivo na fita
  7. Unmount seguro + remount + verificação final

Variáveis de ambiente:
  BACKUPS_SRC       Origem dos snapshots (padrão: /mnt/raid1/backups)
  TAPE_TARGET       Destino na fita via CIFS (padrão: /mnt/lto6-smb-proof/backups)
  TAPE_CIFS_MOUNT   Ponto de montagem CIFS local (padrão: /mnt/lto6-smb-proof)
  TAPE_CIFS_UNIT    Unit systemd do CIFS local (padrão: mnt-lto6\\x2dsmb\\x2dproof.mount)
  NAS_IP            IP da NAS onde roda o ltfs-lto6 (padrão: 192.168.15.4)
  NAS_LTFS_SVC      Serviço LTFS na NAS (padrão: ltfs-lto6.service)
  LTFS_DEVICE       Device da fita na NAS (padrão: /dev/sg0)
  LTFS_JOURNAL_DIR  Diretório do journal no disco local (padrão: /var/lib/ltfs-journal)
"""

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─── Configuração ────────────────────────────────────────────────────────────

BACKUPS_SRC    = os.environ.get("BACKUPS_SRC",    "/mnt/raid1/backups")
TAPE_TARGET    = os.environ.get("TAPE_TARGET",    "/mnt/lto6-smb-proof/backups")
TAPE_CIFS_MOUNT = os.environ.get("TAPE_CIFS_MOUNT", "/mnt/lto6-smb-proof")
TAPE_CIFS_UNIT  = os.environ.get("TAPE_CIFS_UNIT",  r"mnt-lto6\x2dsmb\x2dproof.mount")
NAS_IP          = os.environ.get("NAS_IP",          "192.168.15.4")
NAS_LTFS_SVC    = os.environ.get("NAS_LTFS_SVC",    "ltfs-lto6.service")
LTFS_DEVICE     = os.environ.get("LTFS_DEVICE",     "/dev/sg0")
JOURNAL_DIR     = Path(os.environ.get("LTFS_JOURNAL_DIR", "/var/lib/ltfs-journal"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ltfs-checkpoint] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("ltfs-checkpoint")


# ─── Helpers de tempo ────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── Journal ─────────────────────────────────────────────────────────────────

def _session_path(session_id: str) -> Path:
    return JOURNAL_DIR / "sessions" / f"session_{session_id}.json"


def _load_journal(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _save_journal(path: Path, data: dict) -> None:
    """Escrita atômica via rename para não corromper o journal em caso de falha."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(path)


def _find_incomplete_session() -> Optional[Path]:
    sessions_dir = JOURNAL_DIR / "sessions"
    if not sessions_dir.exists():
        return None
    candidates = sorted(sessions_dir.glob("session_*.json"), reverse=True)
    for p in candidates:
        try:
            data = _load_journal(p)
            if data.get("status") in ("in_progress", "failed", "recovering"):
                return p
        except Exception:
            continue
    return None


# ─── SHA256 ──────────────────────────────────────────────────────────────────

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ─── Operações de fita (via SSH na NAS) ──────────────────────────────────────

def _ssh_nas(cmd: str, timeout: int = 60) -> int:
    """Executa comando na NAS via SSH. Retorna exit code."""
    full = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=no",
        f"root@{NAS_IP}",
        cmd,
    ]
    log.info("[SSH→NAS] %s", cmd)
    result = subprocess.run(full, timeout=timeout, check=False)
    return result.returncode


def _nas_ltfs_is_active() -> bool:
    rc = _ssh_nas(f"systemctl is-active --quiet {NAS_LTFS_SVC}")
    return rc == 0


def nas_run_ltfsck() -> bool:
    """Executa ltfsck --full-recovery na NAS. Requer que ltfs-lto6 esteja parado."""
    log.info("Executando ltfsck --full-recovery em %s (NAS)", LTFS_DEVICE)
    rc = _ssh_nas(f"ltfsck --full-recovery {LTFS_DEVICE}", timeout=600)
    return rc == 0


def nas_stop_ltfs() -> bool:
    """Para ltfs-lto6.service na NAS (flush LTFS buffer → fita física)."""
    log.info("Parando %s na NAS (flush para fita)...", NAS_LTFS_SVC)
    rc = _ssh_nas(f"systemctl stop {NAS_LTFS_SVC}", timeout=300)
    return rc == 0


def nas_start_ltfs() -> bool:
    """Inicia ltfs-lto6.service na NAS (remonta fita)."""
    log.info("Iniciando %s na NAS...", NAS_LTFS_SVC)
    rc = _ssh_nas(f"systemctl start {NAS_LTFS_SVC}", timeout=120)
    if rc != 0:
        return False
    time.sleep(5)
    return _nas_ltfs_is_active()


def cifs_unmount() -> bool:
    """Desmonta o CIFS local antes de parar o LTFS na NAS."""
    log.info("Desmontando CIFS local: %s", TAPE_CIFS_UNIT)
    result = subprocess.run(
        ["systemctl", "stop", TAPE_CIFS_UNIT],
        timeout=60, check=False,
    )
    return result.returncode == 0


def cifs_remount() -> bool:
    """Remonta o CIFS local após LTFS reiniciado na NAS."""
    log.info("Remontando CIFS local: %s", TAPE_CIFS_UNIT)
    result = subprocess.run(
        ["systemctl", "start", TAPE_CIFS_UNIT],
        timeout=60, check=False,
    )
    if result.returncode != 0:
        return False
    time.sleep(3)
    verify = subprocess.run(
        ["mountpoint", "-q", TAPE_CIFS_MOUNT],
        timeout=10, check=False,
    )
    return verify.returncode == 0


def tape_safe_unmount_and_flush() -> bool:
    """
    Sequência segura de unmount:
      1. Desmonta CIFS local (evita I/O pendente via CIFS durante stop LTFS)
      2. Para ltfs-lto6 na NAS (sync interno do LTFS → flush para fita física)
    """
    if not cifs_unmount():
        log.error("Falha ao desmontar CIFS local")
        return False
    if not nas_stop_ltfs():
        log.error("Falha ao parar %s na NAS", NAS_LTFS_SVC)
        return False
    log.info("Flush para fita concluído.")
    return True


def tape_remount_and_verify() -> bool:
    """
    Sequência de remount:
      1. Inicia ltfs-lto6 na NAS
      2. Remonta CIFS local
      3. Verifica acessibilidade do mount
    """
    if not nas_start_ltfs():
        log.error("Falha ao iniciar %s na NAS", NAS_LTFS_SVC)
        return False
    if not cifs_remount():
        log.error("Falha ao remontar CIFS local")
        return False
    # Verificação de acessibilidade (só /proc/mounts — não faz syscall de FS)
    check = subprocess.run(
        ["mountpoint", "-q", TAPE_CIFS_MOUNT],
        timeout=10, check=False,
    )
    ok = check.returncode == 0
    if ok:
        log.info("Fita remontada e CIFS verificado com sucesso.")
    else:
        log.error("CIFS não está montado após remount.")
    return ok


# ─── Operações de snapshot ────────────────────────────────────────────────────

def build_file_manifest(snap_dir: Path) -> dict:
    """Escaneia todos os arquivos regulares do snapshot e retorna manifest pendente."""
    manifest = {}
    for f in sorted(snap_dir.rglob("*")):
        if f.is_file():
            rel = str(f.relative_to(snap_dir))
            manifest[rel] = {
                "status": "pending",
                "size": f.stat().st_size,
                "sha256_src": None,
                "sha256_tape": None,
                "written_at": None,
            }
    return manifest


def sync_snapshot_to_tape(
    snap_name: str,
    src: Path,
    dest: Path,
    only_files: Optional[list] = None,
) -> int:
    """
    Executa rsync do snapshot para a fita.
    Se only_files for fornecido, usa --files-from para sincronizar apenas esses arquivos.
    Retorna exit code do rsync (0, 23 e 24 são aceitáveis).

    --whole-file: cópia completa sem delta (evita seeks de leitura na fita).
    --no-partial: sem arquivos parciais (arquivos incompletos não ficam na fita).
    --omit-link-times: LTFS não suporta lutimes em symlinks (evita exit 23 espúrio).
    """
    cmd = [
        "rsync",
        "--archive",
        "--hard-links",
        "--omit-link-times",
        "--whole-file",
        "--no-partial",
        "--timeout=300",
        "--stats",
    ]

    files_from_path: Optional[Path] = None
    if only_files is not None:
        files_from_path = Path(f"/tmp/ltfs-resume-{snap_name}.txt")
        files_from_path.write_text("\n".join(only_files))
        cmd += ["--files-from", str(files_from_path)]

    dest.mkdir(parents=True, exist_ok=True)
    cmd += [f"{src}/", f"{dest}/"]

    log.info("[RSYNC] %s (%d arquivo(s))", snap_name,
             len(only_files) if only_files is not None else "todos")
    result = subprocess.run(cmd, check=False)

    if files_from_path:
        files_from_path.unlink(missing_ok=True)

    return result.returncode


def verify_files_on_tape(
    snap_name: str,
    snap_data: dict,
    src: Path,
    dest: Path,
    journal_path: Path,
    journal: dict,
) -> tuple:
    """
    Verifica SHA256 de cada arquivo não-done no destino (fita).
    Atualiza o journal após cada arquivo (checkpoint por arquivo).
    Retorna (ok_count, fail_count).

    Estratégia SHA256:
    - Calcula SHA256 da origem se ainda não temos (e a origem existe)
    - Calcula SHA256 do arquivo na fita
    - Se temos SHA256 da origem: compara ambos
    - Se não temos SHA256 da origem (arquivo removido): aceita presença na fita como evidência
    """
    ok = 0
    fail = 0
    files = snap_data["files"]

    for rel_path, fdata in files.items():
        if fdata["status"] == "done":
            ok += 1
            continue

        tape_file = dest / rel_path
        src_file = src / rel_path

        if not tape_file.exists():
            log.warning("[MISSING] %s/%s — não encontrado na fita", snap_name, rel_path)
            fdata["status"] = "failed"
            fail += 1
            _save_journal(journal_path, journal)
            continue

        # SHA256 da origem (calculado uma vez e armazenado no journal)
        if fdata["sha256_src"] is None and src_file.exists():
            try:
                fdata["sha256_src"] = sha256_file(src_file)
            except Exception as e:
                log.warning("[SHA256-SRC-ERR] %s/%s — %s", snap_name, rel_path, e)

        # SHA256 na fita
        try:
            tape_sha = sha256_file(tape_file)
        except Exception as e:
            log.warning("[SHA256-TAPE-ERR] %s/%s — %s", snap_name, rel_path, e)
            fdata["status"] = "failed"
            fail += 1
            _save_journal(journal_path, journal)
            continue

        # Verificação
        src_sha = fdata.get("sha256_src")
        if src_sha and tape_sha != src_sha:
            log.warning("[MISMATCH] %s/%s — src=%s... tape=%s...",
                        snap_name, rel_path, src_sha[:12], tape_sha[:12])
            fdata["status"] = "failed"
            fdata["sha256_tape"] = tape_sha
            fail += 1
        else:
            fdata["sha256_tape"] = tape_sha
            fdata["status"] = "done"
            fdata["written_at"] = _now_iso()
            log.debug("[OK] %s/%s — %s...", snap_name, rel_path, tape_sha[:12])
            ok += 1

        _save_journal(journal_path, journal)

    return ok, fail


# ─── Fluxo principal ─────────────────────────────────────────────────────────

def _find_snapshots(src_dir: Path) -> list:
    return sorted(
        p for p in src_dir.iterdir()
        if p.is_dir()
        and p.name.startswith("rpa4all-snapshot-")
        and ".tmp." not in p.name
    )


def _process_session(
    journal: dict,
    journal_path: Path,
    src_dir: Path,
    tape_target: Path,
    recovery: bool,
) -> int:
    """
    Processa todos os snapshots da sessão.
    Em recovery=True, sincroniza apenas arquivos não-done por snapshot.
    Retorna 0 em sucesso, 1 em falha.
    """
    total_ok = 0
    total_fail = 0

    for snap_name, snap_data in journal["snapshots"].items():
        if snap_data["status"] == "done":
            log.info("[SKIP] %s — já completo no journal", snap_name)
            continue

        src = src_dir / snap_name
        dest = tape_target / snap_name

        if not src.exists():
            log.warning("[SKIP] %s — origem não encontrada em %s", snap_name, src_dir)
            snap_data["status"] = "skipped"
            _save_journal(journal_path, journal)
            continue

        # Em recovery: sincronizar apenas arquivos pendentes
        pending = [
            rel for rel, fdata in snap_data["files"].items()
            if fdata["status"] != "done"
        ]

        if not pending:
            log.info("[RSYNC-SKIP] %s — todos arquivos já verificados, pulando rsync", snap_name)
        else:
            only = pending if recovery else None
            rsync_exit = sync_snapshot_to_tape(snap_name, src, dest, only_files=only)

            # 0=ok, 23=mtime em symlinks (não-fatal no LTFS/CIFS), 24=arquivo sumiu na origem
            if rsync_exit not in (0, 23, 24):
                log.error("[RSYNC-FAIL] %s exit=%d", snap_name, rsync_exit)
                snap_data["status"] = "failed"
                _save_journal(journal_path, journal)
                total_fail += len(pending)
                continue

        snap_data["synced_at"] = _now_iso()
        _save_journal(journal_path, journal)

        # Verificação SHA256 por arquivo (checkpoint por arquivo)
        log.info("[VERIFY] %s — verificando SHA256 na fita para %d arquivo(s)...",
                 snap_name, len(snap_data["files"]))
        ok, fail = verify_files_on_tape(
            snap_name, snap_data, src, dest, journal_path, journal
        )
        log.info("[VERIFY] %s — ok=%d fail=%d", snap_name, ok, fail)
        total_ok += ok
        total_fail += fail

        snap_data["status"] = "done" if fail == 0 else "failed"
        _save_journal(journal_path, journal)

    # ── Unmount seguro + flush para fita física ──
    log.info("Iniciando sequência de unmount seguro e flush para fita...")
    if not tape_safe_unmount_and_flush():
        log.error("Falha no unmount/flush — intervenção manual necessária")
        journal["status"] = "failed"
        _save_journal(journal_path, journal)
        return 1

    # ── Remount + verificação ──
    log.info("Remontando fita e verificando acesso...")
    if not tape_remount_and_verify():
        log.error("Falha no remount — intervenção manual necessária")
        journal["status"] = "failed"
        _save_journal(journal_path, journal)
        return 1

    # ── Resultado final ──
    if total_fail == 0:
        journal["status"] = "completed"
        journal["completed_at"] = _now_iso()
        log.info("Sessão %s concluída: ok=%d", journal["session_id"], total_ok)
    else:
        journal["status"] = "failed"
        log.error("Sessão %s falhou: ok=%d fail=%d", journal["session_id"], total_ok, total_fail)

    _save_journal(journal_path, journal)
    return 0 if total_fail == 0 else 1


# ─── Comandos ─────────────────────────────────────────────────────────────────

def cmd_run(args) -> int:
    """Drain normal com checkpointing por arquivo."""
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    (JOURNAL_DIR / "sessions").mkdir(exist_ok=True)

    src_dir = Path(BACKUPS_SRC)
    tape_target = Path(TAPE_TARGET)

    # Guard: CIFS acessível?
    if not Path(TAPE_CIFS_MOUNT).exists():
        log.error("CIFS não acessível: %s", TAPE_CIFS_MOUNT)
        return 1

    # Guard: fita gravável?
    tape_target.mkdir(parents=True, exist_ok=True)
    probe = tape_target / ".checkpoint-probe"
    try:
        probe.touch()
        probe.unlink()
    except Exception:
        log.error("Fita não está gravável: %s", tape_target)
        return 1

    snapshots = _find_snapshots(src_dir)
    if not snapshots:
        log.info("Nenhum snapshot completo encontrado em %s", src_dir)
        return 0

    log.info("Encontrado(s) %d snapshot(s): %s",
             len(snapshots), " ".join(s.name for s in snapshots))

    # Criar sessão
    session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    journal_path = _session_path(session_id)
    journal = {
        "session_id": session_id,
        "started_at": _now_iso(),
        "completed_at": None,
        "status": "in_progress",
        "source_dir": str(src_dir),
        "tape_target": str(tape_target),
        "snapshots": {},
    }

    log.info("Construindo manifest de arquivos...")
    for snap in snapshots:
        journal["snapshots"][snap.name] = {
            "status": "pending",
            "synced_at": None,
            "files": build_file_manifest(snap),
        }

    _save_journal(journal_path, journal)
    log.info("Journal criado: %s", journal_path)

    return _process_session(journal, journal_path, src_dir, tape_target, recovery=False)


def cmd_recover(args) -> int:
    """Retoma sessão incompleta após falha de energia ou interrupção."""
    journal_path = _find_incomplete_session()
    if not journal_path:
        log.info("Nenhuma sessão incompleta encontrada. Nada a fazer.")
        return 0

    journal = _load_journal(journal_path)
    log.info("Sessão incompleta: %s (status=%s, iniciada=%s)",
             journal["session_id"], journal["status"], journal["started_at"])

    journal["status"] = "recovering"
    _save_journal(journal_path, journal)

    # Resetar arquivos "writing" → "pending"
    # (escrita foi interrompida: arquivo na fita pode estar incompleto)
    reset_count = 0
    for snap_name, snap_data in journal["snapshots"].items():
        for rel_path, fdata in snap_data["files"].items():
            if fdata["status"] == "writing":
                log.info("[RESET] %s/%s — 'writing' → 'pending'", snap_name, rel_path)
                fdata["status"] = "pending"
                fdata["sha256_tape"] = None
                reset_count += 1
    if reset_count:
        _save_journal(journal_path, journal)
        log.info("%d arquivo(s) resetado(s) para 'pending'", reset_count)

    # ltfsck se fita inconsistente
    if not _nas_ltfs_is_active():
        log.warning("LTFS não está ativo na NAS — executando ltfsck --full-recovery")
        if not nas_run_ltfsck():
            log.error("ltfsck falhou — intervenção manual necessária")
            journal["status"] = "failed"
            _save_journal(journal_path, journal)
            return 2
        if not nas_start_ltfs():
            log.error("Não foi possível montar a fita após ltfsck")
            journal["status"] = "failed"
            _save_journal(journal_path, journal)
            return 2
        if not cifs_remount():
            log.error("Não foi possível remontar CIFS após ltfsck")
            journal["status"] = "failed"
            _save_journal(journal_path, journal)
            return 2

    src_dir = Path(journal["source_dir"])
    tape_target = Path(journal["tape_target"])

    return _process_session(journal, journal_path, src_dir, tape_target, recovery=True)


def cmd_status(args) -> int:
    """Exibe status das últimas sessões do journal."""
    sessions_dir = JOURNAL_DIR / "sessions"
    if not sessions_dir.exists():
        print("Nenhuma sessão encontrada.")
        return 0

    sessions = sorted(sessions_dir.glob("session_*.json"), reverse=True)
    if not sessions:
        print("Nenhuma sessão encontrada.")
        return 0

    print(f"{'SESSION ID':>18}  {'STATUS':12}  {'SNAPS':>8}  INICIADA")
    print("-" * 70)
    for p in sessions[:20]:
        try:
            data = _load_journal(p)
            snaps = data.get("snapshots", {})
            done = sum(1 for s in snaps.values() if s.get("status") == "done")
            total = len(snaps)
            files_ok = sum(
                sum(1 for f in s.get("files", {}).values() if f.get("status") == "done")
                for s in snaps.values()
            )
            files_total = sum(len(s.get("files", {})) for s in snaps.values())
            print(
                f"{data['session_id']:>18}  {data['status']:12}  "
                f"{done}/{total} snaps  {files_ok}/{files_total} arqs  "
                f"{data['started_at']}"
            )
        except Exception as e:
            print(f"{p.name}  [ERRO: {e}]")

    return 0


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="LTFS Checkpoint Writer — drain para fita com journal de recuperação por arquivo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("run",     help="Drain normal com checkpointing")
    sub.add_parser("recover", help="Retoma sessão incompleta após falha de energia")
    sub.add_parser("status",  help="Exibe status das últimas sessões")

    args = parser.parse_args()

    dispatch = {"run": cmd_run, "recover": cmd_recover, "status": cmd_status}
    sys.exit(dispatch[args.cmd](args))


if __name__ == "__main__":
    main()
