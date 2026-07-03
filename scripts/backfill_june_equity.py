#!/usr/bin/env python3
"""Importa candles históricos da KuCoin e reconstrói exchange_snapshots de junho.

Passos:
1. Busca candles 1min BTC-USDT de 01/06 a 10/06 (período sem dados) via API KuCoin
2. Insere candles na tabela btc.candles
3. Reconstrói exchange_snapshots hora a hora usando ledger de saldos + candles

Uso:
    python3 backfill_june_equity.py
"""
from __future__ import annotations

import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras
import requests

# ── path setup ────────────────────────────────────────────────────────────────
_AGENT_DIR = Path("/apps/crypto-trader/trading/btc_trading_agent")
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

from kucoin_api import KUCOIN_BASE, _build_headers  # type: ignore
from secrets_helper import get_database_url  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
LOG = logging.getLogger("backfill_june")

SCHEMA = "btc"
SYMBOL = "BTC-USDT"
KTYPE  = "1min"

# Período sem candles na DB (06-01 a 06-10 inclusive)
CANDLE_GAP_START = int(datetime(2026, 6,  1, 0, 0, 0, tzinfo=timezone.utc).timestamp())
CANDLE_GAP_END   = int(datetime(2026, 6, 11, 3, 55, 0, tzinfo=timezone.utc).timestamp())

# Período alvo para reconstrução de equity (06-01 a agora)
EQUITY_START = int(datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())


# ── DB ────────────────────────────────────────────────────────────────────────

def _connect():
    return psycopg2.connect(get_database_url())


# ── 1. CANDLE IMPORT ──────────────────────────────────────────────────────────

