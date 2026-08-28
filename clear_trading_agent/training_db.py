#!/usr/bin/env python3
"""
Training Database — PostgreSQL (schema: clear)
Gerencia histórico de trades, decisões e estados de mercado para o Clear Trading Agent.
Adaptado de btc_trading_agent/training_db.py para mercado B3.
"""
from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as _np
import psycopg2
import psycopg2.extras
import psycopg2.pool

logger = logging.getLogger(__name__)


def _safe_float(val: Any) -> Any:
    """Converte np.float64/np.int64 para float/int nativo Python."""
    if val is None:
        return None
    if isinstance(val, (_np.floating, _np.complexfloating)):
        return float(val)
    if isinstance(val, (_np.integer,)):
        return int(val)
    if isinstance(val, _np.ndarray):
        return val.tolist()
    return val


class _NumpyEncoder(json.JSONEncoder):
    """Encoder JSON que converte tipos numpy para nativos Python."""

    def default(self, obj: Any) -> Any:
        """Serializa tipos numpy."""
        if isinstance(obj, (_np.floating, _np.complexfloating)):
            return float(obj)
        if isinstance(obj, (_np.integer,)):
            return int(obj)
        if isinstance(obj, _np.ndarray):
            return obj.tolist()
        if isinstance(obj, _np.bool_):
            return bool(obj)
        return super().default(obj)


# ====================== CONFIGURAÇÃO ======================
from clear_trading_agent.secrets_helper import get_database_url as _get_database_url

DATABASE_URL = _get_database_url()
SCHEMA = "clear"


