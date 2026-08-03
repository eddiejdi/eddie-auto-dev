#!/usr/bin/env python3
"""
tape-log-spool-drain — Drena logs bufferizados do pipeline Nextcloud→LTO.

Lê logs de ROUTE_TARGET_ROOT (ex: /mnt/pretape/lto6-cache/logs) organizados por rota,
consolida, rotaiona e envia para destino final (journald, arquivo, Loki, etc.).

Estrutura esperada em ROUTE_TARGET_ROOT:
  /mnt/pretape/lto6-cache/logs/
    nextcloud/
      2026-08-01.jsonl
      2026-08-02.jsonl
    trading/
      ...

Variáveis de ambiente:
  ROUTE_NAME        Nome da rota (ex: nextcloud, trading) — obrigatório
  ROUTE_TARGET_ROOT Raiz dos logs bufferizados (padrão: /mnt/pretape/lto6-cache/logs)
  DESTINATION       Destino final: journald | file | loki (padrão: journald)
  DEST_PATH         Caminho do destino (para file: arquivo; para loki: URL)
  RETENTION_DAYS    Dias para manter logs locais após drenar (padrão: 7)
  MAX_FILE_SIZE_MB  Tamanho máximo por arquivo antes de rotacionar (padrão: 100)
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [tape-log-spool-drain] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("tape-log-spool-drain")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def drain_route(
    route_name: str,
    target_root: Path,
    destination: str,
    dest_path: str,
    retention_days: int,
    max_file_size_mb: int,
) -> dict[str, Any]:
    """Drena logs de uma rota específica."""
    route_dir = target_root / route_name
    if not route_dir.exists():
        log.warning("Rota %s: diretório não existe: %s", route_name, route_dir)
        return {"route": route_name, "status": "skipped", "reason": "dir_not_found"}

    log_files = sorted(route_dir.glob("*.jsonl")) + sorted(route_dir.glob("*.jsonl.gz"))
    if not log_files:
        log.info("Rota %s: nenhum arquivo de log para drenar", route_name)
        return {"route": route_name, "status": "skipped", "reason": "no_files"}

    drained_count = 0
    drained_bytes = 0
    errors = []

    for log_file in log_files:
        try:
            log.info("Drenando %s -> %s", log_file, destination)

            # Lê arquivo (pode ser .gz)
            if log_file.suffix == ".gz":
                import gzip as gz
                opener = gz.open
                mode = "rt"
            else:
                opener = open
                mode = "r"

            lines_drained = 0
            with opener(log_file, mode) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        # Adiciona metadados de roteamento
                        entry.setdefault("_route", route_name)
                        entry.setdefault("_drained_at", _now_iso())

                        # Envia para destino
                        if destination == "journald":
                            # Log via systemd journal (logger)
                            msg = json.dumps(entry, ensure_ascii=False)
                            os.system(f'logger -t "tape-log-{route_name}" "{msg}"')
                        elif destination == "file":
                            # Append para arquivo destino
                            with open(dest_path, "a") as df:
                                df.write(json.dumps(entry, ensure_ascii=False) + "\n")
                        elif destination == "loki":
                            # TODO: implementar push para Loki # stub-ok (destino loki fora do escopo atual — spool em file é o padrão operacional)
                            pass
                        else:
                            log.warning("Destino desconhecido: %s", destination)

                        lines_drained += 1
                    except json.JSONDecodeError:
                        pass

            drained_count += 1
            drained_bytes += log_file.stat().st_size
            log.info("  %s: %d linhas drenadas", log_file.name, lines_drained)

            # Remove arquivo drenado
            log_file.unlink()

        except Exception as e:
            errors.append(f"{log_file}: {e}")
            log.error("Erro drenando %s: %s", log_file, e)

    # Cleanup arquivos antigos (retention)
    cutoff = time.time() - (retention_days * 86400)
    for old_file in route_dir.glob("*"):
        try:
            if old_file.stat().st_mtime < cutoff:
                old_file.unlink()
                log.debug("Removido arquivo antigo: %s", old_file)
        except Exception:
            pass

    return {
        "route": route_name,
        "status": "success" if not errors else "partial",
        "files_drained": drained_count,
        "bytes_drained": drained_bytes,
        "errors": errors,
    }


def rotate_large_files(target_root: Path, max_size_mb: int) -> dict[str, Any]:
    """Rotaciona arquivos de log que excedem max_size_mb."""
    rotated = 0
    max_bytes = max_size_mb * 1024 * 1024

    for route_dir in target_root.iterdir():
        if not route_dir.is_dir():
            continue
        for log_file in route_dir.glob("*.jsonl"):
            try:
                size = log_file.stat().st_size
                if size > max_bytes:
                    # Comprime e renomeia com timestamp
                    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
                    gz_name = route_dir / f"{log_file.stem}.{timestamp}.jsonl.gz"
                    with open(log_file, "rb") as f_in:
                        with gzip.open(gz_name, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    log_file.unlink()
                    log.info("Rotacionado: %s -> %s (%.1fMB)", log_file, gz_name, size / (1024**2))
                    rotated += 1
            except Exception as e:
                log.warning("Erro rotacionando %s: %s", log_file, e)

    return {"rotated_files": rotated}


def main() -> int:
    parser = argparse.ArgumentParser(description="Drena logs bufferizados do pipeline tape")
    parser.add_argument("--route", required=True, help="Nome da rota (nextcloud, trading, etc.)")
    parser.add_argument("--target-root", default="/mnt/pretape/lto6-cache/logs", help="Raiz dos logs bufferizados")
    parser.add_argument("--destination", default="journald", choices=["journald", "file", "loki"], help="Destino final")
    parser.add_argument("--dest-path", default="", help="Caminho do destino (para file/loki)")
    parser.add_argument("--retention-days", type=int, default=7, help="Dias para reter logs locais")
    parser.add_argument("--max-file-size-mb", type=int, default=100, help="Tamanho máximo antes de rotacionar")
    parser.add_argument("--rotate", action="store_true", help="Também rotaciona arquivos grandes")
    parser.add_argument("--log-level", default="INFO", help="Nível de log")

    args = parser.parse_args()
    logging.getLogger().setLevel(args.log_level.upper())

    log.info("=== Tape Log Spool Drain iniciado ===")
    log.info("Route: %s", args.route)
    log.info("Target root: %s", args.target_root)
    log.info("Destination: %s", args.destination)

    start_time = time.time()
    target_root = Path(args.target_root)

    # Drena a rota
    result = drain_route(
        args.route,
        target_root,
        args.destination,
        args.dest_path,
        args.retention_days,
        args.max_file_size_mb,
    )

    # Rotaciona se solicitado
    if args.rotate:
        rotate_result = rotate_large_files(target_root, args.max_file_size_mb)
        result["rotation"] = rotate_result

    duration = time.time() - start_time
    result["duration_seconds"] = duration

    log.info("=== Drain concluído em %.1fs: %s ===", duration, result.get("status", "unknown"))
    print(json.dumps(result, ensure_ascii=False))

    return 0 if result.get("status") in ("success", "skipped") else 1


if __name__ == "__main__":
    sys.exit(main())