#!/usr/bin/env python3
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

try:
    import psycopg2
    import psycopg2.extras
except ModuleNotFoundError:  # pragma: no cover - test environment fallback
    psycopg2 = None  # type: ignore[assignment]
    REAL_DICT_CURSOR = None
else:
    REAL_DICT_CURSOR = psycopg2.extras.RealDictCursor
import requests


RUNTIME_DIR = Path(os.environ.get("BTC_AGENT_DIR", "/apps/crypto-trader/trading/btc_trading_agent"))
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))
REPO_AGENT_DIR = Path(__file__).resolve().parents[1] / "btc_trading_agent"
if REPO_AGENT_DIR.exists() and str(REPO_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_AGENT_DIR))

import kucoin_api  # type: ignore
from kucoin_api import get_balances, get_fills, get_price_fast  # type: ignore
from position_reconstruction import reconstruct_open_buys, summarize_open_buys  # type: ignore
from secrets_helper import get_database_url  # type: ignore


LOG = logging.getLogger("kucoin_postgres_sync")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

SCHEMA = "btc"
SYNC_PROFILE = "exchange_sync"
LEDGER_WINDOW_MS = 24 * 60 * 60 * 1000
LEDGER_BACKFILL_DAYS = int(os.environ.get("KUCOIN_LEDGER_BACKFILL_DAYS", "180"))
LEDGER_BACKFILL_MS = LEDGER_BACKFILL_DAYS * LEDGER_WINDOW_MS
LEDGER_CURSOR_OVERLAP_MS = 5 * 60 * 1000
LEDGER_REQUEST_SPACING_SEC = 0.35
ACCOUNT_LEDGER_SYNC_KEY = "account_ledgers_v2"
TRADING_FEE_PCT = 0.001
SELL_SIDES = frozenset({"sell", "sell_reconciled"})
BACKFILL_PNL_LIMIT = int(os.environ.get("KUCOIN_PNL_BACKFILL_LIMIT", "500"))


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    url = get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL unavailable")
    return url


def _connect():
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for database access")
    return psycopg2.connect(_db_url())


def _ensure_tables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.exchange_balance_snapshots (
                id BIGSERIAL PRIMARY KEY,
                synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                account_type TEXT NOT NULL,
                currency TEXT NOT NULL,
                balance DOUBLE PRECISION NOT NULL,
                available DOUBLE PRECISION NOT NULL,
                holds DOUBLE PRECISION NOT NULL,
                price_usdt DOUBLE PRECISION,
                metadata JSONB
            )
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_exchange_balance_snapshots_lookup
            ON {SCHEMA}.exchange_balance_snapshots (account_type, currency, synced_at DESC)
        """)
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.exchange_sync_state (
                sync_key TEXT PRIMARY KEY,
                synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                cursor_value TEXT,
                metadata JSONB,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.exchange_account_ledgers (
                ledger_id TEXT PRIMARY KEY,
                synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                currency TEXT NOT NULL,
                amount DOUBLE PRECISION NOT NULL,
                fee DOUBLE PRECISION NOT NULL DEFAULT 0,
                balance DOUBLE PRECISION,
                account_type TEXT,
                biz_type TEXT,
                direction TEXT,
                created_at_ms BIGINT,
                context JSONB,
                metadata JSONB
            )
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_exchange_account_ledgers_lookup
            ON {SCHEMA}.exchange_account_ledgers (currency, account_type, created_at_ms DESC)
        """)
    conn.commit()


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _get_sync_cursor_ms(conn, sync_key: str) -> Optional[int]:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT cursor_value FROM {SCHEMA}.exchange_sync_state WHERE sync_key = %s",
            (sync_key,),
        )
        row = cur.fetchone()
    if not row or not row[0]:
        return None
    try:
        return int(row[0])
    except Exception:
        return None


def _iter_time_windows(start_ms: int, end_ms: int, window_ms: int = LEDGER_WINDOW_MS) -> Iterable[tuple[int, int]]:
    cursor = max(start_ms, 0)
    while cursor <= end_ms:
        window_end = min(cursor + window_ms - 1, end_ms)
        yield cursor, window_end
        cursor = window_end + 1


