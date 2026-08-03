#!/usr/bin/env python3
"""
ltfs-cache-flush — Worker que drena staging do Nextcloud para fita LTFS.

Fluxo:
  1. Adquire lock exclusivo global (/run/lock/tape-global.lock)
  2. Escaneia buffer roots por arquivos maduros (--min-age-seconds, --min-stable-seconds)
  3. Para cada arquivo: rsync -> verifica SHA256 -> registra em catalog.jsonl + placements.json
  4. Atualiza métricas e libera lock

Uso (via systemd drop-in 60-tape-gate.conf):
  ltfs-cache-flush --buffer-root /mnt/pretape/lto6-cache \
    --primary-buffer-root /mnt/pretape/lto6-cache \
    --target-root /mnt/lto6-smb-proof/backups \
    --state-file /var/lib/ltfs-cache-flush/state.json \
    --placement-file /var/lib/ltfs-cache-flush/placements.json \
    --catalog-file /var/lib/ltfs-cache-flush/catalog.jsonl \
    --metrics-file /var/lib/ltfs-cache-flush/metrics.json \
    --metrics-state-file /var/lib/ltfs-cache-flush/metrics_state.json \
    --lock-file /run/ltfs-cache-flush.lock \
    --min-age-seconds 900 --min-stable-seconds 300 \
    --high-watermark-percent 85 --low-watermark-percent 70 \
    --min-target-total-bytes 107374182400 --min-target-free-bytes 10737418240 \
    --placement-policy newest-first --log-level INFO
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ─── Configuração ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ltfs-cache-flush] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("ltfs-cache-flush")

GLOBAL_TAPE_LOCK = Path("/run/lock/tape-global.lock")
LOCAL_FLUSH_LOCK = Path("/run/ltfs-cache-flush.lock")

# ─── Helpers ───────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _acquire_lock(lock_path: Path, timeout: int = 300) -> int:
    """Adquire lock exclusivo (flock). Retorna fd do lock."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = lock_path.open("w").fileno()
    start = time.time()
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.time() - start >= timeout:
                raise RuntimeError(f"Lock {lock_path} não adquirido após {timeout}s")
            time.sleep(1)


