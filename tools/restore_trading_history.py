#!/usr/bin/env python3
"""Restaura histórico de trades e candles da KuCoin para PostgreSQL.

Baixa todos os orders executados de 2026 via API KuCoin (paginado por
janelas de 7 dias) e insere no banco PostgreSQL (schema btc).
Também baixa candles de 15min para todo o período.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import argparse
from datetime import datetime, timedelta
from typing import Any

import psycopg2
import psycopg2.extras
import requests

# ── Configuração ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("restore_history")

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore trading history to Postgres")
    parser.add_argument("--database-url", dest="database_url", help="Postgres DSN (or set DATABASE_URL env)")
    return parser.parse_args()

ARGS = _parse_args()
DATABASE_URL = ARGS.database_url or os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    logging.error(
        "DATABASE_URL is required. Provide --database-url or set DATABASE_URL environment variable.\n"
        "Example: export DATABASE_URL=postgresql://postgres:pass@host:5433/btc_trading"
    )
    sys.exit(1)
SCHEMA = "btc"
KUCOIN_BASE = "https://api.kucoin.com"

# Símbolos para restaurar
SYMBOLS = ["BTC-USDT", "ETH-USDT", "XRP-USDT", "SOL-USDT", "DOGE-USDT", "ADA-USDT"]

# Período: 1 Jan 2026 até agora
START_DATE = datetime(2026, 1, 1)
WINDOW_DAYS = 7  # KuCoin limita range de tempo

# ── KuCoin Auth ───────────────────────────────────────────────
_api_key = ""
_api_secret = ""
_api_passphrase = ""


def _load_kucoin_credentials() -> None:
    """Carrega credenciais KuCoin do .env ou ambiente."""
    global _api_key, _api_secret, _api_passphrase

    env_file = os.path.join(os.path.dirname(__file__), "..", "data", ".env")
    # Tenta carregar do diretório do trading agent
    agent_env = "/home/homelab/myClaude/btc_trading_agent/.env"

    for path in [agent_env, env_file]:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        key, _, val = line.partition("=")
                        os.environ.setdefault(key.strip(), val.strip())
            break

    _api_key = os.environ.get("KUCOIN_API_KEY", "")
    _api_secret = os.environ.get("KUCOIN_API_SECRET", "")
    _api_passphrase = os.environ.get("KUCOIN_API_PASSPHRASE", "")

    if _api_key:
        logger.info(f"🔑 KuCoin key loaded: {_api_key[:8]}...")
    else:
        logger.error("❌ Sem credenciais KuCoin!")
        sys.exit(1)


def _build_headers(method: str, endpoint: str, body_str: str = "") -> dict[str, str]:
    """Constrói headers autenticados para KuCoin API."""
    import base64
    import hashlib
    import hmac

    now = str(int(time.time() * 1000))
    str_to_sign = now + method.upper() + endpoint + body_str

    signature = base64.b64encode(
        hmac.new(
            _api_secret.encode("utf-8"),
            str_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    passphrase = base64.b64encode(
        hmac.new(
            _api_secret.encode("utf-8"),
            _api_passphrase.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    return {
        "KC-API-KEY": _api_key,
        "KC-API-SIGN": signature,
        "KC-API-TIMESTAMP": now,
        "KC-API-PASSPHRASE": passphrase,
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json",
    }


# ── Database ──────────────────────────────────────────────────
def get_db_conn() -> Any:
    """Cria conexão PostgreSQL com autocommit."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f"SET search_path TO {SCHEMA}, public")
    return conn