def _snapshot_balances(conn) -> int:
    counts = 0
    usdt_brl = get_price_fast("USDT-BRL", timeout=5) or 0.0
    btc_usdt = get_price_fast("BTC-USDT", timeout=5) or 0.0

    _price_cache: Dict[str, Optional[float]] = {}

    def price_in_usdt(currency: str) -> Optional[float]:
        if currency == "USDT":
            return 1.0
        if currency == "BTC":
            return btc_usdt or None
        if currency == "BRL" and usdt_brl > 0:
            return 1.0 / usdt_brl
        # Demais moedas (ETH, KCS, ...): cotar <CUR>-USDT sob demanda, com
        # cache por execução — sem isso os saldos ficam avaliados em 0.
        if currency not in _price_cache:
            try:
                _price_cache[currency] = get_price_fast(f"{currency}-USDT", timeout=5) or None
            except Exception:
                _price_cache[currency] = None
        return _price_cache[currency]

    with conn.cursor() as cur:
        for account_type in ("trade", "main"):
            balances = get_balances(account_type=account_type)
            for balance in balances:
                if balance.get("balance", 0) <= 0 and balance.get("available", 0) <= 0:
                    continue
                cur.execute(
                    f"""
                    INSERT INTO {SCHEMA}.exchange_balance_snapshots
                        (account_type, currency, balance, available, holds, price_usdt, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        account_type,
                        balance["currency"],
                        _safe_float(balance["balance"]),
                        _safe_float(balance["available"]),
                        _safe_float(balance["holds"]),
                        price_in_usdt(balance["currency"]),
                        json.dumps({"source": "kucoin_sync"}),
                    ),
                )
                counts += 1

        # Subcontas KuCoin (account_type = "sub:<nome>"); best-effort — a
        # chave master pode não ter permissão ou não existirem subcontas.
        try:
            sub_balances = kucoin_api.get_sub_account_balances()
        except Exception as exc:
            logging.getLogger(__name__).warning("Sub-account snapshot skipped: %s", exc)
            sub_balances = []
        for balance in sub_balances:
            if balance.get("balance", 0) <= 0 and balance.get("available", 0) <= 0:
                continue
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.exchange_balance_snapshots
                    (account_type, currency, balance, available, holds, price_usdt, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    f"sub:{balance['sub_name']}",
                    balance["currency"],
                    _safe_float(balance["balance"]),
                    _safe_float(balance["available"]),
                    _safe_float(balance["holds"]),
                    price_in_usdt(balance["currency"]),
                    json.dumps({"source": "kucoin_sync", "sub_account_type": balance["account_type"]}),
                ),
            )
            counts += 1
        cur.execute(
            f"""
            INSERT INTO {SCHEMA}.exchange_sync_state (sync_key, synced_at, metadata, updated_at)
            VALUES (%s, NOW(), %s, NOW())
            ON CONFLICT (sync_key) DO UPDATE SET
                synced_at = EXCLUDED.synced_at,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            """,
            ("balances", json.dumps({"rows_inserted": counts})),
        )
    conn.commit()
    return counts


def _aggregate_fills(fills: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for fill in fills:
        order_id = str(fill.get("orderId") or fill.get("order_id") or "").strip()
        trade_id = str(fill.get("tradeId") or fill.get("trade_id") or "").strip()
        if not order_id:
            continue
        key = order_id
        price = _safe_float(fill.get("price"))
        size = _safe_float(fill.get("size"))
        funds = _safe_float(fill.get("funds"))
        created_at = fill.get("createdAt") or fill.get("created_at") or fill.get("timestamp")
        row = grouped.setdefault(
            key,
            {
                "order_id": order_id,
                "trade_ids": [],
                "symbol": fill.get("symbol") or "BTC-USDT",
                "side": (fill.get("side") or "").lower(),
                "size": 0.0,
                "funds": 0.0,
                "weighted_notional": 0.0,
                "created_at": created_at,
                "raw_fills": [],
            },
        )
        if trade_id:
            row["trade_ids"].append(trade_id)
        row["size"] += size
        row["funds"] += funds
        row["weighted_notional"] += price * size
        row["raw_fills"].append(fill)
        row["created_at"] = created_at or row["created_at"]

    for row in grouped.values():
        size = row["size"]
        row["price"] = (row["weighted_notional"] / size) if size > 0 else 0.0
        row["trade_ids"] = sorted(set(row["trade_ids"]))
    return grouped


def _row_event_timestamp(row: Dict[str, Any]) -> float:
    created_at = row.get("created_at")
    try:
        if created_at is None:
            return time.time()
        return float(created_at) / 1000.0
    except Exception:
        return time.time()


def _parse_metadata(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _fill_notional_usdt(fill: Dict[str, Any]) -> float:
    funds = _safe_float(fill.get("funds"))
    if funds > 0:
        return funds
    return _safe_float(fill.get("price")) * _safe_float(fill.get("size"))


def _fee_usdt_from_fill(fill: Dict[str, Any], notional_usdt: float) -> float:
    fee = _safe_float(fill.get("fee"))
    currency = str(fill.get("feeCurrency") or "USDT").upper()
    if fee <= 0:
        rate = _safe_float(fill.get("feeRate")) or TRADING_FEE_PCT
        return notional_usdt * rate
    if currency == "USDT":
        return fee
    rate = _safe_float(fill.get("feeRate")) or TRADING_FEE_PCT
    return notional_usdt * rate


def _sum_sell_fees_usdt(raw_fills: Iterable[Dict[str, Any]]) -> float:
    total = 0.0
    for fill in raw_fills:
        total += _fee_usdt_from_fill(fill, _fill_notional_usdt(fill))
    return total


def _buy_fee_usdt(price: float, size: float, metadata: Dict[str, Any]) -> float:
    fills = metadata.get("fills")
    if isinstance(fills, list) and fills:
        return sum(
            _fee_usdt_from_fill(fill, _fill_notional_usdt(fill))
            for fill in fills
            if isinstance(fill, dict)
        )
    return price * size * TRADING_FEE_PCT


def _consume_buy_queue(queue: list[Dict[str, Any]], amount: float) -> None:
    remaining = amount
    while remaining > 1e-12 and queue:
        head = queue[0]
        take = min(remaining, head["size"])
        head["size"] -= take
        remaining -= take
        if head["size"] <= 1e-12:
            queue.pop(0)


def _fifo_cost_for_sell(
    trades_before: Iterable[Dict[str, Any]],
    sell_size: float,
) -> Optional[tuple[float, float, float]]:
    """Retorna (avg_entry, buy_fees_usdt, matched_size) via FIFO."""
    if sell_size <= 0:
        return None

    queue: list[Dict[str, Any]] = []
    for trade in trades_before:
        side = str(trade.get("side") or "").lower()
        metadata = _parse_metadata(trade.get("metadata"))
        if side == "buy":
            if str(metadata.get("source") or "") == "external_deposit":
                continue
            queue.append(
                {
                    "price": _safe_float(trade.get("price")),
                    "size": _safe_float(trade.get("size")),
                    "metadata": metadata,
                }
            )
        elif side in SELL_SIDES:
            _consume_buy_queue(queue, _safe_float(trade.get("size")))

    need = sell_size
    cost = 0.0
    buy_fees = 0.0
    matched = 0.0
    while need > 1e-12 and queue:
        head = queue[0]
        take = min(need, head["size"])
        cost += take * head["price"]
        buy_fees += _buy_fee_usdt(head["price"], take, head["metadata"])
        matched += take
        head["size"] -= take
        need -= take
        if head["size"] <= 1e-12:
            queue.pop(0)

    if matched <= 1e-12:
        return None
    return cost / matched, buy_fees, matched


def _compute_net_sell_pnl(
    sell_price: float,
    sell_size: float,
    avg_entry: float,
    sell_fee_usdt: float,
    buy_fee_usdt: float,
) -> tuple[float, float]:
    gross_pnl = (sell_price - avg_entry) * sell_size
    net_pnl = gross_pnl - sell_fee_usdt - buy_fee_usdt
    net_sell_price = sell_price - (sell_fee_usdt / sell_size if sell_size > 0 else 0.0)
    net_buy_price = avg_entry * (1 + TRADING_FEE_PCT)
    pnl_pct = ((net_sell_price / net_buy_price) - 1) * 100 if net_buy_price > 0 else 0.0
    return round(net_pnl, 6), round(pnl_pct, 4)


def _load_trades_before_sell(
    cur,
    *,
    symbol: str,
    profile: str,
    sell_ts: float,
    sell_id: int,
) -> list[Dict[str, Any]]:
    cur.execute(
        f"""
        SELECT id, side, price, size, timestamp, metadata
        FROM {SCHEMA}.trades
        WHERE symbol = %s
          AND profile = %s
          AND dry_run = FALSE
          AND side IN ('buy', 'sell', 'sell_reconciled')
          AND (timestamp < %s OR (timestamp = %s AND id < %s))
        ORDER BY timestamp ASC, id ASC
        """,
        (symbol, profile, sell_ts, sell_ts, sell_id),
    )
    return [dict(row) for row in cur.fetchall()]


def _refresh_sell_pnl(cur, trade_id: int, *, force: bool = False) -> bool:
    """Calcula e persiste PnL líquido (FIFO + fees) para um SELL sem pnl."""
    cur.execute(
        f"""
        SELECT id, symbol, profile, side, price, size, timestamp, pnl, metadata
        FROM {SCHEMA}.trades
        WHERE id = %s
        """,
        (trade_id,),
    )
    trade = cur.fetchone()
    if not trade:
        return False

    side = str(trade.get("side") or "").lower()
    if side not in SELL_SIDES:
        return False
    if trade.get("pnl") is not None and not force:
        return False

    symbol = str(trade.get("symbol") or "BTC-USDT")
    profile = str(trade.get("profile") or SYNC_PROFILE)
    sell_price = _safe_float(trade.get("price"))
    sell_size = _safe_float(trade.get("size"))
    if sell_price <= 0 or sell_size <= 0:
        return False

    metadata = _parse_metadata(trade.get("metadata"))
    raw_fills = metadata.get("fills")
    if not isinstance(raw_fills, list):
        raw_fills = []
    sell_fee_usdt = _sum_sell_fees_usdt(
        fill for fill in raw_fills if isinstance(fill, dict)
    )
    if sell_fee_usdt <= 0:
        sell_fee_usdt = sell_price * sell_size * TRADING_FEE_PCT

    trades_before = _load_trades_before_sell(
        cur,
        symbol=symbol,
        profile=profile,
        sell_ts=_safe_float(trade.get("timestamp")),
        sell_id=int(trade["id"]),
    )
    fifo = _fifo_cost_for_sell(trades_before, sell_size)
    if fifo is None:
        return False

    avg_entry, buy_fee_usdt, matched_size = fifo
    if matched_size + 1e-9 < sell_size:
        LOG.debug(
            "PnL parcial trade_id=%s profile=%s matched=%.8f sell=%.8f",
            trade_id,
            profile,
            matched_size,
            sell_size,
        )

    pnl, pnl_pct = _compute_net_sell_pnl(
        sell_price,
        sell_size,
        avg_entry,
        sell_fee_usdt,
        buy_fee_usdt,
    )
    merged_metadata = {
        **metadata,
        "pnl_source": "kucoin_sync_fifo_net",
        "pnl_avg_entry": round(avg_entry, 8),
        "pnl_sell_fee_usdt": round(sell_fee_usdt, 8),
        "pnl_buy_fee_usdt": round(buy_fee_usdt, 8),
        "pnl_matched_size": round(matched_size, 8),
    }
    cur.execute(
        f"""
        UPDATE {SCHEMA}.trades
        SET pnl = %s,
            pnl_pct = %s,
            metadata = %s
        WHERE id = %s
        """,
        (pnl, pnl_pct, json.dumps(merged_metadata), trade_id),
    )
    LOG.info(
        "PnL líquido trade_id=%s profile=%s symbol=%s pnl=%.6f (%.4f%%)",
        trade_id,
        profile,
        symbol,
        pnl,
        pnl_pct,
    )
    return True


def _backfill_missing_sell_pnl(cur, *, limit: int = BACKFILL_PNL_LIMIT) -> int:
    """Preenche pnl ausente em SELLs históricos usando FIFO + fees dos fills."""
    cur.execute(
        f"""
        SELECT id
        FROM {SCHEMA}.trades
        WHERE side IN ('sell', 'sell_reconciled')
          AND dry_run = FALSE
          AND pnl IS NULL
        ORDER BY timestamp DESC
        LIMIT %s
        """,
        (max(1, int(limit)),),
    )
    trade_ids = [int(row["id"]) for row in cur.fetchall()]
    updated = 0
    for trade_id in trade_ids:
        if _refresh_sell_pnl(cur, trade_id):
            updated += 1
    if updated:
        LOG.info("Backfill PnL líquido: %s SELLs atualizados", updated)
    return updated


def _trades_has_profile(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = 'trades' AND column_name = 'profile'
            """,
            (SCHEMA,),
        )
        return cur.fetchone() is not None


