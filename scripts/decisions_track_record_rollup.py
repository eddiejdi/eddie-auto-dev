#!/usr/bin/env python3
"""Rollup horário de track_record_trs/track_record_boost → PostgreSQL.

Pré-computa médias horárias de btc.decisions.features->>'track_record_trs'
e 'track_record_boost' em btc.decisions_track_record_hourly, evitando que
o dashboard Grafana precise agregar sobre milhões de linhas JSONB toda
vez que o período é ampliado (ex.: 90 dias levava ~2s por query e
contribuía para instabilidade do dashboard — ver PR de correção do
painel "Decisões Recentes").

Uso:
    python3 decisions_track_record_rollup.py                  # refresh incremental (últimas 3h)
    python3 decisions_track_record_rollup.py --hours-back 6   # janela de refresh maior
    python3 decisions_track_record_rollup.py --backfill 2160  # backfill único de 90 dias
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("decisions_track_record_rollup")

DATABASE_URL = os.environ.get("DATABASE_URL")
SCHEMA = "btc"


def ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.decisions_track_record_hourly (
                symbol TEXT NOT NULL,
                profile TEXT NOT NULL,
                servidor TEXT NOT NULL,
                bucket_hour TIMESTAMPTZ NOT NULL,
                avg_trs DOUBLE PRECISION,
                avg_boost DOUBLE PRECISION,
                sample_count INTEGER NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (symbol, profile, servidor, bucket_hour)
            )
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_decisions_trh_bucket
            ON {SCHEMA}.decisions_track_record_hourly (bucket_hour)
        """)


def refresh(conn, since: datetime) -> int:
    """Recalcula e faz upsert dos buckets horários desde `since` até agora.

    Reprocessa a janela inteira (não só linhas novas) porque o bucket da
    hora corrente segue recebendo decisões até a hora fechar — refazer o
    upsert idempotente é mais simples e seguro do que rastrear um high-water
    mark de linha processada.
    """
    since_epoch = since.timestamp()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {SCHEMA}.decisions_track_record_hourly
                (symbol, profile, servidor, bucket_hour, avg_trs, avg_boost, sample_count, updated_at)
            SELECT
                symbol,
                profile,
                servidor,
                date_trunc('hour', to_timestamp("timestamp")) AS bucket_hour,
                avg(NULLIF(features->>'track_record_trs', '')::double precision) AS avg_trs,
                avg(NULLIF(features->>'track_record_boost', '')::double precision) AS avg_boost,
                count(*) AS sample_count,
                now() AS updated_at
            FROM {SCHEMA}.decisions
            WHERE "timestamp" >= %(since_epoch)s
              AND profile IS NOT NULL
              AND (features ? 'track_record_trs' OR features ? 'track_record_boost')
            GROUP BY symbol, profile, servidor, date_trunc('hour', to_timestamp("timestamp"))
            ON CONFLICT (symbol, profile, servidor, bucket_hour) DO UPDATE SET
                avg_trs = EXCLUDED.avg_trs,
                avg_boost = EXCLUDED.avg_boost,
                sample_count = EXCLUDED.sample_count,
                updated_at = EXCLUDED.updated_at
            """,
            {"since_epoch": since_epoch},
        )
        return cur.rowcount


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollup horário de track record → Postgres")
    parser.add_argument(
        "--hours-back", type=int, default=3,
        help="Janela de refresh incremental em horas (default: 3, cobre atraso + fechamento de hora)",
    )
    parser.add_argument(
        "--backfill", type=int,
        help="Backfill único em horas a partir de agora (ex: 2160 = 90 dias). Sobrepõe --hours-back.",
    )
    args = parser.parse_args()

    if not DATABASE_URL:
        logger.error("❌ DATABASE_URL não configurado no ambiente")
        return 1

    window_hours = args.backfill or args.hours_back
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    logger.info(f"🔄 Rollup track record — janela de {window_hours}h (desde {since.isoformat()})")

    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
    except Exception as e:
        logger.error(f"❌ Falha ao conectar no PostgreSQL: {e}", exc_info=True)
        return 1

    try:
        ensure_table(conn)
        rows = refresh(conn, since)
        conn.commit()
        logger.info(f"✅ {rows} buckets horários atualizados")
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Falha no refresh do rollup: {e}", exc_info=True)
        return 1
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
