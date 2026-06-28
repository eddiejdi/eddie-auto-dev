#!/usr/bin/env python3
"""
Executa migrations SQL numeradas em sequência, registrando quais já foram aplicadas.

Uso:
    python3 tools/migrations/run_migration.py [--dry-run] [--version 001]

Variáveis de ambiente:
    DATABASE_URL — connection string PostgreSQL (obrigatório)
                   Exemplo: postgresql://user:pass@host:5433/dbname
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:shared_memory_2026@192.168.15.2:5433/postgres",
)

MIGRATIONS_DIR = Path(__file__).parent


def get_connection():
    try:
        import psycopg2
    except ImportError:
        print("ERRO: psycopg2 não instalado. Execute: pip install psycopg2-binary", file=sys.stderr)
        sys.exit(1)
    return psycopg2.connect(DATABASE_URL)


def ensure_migrations_table(cur) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def applied_versions(cur) -> set[str]:
    cur.execute("SELECT version FROM schema_migrations")
    return {row[0] for row in cur.fetchall()}


def list_migration_files() -> list[tuple[str, Path]]:
    """Retorna lista de (version, path) ordenada por versão."""
    files = []
    for f in MIGRATIONS_DIR.glob("*.sql"):
        m = re.match(r"^(\d+)_", f.name)
        if m:
            files.append((m.group(1), f))
    return sorted(files, key=lambda x: x[0])


def run(dry_run: bool = False, target_version: str | None = None) -> None:
    conn = get_connection()
    cur = conn.cursor()

    ensure_migrations_table(cur)
    conn.commit()

    applied = applied_versions(cur)
    pending = [
        (ver, path) for ver, path in list_migration_files()
        if ver not in applied and (target_version is None or ver == target_version)
    ]

    if not pending:
        print("Nenhuma migration pendente.")
        cur.close()
        conn.close()
        return

    for version, path in pending:
        sql = path.read_text(encoding="utf-8")
        print(f"[{'DRY-RUN' if dry_run else 'APLICANDO'}] {path.name} ...")

        if dry_run:
            print(f"  → {sql[:200].strip()}{'...' if len(sql) > 200 else ''}")
            continue

        try:
            cur.execute(sql)
            conn.commit()
            print(f"  ✓ {path.name} aplicada com sucesso.")
        except Exception as exc:
            conn.rollback()
            print(f"  ✗ FALHA em {path.name}: {exc}", file=sys.stderr)
            cur.close()
            conn.close()
            sys.exit(1)

    cur.close()
    conn.close()
    if not dry_run:
        print(f"\n{len(pending)} migration(s) aplicada(s) com sucesso.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa migrations SQL do homelab.")
    parser.add_argument("--dry-run", action="store_true", help="Mostra o SQL sem executar.")
    parser.add_argument("--version", help="Aplica apenas a versão especificada (ex: 001).")
    parser.add_argument("--list", action="store_true", help="Lista migrations e status.")
    args = parser.parse_args()

    if args.list:
        conn = get_connection()
        cur = conn.cursor()
        ensure_migrations_table(cur)
        conn.commit()
        applied = applied_versions(cur)
        cur.close()
        conn.close()
        print(f"{'VER':<6} {'STATUS':<12} {'ARQUIVO'}")
        print("-" * 50)
        for ver, path in list_migration_files():
            status = "✓ aplicada" if ver in applied else "○ pendente"
            print(f"{ver:<6} {status:<12} {path.name}")
        return

    run(dry_run=args.dry_run, target_version=args.version)


if __name__ == "__main__":
    main()