# ====================== DATABASE MANAGER ======================
class TrainingDatabase:
    """Gerenciador do banco de dados de treinamento (PostgreSQL, schema clear)."""

    def __init__(self, dsn: Optional[str] = None) -> None:
        self.dsn = dsn or DATABASE_URL
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1, maxconn=5, dsn=self.dsn
        )
        self._ensure_schema()

    def close(self) -> None:
        """Fecha pool de conexões."""
        if self._pool:
            self._pool.closeall()

    @contextmanager
    def _get_conn(self):
        """Context manager para conexões do pool."""
        conn = self._pool.getconn()
        try:
            conn.autocommit = False
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self._pool.putconn(conn)

    def _ensure_schema(self) -> None:
        """Garante que o schema e tabelas existem."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

            # ===== TRADES =====
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.trades (
                    id SERIAL PRIMARY KEY,
                    timestamp DOUBLE PRECISION NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price DOUBLE PRECISION NOT NULL,
                    volume DOUBLE PRECISION,
                    funds DOUBLE PRECISION,
                    order_id TEXT,
                    order_type TEXT DEFAULT 'market',
                    status TEXT DEFAULT 'executed',
                    pnl DOUBLE PRECISION,
                    pnl_pct DOUBLE PRECISION,
                    commission DOUBLE PRECISION DEFAULT 0,
                    dry_run BOOLEAN DEFAULT FALSE,
                    profile TEXT NOT NULL DEFAULT 'default',
                    asset_class TEXT DEFAULT 'equity',
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # ===== DECISIONS =====
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.decisions (
                    id SERIAL PRIMARY KEY,
                    timestamp DOUBLE PRECISION NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL,
                    price DOUBLE PRECISION NOT NULL,
                    reason TEXT,
                    executed BOOLEAN DEFAULT FALSE,
                    trade_id INTEGER REFERENCES {SCHEMA}.trades(id),
                    profile TEXT NOT NULL DEFAULT 'default',
                    features JSONB
                )
            """)

            # ===== MARKET STATES =====
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.market_states (
                    id SERIAL PRIMARY KEY,
                    timestamp DOUBLE PRECISION NOT NULL,
                    symbol TEXT NOT NULL,
                    price DOUBLE PRECISION NOT NULL,
                    bid DOUBLE PRECISION,
                    ask DOUBLE PRECISION,
                    spread DOUBLE PRECISION,
                    spread_pct DOUBLE PRECISION,
                    rsi DOUBLE PRECISION,
                    momentum DOUBLE PRECISION,
                    volatility DOUBLE PRECISION,
                    trend DOUBLE PRECISION,
                    volume DOUBLE PRECISION,
                    trade_flow DOUBLE PRECISION
                )
            """)

            # ===== LEARNING REWARDS =====
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.learning_rewards (
                    id SERIAL PRIMARY KEY,
                    timestamp DOUBLE PRECISION NOT NULL,
                    symbol TEXT NOT NULL,
                    state_hash TEXT NOT NULL,
                    action INTEGER NOT NULL,
                    reward DOUBLE PRECISION NOT NULL,
                    next_state_hash TEXT,
                    episode INTEGER DEFAULT 0
                )
            """)

            # ===== PERFORMANCE STATS =====
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.performance_stats (
                    id SERIAL PRIMARY KEY,
                    timestamp DOUBLE PRECISION NOT NULL,
                    symbol TEXT NOT NULL,
                    period TEXT NOT NULL,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    total_pnl DOUBLE PRECISION DEFAULT 0,
                    max_drawdown DOUBLE PRECISION DEFAULT 0,
                    sharpe_ratio DOUBLE PRECISION,
                    win_rate DOUBLE PRECISION,
                    avg_trade_pnl DOUBLE PRECISION,
                    metadata JSONB
                )
            """)

            # ===== CANDLES =====
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

            # ===== AI TRADE CONTROLS =====
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.ai_trade_controls (
                    id SERIAL PRIMARY KEY,
                    timestamp DOUBLE PRECISION NOT NULL,
                    symbol TEXT NOT NULL,
                    profile TEXT NOT NULL DEFAULT 'default',
                    trigger TEXT,
                    mode TEXT NOT NULL DEFAULT 'shadow',
                    model TEXT,
                    suggested_min_confidence DOUBLE PRECISION,
                    suggested_min_trade_interval INTEGER,
                    suggested_max_position_pct DOUBLE PRECISION,
                    suggested_max_positions INTEGER,
                    applied_min_confidence DOUBLE PRECISION,
                    applied_min_trade_interval INTEGER,
                    applied_max_position_pct DOUBLE PRECISION,
                    applied_max_positions INTEGER,
                    rationale TEXT,
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # ===== AI TRADE WINDOWS =====
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.ai_trade_windows (
                    id SERIAL PRIMARY KEY,
                    timestamp DOUBLE PRECISION NOT NULL,
                    symbol TEXT NOT NULL,
                    profile TEXT NOT NULL DEFAULT 'default',
                    trigger TEXT,
                    mode TEXT NOT NULL DEFAULT 'apply',
                    model TEXT,
                    regime TEXT,
                    reference_price DOUBLE PRECISION,
                    entry_low DOUBLE PRECISION,
                    entry_high DOUBLE PRECISION,
                    target_sell DOUBLE PRECISION,
                    min_confidence DOUBLE PRECISION,
                    min_trade_interval INTEGER,
                    ttl_seconds INTEGER,
                    valid_until DOUBLE PRECISION,
                    rationale TEXT,
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # ===== TAX EVENTS =====
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.tax_events (
                    id SERIAL PRIMARY KEY,
                    timestamp DOUBLE PRECISION NOT NULL,
                    symbol TEXT NOT NULL,
                    asset_class TEXT NOT NULL DEFAULT 'equity',
                    trade_type TEXT NOT NULL DEFAULT 'swing',
                    side TEXT NOT NULL,
                    volume DOUBLE PRECISION NOT NULL,
                    price DOUBLE PRECISION NOT NULL,
                    gross_value DOUBLE PRECISION NOT NULL,
                    pnl DOUBLE PRECISION DEFAULT 0,
                    commission DOUBLE PRECISION DEFAULT 0,
                    irrf DOUBLE PRECISION DEFAULT 0,
                    tax_exempt BOOLEAN DEFAULT FALSE,
                    year_month TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # ===== TAX MONTHLY SUMMARY =====
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.tax_monthly_summary (
                    id SERIAL PRIMARY KEY,
                    year_month TEXT NOT NULL,
                    equity_swing_sales_total DOUBLE PRECISION DEFAULT 0,
                    equity_swing_pnl DOUBLE PRECISION DEFAULT 0,
                    equity_daytrade_pnl DOUBLE PRECISION DEFAULT 0,
                    futures_swing_pnl DOUBLE PRECISION DEFAULT 0,
                    futures_daytrade_pnl DOUBLE PRECISION DEFAULT 0,
                    irrf_total DOUBLE PRECISION DEFAULT 0,
                    commissions_total DOUBLE PRECISION DEFAULT 0,
                    equity_swing_exempt BOOLEAN DEFAULT TRUE,
                    total_tax_due DOUBLE PRECISION DEFAULT 0,
                    events_count INTEGER DEFAULT 0,
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(year_month)
                )
            """)

            # ===== TAX ACCUMULATED LOSSES =====
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.tax_accumulated_losses (
                    id SERIAL PRIMARY KEY,
                    category TEXT NOT NULL,
                    amount DOUBLE PRECISION NOT NULL DEFAULT 0,
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(category)
                )
            """)

            # ===== INDICES =====
            indices = [
                f"CREATE INDEX IF NOT EXISTS idx_clear_trades_symbol ON {SCHEMA}.trades(symbol)",
                f"CREATE INDEX IF NOT EXISTS idx_clear_trades_symbol_profile ON {SCHEMA}.trades(symbol, profile)",
                f"CREATE INDEX IF NOT EXISTS idx_clear_trades_timestamp ON {SCHEMA}.trades(timestamp)",
                f"CREATE INDEX IF NOT EXISTS idx_clear_trades_dry_run ON {SCHEMA}.trades(dry_run)",
                f"CREATE INDEX IF NOT EXISTS idx_clear_trades_asset_class ON {SCHEMA}.trades(asset_class)",
                f"CREATE INDEX IF NOT EXISTS idx_clear_decisions_timestamp ON {SCHEMA}.decisions(timestamp)",
                f"CREATE INDEX IF NOT EXISTS idx_clear_decisions_symbol ON {SCHEMA}.decisions(symbol)",
                f"CREATE INDEX IF NOT EXISTS idx_clear_decisions_symbol_profile ON {SCHEMA}.decisions(symbol, profile)",
                f"CREATE INDEX IF NOT EXISTS idx_clear_market_states_timestamp ON {SCHEMA}.market_states(timestamp)",
                f"CREATE INDEX IF NOT EXISTS idx_clear_market_states_symbol ON {SCHEMA}.market_states(symbol, timestamp)",
                f"CREATE INDEX IF NOT EXISTS idx_clear_candles_lookup ON {SCHEMA}.candles(symbol, ktype, timestamp)",
                f"CREATE INDEX IF NOT EXISTS idx_clear_learning_rewards_symbol ON {SCHEMA}.learning_rewards(symbol)",
                f"CREATE INDEX IF NOT EXISTS idx_clear_ai_controls_lookup ON {SCHEMA}.ai_trade_controls(symbol, profile, timestamp DESC)",
                f"CREATE INDEX IF NOT EXISTS idx_clear_ai_windows_lookup ON {SCHEMA}.ai_trade_windows(symbol, profile, timestamp DESC)",
                f"CREATE INDEX IF NOT EXISTS idx_clear_tax_events_symbol ON {SCHEMA}.tax_events(symbol, year_month)",
                f"CREATE INDEX IF NOT EXISTS idx_clear_tax_events_ym ON {SCHEMA}.tax_events(year_month)",
                f"CREATE INDEX IF NOT EXISTS idx_clear_tax_monthly_ym ON {SCHEMA}.tax_monthly_summary(year_month)",
            ]
            for idx in indices:
                cur.execute(idx)

            conn.commit()
            logger.info("✅ PostgreSQL schema clear.* initialized")

    # ====================== TRADES ======================
    def record_trade(
        self,
        symbol: str,
        side: str,
        price: float,
        volume: float = 0,
        funds: float = 0,
        order_id: str = "",
        order_type: str = "market",
        dry_run: bool = False,
        commission: float = 0,
        asset_class: str = "equity",
        metadata: Optional[Dict] = None,
        profile: str = "default",
    ) -> int:
        """Registra um trade executado."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.trades
                    (timestamp, symbol, side, price, volume, funds,
                     order_id, order_type, dry_run, commission,
                     asset_class, metadata, profile)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    time.time(), symbol, side, _safe_float(price),
                    _safe_float(volume), _safe_float(funds),
                    order_id, order_type, dry_run, _safe_float(commission),
                    asset_class,
                    json.dumps(metadata, cls=_NumpyEncoder) if metadata else None,
                    profile,
                ),
            )
            return cur.fetchone()[0]

    def update_trade_pnl(self, trade_id: int, pnl: float, pnl_pct: float) -> None:
        """Atualiza PnL de um trade."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE {SCHEMA}.trades SET pnl = %s, pnl_pct = %s WHERE id = %s",
                (_safe_float(pnl), _safe_float(pnl_pct), trade_id),
            )

    def count_trades_since(
        self,
        symbol: str,
        since: float,
        dry_run: bool = False,
        profile: Optional[str] = None,
    ) -> int:
        """Conta trades desde um timestamp (para limite diário)."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT COUNT(*) FROM {SCHEMA}.trades
                WHERE symbol = %s AND timestamp >= %s AND dry_run = %s
            """
            params: list[Any] = [symbol, since, dry_run]
            if profile:
                sql += " AND profile = %s"
                params.append(profile)
            cur.execute(sql, params)
            return cur.fetchone()[0]

    def get_recent_trades(
        self,
        symbol: str,
        limit: int = 50,
        dry_run: Optional[bool] = None,
        profile: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retorna trades recentes."""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            sql = f"SELECT * FROM {SCHEMA}.trades WHERE symbol = %s"
            params: list[Any] = [symbol]
            if dry_run is not None:
                sql += " AND dry_run = %s"
                params.append(dry_run)
            if profile:
                sql += " AND profile = %s"
                params.append(profile)
            sql += " ORDER BY timestamp DESC LIMIT %s"
            params.append(limit)
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    # ====================== DECISIONS ======================
    def record_decision(
        self,
        symbol: str,
        action: str,
        confidence: float,
        price: float,
        reason: str = "",
        executed: bool = False,
        trade_id: Optional[int] = None,
        features: Optional[Dict] = None,
        profile: str = "default",
    ) -> int:
        """Registra uma decisão de trading."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.decisions
                    (timestamp, symbol, action, confidence, price,
                     reason, executed, trade_id, profile, features)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    time.time(), symbol, action,
                    _safe_float(confidence), _safe_float(price),
                    reason, executed, trade_id, profile,
                    json.dumps(features, cls=_NumpyEncoder) if features else None,
                ),
            )
            return cur.fetchone()[0]

    def mark_decision_executed(self, decision_id: int, trade_id: int) -> None:
        """Marca uma decisão como executada, vinculando ao trade_id."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE {SCHEMA}.decisions SET executed = TRUE, trade_id = %s WHERE id = %s",
                (trade_id, decision_id),
            )

    # ====================== MARKET STATES ======================
    def record_market_state(
        self,
        symbol: str,
        price: float,
        bid: float = 0,
        ask: float = 0,
        spread: float = 0,
        spread_pct: float = 0,
        rsi: float = 50,
        momentum: float = 0,
        volatility: float = 0,
        trend: float = 0,
        volume: float = 0,
        trade_flow: float = 0,
    ) -> int:
        """Registra estado de mercado."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.market_states
                    (timestamp, symbol, price, bid, ask, spread, spread_pct,
                     rsi, momentum, volatility, trend, volume, trade_flow)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    time.time(), symbol, _safe_float(price),
                    _safe_float(bid), _safe_float(ask),
                    _safe_float(spread), _safe_float(spread_pct),
                    _safe_float(rsi), _safe_float(momentum),
                    _safe_float(volatility), _safe_float(trend),
                    _safe_float(volume), _safe_float(trade_flow),
                ),
            )
            return cur.fetchone()[0]

    # ====================== CANDLES ======================
    def upsert_candles(self, symbol: str, ktype: str, candles: List[Dict]) -> int:
        """Insere ou atualiza candles (upsert por timestamp+symbol+ktype)."""
        if not candles:
            return 0
        with self._get_conn() as conn:
            cur = conn.cursor()
            count = 0
            for c in candles:
                cur.execute(
                    f"""
                    INSERT INTO {SCHEMA}.candles
                        (timestamp, symbol, ktype, open, high, low, close, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (timestamp, symbol, ktype)
                    DO UPDATE SET
                        open = EXCLUDED.open, high = EXCLUDED.high,
                        low = EXCLUDED.low, close = EXCLUDED.close,
                        volume = EXCLUDED.volume
                    """,
                    (
                        int(c["timestamp"]), symbol, ktype,
                        float(c["open"]), float(c["high"]),
                        float(c["low"]), float(c["close"]),
                        float(c.get("volume", 0)),
                    ),
                )
                count += 1
            return count

    # ====================== LEARNING REWARDS ======================
    def record_reward(
        self,
        symbol: str,
        state_hash: str,
        action: int,
        reward: float,
        next_state_hash: str = "",
        episode: int = 0,
    ) -> int:
        """Registra uma recompensa de aprendizado."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.learning_rewards
                    (timestamp, symbol, state_hash, action, reward,
                     next_state_hash, episode)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    time.time(), symbol, state_hash, action,
                    _safe_float(reward), next_state_hash, episode,
                ),
            )
            return cur.fetchone()[0]

    # ====================== STATS ======================
    def get_performance_summary(
        self,
        symbol: str,
        days: int = 30,
        dry_run: bool = False,
        profile: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retorna resumo de performance."""
        since = time.time() - (days * 86400)
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            sql = f"""
                SELECT
                    COUNT(*) as total_trades,
                    COUNT(*) FILTER (WHERE side = 'sell' AND pnl > 0) as winning_sells,
                    COUNT(*) FILTER (WHERE side = 'sell' AND pnl IS NOT NULL) as total_sells,
                    COALESCE(SUM(pnl) FILTER (WHERE side = 'sell'), 0) as total_pnl,
                    COALESCE(AVG(pnl) FILTER (WHERE side = 'sell' AND pnl IS NOT NULL), 0) as avg_pnl,
                    COALESCE(MAX(pnl) FILTER (WHERE side = 'sell'), 0) as best_trade,
                    COALESCE(MIN(pnl) FILTER (WHERE side = 'sell'), 0) as worst_trade
                FROM {SCHEMA}.trades
                WHERE symbol = %s AND timestamp >= %s AND dry_run = %s
            """
            params: list[Any] = [symbol, since, dry_run]
            if profile:
                sql += " AND profile = %s"
                params.append(profile)
            cur.execute(sql, params)
            row = dict(cur.fetchone())
            total_sells = row.get("total_sells", 0)
            winning_sells = row.get("winning_sells", 0)
            row["win_rate"] = (winning_sells / total_sells * 100) if total_sells > 0 else 0
            return row

    # ====================== TAX EVENTS ======================

    def record_tax_event(
        self,
        symbol: str,
        asset_class: str,
        trade_type: str,
        side: str,
        volume: float,
        price: float,
        gross_value: float,
        pnl: float = 0.0,
        commission: float = 0.0,
        irrf: float = 0.0,
        tax_exempt: bool = False,
        year_month: str = "",
    ) -> int:
        """Registra evento fiscal no banco de dados."""
        if not year_month:
            from datetime import datetime, timezone, timedelta
            brt = timezone(timedelta(hours=-3))
            year_month = datetime.now(brt).strftime("%Y-%m")

        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.tax_events
                    (timestamp, symbol, asset_class, trade_type, side,
                     volume, price, gross_value, pnl, commission,
                     irrf, tax_exempt, year_month)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    time.time(), symbol, asset_class, trade_type, side,
                    _safe_float(volume), _safe_float(price),
                    _safe_float(gross_value), _safe_float(pnl),
                    _safe_float(commission), _safe_float(irrf),
                    tax_exempt, year_month,
                ),
            )
            return cur.fetchone()[0]

    def upsert_tax_monthly_summary(
        self,
        year_month: str,
        equity_swing_sales_total: float = 0.0,
        equity_swing_pnl: float = 0.0,
        equity_daytrade_pnl: float = 0.0,
        futures_swing_pnl: float = 0.0,
        futures_daytrade_pnl: float = 0.0,
        irrf_total: float = 0.0,
        commissions_total: float = 0.0,
        equity_swing_exempt: bool = True,
        total_tax_due: float = 0.0,
        events_count: int = 0,
    ) -> None:
        """Insere ou atualiza resumo fiscal mensal."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.tax_monthly_summary
                    (year_month, equity_swing_sales_total, equity_swing_pnl,
                     equity_daytrade_pnl, futures_swing_pnl, futures_daytrade_pnl,
                     irrf_total, commissions_total, equity_swing_exempt,
                     total_tax_due, events_count, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (year_month) DO UPDATE SET
                    equity_swing_sales_total = EXCLUDED.equity_swing_sales_total,
                    equity_swing_pnl = EXCLUDED.equity_swing_pnl,
                    equity_daytrade_pnl = EXCLUDED.equity_daytrade_pnl,
                    futures_swing_pnl = EXCLUDED.futures_swing_pnl,
                    futures_daytrade_pnl = EXCLUDED.futures_daytrade_pnl,
                    irrf_total = EXCLUDED.irrf_total,
                    commissions_total = EXCLUDED.commissions_total,
                    equity_swing_exempt = EXCLUDED.equity_swing_exempt,
                    total_tax_due = EXCLUDED.total_tax_due,
                    events_count = EXCLUDED.events_count,
                    updated_at = NOW()
                """,
                (
                    year_month,
                    _safe_float(equity_swing_sales_total),
                    _safe_float(equity_swing_pnl),
                    _safe_float(equity_daytrade_pnl),
                    _safe_float(futures_swing_pnl),
                    _safe_float(futures_daytrade_pnl),
                    _safe_float(irrf_total),
                    _safe_float(commissions_total),
                    equity_swing_exempt,
                    _safe_float(total_tax_due),
                    events_count,
                ),
            )

    def get_tax_monthly_summary(self, year_month: str) -> Optional[Dict[str, Any]]:
        """Retorna resumo fiscal de um mês."""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                f"SELECT * FROM {SCHEMA}.tax_monthly_summary WHERE year_month = %s",
                (year_month,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def upsert_tax_accumulated_loss(self, category: str, amount: float) -> None:
        """Insere ou atualiza prejuízo acumulado de uma categoria."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.tax_accumulated_losses (category, amount, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (category) DO UPDATE SET
                    amount = EXCLUDED.amount,
                    updated_at = NOW()
                """,
                (category, _safe_float(amount)),
            )

    def get_tax_accumulated_losses(self) -> Dict[str, float]:
        """Retorna prejuízos acumulados por categoria."""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                f"SELECT category, amount FROM {SCHEMA}.tax_accumulated_losses"
            )
            return {row["category"]: float(row["amount"]) for row in cur.fetchall()}

    def get_tax_events(
        self,
        year_month: str,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retorna eventos fiscais de um mês."""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            sql = f"SELECT * FROM {SCHEMA}.tax_events WHERE year_month = %s"
            params: list[Any] = [year_month]
            if symbol:
                sql += " AND symbol = %s"
                params.append(symbol)
            sql += " ORDER BY timestamp DESC"
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
