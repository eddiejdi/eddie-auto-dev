#!/usr/bin/env python3
"""Prometheus exporter — KuMining (cloud mining KuCoin): rendimentos e custos.

Fonte de dados: tabela `btc.exchange_account_ledgers` (Postgres), sincronizada
a cada 15min pelo `kucoin_postgres_sync.py`. Filtrando bizTypes de mining:

  - Cloud Mining Earnings        → payout BTC (e outros) da mineração
  - CLOUD_MINING_OTHER           → merge mining (HTR, FB, ELA, ...)
  - Cloud Mining Hash Power Fee  → custo do hashrate (compra do contrato)
  - Cloud Mining Electricity Fee → custo diário de energia

Conversões (USDT→USD≈1): preço de cada moeda via API pública KuCoin;
USDT→BRL via awesomeapi (USD-BRL). Requer DATABASE_URL (env).

Metrics (porta 9130):
  kumining_earnings_usdt_total{currency,day}    — ganhos por moeda/dia (7d)
  kumining_earnings_brl_total{currency,day}     — idem em BRL
  kumining_costs_usdt_total{type,day}           — custos por tipo/dia
  kumining_costs_brl_total{type,day}
  kumining_net_brl{day}                         — (ganhos USD − custos) em BRL
  kumining_btc_price_usd / kumining_brl_rate
  kumining_scrape_success{source}
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import psycopg2
except ImportError:
    psycopg2 = None

try:
    from prometheus_client import Gauge, start_http_server
except ImportError:
    Gauge = None
    start_http_server = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [kumining] %(message)s",
)
log = logging.getLogger("kumining")

MINING_BIZ = {
    "earn": ("Cloud Mining Earnings",),
    "earn_other": ("CLOUD_MINING_OTHER",),
    "cost": ("Cloud Mining Hash Power Fee", "Cloud Mining Electricity Fee"),
}
COST_TYPES = {
    "Cloud Mining Hash Power Fee": "hashpower",
    "Cloud Mining Electricity Fee": "electricity",
}
DAYS = 7
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"


def _get_db_dsn() -> str:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        log.error("DATABASE_URL environment variable is required")
        sys.exit(1)
    return dsn


def _http_json(url: str, timeout: float = 12.0):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def fetch_ledgers(dsn: str, days: int) -> list[dict]:
    """Lê entradas de mining de btc.exchange_account_ledgers (últimos N dias)."""
    if psycopg2 is None:
        log.error("psycopg2 not installed")
        return []
    u = urllib.parse.urlparse(dsn)
    conn = psycopg2.connect(
        host=u.hostname or "127.0.0.1",
        port=u.port or 5433,
        dbname=u.path.lstrip("/"),
        user=u.username,
        password=u.password,
    )
    try:
        cur = conn.cursor()
        since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
        cur.execute(
            """
            SELECT ledger_id, currency, amount, direction, biz_type, created_at_ms
            FROM btc.exchange_account_ledgers
            WHERE created_at_ms >= %s
              AND biz_type IN ('Cloud Mining Earnings', 'CLOUD_MINING_OTHER',
                               'Cloud Mining Hash Power Fee', 'Cloud Mining Electricity Fee')
            ORDER BY created_at_ms
            """,
            (since,),
        )
        rows = [
            {
                "ledger_id": r[0],
                "currency": r[1],
                "amount": float(r[2] or 0),
                "direction": r[3],
                "biz_type": r[4],
                "created_at_ms": r[5],
            }
            for r in cur.fetchall()
        ]
        log.info("ledgers de mining: %d (desde %s)", len(rows), since)
        return rows
    finally:
        conn.close()


def fetch_price_usdt(currency: str) -> float | None:
    """Preço da moeda em USDT via API pública KuCoin."""
    if currency == "USDT":
        return 1.0
    try:
        url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={currency}-USDT"
        data = _http_json(url, timeout=8).get("data")
        return float(data["price"]) if data else None
    except Exception as exc:
        log.warning("preço %s-USDT falhou: %s", currency, exc)
        return None


def fetch_brl_rate() -> float | None:
    """USDT→BRL via awesomeapi (USD-BRL)."""
    try:
        data = _http_json("https://economia.awesomeapi.com.br/json/last/USD-BRL", timeout=8)
        return float(data["USDBRL"]["bid"])
    except Exception as exc:
        log.warning("USD-BRL falhou: %s", exc)
        return None


def aggregate(rows: list[dict]) -> dict:
    """Agrega por dia UTC: (currency, biz_type, day) → valor com sinal."""
    totals: dict[tuple, float] = defaultdict(float)
    for r in rows:
        sign = 1.0 if r["direction"] == "in" else -1.0
        day = datetime.fromtimestamp(r["created_at_ms"] / 1000, tz=timezone.utc).date().isoformat()
        totals[(r["currency"], r["biz_type"], day)] += sign * abs(r["amount"])
    return dict(totals)


def main() -> None:
    parser = argparse.ArgumentParser(description="KuMining Prometheus exporter")
    parser.add_argument("--port", type=int, default=9130)
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.environ.get("KUMINING_INTERVAL", "300")),
    )
    args = parser.parse_args()

    dsn = _get_db_dsn()
    if Gauge is None:
        log.error("prometheus_client not installed")
        sys.exit(1)

    g_earn_usdt = Gauge("kumining_earnings_usdt_total", "Ganhos de mining em USDT por dia", ["currency", "day"])
    g_earn_brl = Gauge("kumining_earnings_brl_total", "Ganhos de mining em BRL por dia", ["currency", "day"])
    g_cost_usdt = Gauge("kumining_costs_usdt_total", "Custos de mining em USDT por dia", ["type", "day"])
    g_cost_brl = Gauge("kumining_costs_brl_total", "Custos de mining em BRL por dia", ["type", "day"])
    g_net_brl = Gauge("kumining_net_brl", "Líquido diário (ganhos USD − custos) em BRL", ["day"])
    g_btc_price = Gauge("kumining_btc_price_usd", "Preço BTC em USD")
    g_brl_rate = Gauge("kumining_brl_rate", "Taxa USDT→BRL usada")
    g_ok = Gauge("kumining_scrape_success", "Último scrape OK", ["source"])

    start_http_server(args.port)
    log.info("Prometheus metrics on :%d (interval=%ds)", args.port, args.interval)

    while True:
        try:
            rows = fetch_ledgers(dsn, DAYS)
            totals = aggregate(rows)

            prices: dict[str, float | None] = {}
            brl = fetch_brl_rate()
            g_ok.labels(source="kucoin").set(1)
            g_ok.labels(source="awesomeapi").set(1 if brl else 0)
            if brl:
                g_brl_rate.set(brl)

            day_totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
            for (currency, biz_type, day), value in totals.items():
                price = prices.get(currency)
                if price is None:
                    price = fetch_price_usdt(currency)
                    prices[currency] = price
                usd = abs(value) * (price or 0.0)

                if biz_type in MINING_BIZ["earn"] + MINING_BIZ["earn_other"]:
                    g_earn_usdt.labels(currency=currency, day=day).set(usd)
                    if brl:
                        g_earn_brl.labels(currency=currency, day=day).set(usd * brl)
                    day_totals[day]["earn_usd"] += usd
                elif biz_type in MINING_BIZ["cost"]:
                    cost_type = COST_TYPES.get(biz_type, biz_type)
                    g_cost_usdt.labels(type=cost_type, day=day).set(usd)
                    if brl:
                        g_cost_brl.labels(type=cost_type, day=day).set(usd * brl)
                    day_totals[day]["cost_usd"] += usd

            for day, d in day_totals.items():
                net = d["earn_usd"] - d["cost_usd"]
                if brl:
                    g_net_brl.labels(day=day).set(net * brl)

            btc_price = prices.get("BTC") or fetch_price_usdt("BTC")
            if btc_price:
                g_btc_price.set(btc_price)

            summary = {
                day: {"earn_usd": round(d["earn_usd"], 6), "cost_usd": round(d["cost_usd"], 6)}
                for day, d in sorted(day_totals.items())
            }
            log.info("resumo %s brl=%.4f btc=%.2f", json.dumps(summary), brl or 0.0, btc_price or 0.0)
        except Exception as exc:
            log.error("scrape falhou: %s", exc)
            g_ok.labels(source="kucoin").set(0)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
