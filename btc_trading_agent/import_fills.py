#!/usr/bin/env python3
"""Importa fills (execuções) da KuCoin e persiste em btc.trades

Uso:
    python3 import_fills.py            # baixa todos os fills (conta inteira)
    python3 import_fills.py --symbol BTC-USDT
"""
import os
import time
import json
import logging
from urllib.parse import urlencode
from pathlib import Path

import requests

from kucoin_api import KUCOIN_BASE, _build_headers, rate_limit, validate_credentials
from training_db import TrainingDatabase

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s',
                    handlers=[logging.FileHandler(LOG_DIR / "import_fills.log"), logging.StreamHandler()])
logger = logging.getLogger(__name__)


def fetch_all_fills(symbol: str = None, page_size: int = 100):
    """Paginação completa das fills da conta; retorna lista de items."""
    validate_credentials()
    page = 1
    all_items = []
    while True:
        params = {"pageSize": page_size, "currentPage": page}
        if symbol:
            params["symbol"] = symbol

        qs = urlencode(params)
        endpoint = f"/api/v1/fills?{qs}"
        headers = _build_headers("GET", endpoint)
        rate_limit()
        try:
            r = requests.get(KUCOIN_BASE + endpoint, headers=headers, timeout=15)
            if r.status_code != 200:
                logger.warning(f"KuCoin fills request failed: {r.status_code} {r.text[:200]}")
                break

            payload = r.json()
            if payload.get("code") != "200000":
                logger.warning(f"KuCoin fills returned non-200000 code: {payload}")
                break

            page_items = payload.get("data", {}).get("items", [])
            if not page_items:
                break

            all_items.extend(page_items)
            logger.info(f"Fetched page {page} ({len(page_items)} fills)")

            # Se menos que page_size, fim
            if len(page_items) < page_size:
                break

            page += 1
            time.sleep(0.2)
        except Exception as e:
            logger.exception("Error fetching fills: %s", e)
            break

    return all_items


def to_timestamp(ts_value):
    """Converte campo de timestamp (segundos ou ms) para float segundos."""
    if ts_value is None:
        return time.time()
    try:
        t = int(ts_value)
    except Exception:
        try:
            return float(ts_value)
        except Exception:
            return time.time()

    # heurística: se > 1e12 -> ms
    if t > 1_000_000_000_000:
        return t / 1000.0
    if t > 1_000_000_000:
        # already seconds
        return float(t)
    return float(t)


def persist_fills(fills, db: TrainingDatabase):
    """Insere fills únicos na tabela trades usando orderId para evitar duplicatas."""
    inserted = 0
    try:
        for f in fills:
            order_id = f.get("orderId") or f.get("order_id") or f.get("orderOid")
            symbol = f.get("symbol") or f.get("symbolName") or f.get("currency")
            side = f.get("side") or f.get("direction") or "unknown"
            price = f.get("price") or f.get("dealPrice") or f.get("matchPrice")
            size = f.get("size") or f.get("dealSize") or f.get("filledSize")
            funds = f.get("funds") or f.get("dealFunds")
            status = f.get("status")
            created_at = f.get("createdAt") or f.get("created_at") or f.get("time")

            ts = to_timestamp(created_at)

            # evitar duplicatas por order_id
            exists = False
            if order_id:
                # verificar existência diretamente no DB
                with db._get_conn() as conn:
                    cur = conn.cursor()
                    cur.execute(f"SELECT id FROM {db.dsn.split('/')[-1]}.trades WHERE order_id = %s", (order_id,))
                    if cur.fetchone():
                        exists = True

            if exists:
                logger.debug(f"Skipping existing order {order_id}")
                continue

            metadata = {"raw": f}
            try:
                db.record_trade(symbol=symbol or "UNKNOWN", side=side.upper(), price=float(price) if price else 0.0,
                                size=float(size) if size else None, funds=float(funds) if funds else None,
                                order_id=order_id, dry_run=False, metadata=metadata)
                inserted += 1
            except Exception:
                logger.exception("Failed to persist fill: %s", f)

    finally:
        logger.info(f"Inserted {inserted} fills (attempted {len(fills)})")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", help="Symbol to fetch fills for (default: all)")
    parser.add_argument("--limit", type=int, default=100, help="page size per request")
    args = parser.parse_args()

    db = TrainingDatabase()

    try:
        fills = fetch_all_fills(symbol=args.symbol, page_size=args.limit)
        logger.info(f"Total fills fetched: {len(fills)}")
        if fills:
            persist_fills(fills, db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
