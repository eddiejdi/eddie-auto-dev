#!/usr/bin/env python3
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import psycopg2
import psycopg2.extras
import requests


RUNTIME_DIR = Path(os.environ.get("BTC_AGENT_DIR", "/apps/crypto-trader/trading/btc_trading_agent"))
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

import kucoin_api  # type: ignore
from kucoin_api import get_balances, get_fills, get_price_fast  # type: ignore
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


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    url = get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL unavailable")
    return url


def _connect():
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

    def price_in_usdt(currency: str) -> Optional[float]:
        if currency == "USDT":
            return 1.0
        if currency == "BTC":
            return btc_usdt or None
        if currency == "BRL" and usdt_brl > 0:
            return 1.0 / usdt_brl
        return None

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
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
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

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Posição por profile
        cur.execute(f"""
            SELECT
                profile,
                (SUM(size) FILTER (WHERE side='buy')
                 - COALESCE(SUM(size) FILTER (WHERE side='sell'), 0))::numeric(20,10) AS net_position,
                COUNT(*) FILTER (WHERE side='buy') AS buys,
                COUNT(*) FILTER (WHERE side='sell') AS sells,
                COUNT(*) FILTER (WHERE (order_id IS NULL OR order_id = '') AND side IN ('buy', 'sell')) AS orphan_trades
            FROM {SCHEMA}.trades
            WHERE symbol = 'BTC-USDT'
            GROUP BY profile
        """)
        for row in cur.fetchall():
            profile = row["profile"]
            net = float(row["net_position"] or 0)
            orphans = int(row["orphan_trades"] or 0)
            result["profiles"][profile] = {
                "net_position": net,
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
            base_balance = 0.0
            for acc in get_balances(account_type="trade"):
                if acc.get("currency") == "BTC":
                    base_balance = _safe_float(acc.get("balance"))
                    break

            total_db_position = sum(
                p["net_position"] for p in result["profiles"].values()
            )
            diff = abs(total_db_position - base_balance)
            result["exchange_btc_balance"] = base_balance
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


def _sync_fills(conn) -> int:
    """Sincroniza fills da KuCoin com o banco de dados.

    Para cada fill agrupado por order_id:
    1. Se order_id já existe no BD → atualiza metadata/size/price
    2. Senão, tenta vincular a um trade órfão do agent (sem order_id, timestamp próximo)
    3. Se nenhum match encontrado → insere como novo trade exchange_sync
    """
    fills = get_fills(limit=200) or []
    grouped = _aggregate_fills(fills)
    inserted = 0
    matched_orphans = 0
    has_profile = _trades_has_profile(conn)

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
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
                continue

            # 2. Tentar vincular a trade órfão do agent
            orphan_id = _match_orphan_to_fill(cur, order_id, row, event_ts)
            if orphan_id is not None:
                matched_orphans += 1
                continue

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
                        SYNC_PROFILE,
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
            trade_id = cur.fetchone()["id"]
            inserted += 1
            LOG.info(
                "Synced fill order_id=%s trade_id=%s symbol=%s side=%s size=%.8f price=%.8f",
                order_id,
                trade_id,
                row["symbol"],
                row["side"],
                row["size"],
                row["price"],
            )

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
            })),
        )
    conn.commit()
    if matched_orphans:
        LOG.info("Matched %d orphan agent trades to KuCoin fills", matched_orphans)
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
