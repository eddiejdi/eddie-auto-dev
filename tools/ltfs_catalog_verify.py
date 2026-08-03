#!/usr/bin/env python3
"""
ltfs-catalog-verify — Valida integridade do catálogo LTFS pós-flush.

Verifica:
  1. catalog.jsonl: cada entrada tem SHA256 válido e arquivo existe na fita
  2. placements.json: consistente com catalog
  3. Amostragem: verifica SHA256 de N arquivos aleatórios na fita
  4. Métricas: exporta resultados para Prometheus

Uso:
  ltfs-catalog-verify --catalog /var/lib/ltfs-cache-flush/catalog.jsonl \
    --placements /var/lib/ltfs-cache-flush/placements.json \
    --tape-root /mnt/lto6-smb-proof/backups \
    --sample-percent 10 --sample-max 100 \
    --metrics-file /var/lib/ltfs-cache-flush/catalog_verify_metrics.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ltfs-catalog-verify] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("ltfs-catalog-verify")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content)
    tmp.replace(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_catalog(catalog_file: Path) -> list[dict[str, Any]]:
    entries = []
    if not catalog_file.exists():
        log.warning("Catalog não existe: %s", catalog_file)
        return entries
    with catalog_file.open() as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as e:
                log.error("Linha %d do catalog inválida: %s", line_num, e)
    return entries


def load_placements(placements_file: Path) -> dict[str, Any]:
    if not placements_file.exists():
        return {}
    try:
        return json.loads(placements_file.read_text())
    except Exception as e:
        log.error("Placements inválido: %s", e)
        return {}


def verify_catalog_structure(entries: list[dict]) -> dict[str, Any]:
    """Valida estrutura básica de cada entrada do catalog."""
    required_fields = {"timestamp", "action", "src_root", "rel_path", "size", "sha256", "target_root"}
    results = {"total": len(entries), "valid": 0, "invalid": 0, "errors": []}

    for i, entry in enumerate(entries):
        missing = required_fields - set(entry.keys())
        if missing:
            results["invalid"] += 1
            results["errors"].append(f"Entry {i}: missing fields {missing}")
        else:
            # Valida SHA256 format
            sha = entry.get("sha256", "")
            if not (isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)):
                results["invalid"] += 1
                results["errors"].append(f"Entry {i}: invalid sha256 format")
            else:
                results["valid"] += 1

    return results


def verify_placements_consistency(
    catalog_entries: list[dict], placements: dict
) -> dict[str, Any]:
    """Verifica se placements.json é consistente com catalog."""
    results = {"checked": 0, "consistent": 0, "inconsistent": 0, "missing_in_placements": 0, "errors": []}

    for entry in catalog_entries:
        if entry.get("action") != "flush":
            continue
        rel = entry.get("rel_path")
        if not rel:
            continue
        results["checked"] += 1

        placement = placements.get(rel)
        if not placement:
            results["missing_in_placements"] += 1
            results["errors"].append(f"Placement ausente para: {rel}")
            continue

        # Compara campos-chave
        mismatches = []
        for field in ("sha256", "size", "target_root"):
            cat_val = entry.get(field)
            plc_val = placement.get(field)
            if cat_val != plc_val:
                mismatches.append(f"{field}: catalog={cat_val} placement={plc_val}")

        if mismatches:
            results["inconsistent"] += 1
            results["errors"].append(f"{rel}: {', '.join(mismatches)}")
        else:
            results["consistent"] += 1

    return results


def sample_verify_tape(
    catalog_entries: list[dict],
    tape_root: Path,
    sample_percent: int,
    sample_max: int,
) -> dict[str, Any]:
    """Amostra e verifica SHA256 de arquivos na fita."""
    flush_entries = [e for e in catalog_entries if e.get("action") == "flush"]
    if not flush_entries:
        return {"sampled": 0, "verified": 0, "mismatched": 0, "missing": 0, "errors": []}

    # Calcula tamanho da amostra
    sample_size = min(len(flush_entries) * sample_percent // 100, sample_max)
    sample_size = max(sample_size, 1) if flush_entries else 0

    sampled = random.sample(flush_entries, sample_size) if sample_size < len(flush_entries) else flush_entries

    results = {"sampled": len(sampled), "verified": 0, "mismatched": 0, "missing": 0, "errors": []}

    for entry in sampled:
        rel = entry.get("rel_path")
        expected_sha = entry.get("sha256")
        target_root_str = entry.get("target_root")
        if not rel or not expected_sha or not target_root_str:
            results["errors"].append(f"Entry incompleto: {entry}")
            continue

        tape_file = Path(target_root_str) / rel
        if not tape_file.exists():
            results["missing"] += 1
            results["errors"].append(f"Arquivo não encontrado na fita: {tape_file}")
            continue

        try:
            actual_sha = sha256_file(tape_file)
            if actual_sha == expected_sha:
                results["verified"] += 1
            else:
                results["mismatched"] += 1
                results["errors"].append(f"SHA mismatch {rel}: expected={expected_sha[:12]}... actual={actual_sha[:12]}...")
        except Exception as e:
            results["errors"].append(f"Erro lendo {tape_file}: {e}")

    return results


def export_metrics(metrics_file: Path, results: dict[str, Any]) -> None:
    """Exporta métricas no formato Prometheus text."""
    lines = [
        "# HELP ltfs_catalog_verify_total Total catalog entries",
        "# TYPE ltfs_catalog_verify_total gauge",
        f"ltfs_catalog_verify_total {results.get('structure', {}).get('total', 0)}",
        "# HELP ltfs_catalog_verify_valid Valid catalog entries",
        "# TYPE ltfs_catalog_verify_valid gauge",
        f"ltfs_catalog_verify_valid {results.get('structure', {}).get('valid', 0)}",
        "# HELP ltfs_catalog_verify_invalid Invalid catalog entries",
        "# TYPE ltfs_catalog_verify_invalid gauge",
        f"ltfs_catalog_verify_invalid {results.get('structure', {}).get('invalid', 0)}",
        "# HELP ltfs_catalog_placements_consistent Consistent placements",
        "# TYPE ltfs_catalog_placements_consistent gauge",
        f"ltfs_catalog_placements_consistent {results.get('placements', {}).get('consistent', 0)}",
        "# HELP ltfs_catalog_placements_inconsistent Inconsistent placements",
        "# TYPE ltfs_catalog_placements_inconsistent gauge",
        f"ltfs_catalog_placements_inconsistent {results.get('placements', {}).get('inconsistent', 0)}",
        "# HELP ltfs_catalog_tape_verified Files verified on tape (sample)",
        "# TYPE ltfs_catalog_tape_verified gauge",
        f"ltfs_catalog_tape_verified {results.get('tape_sample', {}).get('verified', 0)}",
        "# HELP ltfs_catalog_tape_mismatched Files with SHA mismatch on tape (sample)",
        "# TYPE ltfs_catalog_tape_mismatched gauge",
        f"ltfs_catalog_tape_mismatched {results.get('tape_sample', {}).get('mismatched', 0)}",
        "# HELP ltfs_catalog_tape_missing Files missing on tape (sample)",
        "# TYPE ltfs_catalog_tape_missing gauge",
        f"ltfs_catalog_tape_missing {results.get('tape_sample', {}).get('missing', 0)}",
        "# HELP ltfs_catalog_verify_timestamp Unix timestamp of verification",
        "# TYPE ltfs_catalog_verify_timestamp gauge",
        f"ltfs_catalog_verify_timestamp {int(time.time())}",
    ]
    _atomic_write(metrics_file, "\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida integridade do catálogo LTFS")
    parser.add_argument("--catalog", required=True, help="Caminho para catalog.jsonl")
    parser.add_argument("--placements", required=True, help="Caminho para placements.json")
    parser.add_argument("--tape-root", required=True, help="Raiz da fita montada via CIFS")
    parser.add_argument("--sample-percent", type=int, default=10, help="Porcentagem de arquivos para amostrar (1-100)")
    parser.add_argument("--sample-max", type=int, default=100, help="Máximo de arquivos para amostrar")
    parser.add_argument("--metrics-file", required=True, help="Arquivo de saída métricas Prometheus")
    parser.add_argument("--log-level", default="INFO", help="Nível de log")

    args = parser.parse_args()
    logging.getLogger().setLevel(args.log_level.upper())

    log.info("=== Validação de catálogo LTFS iniciada ===")
    log.info("Catalog: %s", args.catalog)
    log.info("Placements: %s", args.placements)
    log.info("Tape root: %s", args.tape_root)
    log.info("Sample: %d%% (max %d)", args.sample_percent, args.sample_max)

    start_time = time.time()

    # Carrega dados
    catalog_entries = load_catalog(Path(args.catalog))
    log.info("Catalog entries carregadas: %d", len(catalog_entries))

    placements = load_placements(Path(args.placements))
    log.info("Placements carregados: %d", len(placements))

    # Verificações
    structure_results = verify_catalog_structure(catalog_entries)
    log.info("Estrutura: total=%d valid=%d invalid=%d",
             structure_results["total"], structure_results["valid"], structure_results["invalid"])

    placements_results = verify_placements_consistency(catalog_entries, placements)
    log.info("Placements: checked=%d consistent=%d inconsistent=%d missing=%d",
             placements_results["checked"], placements_results["consistent"],
             placements_results["inconsistent"], placements_results["missing_in_placements"])

    tape_results = sample_verify_tape(catalog_entries, Path(args.tape_root), args.sample_percent, args.sample_max)
    log.info("Tape sample: sampled=%d verified=%d mismatched=%d missing=%d",
             tape_results["sampled"], tape_results["verified"],
             tape_results["mismatched"], tape_results["missing"])

    # Consolida resultados
    all_results = {
        "timestamp": _now_iso(),
        "duration_seconds": time.time() - start_time,
        "structure": structure_results,
        "placements": placements_results,
        "tape_sample": tape_results,
    }

    # Exporta métricas
    export_metrics(Path(args.metrics_file), all_results)
    log.info("Métricas exportadas para: %s", args.metrics_file)

    # Determina exit code
    critical_failures = (
        structure_results["invalid"] > 0 or
        placements_results["inconsistent"] > 0 or
        tape_results["mismatched"] > 0 or
        tape_results["missing"] > 0
    )

    if critical_failures:
        log.error("=== VALIDAÇÃO FALHOU ===")
        return 1
    else:
        log.info("=== VALIDAÇÃO OK ===")
        return 0


if __name__ == "__main__":
    sys.exit(main())