#!/usr/bin/env python3
"""Valida fronteiras iniciais entre dominios do monorepo.

Objetivo:
  - impedir novos vazamentos obvios de paths/nomes de repo antigos
  - documentar o que ja esta sob governanca de trading, homelab e shared

Uso:
  python3 scripts/validate_domain_boundaries.py
  python3 scripts/validate_domain_boundaries.py --strict
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "domain_boundaries.json"
SKIP_DIRS = {
    ".git",
    ".venv",
    ".venv_decomp",
    ".venv_selenium",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    ".archive",
    "artifacts",
    "backups",
    "uploads",
    "tmp",
    ".tmp",
}


@dataclass
class Violation:
    domain: str
    path: Path
    needle: str


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def iter_owned_files(patterns: Iterable[str]) -> list[Path]:
    files: set[Path] = set()
    for rel_pattern in patterns:
        for path in REPO_ROOT.glob(rel_pattern):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.is_file():
                files.add(path)
            elif path.is_dir():
                for nested in path.rglob("*"):
                    if nested.is_file() and not any(part in SKIP_DIRS for part in nested.parts):
                        files.add(nested)
    return sorted(files)


def scan_domain(domain_name: str, domain_cfg: dict) -> list[Violation]:
    violations: list[Violation] = []
    owned_files = iter_owned_files(domain_cfg.get("owned_paths", []))
    forbidden = domain_cfg.get("forbidden_substrings", [])

    for path in owned_files:
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for needle in forbidden:
            if needle in content:
                violations.append(
                    Violation(domain=domain_name, path=path, needle=needle)
                )

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida fronteiras de dominios")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Retorna exit code 1 se encontrar violacoes",
    )
    args = parser.parse_args()

    config = load_config()
    domains: dict = config["domains"]
    violations: list[Violation] = []

    print("=== Domain Boundaries ===")
    for name, cfg in domains.items():
        owned_files = iter_owned_files(cfg.get("owned_paths", []))
        print(
            f"- {name}: repo alvo={cfg['target_repo']} | arquivos monitorados={len(owned_files)}"
        )
        violations.extend(scan_domain(name, cfg))

    if violations:
        print("\nViolacoes encontradas:")
        for item in violations:
            rel = item.path.relative_to(REPO_ROOT).as_posix()
            print(f"  - [{item.domain}] {rel}: contem '{item.needle}'")
        return 1 if args.strict else 0

    print("\nNenhuma violacao encontrada no escopo monitorado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