def _match_orphan_to_fill(
    cur,
    order_id: str,
    row: Dict[str, Any],
    event_ts: float,
) -> Optional[int]:
    """Tenta vincular um fill KuCoin a um trade órfão do agent (sem order_id).

    Procura trades com source='external_deposit' ou sem order_id que tenham
    timestamp próximo (±120s), mesmo side e size similar (±20%).
    Retorna o id do trade vinculado ou None.
    """
    side = row["side"]
    size = row["size"]
    if size <= 0:
        return None

    cur.execute(
        f"""
        SELECT id, size, timestamp, metadata
        FROM {SCHEMA}.trades
        WHERE symbol = %s
          AND side = %s
          AND (order_id IS NULL OR order_id = '')
          AND ABS(timestamp - %s) < 120
          AND size > 0
          AND ABS(size - %s) / GREATEST(size, %s) < 0.20
        ORDER BY ABS(timestamp - %s) ASC
        LIMIT 1
        """,
        (row["symbol"], side, event_ts, size, size, event_ts),
    )
    orphan = cur.fetchone()
    if not orphan:
        return None

    orphan_id = orphan["id"]
    existing_metadata = orphan.get("metadata") or {}
    if not isinstance(existing_metadata, dict):
        try:
            existing_metadata = json.loads(existing_metadata)
        except Exception:
            existing_metadata = {}

    merged_metadata = {
        **existing_metadata,
        "source": "kucoin_sync",
        "original_source": existing_metadata.get("source", "unknown"),
        "matched_by": "orphan_fill_reconciliation",
        "trade_ids": row["trade_ids"],
        "fills": row["raw_fills"],
    }
    cur.execute(
        f"""
        UPDATE {SCHEMA}.trades
        SET order_id = %s,
            timestamp = %s,
            price = %s,
            size = %s,
            funds = %s,
            dry_run = FALSE,
            metadata = %s
        WHERE id = %s
        """,
        (
            order_id,
            event_ts,
            row["price"],
            row["size"],
            row["funds"],
            json.dumps(merged_metadata),
            orphan_id,
        ),
    )
    LOG.info(
        "Matched orphan trade #%s to fill order_id=%s (was source=%s, delta_ts=%.1fs, delta_size=%.6f)",
        orphan_id,
        order_id,
        existing_metadata.get("source", "?"),
        abs(float(orphan["timestamp"]) - event_ts),
        abs(float(orphan["size"]) - size),
    )
    return orphan_id