def _release_lock(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        os.close(fd)
    except Exception:
        pass


def _run_cmd(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    log.debug("[CMD] %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content)
    tmp.replace(path)


# ─── Coleta de candidatos ──────────────────────────────────────────────────────


def collect_candidates(
    buffer_roots: list[Path],
    min_age_seconds: int,
    min_stable_seconds: int,
) -> list[dict[str, Any]]:
    """
    Retorna lista de arquivos candidatos para flush.
    Critérios:
      - Arquivo regular (não symlink, não dir)
      - Idade >= min_age_seconds (mtime)
      - Estável >= min_stable_seconds (mtime não muda há N segundos)
    """
    now = time.time()
    candidates: list[dict[str, Any]] = []

    for root in buffer_roots:
        if not root.exists():
            log.warning("Buffer root não existe: %s", root)
            continue
        for f in root.rglob("*"):
            if not f.is_file():
                continue
            try:
                st = f.stat()
            except OSError:
                continue
            age = now - st.st_mtime
            if age < min_age_seconds:
                continue
            # Estabilidade: mtime não muda há min_stable_seconds
            # (aproximação: se age >= min_age_seconds + min_stable_seconds, considera estável)
            if age < min_age_seconds + min_stable_seconds:
                continue
            rel = f.relative_to(root)
            candidates.append({
                "src_root": str(root),
                "rel_path": str(rel),
                "abs_path": str(f),
                "size": st.st_size,
                "mtime": st.st_mtime,
                "sha256": None,  # calculado no flush
            })
    log.info("Candidatos coletados: %d arquivo(s)", len(candidates))
    return candidates


# ─── Estado persistente ────────────────────────────────────────────────────────


def load_state(state_file: Path) -> dict[str, Any]:
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except Exception:
            pass
    return {"flushed": {}, "failed": {}, "last_run": None}


def save_state(state_file: Path, state: dict[str, Any]) -> None:
    _atomic_write(state_file, json.dumps(state, indent=2, ensure_ascii=False))


def load_placements(placement_file: Path) -> dict[str, Any]:
    if placement_file.exists():
        try:
            return json.loads(placement_file.read_text())
        except Exception:
            pass
    return {}


def save_placements(placement_file: Path, placements: dict[str, Any]) -> None:
    _atomic_write(placement_file, json.dumps(placements, indent=2, ensure_ascii=False))


def append_catalog(catalog_file: Path, entry: dict[str, Any]) -> None:
    catalog_file.parent.mkdir(parents=True, exist_ok=True)
    with catalog_file.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_metrics(metrics_file: Path) -> dict[str, Any]:
    if metrics_file.exists():
        try:
            return json.loads(metrics_file.read_text())
        except Exception:
            pass
    return {"runs": []}


def save_metrics(metrics_file: Path, metrics: dict[str, Any]) -> None:
    _atomic_write(metrics_file, json.dumps(metrics, indent=2, ensure_ascii=False))


# ─── Flush de um arquivo ───────────────────────────────────────────────────────


def flush_file(
    candidate: dict[str, Any],
    target_root: Path,
    state: dict[str, Any],
    placements: dict[str, Any],
    catalog_file: Path,
    placement_policy: str,
) -> tuple[bool, str]:
    """
    Flush de um arquivo para a fita.
    Retorna (sucesso, mensagem).
    """
    src = Path(candidate["abs_path"])
    rel = candidate["rel_path"]
    dest = target_root / rel

    # Verifica se já foi flushado com sucesso (idempotência)
    flushed_key = f"{candidate['src_root']}:{rel}"
    if flushed_key in state.get("flushed", {}):
        existing = state["flushed"][flushed_key]
        if existing.get("size") == candidate["size"] and existing.get("sha256"):
            # Verifica se arquivo na fita ainda existe e bate SHA256
            if dest.exists():
                try:
                    tape_sha = sha256_file(dest)
                    if tape_sha == existing["sha256"]:
                        log.debug("[SKIP] Já flushado e verificado: %s", rel)
                        return True, "already_flushed"
                except Exception:
                    pass

    # Garante diretório destino
    dest.parent.mkdir(parents=True, exist_ok=True)

    # rsync --whole-file --no-partial (evita arquivos parciais na fita)
    rsync_cmd = [
        "rsync",
        "--archive",
        "--hard-links",
        "--omit-link-times",
        "--whole-file",
        "--no-partial",
        "--timeout=300",
        str(src),
        str(dest),
    ]
    log.info("[RSYNC] %s -> %s", rel, dest)
    rsync_result = _run_cmd(rsync_cmd)
    if rsync_result.returncode not in (0, 23, 24):
        msg = f"rsync falhou (exit={rsync_result.returncode}): {rsync_result.stderr[:200]}"
        log.error(msg)
        state.setdefault("failed", {})[flushed_key] = {
            "error": msg,
            "attempted_at": _now_iso(),
        }
        return False, msg

    # SHA256 na fita
    try:
        tape_sha = sha256_file(dest)
    except Exception as e:
        msg = f"SHA256 falhou no destino: {e}"
        log.error(msg)
        state.setdefault("failed", {})[flushed_key] = {
            "error": msg,
            "attempted_at": _now_iso(),
        }
        return False, msg

    # SHA256 na origem (para comparação)
    try:
        src_sha = sha256_file(src)
    except Exception as e:
        log.warning("SHA256 origem falhou (arquivo pode ter sido removido): %s", e)
        src_sha = None

    if src_sha and tape_sha != src_sha:
        msg = f"SHA256 mismatch: src={src_sha[:12]}... tape={tape_sha[:12]}..."
        log.error("[MISMATCH] %s", msg)
        state.setdefault("failed", {})[flushed_key] = {
            "error": msg,
            "attempted_at": _now_iso(),
            "src_sha256": src_sha,
            "tape_sha256": tape_sha,
        }
        return False, msg

    # Sucesso: registra estado
    state.setdefault("flushed", {})[flushed_key] = {
        "size": candidate["size"],
        "sha256": tape_sha,
        "flushed_at": _now_iso(),
        "src_root": candidate["src_root"],
        "rel_path": rel,
        "target_root": str(target_root),
    }

    # Placements (para recovery: onde cada arquivo está na fita)
    placements[rel] = {
        "target_root": str(target_root),
        "size": candidate["size"],
        "sha256": tape_sha,
        "flushed_at": _now_iso(),
        "src_root": candidate["src_root"],
    }

    # Catalog (append-only log imutável)
    catalog_entry = {
        "timestamp": _now_iso(),
        "action": "flush",
        "src_root": candidate["src_root"],
        "rel_path": rel,
        "size": candidate["size"],
        "sha256": tape_sha,
        "target_root": str(target_root),
        "policy": placement_policy,
    }
    append_catalog(catalog_file, catalog_entry)

    log.info("[OK] %s (%d bytes, %s...)", rel, candidate["size"], tape_sha[:12])
    return True, "flushed"


# ─── Verificação de capacidade do target ───────────────────────────────────────


def check_target_capacity(
    target_root: Path,
    min_total_bytes: int,
    min_free_bytes: int,
) -> bool:
    """Verifica se o target (fita via CIFS) tem espaço mínimo."""
    try:
        stat = shutil.disk_usage(target_root)
    except Exception as e:
        log.warning("Não checar capacidade do target: %s", e)
        return True  # não bloqueia se não consegue checar

    total_gb = stat.total / (1024**3)
    free_gb = stat.free / (1024**3)
    used_pct = (stat.used / stat.total) * 100 if stat.total > 0 else 0

    log.info("Target capacity: total=%.1fGB free=%.1fGB used=%.1f%%", total_gb, free_gb, used_pct)

    if stat.total < min_total_bytes:
        log.error("Target total space %.1fGB < mínimo %.1fGB", total_gb, min_total_bytes / (1024**3))
        return False
    if stat.free < min_free_bytes:
        log.error("Target free space %.1fGB < mínimo %.1fGB", free_gb, min_free_bytes / (1024**3))
        return False
    return True


# ─── Métricas ──────────────────────────────────────────────────────────────────


def update_metrics(
    metrics_file: Path,
    metrics_state_file: Path,
    run_result: dict[str, Any],
) -> None:
    metrics = load_metrics(metrics_file)
    metrics.setdefault("runs", []).append(run_result)
    # Mantém últimos 100 runs
    metrics["runs"] = metrics["runs"][-100:]
    save_metrics(metrics_file, metrics)

    # Estado resumido para exporter Prometheus
    state = {
        "last_run": run_result.get("timestamp"),
        "last_status": run_result.get("status"),
        "files_flushed": run_result.get("files_flushed", 0),
        "files_failed": run_result.get("files_failed", 0),
        "bytes_flushed": run_result.get("bytes_flushed", 0),
        "duration_seconds": run_result.get("duration_seconds", 0),
    }
    _atomic_write(metrics_state_file, json.dumps(state, indent=2))


# ─── Cleanup de staging (G7) ───────────────────────────────────────────────────


def cleanup_flushed_files(
    state: dict[str, Any],
    catalog_file: Path,
    policy: str,
    trash_root: Path,
    max_age_days: int,
) -> dict[str, Any]:
    """
    Aplica política de limpeza sobre arquivos já flushados com sucesso.

    Policies:
      - none             : não faz nada
      - delete           : remove arquivo do staging após flush confirmado
      - move-to-flushed  : move para <trash_root> (retém por max_age_days)
      - move-to-trash    : igual a move-to-flushed (alias)
    """
    if policy == "none":
        return {"policy": policy, "removed": 0, "moved": 0}

    flushed = state.get("flushed", {})
    removed = 0
    moved = 0
    now = time.time()

    for key, entry in flushed.items():
        if not entry.get("sha256"):
            continue
        src = Path(entry.get("abs_path", ""))
        if not src:
            # estado antigo não tinha abs_path — derivar de src_root+rel_path
            src_root = entry.get("src_root", "")
            rel = entry.get("rel_path", "")
            if src_root and rel:
                src = Path(src_root) / rel
        if not src.exists():
            continue

        # Só limpa se arquivo ainda existe no staging (ainda não removido)
        try:
            if policy in ("delete",):
                src.unlink()
                removed += 1
                log.info("[CLEANUP] removido do staging: %s", src)
            elif policy in ("move-to-flushed", "move-to-trash"):
                dest = trash_root / Path(entry.get("rel_path", ""))
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                moved += 1
                log.info("[CLEANUP] movido para %s: %s", trash_root, src)
        except OSError as exc:
            log.warning("[CLEANUP] falha ao limpar %s: %s", src, exc)

    # TTL do trash: apaga arquivos antigos em trash_root além de max_age_days
    expired = 0
    if trash_root.exists() and policy in ("move-to-flushed", "move-to-trash"):
        cutoff = now - (max_age_days * 86400)
        for f in trash_root.rglob("*"):
            if f.is_file():
                try:
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
                        expired += 1
                except OSError:
                    pass
        if expired:
            log.info("[CLEANUP] %d arquivo(s) expirados removidos de %s", expired, trash_root)

    return {"policy": policy, "removed": removed, "moved": moved, "expired": expired}


# ─── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="LTFS Cache Flush — drena staging para fita")
    parser.add_argument("--buffer-root", action="append", required=True, help="Raiz do buffer de staging (pode repetir)")
    parser.add_argument("--primary-buffer-root", required=True, help="Raiz primária (para métricas)")
    parser.add_argument("--target-root", action="append", required=True, help="Raiz destino na fita via CIFS (pode repetir)")
    parser.add_argument("--state-file", required=True, help="Arquivo de estado JSON")
    parser.add_argument("--placement-file", required=True, help="Arquivo de placements JSON")
    parser.add_argument("--catalog-file", required=True, help="Arquivo de catalog JSONL (append-only)")
    parser.add_argument("--metrics-file", required=True, help="Arquivo de métricas JSON")
    parser.add_argument("--metrics-state-file", required=True, help="Arquivo de estado de métricas JSON")
    parser.add_argument("--lock-file", required=True, help="Lock local do flush")
    parser.add_argument("--min-age-seconds", type=int, default=900, help="Idade mínima do arquivo (s)")
    parser.add_argument("--min-stable-seconds", type=int, default=300, help="Estabilidade mínima (s)")
    parser.add_argument("--high-watermark-percent", type=int, default=85, help="Watermark alto staging (%)")
    parser.add_argument("--low-watermark-percent", type=int, default=70, help="Watermark baixo staging (%)")
    parser.add_argument("--min-target-total-bytes", type=int, default=107374182400, help="Espaço total mínimo target (bytes)")
    parser.add_argument("--min-target-free-bytes", type=int, default=10737418240, help="Espaço livre mínimo target (bytes)")
    parser.add_argument("--placement-policy", default="newest-first", help="Política de colocação")
    parser.add_argument("--log-level", default="INFO", help="Nível de log")
    parser.add_argument("--dry-run", action="store_true", help="Não executa flush, só lista candidatos")
    parser.add_argument("--cleanup-policy", default="none", choices=["none", "delete", "move-to-flushed", "move-to-trash"],
                        help="Política de limpeza do staging após flush confirmado (G7)")
    parser.add_argument("--cleanup-trash-root", default="/mnt/raid1/lto6-cache/.flushed",
                        help="Diretório de retenção para policy=move-to-flushed/trash")
    parser.add_argument("--cleanup-max-age-days", type=int, default=30,
                        help="Idade máxima (dias) no trash antes de remover")

    args = parser.parse_args()

    logging.getLogger().setLevel(args.log_level.upper())

    buffer_roots = [Path(p) for p in args.buffer_root]
    target_roots = [Path(p) for p in args.target_root]
    primary_root = Path(args.primary_buffer_root)

    log.info("=== LTFS Cache Flush iniciado ===")
    log.info("Buffer roots: %s", ", ".join(str(p) for p in buffer_roots))
    log.info("Target roots: %s", ", ".join(str(p) for p in target_roots))
    log.info("Min age: %ds, min stable: %ds", args.min_age_seconds, args.min_stable_seconds)

    start_time = time.time()
    run_id = _now_iso()

    # Lock global de fita (compartilhado com outros writers)
    global_lock_fd = -1
    local_lock_fd = -1
    try:
        log.info("Adquirindo lock global de fita: %s", GLOBAL_TAPE_LOCK)
        global_lock_fd = _acquire_lock(GLOBAL_TAPE_LOCK, timeout=600)
        log.info("Lock global adquirido")

        log.info("Adquirindo lock local de flush: %s", args.lock_file)
        local_lock_fd = _acquire_lock(Path(args.lock_file), timeout=60)
        log.info("Lock local adquirido")

        # Carrega estado persistente
        state = load_state(Path(args.state_file))
        placements = load_placements(Path(args.placement_file))

        # Verifica capacidade do target (usa primeiro target root)
        if not check_target_capacity(target_roots[0], args.min_target_total_bytes, args.min_target_free_bytes):
            return 1

        # Coleta candidatos
        candidates = collect_candidates(buffer_roots, args.min_age_seconds, args.min_stable_seconds)

        if not candidates:
            log.info("Nenhum candidato para flush")
            run_result = {
                "timestamp": run_id,
                "status": "success",
                "files_flushed": 0,
                "files_failed": 0,
                "bytes_flushed": 0,
                "duration_seconds": time.time() - start_time,
                "candidates": 0,
            }
            update_metrics(Path(args.metrics_file), Path(args.metrics_state_file), run_result)
            return 0

        if args.dry_run:
            log.info("DRY-RUN: %d candidatos seriam flushados", len(candidates))
            for c in candidates:
                log.info("  %s (%d bytes)", c["rel_path"], c["size"])
            return 0

        # Flush sequencial (um target root por enquanto)
        target_root = target_roots[0]
        flushed_count = 0
        failed_count = 0
        bytes_flushed = 0

        for candidate in candidates:
            ok, msg = flush_file(
                candidate,
                target_root,
                state,
                placements,
                Path(args.catalog_file),
                args.placement_policy,
            )
            if ok and msg == "flushed":
                flushed_count += 1
                bytes_flushed += candidate["size"]
            elif ok and msg == "already_flushed":
                pass  # já contado anteriormente
            else:
                failed_count += 1

        # Persiste estado
        save_state(Path(args.state_file), state)
        save_placements(Path(args.placement_file), placements)

        # G7: Cleanup do staging após flush confirmado
        cleanup_result = cleanup_flushed_files(
            state,
            Path(args.catalog_file),
            args.cleanup_policy,
            Path(args.cleanup_trash_root),
            args.cleanup_max_age_days,
        )
        if cleanup_result["policy"] != "none":
            log.info("[CLEANUP] %s: removidos=%d movidos=%d expirados=%d",
                     cleanup_result["policy"], cleanup_result["removed"],
                     cleanup_result["moved"], cleanup_result["expired"])
            # Persiste estado atualizado (abs_path removido do staging)
            save_state(Path(args.state_file), state)

        duration = time.time() - start_time
        status = "success" if failed_count == 0 else "partial_failure"

        run_result = {
            "timestamp": run_id,
            "status": status,
            "files_flushed": flushed_count,
            "files_failed": failed_count,
            "bytes_flushed": bytes_flushed,
            "duration_seconds": duration,
            "candidates": len(candidates),
        }
        update_metrics(Path(args.metrics_file), Path(args.metrics_state_file), run_result)

        log.info("=== Flush concluído: %d ok, %d falhas, %.1fMB em %.1fs ===",
                 flushed_count, failed_count, bytes_flushed / (1024**2), duration)

        return 0 if failed_count == 0 else 1

    except Exception as e:
        log.exception("Erro fatal no flush: %s", e)
        run_result = {
            "timestamp": run_id,
            "status": "error",
            "error": str(e),
            "duration_seconds": time.time() - start_time,
        }
        update_metrics(Path(args.metrics_file), Path(args.metrics_state_file), run_result)
        return 1
    finally:
        if local_lock_fd >= 0:
            _release_lock(local_lock_fd)
        if global_lock_fd >= 0:
            _release_lock(global_lock_fd)
        log.info("Locks liberados")


if __name__ == "__main__":
    sys.exit(main())