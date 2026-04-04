#!/usr/bin/env python3
"""Migração do banco de dados — schema marketing.

Cria o schema `marketing` e todas as tabelas necessárias no PostgreSQL.
Seguro para executar múltiplas vezes (usa IF NOT EXISTS).

Uso:
    python3 marketing/db_migrate.py            # Executa migração
    python3 marketing/db_migrate.py --dry-run  # Apenas imprime SQL
"""

import argparse
import logging
import os
import sys

logger = logging.getLogger("marketing.db_migrate")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@192.168.15.2:5433/shared",
)

MIGRATION_SQL = """
-- ============================================================
-- Marketing Schema Migration — RPA4ALL
-- Seguro para re-execução (IF NOT EXISTS em tudo)
-- ============================================================

-- Schema
CREATE SCHEMA IF NOT EXISTS marketing;

-- Tabela de leads
CREATE TABLE IF NOT EXISTS marketing.leads (
    id              SERIAL PRIMARY KEY,
    nome            VARCHAR(200)    NOT NULL,
    email           VARCHAR(254)    NOT NULL,
    empresa         VARCHAR(200)    NOT NULL,
    cargo           VARCHAR(200),
    telefone        VARCHAR(30),
    origem          VARCHAR(100)    DEFAULT 'landing_diagnostico',
    utm_source      VARCHAR(100),
    utm_medium      VARCHAR(100),
    utm_campaign    VARCHAR(100),
    status          VARCHAR(50)     DEFAULT 'novo',
    created_at      TIMESTAMPTZ     DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     DEFAULT NOW(),
    drip_step       INT             DEFAULT 0,
    drip_next_at    TIMESTAMPTZ,
    notas           TEXT
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_leads_email
    ON marketing.leads (email);

CREATE INDEX IF NOT EXISTS idx_leads_status
    ON marketing.leads (status);

CREATE INDEX IF NOT EXISTS idx_leads_created_at
    ON marketing.leads (created_at);

CREATE INDEX IF NOT EXISTS idx_leads_drip_next
    ON marketing.leads (drip_next_at)
    WHERE drip_step < 5 AND status = 'novo';

-- Tabela de métricas diárias
CREATE TABLE IF NOT EXISTS marketing.daily_metrics (
    id                      SERIAL PRIMARY KEY,
    data                    DATE            NOT NULL UNIQUE,
    leads_total             INT             DEFAULT 0,
    leads_novos             INT             DEFAULT 0,
    cpl_meta                NUMERIC(10,2),
    cpl_google              NUMERIC(10,2),
    cpl_linkedin            NUMERIC(10,2),
    custo_total             NUMERIC(10,2),
    diagnosticos_agendados  INT             DEFAULT 0,
    created_at              TIMESTAMPTZ     DEFAULT NOW()
);

-- Tabela de tracking de emails enviados
CREATE TABLE IF NOT EXISTS marketing.email_log (
    id          SERIAL PRIMARY KEY,
    lead_id     INT             NOT NULL REFERENCES marketing.leads(id),
    drip_step   INT             NOT NULL,
    subject     VARCHAR(300),
    sent_at     TIMESTAMPTZ     DEFAULT NOW(),
    status      VARCHAR(50)     DEFAULT 'sent'
);

CREATE INDEX IF NOT EXISTS idx_email_log_lead
    ON marketing.email_log (lead_id);

-- Tabela de posts orgânicos no X
CREATE TABLE IF NOT EXISTS marketing.x_posts_log (
    id          SERIAL PRIMARY KEY,
    post_id     VARCHAR(50),
    post_key    VARCHAR(20)     NOT NULL,
    text        TEXT            NOT NULL,
    posted_at   TIMESTAMPTZ     DEFAULT NOW(),
    status      VARCHAR(50)     DEFAULT 'posted'
);

CREATE INDEX IF NOT EXISTS idx_x_posts_key
    ON marketing.x_posts_log (post_key);

-- Tabela de campanhas (tracking de budget)
CREATE TABLE IF NOT EXISTS marketing.campaigns (
    id          SERIAL PRIMARY KEY,
    canal       VARCHAR(50)     NOT NULL,
    nome        VARCHAR(200)    NOT NULL,
    budget_dia  NUMERIC(10,2),
    status      VARCHAR(50)     DEFAULT 'draft',
    created_at  TIMESTAMPTZ     DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     DEFAULT NOW()
);

-- Trigger para updated_at automático
CREATE OR REPLACE FUNCTION marketing.update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_leads_updated'
    ) THEN
        CREATE TRIGGER trg_leads_updated
            BEFORE UPDATE ON marketing.leads
            FOR EACH ROW EXECUTE FUNCTION marketing.update_timestamp();
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_campaigns_updated'
    ) THEN
        CREATE TRIGGER trg_campaigns_updated
            BEFORE UPDATE ON marketing.campaigns
            FOR EACH ROW EXECUTE FUNCTION marketing.update_timestamp();
    END IF;
END;
$$;
"""


def run_migration(dry_run: bool = False) -> bool:
    """Executa a migração do banco de dados."""
    if dry_run:
        print("=== DRY RUN — SQL que seria executado ===")
        print(MIGRATION_SQL)
        return True

    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(MIGRATION_SQL)
        conn.close()
        logger.info("Migração concluída com sucesso")
        return True
    except Exception:
        logger.exception("Erro ao executar migração")
        return False


def main() -> None:
    """Entry point CLI."""
    parser = argparse.ArgumentParser(description="Marketing DB migration")
    parser.add_argument("--dry-run", action="store_true", help="Apenas imprime SQL")
    args = parser.parse_args()

    ok = run_migration(dry_run=args.dry_run)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