def _cleanup_duplicate_orphans(conn) -> int:
    """Reconcilia orphan trades duplicados retroativamente.

    Procura trades sem order_id que possuem um trade correspondente COM order_id
    (mesmo side, timestamp±120s, size±20%). Marca o orphan como reconciliado
    trocando o side para 'buy_reconciled'/'sell_reconciled' e adicionando
    metadata de auditoria. Executa apenas uma vez (verifica flag no sync_state).
    """
    with conn.cursor(cursor_factory=REAL_DICT_CURSOR) as cur:
        # Verificar se cleanup já executou
        cur.execute(
            f"SELECT metadata FROM {SCHEMA}.exchange_sync_state WHERE sync_key = %s",
            ("orphan_cleanup_done",),
        )
        row = cur.fetchone()
        if row:
            LOG.info("Orphan cleanup already executed, skipping.")
            return 0

        # Encontrar orphans duplicados
        cur.execute(f"""
            SELECT o.id AS orphan_id, o.side AS orphan_side, o.size AS orphan_size,
                   o.timestamp AS orphan_ts, o.metadata AS orphan_metadata, o.profile AS orphan_profile,
                   f.id AS fill_id, f.order_id AS fill_order_id,
                   ABS(f.timestamp - o.timestamp) AS delta_ts,
                   ABS(f.size - o.size) AS delta_size
            FROM {SCHEMA}.trades o
            INNER JOIN LATERAL (
                SELECT id, order_id, timestamp, size
                FROM {SCHEMA}.trades
                WHERE order_id IS NOT NULL AND order_id != ''
                  AND symbol = 'BTC-USDT'
                  AND side = o.side
                  AND ABS(timestamp - o.timestamp) < 120
                  AND size > 0
                  AND ABS(size - o.size) / GREATEST(o.size, 0.000001) < 0.20
                ORDER BY ABS(timestamp - o.timestamp) ASC
                LIMIT 1
            ) f ON TRUE
            WHERE o.symbol = 'BTC-USDT'
              AND (o.order_id IS NULL OR o.order_id = '')
              AND o.side IN ('buy', 'sell')
        """)
        duplicates = cur.fetchall()

        if not duplicates:
            LOG.info("No duplicate orphan trades found for cleanup.")
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.exchange_sync_state (sync_key, synced_at, metadata, updated_at)
                VALUES (%s, NOW(), %s, NOW())
                ON CONFLICT (sync_key) DO UPDATE SET synced_at = EXCLUDED.synced_at,
                    metadata = EXCLUDED.metadata, updated_at = NOW()
                """,
                ("orphan_cleanup_done", json.dumps({"cleaned": 0, "timestamp": time.time()})),
            )
            conn.commit()
            return 0

        cleaned = 0
        for dup in duplicates:
            orphan_meta = dup["orphan_metadata"] or {}
            if not isinstance(orphan_meta, dict):
                try:
                    orphan_meta = json.loads(orphan_meta)
                except Exception:
                    orphan_meta = {}

            reconciled_meta = {
                **orphan_meta,
                "reconciled": True,
                "reconciled_reason": "duplicate_of_filled_trade",
                "duplicate_of_trade_id": dup["fill_id"],
                "duplicate_of_order_id": dup["fill_order_id"],
                "original_side": dup["orphan_side"],
                "delta_ts": float(dup["delta_ts"]),
                "delta_size": float(dup["delta_size"]),
            }

            new_side = f"{dup['orphan_side']}_reconciled"
            cur.execute(
                f"""
                UPDATE {SCHEMA}.trades
                SET side = %s, metadata = %s
                WHERE id = %s
                """,
                (new_side, json.dumps(reconciled_meta), dup["orphan_id"]),
            )
            cleaned += 1

        LOG.info(
            "Cleanup: marked %d duplicate orphan trades as reconciled (side → *_reconciled)",
            cleaned,
        )

        cur.execute(
            f"""
            INSERT INTO {SCHEMA}.exchange_sync_state (sync_key, synced_at, metadata, updated_at)
            VALUES (%s, NOW(), %s, NOW())
            ON CONFLICT (sync_key) DO UPDATE SET synced_at = EXCLUDED.synced_at,
                metadata = EXCLUDED.metadata, updated_at = NOW()
            """,
            ("orphan_cleanup_done", json.dumps({"cleaned": cleaned, "timestamp": time.time()})),
        )
    conn.commit()
    return cleaned


def _reconcile_position_integrity(conn) -> Dict[str, Any]:
    """Verifica integridade de posição: detecta trades fantasmas e registra estado.

    Calcula posição teórica (SUM BUY - SUM SELL) por profile e compara com
    o saldo real na exchange. Registra resultado no exchange_sync_state.
    """
    result: Dict[str, Any] = {"profiles": {}, "orphan_count": 0, "reconciled": 0}

    with conn.cursor(cursor_factory=REAL_DICT_CURSOR) as cur:
        cur.execute(f"""
            SELECT profile
            FROM {SCHEMA}.trades
            WHERE symbol = 'BTC-USDT'
              AND dry_run = FALSE
              AND profile NOT IN ('default', 'exchange_sync')
            GROUP BY profile
            HAVING ABS(
                COALESCE(SUM(
                    CASE
                        WHEN side='buy'
                             AND COALESCE(metadata->>'source','') != 'external_deposit'
                        THEN size
                        WHEN side IN ('sell', 'sell_reconciled')
                        THEN -size
                        ELSE 0
                    END
                ), 0)
            ) > %s
        """, (_PROFILE_MIN_OPEN_POSITION,))
        active_non_system_profiles = {str(row["profile"]) for row in cur.fetchall()}

        # Posição live reconstruída por profile. Dry-run entries are useful for
        # backtests and shadow analysis, but they must not affect exchange
        # reconciliation; raw buy-sell history also overstates positions after
        # slot-level reconciliations.
        cur.execute(f"""
            SELECT
                profile,
                COUNT(*) FILTER (WHERE side='buy') AS buys,
                COUNT(*) FILTER (WHERE side='sell') AS sells,
                COUNT(*) FILTER (WHERE (order_id IS NULL OR order_id = '') AND side IN ('buy', 'sell')) AS orphan_trades
            FROM {SCHEMA}.trades
            WHERE symbol = 'BTC-USDT'
              AND dry_run = FALSE
            GROUP BY profile
        """)
        for row in cur.fetchall():
            profile = row["profile"]
            profile_name = str(profile or "default")
            cur.execute(
                f"""
                SELECT id, side, size, price, timestamp, metadata, dry_run
                FROM {SCHEMA}.trades
                WHERE symbol = 'BTC-USDT'
                  AND dry_run = FALSE
                  AND profile = %s
                ORDER BY timestamp DESC
                LIMIT 500
                """,
                (profile,),
            )
            shared_profile_ambiguous = profile_name not in {"default", "exchange_sync"} and (
                len(active_non_system_profiles) > 1
            )
            open_buys = reconstruct_open_buys(
                [dict(trade) for trade in cur.fetchall()],
                shared_profile_ambiguous=shared_profile_ambiguous,
                exclude_external_deposits=True,
            )
            net, avg_entry = summarize_open_buys(open_buys)
            orphans = int(row["orphan_trades"] or 0)
            result["profiles"][profile] = {
                "net_position": net,
                "avg_entry_price": avg_entry,
                "open_entries": len(open_buys),
                "buys": row["buys"],
                "sells": row["sells"],
                "orphan_trades": orphans,
            }
            result["orphan_count"] += orphans
            if orphans > 0:
                LOG.warning(
                    "Profile %s has %d orphan trades (no order_id), net_position=%.10f",
                    profile, orphans, net,
                )

        # Buscar saldo real exchange para comparar
        try:
            exchange_balances: Dict[str, float] = {}
            base_balance = 0.0
            for acc in get_balances(account_type="trade"):
                if acc.get("currency") == "BTC":
                    balance = _safe_float(acc.get("balance"))
                    exchange_balances["trade"] = balance
                    base_balance += balance
                    break
            try:
                sub_balances = kucoin_api.get_sub_account_balances()
            except Exception as exc:
                LOG.warning("Could not fetch sub-account BTC balances for integrity check: %s", exc)
                sub_balances = []
            if not isinstance(sub_balances, list):
                sub_balances = []
            for acc in sub_balances:
                if acc.get("currency") != "BTC":
                    continue
                sub_name = acc.get("sub_name") or "unknown"
                balance = _safe_float(acc.get("balance"))
                key = f"sub:{sub_name}"
                exchange_balances[key] = exchange_balances.get(key, 0.0) + balance
                base_balance += balance

            total_db_position = sum(
                p["net_position"] for p in result["profiles"].values()
            )
            diff = abs(total_db_position - base_balance)
            result["exchange_btc_balance"] = base_balance
            result["exchange_btc_balances"] = exchange_balances
            result["db_total_position"] = total_db_position
            result["position_diff"] = diff

            if diff > 0.00001:
                LOG.warning(
                    "Position mismatch: DB=%.10f vs Exchange=%.10f (diff=%.10f)",
                    total_db_position, base_balance, diff,
                )
            else:
                LOG.info(
                    "Position integrity OK: DB=%.10f ≈ Exchange=%.10f",
                    total_db_position, base_balance,
                )

            # Detectar profiles individualmente presos com exchange zerada.
            # Um profile stuck é aquele com net_position > threshold enquanto
            # o saldo real da exchange está zerado — indicando buys órfãos sem
            # SELL correspondente no ledger do profile.
            if base_balance < _PROFILE_MIN_OPEN_POSITION:
                stuck: list = []
                for p, data in result["profiles"].items():
                    if data["net_position"] > _PROFILE_MIN_OPEN_POSITION:
                        stuck.append(p)
                        LOG.warning(
                            "Stuck profile detected (exchange≈0): profile=%s net=%.10f",
                            p,
                            data["net_position"],
                        )
                if stuck:
                    result["stuck_profiles"] = stuck

        except Exception as exc:
            LOG.warning("Could not fetch exchange balance for integrity check: %s", exc)
            result["exchange_btc_balance"] = None

        # Salvar resultado
        cur.execute(
            f"""
            INSERT INTO {SCHEMA}.exchange_sync_state
                (sync_key, synced_at, metadata, updated_at)
            VALUES (%s, NOW(), %s, NOW())
            ON CONFLICT (sync_key) DO UPDATE SET
                synced_at = EXCLUDED.synced_at,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            """,
            ("position_integrity", json.dumps(result)),
        )
    conn.commit()
    return result


# Tolerância de size para match profile-aware de SELL fills (±25%)
_PROFILE_SELL_SIZE_TOLERANCE = 0.25
# Janela de tempo para match profile-aware de SELL fills (±3 horas)
_PROFILE_SELL_TIME_WINDOW_SEC = 3 * 60 * 60
# Saldo mínimo de posição para considerar um perfil como "aberto"
_PROFILE_MIN_OPEN_POSITION = 0.000001


def _match_open_buy_profile(
    cur,
    row: Dict[str, Any],
    event_ts: float,
) -> Optional[str]:
    """Retorna o profile que possui BUY aberto correspondente a um fill SELL.

    Em contas compartilhadas, um fill SELL da exchange pode fechar um BUY
    aberto em qualquer profile. Esta função identifica qual profile tem o
    BUY mais recente e compatível (symbol, size ±25%, timestamp ±3h) cuja
    posição ainda está aberta (SUM(buy) > SUM(sell) + size).

    Só é executada para fills SELL. Retorna None se não houver match.
    """
    if row.get("side") != "sell":
        return None

    size = float(row.get("size") or 0)
    if size <= _PROFILE_MIN_OPEN_POSITION:
        return None

    symbol = row.get("symbol", "BTC-USDT")
    ts_low = event_ts - _PROFILE_SELL_TIME_WINDOW_SEC
    ts_high = event_ts + _PROFILE_SELL_TIME_WINDOW_SEC
    size_min = size * (1.0 - _PROFILE_SELL_SIZE_TOLERANCE)
    size_max = size * (1.0 + _PROFILE_SELL_SIZE_TOLERANCE)

    # Busca profiles com posição aberta E com BUY próximo ao fill SELL.
    # "Posição aberta" = SUM(buy) - SUM(sell) >= threshold no profile.
    # O COALESCE garante profiles sem qualquer sell ainda (apenas buys).
    cur.execute(
        f"""
        SELECT
            t.profile,
            MAX(t.timestamp) AS last_buy_ts
        FROM {SCHEMA}.trades t
        INNER JOIN (
            SELECT
                profile,
                COALESCE(SUM(size) FILTER (WHERE side = 'buy'), 0)
                - COALESCE(SUM(size) FILTER (WHERE side = 'sell'), 0) AS net_pos
            FROM {SCHEMA}.trades
            WHERE symbol = %s AND dry_run = FALSE
            GROUP BY profile
            HAVING COALESCE(SUM(size) FILTER (WHERE side = 'buy'), 0)
                 - COALESCE(SUM(size) FILTER (WHERE side = 'sell'), 0) >= %s
        ) open_profiles ON open_profiles.profile = t.profile
        WHERE t.symbol = %s
          AND t.side = 'buy'
          AND t.dry_run = FALSE
          AND t.timestamp BETWEEN %s AND %s
          AND t.size BETWEEN %s AND %s
        GROUP BY t.profile
        ORDER BY last_buy_ts DESC
        LIMIT 1
        """,
        (symbol, _PROFILE_MIN_OPEN_POSITION, symbol, ts_low, ts_high, size_min, size_max),
    )
    match = cur.fetchone()
    if not match:
        return None

    # Suporte a RealDictCursor e cursor simples
    profile = match["profile"] if hasattr(match, "__getitem__") else match[0]
    LOG.info(
        "profile-aware SELL match: order_id=%s size=%.8f → profile=%s",
        row.get("order_id", "?"),
        size,
        profile,
    )
    return profile


def _sync_fills(conn) -> int:
    """Sincroniza fills da KuCoin com o banco de dados.

    Para cada fill agrupado por order_id:
    1. Se order_id já existe no BD → atualiza metadata/size/price
    2. Senão, tenta vincular a um trade órfão do agent (sem order_id, timestamp próximo)
    2b. Para fills SELL sem orphan, detecta o profile com BUY aberto compatível
    3. Se nenhum match encontrado → insere como novo trade exchange_sync
    """
    fills = get_fills(limit=200) or []
    grouped = _aggregate_fills(fills)
    inserted = 0
    matched_orphans = 0
    pnl_updated = 0
    has_profile = _trades_has_profile(conn)

    with conn.cursor(cursor_factory=REAL_DICT_CURSOR) as cur:
        for order_id, row in sorted(grouped.items(), key=lambda item: str(item[1]["created_at"])):
            event_ts = _row_event_timestamp(row)
            metadata = {
                "source": "kucoin_sync",
                "trade_ids": row["trade_ids"],
                "fills": row["raw_fills"],
            }
            # 1. Busca exata por order_id
            cur.execute(
                f"SELECT id, metadata FROM {SCHEMA}.trades WHERE order_id = %s LIMIT 1",
                (order_id,),
            )
            existing = cur.fetchone()
            if existing:
                existing_metadata = existing.get("metadata") or {}
                if not isinstance(existing_metadata, dict):
                    existing_metadata = {}
                merged_metadata = {
                    **existing_metadata,
                    **metadata,
                }
                cur.execute(
                    f"""
                    UPDATE {SCHEMA}.trades
                    SET timestamp = %s,
                        price = %s,
                        size = %s,
                        funds = %s,
                        dry_run = FALSE,
                        metadata = %s
                    WHERE id = %s
                    """,
                    (
                        event_ts,
                        row["price"],
                        row["size"],
                        row["funds"],
                        json.dumps(merged_metadata),
                        existing["id"],
                    ),
                )
                if row.get("side") == "sell" and _refresh_sell_pnl(cur, int(existing["id"])):
                    pnl_updated += 1
                continue

            # 2. Tentar vincular a trade órfão do agent
            orphan_id = _match_orphan_to_fill(cur, order_id, row, event_ts)
            if orphan_id is not None:
                matched_orphans += 1
                if row.get("side") == "sell" and _refresh_sell_pnl(cur, int(orphan_id)):
                    pnl_updated += 1
                continue

            # 2b. Para fills SELL: detectar o profile com BUY aberto compatível
            # Isso resolve o bug de conta compartilhada onde BUYs ao vivo (com
            # order_id) ficavam sem SELL correspondente no mesmo profile.
            insert_profile = SYNC_PROFILE
            if has_profile and row.get("side") == "sell":
                matched_profile = _match_open_buy_profile(cur, row, event_ts)
                if matched_profile is not None:
                    insert_profile = matched_profile
                    metadata["matched_profile"] = matched_profile
                    metadata["profile_match_source"] = "open_buy_profile_match"

            # 3. Inserir como novo trade
            if has_profile:
                cur.execute(
                    f"""
                    INSERT INTO {SCHEMA}.trades
                        (timestamp, symbol, side, price, size, funds, order_id, dry_run, metadata, profile)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, %s, %s)
                    RETURNING id
                    """,
                    (
                        event_ts,
                        row["symbol"],
                        row["side"],
                        row["price"],
                        row["size"],
                        row["funds"],
                        order_id,
                        json.dumps(metadata),
                        insert_profile,
                    ),
                )
            else:
                cur.execute(
                    f"""
                    INSERT INTO {SCHEMA}.trades
                        (timestamp, symbol, side, price, size, funds, order_id, dry_run, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, %s)
                    RETURNING id
                    """,
                    (
                        event_ts,
                        row["symbol"],
                        row["side"],
                        row["price"],
                        row["size"],
                        row["funds"],
                        order_id,
                        json.dumps(metadata),
                    ),
                )
            trade_id = int(cur.fetchone()["id"])
            inserted += 1
            if row.get("side") == "sell" and _refresh_sell_pnl(cur, trade_id):
                pnl_updated += 1
            LOG.info(
                "Synced fill order_id=%s trade_id=%s symbol=%s side=%s size=%.8f price=%.8f",
                order_id,
                trade_id,
                row["symbol"],
                row["side"],
                row["size"],
                row["price"],
            )

        pnl_updated += _backfill_missing_sell_pnl(cur)

        cur.execute(
            f"""
            INSERT INTO {SCHEMA}.exchange_sync_state (sync_key, synced_at, metadata, updated_at)
            VALUES (%s, NOW(), %s, NOW())
            ON CONFLICT (sync_key) DO UPDATE SET
                synced_at = EXCLUDED.synced_at,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            """,
            ("fills", json.dumps({
                "orders_seen": len(grouped),
                "orders_inserted": inserted,
                "orphans_matched": matched_orphans,
                "pnl_updated": pnl_updated,
            })),
        )
    conn.commit()
    if matched_orphans:
        LOG.info("Matched %d orphan agent trades to KuCoin fills", matched_orphans)
    if pnl_updated:
        LOG.info("PnL líquido atualizado em %d SELLs", pnl_updated)
    return inserted


def _fetch_account_ledgers(
    start_ms: int,
    end_ms: int,
    currency: Optional[str] = None,
    page_size: int = 500,
) -> list[dict[str, Any]]:
    page = 1
    rows: list[dict[str, Any]] = []
    while True:
        endpoint = (
            f"/api/v1/accounts/ledgers?startAt={start_ms}&endAt={end_ms}"
            f"&pageSize={page_size}&currentPage={page}"
        )
        if currency:
            endpoint += f"&currency={currency}"
        attempt = 0
        while True:
            headers = kucoin_api._build_headers("GET", endpoint)
            response = requests.get(kucoin_api.KUCOIN_BASE + endpoint, headers=headers, timeout=10)
            if response.status_code != 429:
                break
            attempt += 1
            wait_s = max(float(response.headers.get("Retry-After", "0") or 0), min(2**attempt, 15))
            LOG.warning(
                "KuCoin ledger rate limit hit for window %s-%s page=%s; retrying in %.1fs",
                start_ms,
                end_ms,
                page,
                wait_s,
            )
            time.sleep(wait_s)
            if attempt >= 6:
                response.raise_for_status()
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != "200000":
            raise RuntimeError(f"KuCoin ledger API error: {payload}")
        data = payload.get("data", {}) or {}
        items = data.get("items", []) or []
        rows.extend(items)
        total_page = int(data.get("totalPage") or page)
        if not items or page >= total_page:
            break
        page += 1
        time.sleep(LEDGER_REQUEST_SPACING_SEC)
    return rows


def _sync_account_ledgers(conn) -> int:
    inserted = 0
    rows_seen = 0
    now_ms = int(time.time() * 1000)
    last_cursor_ms = _get_sync_cursor_ms(conn, ACCOUNT_LEDGER_SYNC_KEY)
    currency_filter: Optional[str] = None
    if last_cursor_ms is None:
        start_ms = now_ms - LEDGER_BACKFILL_MS
        currency_filter = "BRL"
        LOG.info("Starting KuCoin BRL ledger backfill for the last %s days", LEDGER_BACKFILL_DAYS)
    else:
        start_ms = max(last_cursor_ms - LEDGER_CURSOR_OVERLAP_MS, now_ms - LEDGER_WINDOW_MS)
    max_seen_ms = last_cursor_ms or start_ms
    with conn.cursor() as cur:
        for window_start_ms, window_end_ms in _iter_time_windows(start_ms, now_ms):
            ledgers = _fetch_account_ledgers(
                window_start_ms,
                window_end_ms,
                currency=currency_filter,
                page_size=500,
            )
            rows_seen += len(ledgers)
            if ledgers:
                LOG.info(
                    "Fetched %s ledgers from KuCoin for window %s-%s%s",
                    len(ledgers),
                    window_start_ms,
                    window_end_ms,
                    f" currency={currency_filter}" if currency_filter else "",
                )
            for item in ledgers:
                ledger_id = str(item.get("id") or "").strip()
                if not ledger_id:
                    continue
                created_at_ms = int(item.get("createdAt") or 0)
                max_seen_ms = max(max_seen_ms, created_at_ms)
                cur.execute(
                    f"SELECT 1 FROM {SCHEMA}.exchange_account_ledgers WHERE ledger_id = %s",
                    (ledger_id,),
                )
                if cur.fetchone():
                    continue
                cur.execute(
                    f"""
                    INSERT INTO {SCHEMA}.exchange_account_ledgers
                        (ledger_id, currency, amount, fee, balance, account_type, biz_type,
                         direction, created_at_ms, context, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        ledger_id,
                        item.get("currency"),
                        _safe_float(item.get("amount")),
                        _safe_float(item.get("fee")),
                        _safe_float(item.get("balance")),
                        item.get("accountType"),
                        item.get("bizType"),
                        item.get("direction"),
                        created_at_ms,
                        json.dumps(item.get("context") or ""),
                        json.dumps({"source": "kucoin_sync"}),
                    ),
                )
                inserted += 1
        cur.execute(
            f"""
            INSERT INTO {SCHEMA}.exchange_sync_state
                (sync_key, synced_at, cursor_value, metadata, updated_at)
            VALUES (%s, NOW(), %s, %s, NOW())
            ON CONFLICT (sync_key) DO UPDATE SET
                synced_at = EXCLUDED.synced_at,
                cursor_value = EXCLUDED.cursor_value,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            """,
            (
                ACCOUNT_LEDGER_SYNC_KEY,
                str(max_seen_ms),
                json.dumps({"rows_inserted": inserted, "rows_seen": rows_seen}),
            ),
        )
    conn.commit()
    return inserted


def main() -> int:
    with _connect() as conn:
        _ensure_tables(conn)
        cleaned = _cleanup_duplicate_orphans(conn)
        inserted_fills = _sync_fills(conn)
        inserted_ledgers = _sync_account_ledgers(conn)
        balance_rows = _snapshot_balances(conn)
        integrity = _reconcile_position_integrity(conn)
    orphans = integrity.get("orphan_count", 0)
    diff = integrity.get("position_diff")
    LOG.info(
        "KuCoin sync completed: inserted_fills=%s inserted_ledgers=%s balance_rows=%s orphan_trades=%s position_diff=%s cleaned_orphans=%s",
        inserted_fills,
        inserted_ledgers,
        balance_rows,
        orphans,
        f"{diff:.10f}" if diff is not None else "N/A",
        cleaned,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