def _fetch_candles_range(start_ts: int, end_ts: int) -> list[dict]:
    """Busca candles 1min da KuCoin para um intervalo (máx 1500 por request)."""
    url = (
        f"{KUCOIN_BASE}/api/v1/market/candles"
        f"?type={KTYPE}&symbol={SYMBOL}&startAt={start_ts}&endAt={end_ts}"
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    raw = resp.json().get("data", [])
    candles = []
    for c in raw:
        if len(c) >= 7:
            candles.append({
                "timestamp": int(c[0]),
                "open":   float(c[1]),
                "close":  float(c[2]),
                "high":   float(c[3]),
                "low":    float(c[4]),
                "volume": float(c[5]),
            })
    return candles


def import_missing_candles(conn) -> int:
    """Importa candles de 01/06 a 10/06 (gap sem dados no banco)."""
    LOG.info("Importando candles %s de %s a %s",
             SYMBOL,
             datetime.fromtimestamp(CANDLE_GAP_START, tz=timezone.utc).date(),
             datetime.fromtimestamp(CANDLE_GAP_END, tz=timezone.utc).date())

    # KuCoin retorna máx 1500 candles/request → janela de 1500 min = 25h
    window = 1500 * 60  # segundos
    cursor = CANDLE_GAP_START
    total_inserted = 0

    while cursor < CANDLE_GAP_END:
        win_end = min(cursor + window - 60, CANDLE_GAP_END)
        LOG.info("  janela: %s → %s",
                 datetime.fromtimestamp(cursor, tz=timezone.utc),
                 datetime.fromtimestamp(win_end, tz=timezone.utc))

        candles = _fetch_candles_range(cursor, win_end)
        if not candles:
            LOG.warning("  sem dados nesta janela")
            cursor = win_end + 60
            time.sleep(0.4)
            continue

        inserted = 0
        with conn.cursor() as cur:
            for c in candles:
                cur.execute(
                    f"""
                    INSERT INTO {SCHEMA}.candles (timestamp, symbol, ktype, open, high, low, close, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (c["timestamp"], SYMBOL, KTYPE,
                     c["open"], c["high"], c["low"], c["close"], c["volume"]),
                )
                if cur.rowcount:
                    inserted += 1
        conn.commit()
        LOG.info("  %d candles inseridos (de %d recebidos)", inserted, len(candles))
        total_inserted += inserted
        cursor = win_end + 60
        time.sleep(0.35)  # rate limit

    LOG.info("Candles importados: %d total", total_inserted)
    return total_inserted


# ── 2. EQUITY RECONSTRUCTION ──────────────────────────────────────────────────

def reconstruct_equity_snapshots(conn) -> int:
    """Reconstrói exchange_snapshots hora a hora para todo junho.

    Fonte de saldo: exchange_balance_snapshots (forward-fill desde o último
    snapshot disponível antes de cada hora-alvo).
    Cobertura real: a tabela tem dados desde 31/05 e desde 11/06 com boa densidade.
    Para o gap 01-10/jun, o forward-fill usa o snapshot de 31/05 21:00
    (USDT≈595, BTC≈0.00023), que é a melhor aproximação disponível.

    Insere apenas horas sem snapshot existente (skipa junho 18+ que já tem dados
    minuto a minuto do exporter).
    """
    LOG.info("Reconstruindo exchange_snapshots de 01/06 em diante (via exchange_balance_snapshots)...")

    sql = f"""
    WITH
    -- Janela-alvo: 01/jun até o início dos dados existentes do exporter
    target_end AS (
        SELECT COALESCE(
            DATE_TRUNC('hour', to_timestamp(MIN(timestamp))) - INTERVAL '1 hour',
            '2026-06-22 00:00:00+00'::timestamptz
        ) AS ts
        FROM {SCHEMA}.exchange_snapshots
        WHERE timestamp >= %s
    ),
    hours AS (
        SELECT generate_series(
            '2026-06-01 00:00:00+00'::timestamptz,
            (SELECT ts FROM target_end),
            INTERVAL '1 hour'
        ) AS hour
    ),
    -- Forward-fill: último saldo USDT de exchange_balance_snapshots antes de cada hora
    usdt_snap AS (
        SELECT DISTINCT ON (h.hour)
            h.hour,
            s.balance AS usdt
        FROM hours h
        LEFT JOIN {SCHEMA}.exchange_balance_snapshots s ON
            s.account_type = 'trade' AND
            s.currency = 'USDT' AND
            s.synced_at <= h.hour
        ORDER BY h.hour, s.synced_at DESC NULLS LAST
    ),
    -- Forward-fill: último saldo BTC antes de cada hora
    btc_snap AS (
        SELECT DISTINCT ON (h.hour)
            h.hour,
            s.balance AS btc
        FROM hours h
        LEFT JOIN {SCHEMA}.exchange_balance_snapshots s ON
            s.account_type = 'trade' AND
            s.currency = 'BTC' AND
            s.synced_at <= h.hour
        ORDER BY h.hour, s.synced_at DESC NULLS LAST
    ),
    -- Forward-fill: último candle BTC antes de cada hora
    price_snap AS (
        SELECT DISTINCT ON (h.hour)
            h.hour,
            c.close AS price
        FROM hours h
        LEFT JOIN {SCHEMA}.candles c ON
            c.symbol = 'BTC-USDT' AND
            to_timestamp(c.timestamp) <= h.hour
        ORDER BY h.hour, c.timestamp DESC NULLS LAST
    ),
    final AS (
        SELECT
            h.hour,
            COALESCE(u.usdt,  0) AS usdt,
            COALESCE(b.btc,   0) AS btc,
            COALESCE(p.price, 0) AS price,
            COALESCE(u.usdt, 0) + COALESCE(b.btc, 0) * COALESCE(p.price, 0) AS equity
        FROM hours h
        JOIN usdt_snap  u ON u.hour = h.hour
        JOIN btc_snap   b ON b.hour = h.hour
        JOIN price_snap p ON p.hour = h.hour
        WHERE COALESCE(p.price, 0) > 0
          AND (COALESCE(u.usdt, 0) + COALESCE(b.btc, 0)) > 0
    )
    INSERT INTO {SCHEMA}.exchange_snapshots
        (timestamp, usdt_balance, btc_balance, btc_price, equity_usdt)
    SELECT
        EXTRACT(EPOCH FROM hour)::bigint,
        ROUND(usdt::numeric,  8),
        ROUND(btc::numeric,   8),
        ROUND(price::numeric, 2),
        ROUND(equity::numeric, 2)
    FROM final
    RETURNING timestamp
    """

    with conn.cursor() as cur:
        cur.execute(sql, (EQUITY_START,))
        rows = cur.fetchall()
    conn.commit()

    inserted = len(rows)
    if inserted:
        first_ts = min(r[0] for r in rows)
        last_ts  = max(r[0] for r in rows)
        LOG.info(
            "Inseridos %d snapshots hora a hora: %s → %s",
            inserted,
            datetime.fromtimestamp(first_ts, tz=timezone.utc),
            datetime.fromtimestamp(last_ts,  tz=timezone.utc),
        )
    else:
        LOG.info("Nenhum snapshot inserido — verifique cobertura de dados")
    return inserted


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    conn = _connect()
    try:
        import_missing_candles(conn)
        reconstruct_equity_snapshots(conn)
        LOG.info("✅ Backfill de junho concluído.")
        return 0
    except Exception:
        LOG.exception("Erro durante backfill")
        conn.rollback()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
