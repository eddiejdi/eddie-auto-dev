#!/usr/bin/env python3
"""
ltfs_catalog — Tape Catalog para NAS LTO-6

Indexa arquivos do LTFS no PostgreSQL para busca rápida sem montar fitas.
Suporta múltiplas fitas (NC0321, NC0322, NC0323) com UPSERT eficiente.

Uso como CLI:
    ltfs-catalog-index index --tape NC0322 --mountpoint /mnt/tape/lto6
    ltfs-catalog-index query "relatorio_jan" --limit 20
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

import psycopg2
import psycopg2.extensions

logger = logging.getLogger("ltfs_catalog")

# ---------------------------------------------------------------------------
# SQL da migration — idempotente (CREATE IF NOT EXISTS)
# ---------------------------------------------------------------------------
_MIGRATION_SQL = """
SET search_path = tape_catalog, public;

CREATE SCHEMA IF NOT EXISTS tape_catalog;

CREATE TABLE IF NOT EXISTS tape_catalog.tapes (
    serial      TEXT PRIMARY KEY,
    label       TEXT,
    drive_id    TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    capacity_gb INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS tape_catalog.files (
    id          BIGSERIAL PRIMARY KEY,
    tape_serial TEXT NOT NULL REFERENCES tape_catalog.tapes(serial),
    path        TEXT NOT NULL,
    size_bytes  BIGINT,
    mtime       TIMESTAMPTZ,
    sha256      TEXT,
    ltfs_uid    TEXT,
    indexed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tape_serial, path)
);

CREATE INDEX IF NOT EXISTS idx_files_path_gin
    ON tape_catalog.files USING gin(to_tsvector('simple', path));

CREATE INDEX IF NOT EXISTS idx_files_tape
    ON tape_catalog.files(tape_serial);

