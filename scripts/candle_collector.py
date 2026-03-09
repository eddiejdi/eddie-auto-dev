#!/usr/bin/env python3
"""Coletor periódico de candles BTC da KuCoin → PostgreSQL.

Coleta candles 1min e 15min das últimas N horas e persiste em btc.candles.
Projetado para rodar via systemd timer a cada 15 minutos.

Uso:
    python3 candle_collector.py                    # Coleta últimas 2h
    python3 candle_collector.py --hours 24         # Coleta últimas 24h
    python3 candle_collector.py --backfill 168     # Backfill de 7 dias
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg2
import requests

# ── Configuração ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("candle_collector")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/btc_trading",
)
SCHEMA = "btc"
KUCOIN_BASE = "https://api.kucoin.com"

SYMBOLS = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "DOGE-USDT", "ADA-USDT"]
KTYPES = ["1min", "15min"]


def ensure_table(conn: Any) -> None:
    """Garante que a tabela btc.candles existe."""
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.candles (
                id SERIAL PRIMARY KEY,
                timestamp BIGINT NOT NULL,
                symbol TEXT NOT NULL,
                ktype TEXT NOT NULL,
                open DOUBLE PRECISION,
                high DOUBLE PRECISION,
                low DOUBLE PRECISION,
                close DOUBLE PRECISION,
                volume DOUBLE PRECISION,
                UNIQUE(timestamp, symbol, ktype)
            )
        """)


def fetch_candles(
    conn: Any,
    symbol: str,
    ktype: str,
    hours: int = 2,
) -> int:
    """Baixa candles recentes da KuCoin e insere no PostgreSQL.

    Args:
        conn: Conexão psycopg2 com autocommit.
        symbol: Par de trading (ex: BTC-USDT).
        ktype: Tipo de candle (1min, 15min).
        hours: Horas para buscar retroativamente.

    Returns:
        Número de candles inseridos.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours)
    total_inserted = 0

    # KuCoin limita 1500 candles por request
    # 1min = 1500min = 25h | 15min = 1500*15min = 375h
    window_hours = 24 if ktype == "1min" else 72

    current = start
    while current < now:
        window_end = min(current + timedelta(hours=window_hours), now)
        start_ts = int(current.timestamp())
        end_ts = int(window_end.timestamp())

        url = (
            f"{KUCOIN_BASE}/api/v1/market/candles"
            f"?type={ktype}&symbol={symbol}"
            f"&startAt={start_ts}&endAt={end_ts}"
        )

        time.sleep(0.2)  # Rate limit
        try:
            r = requests.get(url, timeout=15)
            data = r.json()

            if data.get("code") != "200000":
                logger.warning(f"  ⚠️ {symbol} {ktype}: {data.get('msg', 'unknown error')}")
                current = window_end
                continue

            raw = data.get("data", [])
            batch = 0

            with conn.cursor() as cur:
                for c in raw:
                    if len(c) < 7:
                        continue
                    try:
                        cur.execute(
                            f"""
                            INSERT INTO {SCHEMA}.candles
                                (timestamp, symbol, ktype, open, high, low, close, volume)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (timestamp, symbol, ktype) DO NOTHING
                            """,
                            (
                                int(c[0]), symbol, ktype,
                                float(c[1]), float(c[3]), float(c[4]),
                                float(c[2]), float(c[5]),
                            ),
                        )
                        batch += 1
                    except Exception:
                        pass

            total_inserted += batch

        except requests.exceptions.RequestException as e:
            logger.error(f"  ❌ {symbol} {ktype}: {e}")

        current = window_end

    return total_inserted


def main() -> int:
    """Executa coleta de candles."""
    parser = argparse.ArgumentParser(description="Coletor de candles KuCoin → PostgreSQL")
    parser.add_argument("--hours", type=int, default=2, help="Horas para coletar (default: 2)")
    parser.add_argument("--backfill", type=int, help="Backfill em horas (ex: 168 = 7 dias)")
    parser.add_argument("--symbols", nargs="+", default=SYMBOLS, help="Pares para coletar")
    parser.add_argument("--ktypes", nargs="+", default=KTYPES, help="Tipos de candle")
    args = parser.parse_args()

    hours = args.backfill or args.hours

    logger.info(f"🕯️ Candle Collector — {hours}h, {len(args.symbols)} pares, {args.ktypes}")

    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
    except Exception as e:
        logger.error(f"❌ Falha ao conectar no PostgreSQL: {e}")
        return 1

    ensure_table(conn)

    total = 0
    for symbol in args.symbols:
        for ktype in args.ktypes:
            inserted = fetch_candles(conn, symbol, ktype, hours)
            if inserted > 0:
                logger.info(f"  ✅ {symbol} {ktype}: {inserted} candles")
            total += inserted

    conn.close()
    logger.info(f"🏁 Total: {total} candles inseridos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
