#!/usr/bin/env python3
"""Apply the trading DB profile schema migration used by btc_trading_agent."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg2


MIGRATION_SQL = """
CREATE SCHEMA IF NOT EXISTS btc;

CREATE TABLE IF NOT EXISTS btc.ai_plans (
    id SERIAL PRIMARY KEY,
    timestamp DOUBLE PRECISION NOT NULL,
    symbol TEXT NOT NULL,
    plan_text TEXT NOT NULL,
    model TEXT,
    regime TEXT,
    price DOUBLE PRECISION,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS btc.profile_allocations (
    id SERIAL PRIMARY KEY,
    timestamp DOUBLE PRECISION NOT NULL,
    symbol TEXT NOT NULL,
    conservative_pct DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    aggressive_pct DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE btc.trades
    ADD COLUMN IF NOT EXISTS profile TEXT;
UPDATE btc.trades
SET profile = 'default'
WHERE profile IS NULL;
ALTER TABLE btc.trades
    ALTER COLUMN profile SET DEFAULT 'default';
ALTER TABLE btc.trades
    ALTER COLUMN profile SET NOT NULL;

ALTER TABLE btc.decisions
    ADD COLUMN IF NOT EXISTS profile TEXT;
UPDATE btc.decisions
SET profile = 'default'
WHERE profile IS NULL;
ALTER TABLE btc.decisions
    ALTER COLUMN profile SET DEFAULT 'default';
ALTER TABLE btc.decisions
    ALTER COLUMN profile SET NOT NULL;

ALTER TABLE btc.ai_plans
    ADD COLUMN IF NOT EXISTS profile TEXT;
UPDATE btc.ai_plans
SET profile = 'default'
WHERE profile IS NULL;
ALTER TABLE btc.ai_plans
    ALTER COLUMN profile SET DEFAULT 'default';
ALTER TABLE btc.ai_plans
    ALTER COLUMN profile SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_btc_trades_symbol_profile
    ON btc.trades(symbol, profile);
CREATE INDEX IF NOT EXISTS idx_btc_decisions_symbol_profile
    ON btc.decisions(symbol, profile);
CREATE INDEX IF NOT EXISTS idx_btc_ai_plans_symbol_profile_ts
    ON btc.ai_plans(symbol, profile, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_btc_profile_allocations_symbol_ts
    ON btc.profile_allocations(symbol, timestamp DESC);
"""


def _database_url_from_env_file(repo_root: Path) -> str | None:
    env_path = repo_root / "btc_trading_agent" / ".env"
    if not env_path.exists():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    return None


def _resolve_database_url(repo_root: Path, explicit: str | None) -> str:
    if explicit:
        return explicit

    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    file_url = _database_url_from_env_file(repo_root)
    if file_url:
        return file_url

    raise RuntimeError("DATABASE_URL not found in args, env, or btc_trading_agent/.env")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", help="PostgreSQL DSN")
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parent.parent,
        type=Path,
        help="Repository root used to resolve btc_trading_agent/.env",
    )
    args = parser.parse_args()

    dsn = _resolve_database_url(args.repo_root, args.database_url)
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(MIGRATION_SQL)
            cur.execute(
                """
                SELECT table_name, string_agg(column_name, ',' ORDER BY ordinal_position)
                FROM information_schema.columns
                WHERE table_schema = 'btc'
                  AND table_name IN ('trades', 'decisions', 'ai_plans')
                GROUP BY table_name
                ORDER BY table_name
                """
            )
            for table_name, columns in cur.fetchall():
                print(f"{table_name}:{columns}")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