CREATE INDEX IF NOT EXISTS idx_files_mtime
    ON tape_catalog.files(mtime DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_files_sha256
    ON tape_catalog.files(sha256) WHERE sha256 IS NOT NULL;
"""


# ---------------------------------------------------------------------------
# Conexão
# ---------------------------------------------------------------------------

def conectar(database_url: str) -> psycopg2.extensions.connection:
    """Estabelece conexão com o PostgreSQL. autocommit=True conforme padrão do projeto."""
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    return conn


# ---------------------------------------------------------------------------
# Schema / Migration
# ---------------------------------------------------------------------------

def criar_schema(conn: psycopg2.extensions.connection) -> None:
    """Cria o schema tape_catalog e tabelas se ainda não existirem."""
    with conn.cursor() as cur:
        cur.execute(_MIGRATION_SQL)
    logger.info("Schema tape_catalog verificado/criado.")


# ---------------------------------------------------------------------------
# Fitas
# ---------------------------------------------------------------------------

def registrar_fita(
    conn: psycopg2.extensions.connection,
    serial: str,
    label: Optional[str] = None,
    drive_id: Optional[str] = None,
    status: str = "active",
) -> None:
    """Insere ou atualiza metadados da fita. Não sobrescreve com NULL."""
    sql = """
    INSERT INTO tape_catalog.tapes (serial, label, drive_id, status, last_seen)
    VALUES (%s, %s, %s, %s, now())
    ON CONFLICT (serial) DO UPDATE
        SET label     = COALESCE(EXCLUDED.label,    tape_catalog.tapes.label),
            drive_id  = COALESCE(EXCLUDED.drive_id, tape_catalog.tapes.drive_id),
            status    = EXCLUDED.status,
            last_seen = now();
    """
    with conn.cursor() as cur:
        cur.execute(sql, (serial, label, drive_id, status))
    logger.debug("Fita %s registrada/atualizada.", serial)


def listar_fitas(conn: psycopg2.extensions.connection) -> list[dict]:
    """Retorna todas as fitas registradas com contagem de arquivos indexados."""
    sql = """
    SELECT t.serial, t.label, t.drive_id, t.status, t.last_seen,
           COUNT(f.id) AS total_arquivos,
           COALESCE(SUM(f.size_bytes), 0) AS total_bytes
    FROM tape_catalog.tapes t
    LEFT JOIN tape_catalog.files f ON f.tape_serial = t.serial
    GROUP BY t.serial, t.label, t.drive_id, t.status, t.last_seen
    ORDER BY t.serial;
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return [
        {
            "serial": r[0], "label": r[1], "drive_id": r[2],
            "status": r[3], "last_seen": r[4],
            "total_arquivos": r[5], "total_bytes": r[6],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Varredura LTFS
# ---------------------------------------------------------------------------

def _caminhos_ltfs(
    mountpoint: str,
) -> Iterator[tuple[str, int, float, Optional[str]]]:
    """
    Gera tuplas (path_relativo, size_bytes, mtime_unix, ltfs_uid)
    varrendo o mountpoint LTFS recursivamente.
    Ignora entradas inacessíveis silenciosamente.
    """
    base = Path(mountpoint)
    for dirpath, _dirs, files in os.walk(mountpoint):
        for fname in files:
            fpath = Path(dirpath) / fname
            try:
                stat = fpath.stat()
            except OSError:
                continue

            rel = str(fpath.relative_to(base))

            ltfs_uid: Optional[str] = None
            try:
                raw = os.getxattr(str(fpath), "user.ltfs.uid")
                ltfs_uid = raw.decode("utf-8", errors="replace").strip()
            except (OSError, AttributeError):
                pass

            yield rel, stat.st_size, stat.st_mtime, ltfs_uid


# ---------------------------------------------------------------------------
# Indexação
# ---------------------------------------------------------------------------

def indexar(
    conn: psycopg2.extensions.connection,
    tape_serial: str,
    mountpoint: str,
    batch_size: int = 500,
) -> int:
    """
    Varre o mountpoint LTFS e faz UPSERT no catalog.
    Retorna o total de arquivos processados.
    """
    sql_upsert = """
    INSERT INTO tape_catalog.files
           (tape_serial, path, size_bytes, mtime, ltfs_uid, indexed_at)
    VALUES (%s, %s, %s, to_timestamp(%s), %s, now())
    ON CONFLICT (tape_serial, path) DO UPDATE
        SET size_bytes = EXCLUDED.size_bytes,
            mtime      = EXCLUDED.mtime,
            ltfs_uid   = COALESCE(EXCLUDED.ltfs_uid, tape_catalog.files.ltfs_uid),
            indexed_at = now();
    """
    total = 0
    batch: list[tuple] = []

    def _flush(cur: psycopg2.extensions.cursor) -> None:
        if batch:
            cur.executemany(sql_upsert, batch)
            batch.clear()

    with conn.cursor() as cur:
        for rel, size, mtime, uid in _caminhos_ltfs(mountpoint):
            batch.append((tape_serial, rel, size, mtime, uid))
            total += 1
            if len(batch) >= batch_size:
                _flush(cur)
                logger.debug("Batch de %d arquivos persistido.", batch_size)
        _flush(cur)

    logger.info("Indexação concluída: %d arquivos na fita %s.", total, tape_serial)
    return total


# ---------------------------------------------------------------------------
# Busca
# ---------------------------------------------------------------------------

def buscar(
    conn: psycopg2.extensions.connection,
    termo: str,
    tape_serial: Optional[str] = None,
    limite: int = 50,
) -> list[dict]:
    """
    Busca arquivos por termo no path usando índice GIN (full-text 'simple').
    Retorna lista de dicts com tape, path, size e mtime.
    """
    if tape_serial:
        sql = """
        SELECT tape_serial, path, size_bytes, mtime
          FROM tape_catalog.files
         WHERE tape_serial = %s
           AND to_tsvector('simple', path) @@ plainto_tsquery('simple', %s)
         ORDER BY mtime DESC NULLS LAST
         LIMIT %s;
        """
        params: tuple = (tape_serial, termo, limite)
    else:
        sql = """
        SELECT tape_serial, path, size_bytes, mtime
          FROM tape_catalog.files
         WHERE to_tsvector('simple', path) @@ plainto_tsquery('simple', %s)
         ORDER BY mtime DESC NULLS LAST
         LIMIT %s;
        """
        params = (termo, limite)

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return [
        {"tape": r[0], "path": r[1], "size": r[2], "mtime": r[3]}
        for r in rows
    ]


def buscar_duplicados(conn: psycopg2.extensions.connection) -> list[dict]:
    """Retorna arquivos com mesmo sha256 em fitas diferentes (dedup cross-tape)."""
    sql = """
    SELECT sha256, array_agg(tape_serial || ':' || path ORDER BY tape_serial) AS cópias,
           COUNT(*) AS total
      FROM tape_catalog.files
     WHERE sha256 IS NOT NULL
     GROUP BY sha256
    HAVING COUNT(DISTINCT tape_serial) > 1
     ORDER BY total DESC
     LIMIT 100;
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return [{"sha256": r[0], "copias": r[1], "total": r[2]} for r in rows]


# ---------------------------------------------------------------------------
# CLI handlers
# ---------------------------------------------------------------------------

def _obter_database_url() -> str:
    """Lê DATABASE_URL da env ou do arquivo /etc/ltfs-catalog.env."""
    url = os.environ.get("TAPE_CATALOG_DB") or os.environ.get("DATABASE_URL", "")
    if not url:
        env_file = Path("/etc/ltfs-catalog.env")
        if env_file.exists():
            for linha in env_file.read_text().splitlines():
                if linha.startswith("TAPE_CATALOG_DB="):
                    url = linha.split("=", 1)[1].strip().strip('"')
                    break
    return url


def _cmd_index(args: argparse.Namespace) -> None:
    """Handler do subcomando 'index'."""
    database_url = _obter_database_url()
    if not database_url:
        logger.error("TAPE_CATALOG_DB ou DATABASE_URL não definido.")
        sys.exit(1)

    conn = conectar(database_url)
    criar_schema(conn)
    registrar_fita(conn, args.tape, label=args.label, drive_id=args.drive_id)
    total = indexar(conn, args.tape, args.mountpoint, batch_size=args.batch_size)
    print(f"Indexados {total} arquivos da fita {args.tape}.")


def _cmd_query(args: argparse.Namespace) -> None:
    """Handler do subcomando 'query'."""
    database_url = _obter_database_url()
    if not database_url:
        logger.error("TAPE_CATALOG_DB ou DATABASE_URL não definido.")
        sys.exit(1)

    conn = conectar(database_url)
    resultados = buscar(conn, args.termo, tape_serial=args.tape, limite=args.limit)

    if not resultados:
        print("Nenhum arquivo encontrado.")
        return

    for r in resultados:
        size_mb = f"{r['size'] / 1_048_576:.1f}MB" if r["size"] else "?"
        mtime_str = r["mtime"].strftime("%Y-%m-%d") if r["mtime"] else "?"
        print(f"[{r['tape']}]  {r['path']}  ({size_mb}, {mtime_str})")


def _cmd_list(args: argparse.Namespace) -> None:
    """Handler do subcomando 'list' — lista fitas e estatísticas."""
    database_url = _obter_database_url()
    if not database_url:
        logger.error("TAPE_CATALOG_DB ou DATABASE_URL não definido.")
        sys.exit(1)

    conn = conectar(database_url)
    fitas = listar_fitas(conn)

    if not fitas:
        print("Nenhuma fita no catalog.")
        return

    print(f"{'Serial':<10} {'Status':<10} {'Arquivos':>10} {'GB':>8}  Label")
    print("-" * 60)
    for f in fitas:
        gb = (f["total_bytes"] or 0) / 1_073_741_824
        print(
            f"{f['serial']:<10} {f['status']:<10} {f['total_arquivos']:>10} "
            f"{gb:>8.1f}  {f['label'] or '-'}"
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Ponto de entrada principal do CLI ltfs-catalog."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        stream=sys.stderr,
    )

    parser = argparse.ArgumentParser(
        description="LTFS Tape Catalog — indexação e busca de arquivos em fitas LTO-6",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # --- index ---
    p_idx = sub.add_parser("index", help="Indexar arquivos de uma fita LTFS montada")
    p_idx.add_argument("--tape", required=True, metavar="SERIAL",
                       help="Serial da fita (ex: NC0322)")
    p_idx.add_argument("--mountpoint", default="/mnt/tape/lto6",
                       help="Mountpoint LTFS (padrão: /mnt/tape/lto6)")
    p_idx.add_argument("--label", help="Label legível da fita")
    p_idx.add_argument("--drive-id", dest="drive_id",
                       help="ID da unidade de fita (ex: HUJ5485716)")
    p_idx.add_argument("--batch-size", dest="batch_size", type=int, default=500,
                       help="Tamanho do batch de UPSERT (padrão: 500)")
    p_idx.set_defaults(func=_cmd_index)

    # --- query ---
    p_qry = sub.add_parser("query", help="Buscar arquivo por nome/path no catalog")
    p_qry.add_argument("termo", help="Texto para buscar no path dos arquivos")
    p_qry.add_argument("--tape", metavar="SERIAL",
                       help="Filtrar por fita específica (ex: NC0322)")
    p_qry.add_argument("--limit", type=int, default=50,
                       help="Máximo de resultados (padrão: 50)")
    p_qry.set_defaults(func=_cmd_query)

    # --- list ---
    p_lst = sub.add_parser("list", help="Listar fitas no catalog com estatísticas")
    p_lst.set_defaults(func=_cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