def ensure_schema(conn: Any) -> None:
    """Garante que o schema e tabelas existem."""
    cur = conn.cursor()
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.trades (
            id SERIAL PRIMARY KEY,
            timestamp DOUBLE PRECISION NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            price DOUBLE PRECISION NOT NULL,
            size DOUBLE PRECISION,
            funds DOUBLE PRECISION,
            order_id TEXT,
            status TEXT DEFAULT 'executed',
            pnl DOUBLE PRECISION,
            pnl_pct DOUBLE PRECISION,
            dry_run BOOLEAN DEFAULT FALSE,
            metadata JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.candles (
            id SERIAL PRIMARY KEY,
            timestamp BIGINT NOT NULL,
            symbol TEXT NOT NULL,
            ktype TEXT NOT NULL,
            open DOUBLE PRECISION NOT NULL,
            high DOUBLE PRECISION NOT NULL,
            low DOUBLE PRECISION NOT NULL,
            close DOUBLE PRECISION NOT NULL,
            volume DOUBLE PRECISION NOT NULL,
            UNIQUE(timestamp, symbol, ktype)
        )
    """)
    logger.info("✅ Schema e tabelas verificados")


# ── Fetch Orders from KuCoin ─────────────────────────────────
def fetch_orders_window(
    symbol: str, start_ms: int, end_ms: int
) -> list[dict[str, Any]]:
    """Busca orders executados em uma janela de tempo."""
    all_orders: list[dict[str, Any]] = []
    page = 1

    while True:
        endpoint = (
            f"/api/v1/orders?status=done&symbol={symbol}"
            f"&startAt={start_ms}&endAt={end_ms}"
            f"&pageSize=50&currentPage={page}"
        )
        headers = _build_headers("GET", endpoint)
        time.sleep(0.35)  # Rate limit

        try:
            r = requests.get(
                KUCOIN_BASE + endpoint, headers=headers, timeout=15
            )
            data = r.json()

            if data.get("code") != "200000":
                logger.warning(
                    f"⚠️ Orders API error: {data.get('msg', data.get('code'))}"
                )
                break

            items = data.get("data", {}).get("items", [])
            total_pages = data.get("data", {}).get("totalPage", 1)
            total_num = data.get("data", {}).get("totalNum", 0)

            all_orders.extend(items)

            if page == 1 and total_num > 0:
                logger.info(
                    f"  📦 {symbol} janela: {total_num} orders em {total_pages} páginas"
                )

            if page >= total_pages:
                break
            page += 1

        except Exception as e:
            logger.error(f"❌ Erro ao buscar orders: {e}")
            break

    return all_orders


def fetch_fills_window(
    symbol: str, start_ms: int, end_ms: int
) -> list[dict[str, Any]]:
    """Busca fills (execuções) em uma janela de tempo."""
    all_fills: list[dict[str, Any]] = []
    page = 1

    while True:
        endpoint = (
            f"/api/v1/fills?symbol={symbol}"
            f"&startAt={start_ms}&endAt={end_ms}"
            f"&pageSize=50&currentPage={page}"
        )
        headers = _build_headers("GET", endpoint)
        time.sleep(0.35)

        try:
            r = requests.get(
                KUCOIN_BASE + endpoint, headers=headers, timeout=15
            )
            data = r.json()

            if data.get("code") != "200000":
                logger.warning(
                    f"⚠️ Fills API error: {data.get('msg', data.get('code'))}"
                )
                break

            items = data.get("data", {}).get("items", [])
            total_pages = data.get("data", {}).get("totalPage", 1)
            total_num = data.get("data", {}).get("totalNum", 0)

            all_fills.extend(items)

            if page == 1 and total_num > 0:
                logger.info(
                    f"  🔄 {symbol} fills: {total_num} em {total_pages} páginas"
                )

            if page >= total_pages:
                break
            page += 1

        except Exception as e:
            logger.error(f"❌ Erro ao buscar fills: {e}")
            break

    return all_fills


def fetch_all_orders(symbol: str) -> list[dict[str, Any]]:
    """Busca todos os orders de 2026 em janelas de 7 dias."""
    all_orders: list[dict[str, Any]] = []
    current = START_DATE
    end = datetime.now()

    logger.info(f"📥 Baixando orders {symbol} de {current.date()} a {end.date()}")

    while current < end:
        window_end = min(current + timedelta(days=WINDOW_DAYS), end)
        start_ms = int(current.timestamp() * 1000)
        end_ms = int(window_end.timestamp() * 1000)

        orders = fetch_orders_window(symbol, start_ms, end_ms)
        all_orders.extend(orders)

        current = window_end

    logger.info(f"✅ {symbol}: {len(all_orders)} orders baixados")
    return all_orders


def fetch_all_fills(symbol: str) -> list[dict[str, Any]]:
    """Busca todos os fills de 2026 em janelas de 7 dias."""
    all_fills: list[dict[str, Any]] = []
    current = START_DATE
    end = datetime.now()

    logger.info(f"📥 Baixando fills {symbol} de {current.date()} a {end.date()}")

    while current < end:
        window_end = min(current + timedelta(days=WINDOW_DAYS), end)
        start_ms = int(current.timestamp() * 1000)
        end_ms = int(window_end.timestamp() * 1000)

        fills = fetch_fills_window(symbol, start_ms, end_ms)
        all_fills.extend(fills)

        current = window_end

    logger.info(f"✅ {symbol}: {len(all_fills)} fills baixados")
    return all_fills


# ── Insert into PostgreSQL ────────────────────────────────────
def insert_orders_to_db(conn: Any, symbol: str, orders: list[dict[str, Any]]) -> int:
    """Insere orders como trades no PostgreSQL."""
    cur = conn.cursor()
    inserted = 0

    for order in orders:
        # Só inserir orders que foram executados (dealSize > 0)
        deal_size = float(order.get("dealSize", 0))
        deal_funds = float(order.get("dealFunds", 0))

        if deal_size <= 0:
            continue

        order_id = order.get("id", "")
        side = order.get("side", "").lower()
        avg_price = deal_funds / deal_size if deal_size > 0 else 0
        created_at = int(order.get("createdAt", 0))
        ts = created_at / 1000.0 if created_at > 1e12 else float(created_at)

        # Verificar se já existe
        cur.execute(
            f"SELECT id FROM {SCHEMA}.trades WHERE order_id = %s AND symbol = %s",
            (order_id, symbol),
        )
        if cur.fetchone():
            continue

        # Metadata com info original do order
        metadata = {
            "source": "kucoin_restore",
            "type": order.get("type"),
            "fee": order.get("fee"),
            "feeCurrency": order.get("feeCurrency"),
            "clientOid": order.get("clientOid"),
            "restored_at": datetime.now().isoformat(),
        }

        cur.execute(
            f"""
            INSERT INTO {SCHEMA}.trades
                (timestamp, symbol, side, price, size, funds, order_id,
                 dry_run, metadata, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, to_timestamp(%s))
            """,
            (
                ts, symbol, side, avg_price, deal_size, deal_funds,
                order_id, False, json.dumps(metadata), ts,
            ),
        )
        inserted += 1

    logger.info(f"  💾 {symbol}: {inserted} trades inseridos no DB")
    return inserted


def calculate_pnl(conn: Any, symbol: str) -> int:
    """Calcula PnL para trades BUY/SELL pareados."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Buscar todos os trades ordenados por timestamp
    cur.execute(
        f"""
        SELECT id, side, price, size, funds, pnl
        FROM {SCHEMA}.trades
        WHERE symbol = %s AND dry_run = False
        ORDER BY timestamp ASC
        """,
        (symbol,),
    )
    trades = cur.fetchall()

    # Calcular PnL usando FIFO
    buy_queue: list[dict[str, Any]] = []
    updated = 0

    for trade in trades:
        if trade["side"] == "buy":
            buy_queue.append({
                "id": trade["id"],
                "price": trade["price"],
                "size": trade["size"] or 0,
                "funds": trade["funds"] or 0,
            })
        elif trade["side"] == "sell" and buy_queue:
            # Calcular preço médio de entrada
            total_size = sum(b["size"] for b in buy_queue)
            if total_size > 0:
                avg_entry = sum(b["price"] * b["size"] for b in buy_queue) / total_size
            else:
                avg_entry = buy_queue[-1]["price"]

            sell_price = trade["price"]
            sell_size = trade["size"] or 0
            pnl = (sell_price - avg_entry) * sell_size
            pnl_pct = ((sell_price / avg_entry) - 1) * 100 if avg_entry > 0 else 0

            cur2 = conn.cursor()
            cur2.execute(
                f"UPDATE {SCHEMA}.trades SET pnl = %s, pnl_pct = %s WHERE id = %s",
                (round(pnl, 6), round(pnl_pct, 4), trade["id"]),
            )
            updated += 1
            buy_queue.clear()

    if updated > 0:
        logger.info(f"  📊 {symbol}: PnL calculado para {updated} sells")
    return updated


# ── Fetch & Store Candles ─────────────────────────────────────
def fetch_and_store_candles(
    conn: Any, symbol: str, ktype: str = "15min"
) -> int:
    """Baixa candles de 15min desde Jan/2026 e insere no DB."""
    cur = conn.cursor()
    total_inserted = 0
    current = START_DATE
    end = datetime.now()

    logger.info(f"📥 Baixando candles {ktype} para {symbol}")

    while current < end:
        window_end = min(current + timedelta(days=3), end)  # 3 dias por vez
        start_ts = int(current.timestamp())
        end_ts = int(window_end.timestamp())

        url = (
            f"{KUCOIN_BASE}/api/v1/market/candles"
            f"?type={ktype}&symbol={symbol}"
            f"&startAt={start_ts}&endAt={end_ts}"
        )

        time.sleep(0.25)  # Rate limit
        try:
            r = requests.get(url, timeout=15)
            data = r.json()

            if data.get("code") != "200000":
                logger.warning(f"⚠️ Candles error: {data.get('msg')}")
                current = window_end
                continue

            raw = data.get("data", [])
            batch_inserted = 0

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
                    batch_inserted += 1
                except Exception:
                    pass  # Duplicata, ignorar

            total_inserted += batch_inserted

        except Exception as e:
            logger.error(f"❌ Candles error: {e}")

        current = window_end

    logger.info(f"  💾 {symbol}: {total_inserted} candles inseridos")
    return total_inserted


# ── Main ──────────────────────────────────────────────────────
def main() -> None:
    """Fluxo principal de restauração."""
    logger.info("=" * 60)
    logger.info("🔄 RESTAURAÇÃO DE HISTÓRICO DE TRADING — 2026")
    logger.info("=" * 60)

    _load_kucoin_credentials()

    conn = get_db_conn()
    ensure_schema(conn)

    total_trades = 0
    total_candles = 0

    for symbol in SYMBOLS:
        logger.info(f"\n{'='*40}")
        logger.info(f"📊 Processando {symbol}")
        logger.info(f"{'='*40}")

        # 1. Baixar e inserir orders (trades reais)
        orders = fetch_all_orders(symbol)
        if orders:
            inserted = insert_orders_to_db(conn, symbol, orders)
            total_trades += inserted

            # Calcular PnL
            calculate_pnl(conn, symbol)

        # 2. Baixar e inserir fills como complemento
        fills = fetch_all_fills(symbol)
        if fills:
            logger.info(f"  📋 {symbol}: {len(fills)} fills encontrados (complementar)")

        # 3. Baixar candles de 15min
        candles = fetch_and_store_candles(conn, symbol, ktype="15min")
        total_candles += candles

        # 4. Baixar candles de 1min (últimos 7 dias apenas — muitos dados)
        recent_start = datetime.now() - timedelta(days=7)
        old_start = START_DATE
        try:
            # Temporariamente ajustar START_DATE
            globals()["START_DATE"] = recent_start
            candles_1m = fetch_and_store_candles(conn, symbol, ktype="1min")
            total_candles += candles_1m
        finally:
            globals()["START_DATE"] = old_start

    # Resumo final
    logger.info("\n" + "=" * 60)
    logger.info("✅ RESTAURAÇÃO COMPLETA")
    logger.info(f"  📈 Total trades restaurados: {total_trades}")
    logger.info(f"  🕯️ Total candles inseridos: {total_candles}")
    logger.info("=" * 60)

    # Stats do DB
    cur = conn.cursor()
    for table in ["trades", "candles"]:
        cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.{table}")
        count = cur.fetchone()[0]
        logger.info(f"  📊 {SCHEMA}.{table}: {count} registros")

    # Trades por moeda
    cur.execute(
        f"""
        SELECT symbol, COUNT(*), SUM(CASE WHEN side='buy' THEN 1 ELSE 0 END) as buys,
               SUM(CASE WHEN side='sell' THEN 1 ELSE 0 END) as sells,
               COALESCE(SUM(pnl), 0) as total_pnl
        FROM {SCHEMA}.trades WHERE dry_run = False
        GROUP BY symbol ORDER BY symbol
        """
    )
    rows = cur.fetchall()
    if rows:
        logger.info("\n  Trades por moeda:")
        for row in rows:
            logger.info(
                f"    {row[0]:12s} total={row[1]:4d} buys={row[2]:4d} "
                f"sells={row[3]:4d} pnl=${row[4]:.4f}"
            )

    conn.close()


if __name__ == "__main__":
    main()
