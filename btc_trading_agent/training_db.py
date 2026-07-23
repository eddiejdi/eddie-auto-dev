#!/usr/bin/env python3
"""
Training Database - PostgreSQL
Gerencia histórico de trades, recompensas e estatísticas de aprendizado
Migrado de SQLite para PostgreSQL (schema btc.*)
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager

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
from secrets_helper import get_database_url as _get_database_url

# Lazy load DATABASE_URL — permite importar módulo mesmo sem DB configurado
_DATABASE_URL_CACHE = None

def _get_database_url_safe() -> str:
    """Lazy-loaded database URL com fallback seguro."""
    global _DATABASE_URL_CACHE
    if _DATABASE_URL_CACHE is None:
        try:
            _DATABASE_URL_CACHE = _get_database_url()
        except RuntimeError as e:
            logger.warning(f"⚠️ {e} — usando fallback")
            # Fallback para ambiente local
            _DATABASE_URL_CACHE = os.getenv(
                "DATABASE_URL",
                "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/btc_trading"
            )
    return _DATABASE_URL_CACHE

DATABASE_URL = _get_database_url_safe()
SCHEMA = "btc"


PROFILE_MIGRATION_SQL = f"""
CREATE TABLE IF NOT EXISTS {SCHEMA}.ai_plans (
    id SERIAL PRIMARY KEY,
    timestamp DOUBLE PRECISION NOT NULL,
    symbol TEXT NOT NULL,
    plan_text TEXT NOT NULL,
    model TEXT,
    regime TEXT,
    price DOUBLE PRECISION,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {SCHEMA}.profile_allocations (
    id SERIAL PRIMARY KEY,
    timestamp DOUBLE PRECISION NOT NULL,
    symbol TEXT NOT NULL,
    conservative_pct DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    aggressive_pct DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

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
);

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
);

ALTER TABLE {SCHEMA}.trades
    ADD COLUMN IF NOT EXISTS profile TEXT;
UPDATE {SCHEMA}.trades
SET profile = 'default'
WHERE profile IS NULL;
ALTER TABLE {SCHEMA}.trades
    ALTER COLUMN profile SET DEFAULT 'default';
ALTER TABLE {SCHEMA}.trades
    ALTER COLUMN profile SET NOT NULL;

ALTER TABLE {SCHEMA}.trades
    ADD COLUMN IF NOT EXISTS servidor TEXT NOT NULL DEFAULT 'homelab';
ALTER TABLE {SCHEMA}.trades
    ALTER COLUMN servidor SET DEFAULT 'homelab';

ALTER TABLE {SCHEMA}.decisions
    ADD COLUMN IF NOT EXISTS servidor TEXT NOT NULL DEFAULT 'homelab';
ALTER TABLE {SCHEMA}.decisions
    ALTER COLUMN servidor SET DEFAULT 'homelab';

ALTER TABLE {SCHEMA}.decisions
    ADD COLUMN IF NOT EXISTS profile TEXT;
UPDATE {SCHEMA}.decisions
SET profile = 'default'
WHERE profile IS NULL;
ALTER TABLE {SCHEMA}.decisions
    ALTER COLUMN profile SET DEFAULT 'default';
ALTER TABLE {SCHEMA}.decisions
    ALTER COLUMN profile SET NOT NULL;

ALTER TABLE {SCHEMA}.ai_plans
    ADD COLUMN IF NOT EXISTS profile TEXT;
UPDATE {SCHEMA}.ai_plans
SET profile = 'default'
WHERE profile IS NULL;
ALTER TABLE {SCHEMA}.ai_plans
    ALTER COLUMN profile SET DEFAULT 'default';
ALTER TABLE {SCHEMA}.ai_plans
    ALTER COLUMN profile SET NOT NULL;
"""

# ====================== DATABASE MANAGER ======================
class TrainingDatabase:
    """Gerenciador do banco de dados de treinamento (PostgreSQL)"""

    def __init__(self, dsn: str = None):
        self.dsn = dsn or DATABASE_URL
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1, maxconn=5, dsn=self.dsn
        )
        self._ensure_schema()

    def close(self):
        """Fecha pool de conexões"""
        if self._pool:
            self._pool.closeall()

    @contextmanager
    def _get_conn(self):
        """Context manager para conexões do pool"""
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

    def _ensure_schema(self):
        """Garante que o schema e tabelas existem"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            # Serializa a migração entre agentes que sobem simultaneamente
            # (deploy reinicia os 3 profiles juntos → DeadlockDetected nos
            # ALTER TABLE concorrentes). Lock liberado no commit/rollback.
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('btc_ensure_schema'))")
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
                    features JSONB
                )
            """)

            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.market_states (
                    id SERIAL PRIMARY KEY,
                    timestamp DOUBLE PRECISION NOT NULL,
                    symbol TEXT NOT NULL,
                    price DOUBLE PRECISION NOT NULL,
                    bid DOUBLE PRECISION,
                    ask DOUBLE PRECISION,
                    spread DOUBLE PRECISION,
                    orderbook_imbalance DOUBLE PRECISION,
                    trade_flow DOUBLE PRECISION,
                    rsi DOUBLE PRECISION,
                    momentum DOUBLE PRECISION,
                    volatility DOUBLE PRECISION,
                    trend DOUBLE PRECISION,
                    volume DOUBLE PRECISION
                )
            """)

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

            # Log bruto das chamadas ao LLM (prompt + resposta) para servir de
            # dataset de fine-tuning. As tabelas ai_trade_controls/ai_trade_windows/
            # ai_plans guardam a saída já parseada, mas NÃO o prompt/CONTEXT exato
            # enviado ao Ollama nem o texto livre do plano — que é o que o SFT precisa.
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.llm_calls (
                    id SERIAL PRIMARY KEY,
                    timestamp DOUBLE PRECISION NOT NULL,
                    call_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    profile TEXT NOT NULL DEFAULT 'default',
                    trigger TEXT,
                    model TEXT,
                    host TEXT,
                    prompt TEXT NOT NULL,
                    response_text TEXT,
                    response_json JSONB,
                    latency_ms DOUBLE PRECISION,
                    metadata JSONB,
                    servidor TEXT NOT NULL DEFAULT 'homelab',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # Config de runtime do log de LLM, controlada pelo painel (ligar/desligar
            # e parametrizar). Linha única (id=1). Os agentes leem com cache curto.
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.llm_log_config (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    log_controls BOOLEAN NOT NULL DEFAULT TRUE,
                    log_window BOOLEAN NOT NULL DEFAULT TRUE,
                    log_plan BOOLEAN NOT NULL DEFAULT TRUE,
                    sample_rate DOUBLE PRECISION NOT NULL DEFAULT 1.0,
                    max_prompt_chars INTEGER NOT NULL DEFAULT 0,
                    prune_days INTEGER NOT NULL DEFAULT 90,
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_by TEXT,
                    CONSTRAINT llm_log_config_singleton CHECK (id = 1)
                )
            """)
            cur.execute(f"""
                INSERT INTO {SCHEMA}.llm_log_config (id) VALUES (1)
                ON CONFLICT (id) DO NOTHING
            """)

            # Compatibilidade: releases recentes passaram a usar colunas/tabelas
            # com "profile"; manter isso aqui evita depender de migration manual.
            cur.execute(PROFILE_MIGRATION_SQL)

            # Conversão intermoedas (owner USDT_BRL)
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.conversion_requests (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    requested_by TEXT,
                    asset_in TEXT NOT NULL,
                    asset_out TEXT NOT NULL,
                    amount_in DOUBLE PRECISION NOT NULL,
                    min_out DOUBLE PRECISION,
                    status TEXT NOT NULL DEFAULT 'pending',
                    plan_json JSONB,
                    result_json JSONB,
                    dry_run BOOLEAN DEFAULT TRUE,
                    profile TEXT DEFAULT 'conservative',
                    symbol_owner TEXT DEFAULT 'USDT-BRL'
                )
            """)
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.conversion_legs (
                    id SERIAL PRIMARY KEY,
                    request_id INTEGER REFERENCES {SCHEMA}.conversion_requests(id),
                    leg_index INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    amount_in DOUBLE PRECISION,
                    amount_out DOUBLE PRECISION,
                    fee DOUBLE PRECISION,
                    order_id TEXT,
                    status TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.conversion_lock (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    owner TEXT,
                    held_at TIMESTAMPTZ,
                    CONSTRAINT conversion_lock_singleton CHECK (id = 1)
                )
            """)
            cur.execute(f"""
                INSERT INTO {SCHEMA}.conversion_lock (id) VALUES (1)
                ON CONFLICT (id) DO NOTHING
            """)

            # Índices
            indices = [
                f"CREATE INDEX IF NOT EXISTS idx_btc_trades_symbol ON {SCHEMA}.trades(symbol)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_trades_symbol_profile ON {SCHEMA}.trades(symbol, profile)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_trades_timestamp ON {SCHEMA}.trades(timestamp)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_trades_dry_run ON {SCHEMA}.trades(dry_run)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_decisions_timestamp ON {SCHEMA}.decisions(timestamp)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_decisions_symbol ON {SCHEMA}.decisions(symbol)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_decisions_symbol_profile ON {SCHEMA}.decisions(symbol, profile)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_market_states_timestamp ON {SCHEMA}.market_states(timestamp)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_market_states_symbol ON {SCHEMA}.market_states(symbol, timestamp)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_candles_lookup ON {SCHEMA}.candles(symbol, ktype, timestamp)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_learning_rewards_symbol ON {SCHEMA}.learning_rewards(symbol)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_ai_plans_symbol_profile_ts ON {SCHEMA}.ai_plans(symbol, profile, timestamp DESC)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_profile_allocations_symbol_ts ON {SCHEMA}.profile_allocations(symbol, timestamp DESC)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_ai_trade_controls_symbol_profile_ts ON {SCHEMA}.ai_trade_controls(symbol, profile, timestamp DESC)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_ai_trade_windows_symbol_profile_ts ON {SCHEMA}.ai_trade_windows(symbol, profile, timestamp DESC)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_llm_calls_type_symbol_profile_ts ON {SCHEMA}.llm_calls(call_type, symbol, profile, timestamp DESC)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_llm_calls_timestamp ON {SCHEMA}.llm_calls(timestamp)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_conversion_requests_status ON {SCHEMA}.conversion_requests(status)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_conversion_requests_assets ON {SCHEMA}.conversion_requests(asset_in, asset_out)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_conversion_legs_request ON {SCHEMA}.conversion_legs(request_id)",
            ]
            for idx in indices:
                cur.execute(idx)

            conn.commit()
            logger.info("✅ PostgreSQL schema btc.* initialized")

    # ====================== TRADES ======================
    def record_trade(self, symbol: str, side: str, price: float,
                     size: float = None, funds: float = None,
                     order_id: str = None, dry_run: bool = False,
                     metadata: Dict = None, profile: str = 'default',
                     servidor: str = None) -> int:
        """Registra um trade executado"""
        import socket as _socket
        _servidor = servidor or _socket.gethostname()
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {SCHEMA}.trades
                    (timestamp, symbol, side, price, size, funds,
                     order_id, dry_run, metadata, profile, servidor)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                time.time(), symbol, side, price, size, funds,
                order_id, dry_run,
                json.dumps(metadata) if metadata else None,
                profile, _servidor
            ))
            return cur.fetchone()[0]

    def update_trade_pnl(self, trade_id: int, pnl: float, pnl_pct: float):
        """Atualiza PnL de um trade"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                UPDATE {SCHEMA}.trades SET pnl = %s, pnl_pct = %s WHERE id = %s
            """, (pnl, pnl_pct, trade_id))

    def merge_trade_metadata(self, trade_id: int, metadata: Dict[str, Any]) -> None:
        """Mescla chaves de metadata em um trade existente."""
        if not metadata:
            return

        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                f"SELECT metadata FROM {SCHEMA}.trades WHERE id = %s",
                (trade_id,),
            )
            row = cur.fetchone()
            if not row:
                return

            existing_metadata = row.get("metadata") or {}
            if not isinstance(existing_metadata, dict):
                try:
                    existing_metadata = json.loads(existing_metadata)
                except Exception:
                    existing_metadata = {}

            merged_metadata = {
                **existing_metadata,
                **metadata,
            }
            cur.execute(
                f"UPDATE {SCHEMA}.trades SET metadata = %s WHERE id = %s",
                (json.dumps(merged_metadata), trade_id),
            )

    def close_open_buys(self, symbol: str, profile: str, dry_run: bool, reason: str) -> int:
        """Marca todos os buys abertos como 'closed' com a razão indicada.
        Retorna o número de linhas afetadas.
        Usado quando a exchange reporta saldo=0 mas o DB ainda tem posições abertas.
        """
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE {SCHEMA}.trades "
                f"SET status = 'closed', "
                f"    metadata = COALESCE(metadata, '{{}}') || %s::jsonb "
                f"WHERE symbol = %s AND profile = %s AND dry_run = %s "
                f"  AND side = 'buy' AND status != 'closed'",
                (
                    json.dumps({"closed_reason": reason, "auto_closed": True}),
                    symbol, profile, dry_run,
                ),
            )
            return cur.rowcount

    def count_trades_since(self, symbol: str, since: float,
                           dry_run: bool = False, profile: str = None) -> int:
        """Conta trades desde um timestamp (para limite diário)"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            query = f"""
                SELECT COUNT(*) FROM {SCHEMA}.trades
                WHERE symbol = %s AND timestamp > %s AND dry_run = %s
            """
            params = [symbol, since, dry_run]
            if profile:
                query += " AND profile = %s"
                params.append(profile)
            cur.execute(query, params)
            return cur.fetchone()[0]

    def get_pnl_since(self, symbol: str, since: float,
                      dry_run: bool = False, profile: str = None) -> float:
        """Retorna PnL acumulado desde um timestamp (para limite diário de perda)"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            query = f"""
                SELECT COALESCE(SUM(pnl), 0) FROM {SCHEMA}.trades
                WHERE symbol = %s AND timestamp > %s AND dry_run = %s
                  AND pnl IS NOT NULL
            """
            params = [symbol, since, dry_run]
            if profile:
                query += " AND profile = %s"
                params.append(profile)
            cur.execute(query, params)
            return float(cur.fetchone()[0])

    def get_profile_realized_sells(
        self,
        symbol: str,
        profile: str,
        since: float,
        *,
        dry_run: bool = False,
        limit: int = 50,
    ) -> List[Dict]:
        """Retorna SELLs realizados com PnL para cálculo de track record."""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                f"""
                SELECT side, pnl, pnl_pct, timestamp
                FROM {SCHEMA}.trades
                WHERE symbol = %s
                  AND profile = %s
                  AND dry_run = %s
                  AND side IN ('sell', 'sell_reconciled')
                  AND pnl IS NOT NULL
                  AND timestamp > %s
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (symbol, profile, dry_run, since, max(1, int(limit))),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_recent_trades(self, symbol: str = None, limit: int = 100,
                          include_dry: bool = False, profile: str = None) -> List[Dict]:
        """Obtém trades recentes"""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            query = f"SELECT * FROM {SCHEMA}.trades WHERE 1=1"
            params = []

            if symbol:
                query += " AND symbol = %s"
                params.append(symbol)

            if not include_dry:
                query += " AND dry_run = FALSE"

            if profile:
                query += " AND profile = %s"
                params.append(profile)

            query += " ORDER BY timestamp DESC LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    # ====================== DECISIONS ======================
    def record_decision(self, symbol: str, action: str, confidence: float,
                        price: float, reason: str = None, profile: str = "default",
                        features: Dict = None, servidor: str = None) -> int:
        """Registra uma decisão do modelo."""
        import socket as _socket
        _servidor = servidor or _socket.gethostname()
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {SCHEMA}.decisions
                    (timestamp, symbol, action, confidence, price, reason, features, profile, servidor)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                time.time(), symbol, action,
                _safe_float(confidence), _safe_float(price), reason,
                json.dumps(features, cls=_NumpyEncoder) if features else None,
                profile, _servidor
            ))
            return cur.fetchone()[0]

    def mark_decision_executed(self, decision_id: int, trade_id: int):
        """Marca decisão como executada"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                UPDATE {SCHEMA}.decisions
                SET executed = TRUE, trade_id = %s WHERE id = %s
            """, (trade_id, decision_id))

    def merge_decision_features(self, decision_id: int, features: Dict[str, Any]) -> None:
        """Mescla chaves em decisions.features sem apagar as features do modelo."""
        if not features:
            return

        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                UPDATE {SCHEMA}.decisions
                SET features = COALESCE(features, '{{}}'::jsonb) || %s::jsonb
                WHERE id = %s
            """, (
                json.dumps(features, cls=_NumpyEncoder),
                decision_id,
            ))

    def get_recent_decisions(self, symbol: str = None, limit: int = 20) -> List[Dict]:
        """Obtém decisões recentes"""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            query = f"SELECT * FROM {SCHEMA}.decisions WHERE 1=1"
            params = []
            if symbol:
                query += " AND symbol = %s"
                params.append(symbol)
            query += " ORDER BY timestamp DESC LIMIT %s"
            params.append(limit)
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    def record_ai_trade_controls(
        self,
        *,
        symbol: str,
        profile: str,
        trigger: str,
        mode: str,
        model: str,
        suggested: Dict[str, Any],
        applied: Dict[str, Any],
        rationale: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Registra uma sugestão estruturada de parâmetros do Ollama."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {SCHEMA}.ai_trade_controls (
                    timestamp, symbol, profile, trigger, mode, model,
                    suggested_min_confidence, suggested_min_trade_interval,
                    suggested_max_position_pct, suggested_max_positions,
                    applied_min_confidence, applied_min_trade_interval,
                    applied_max_position_pct, applied_max_positions,
                    rationale, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                time.time(),
                symbol,
                profile,
                trigger,
                mode,
                model,
                _safe_float((suggested or {}).get("min_confidence")),
                int((suggested or {}).get("min_trade_interval") or 0) or None,
                _safe_float((suggested or {}).get("max_position_pct")),
                int((suggested or {}).get("max_positions") or 0) or None,
                _safe_float((applied or {}).get("min_confidence")),
                int((applied or {}).get("min_trade_interval") or 0) or None,
                _safe_float((applied or {}).get("max_position_pct")),
                int((applied or {}).get("max_positions") or 0) or None,
                rationale[:1000] if rationale else None,
                json.dumps(metadata, cls=_NumpyEncoder) if metadata else None,
            ))
            row_id = cur.fetchone()[0]
            cur.execute(f"""
                DELETE FROM {SCHEMA}.ai_trade_controls
                WHERE symbol = %s AND profile = %s AND id NOT IN (
                    SELECT id FROM {SCHEMA}.ai_trade_controls
                    WHERE symbol = %s AND profile = %s
                    ORDER BY timestamp DESC LIMIT 200
                )
            """, (symbol, profile, symbol, profile))
            return row_id

    def record_ai_trade_window(
        self,
        *,
        symbol: str,
        profile: str,
        trigger: str,
        mode: str,
        model: str,
        regime: str,
        reference_price: float,
        entry_low: float,
        entry_high: float,
        target_sell: float,
        min_confidence: float,
        min_trade_interval: int,
        ttl_seconds: int,
        valid_until: float,
        rationale: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Registra a janela operacional fresca calculada pela IA."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {SCHEMA}.ai_trade_windows (
                    timestamp, symbol, profile, trigger, mode, model, regime,
                    reference_price, entry_low, entry_high, target_sell,
                    min_confidence, min_trade_interval, ttl_seconds, valid_until,
                    rationale, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                time.time(),
                symbol,
                profile,
                trigger,
                mode,
                model,
                regime,
                _safe_float(reference_price),
                _safe_float(entry_low),
                _safe_float(entry_high),
                _safe_float(target_sell),
                _safe_float(min_confidence),
                int(min_trade_interval or 0) or None,
                int(ttl_seconds or 0) or None,
                _safe_float(valid_until),
                rationale[:1000] if rationale else None,
                json.dumps(metadata, cls=_NumpyEncoder) if metadata else None,
            ))
            row_id = cur.fetchone()[0]
            cur.execute(f"""
                DELETE FROM {SCHEMA}.ai_trade_windows
                WHERE symbol = %s AND profile = %s AND id NOT IN (
                    SELECT id FROM {SCHEMA}.ai_trade_windows
                    WHERE symbol = %s AND profile = %s
                    ORDER BY timestamp DESC LIMIT 200
                )
            """, (symbol, profile, symbol, profile))
            return row_id

    # ====================== LLM CALLS (fine-tuning dataset) ======================
    def record_llm_call(
        self,
        *,
        call_type: str,
        symbol: str,
        profile: str,
        prompt: str,
        response_text: Optional[str] = None,
        response_json: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        host: Optional[str] = None,
        latency_ms: Optional[float] = None,
        trigger: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        servidor: Optional[str] = None,
    ) -> int:
        """Registra o prompt+resposta bruta de uma chamada ao LLM.

        Serve de matéria-prima para o dataset de fine-tuning (call_type é um de
        'controls' | 'window' | 'plan'). Não faz poda no caminho quente — use
        prune_llm_calls() num timer de manutenção.
        """
        import socket as _socket
        _servidor = servidor or _socket.gethostname()
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {SCHEMA}.llm_calls (
                    timestamp, call_type, symbol, profile, trigger, model, host,
                    prompt, response_text, response_json, latency_ms, metadata, servidor
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                time.time(), call_type, symbol, profile, trigger, model, host,
                prompt, response_text,
                json.dumps(response_json, cls=_NumpyEncoder) if response_json else None,
                _safe_float(latency_ms),
                json.dumps(metadata, cls=_NumpyEncoder) if metadata else None,
                _servidor,
            ))
            return cur.fetchone()[0]

    def get_llm_calls(
        self,
        call_type: str = None,
        symbol: str = None,
        profile: str = None,
        since: float = None,
        limit: int = 1000,
    ) -> List[Dict]:
        """Lê chamadas de LLM logadas (para o dataset builder e shadow eval)."""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            query = f"SELECT * FROM {SCHEMA}.llm_calls WHERE 1=1"
            params: List[Any] = []
            if call_type:
                query += " AND call_type = %s"
                params.append(call_type)
            if symbol:
                query += " AND symbol = %s"
                params.append(symbol)
            if profile:
                query += " AND profile = %s"
                params.append(profile)
            if since is not None:
                query += " AND timestamp > %s"
                params.append(since)
            query += " ORDER BY timestamp ASC LIMIT %s"
            params.append(limit)
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    def prune_llm_calls(self, max_age_days: int = 90) -> int:
        """Remove chamadas de LLM mais velhas que max_age_days. Retorna nº removido."""
        cutoff = time.time() - (max_age_days * 86400)
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"DELETE FROM {SCHEMA}.llm_calls WHERE timestamp < %s",
                (cutoff,),
            )
            return cur.rowcount

    def get_llm_call_stats(self) -> Dict[str, Any]:
        """Contagens de btc.llm_calls por call_type (total e últimas 24h) para o painel."""
        since_24h = time.time() - 86400
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(f"""
                SELECT call_type,
                       COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE timestamp > %s) AS last_24h
                FROM {SCHEMA}.llm_calls
                GROUP BY call_type
            """, (since_24h,))
            by_type = {r["call_type"]: {"total": int(r["total"]), "last_24h": int(r["last_24h"])}
                       for r in cur.fetchall()}
            cur.execute(f"SELECT COUNT(*) AS n, MAX(timestamp) AS last_ts FROM {SCHEMA}.llm_calls")
            row = cur.fetchone() or {}
        return {
            "by_type": by_type,
            "total": int(row.get("n") or 0),
            "last_ts": float(row["last_ts"]) if row.get("last_ts") else None,
        }

    # Defaults usados quando a linha de config não existe ou a leitura falha.
    LLM_LOG_CONFIG_DEFAULTS: Dict[str, Any] = {
        "enabled": True,
        "log_controls": True,
        "log_window": True,
        "log_plan": True,
        "sample_rate": 1.0,
        "max_prompt_chars": 0,
        "prune_days": 90,
    }
    _LLM_LOG_CONFIG_FIELDS = (
        "enabled", "log_controls", "log_window", "log_plan",
        "sample_rate", "max_prompt_chars", "prune_days",
    )

    def get_llm_log_config(self) -> Dict[str, Any]:
        """Lê a config de runtime do log de LLM (linha única id=1)."""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                f"SELECT * FROM {SCHEMA}.llm_log_config WHERE id = 1"
            )
            row = cur.fetchone()
            if not row:
                return dict(self.LLM_LOG_CONFIG_DEFAULTS)
            cfg = dict(self.LLM_LOG_CONFIG_DEFAULTS)
            for k in self._LLM_LOG_CONFIG_FIELDS:
                if row.get(k) is not None:
                    cfg[k] = row[k]
            cfg["updated_at"] = str(row.get("updated_at")) if row.get("updated_at") else None
            cfg["updated_by"] = row.get("updated_by")
            return cfg

    def set_llm_log_config(self, updated_by: str = None, **fields: Any) -> Dict[str, Any]:
        """Atualiza campos da config (parcial) e retorna o estado resultante.

        Valida tipos/ranges: booleans; sample_rate em [0,1]; inteiros >= 0.
        Só aceita as chaves conhecidas — o resto é ignorado.
        """
        updates: Dict[str, Any] = {}
        for k in ("enabled", "log_controls", "log_window", "log_plan"):
            if k in fields and fields[k] is not None:
                updates[k] = bool(fields[k])
        if fields.get("sample_rate") is not None:
            sr = float(fields["sample_rate"])
            updates["sample_rate"] = max(0.0, min(1.0, sr))
        if fields.get("max_prompt_chars") is not None:
            updates["max_prompt_chars"] = max(0, int(fields["max_prompt_chars"]))
        if fields.get("prune_days") is not None:
            updates["prune_days"] = max(1, int(fields["prune_days"]))

        if not updates:
            return self.get_llm_log_config()

        set_clause = ", ".join(f"{k} = %s" for k in updates)
        params = list(updates.values()) + [updated_by]
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {SCHEMA}.llm_log_config (id) VALUES (1)
                ON CONFLICT (id) DO NOTHING
            """)
            cur.execute(
                f"UPDATE {SCHEMA}.llm_log_config "
                f"SET {set_clause}, updated_at = NOW(), updated_by = %s WHERE id = 1",
                params,
            )
        return self.get_llm_log_config()

    # ====================== MARKET STATES ======================
    def record_market_state(self, symbol: str, price: float, **kwargs) -> int:
        """Registra estado do mercado."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {SCHEMA}.market_states
                    (timestamp, symbol, price, bid, ask, spread,
                     orderbook_imbalance, trade_flow, rsi, momentum,
                     volatility, trend, volume)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (
                time.time(), symbol, _safe_float(price),
                _safe_float(kwargs.get("bid")),
                _safe_float(kwargs.get("ask")),
                _safe_float(kwargs.get("spread")),
                _safe_float(kwargs.get("orderbook_imbalance")),
                _safe_float(kwargs.get("trade_flow")),
                _safe_float(kwargs.get("rsi")),
                _safe_float(kwargs.get("momentum")),
                _safe_float(kwargs.get("volatility")),
                _safe_float(kwargs.get("trend")),
                _safe_float(kwargs.get("volume")),
            ))
            return cur.fetchone()[0]

    def get_market_history(self, symbol: str, hours: int = 24,
                           limit: int = 1000) -> List[Dict]:
        """Obtém histórico de estados do mercado"""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cutoff = time.time() - (hours * 3600)
            cur.execute(f"""
                SELECT * FROM {SCHEMA}.market_states
                WHERE symbol = %s AND timestamp > %s
                ORDER BY timestamp ASC
                LIMIT %s
            """, (symbol, cutoff, limit))
            return [dict(row) for row in cur.fetchall()]

    # ====================== LEARNING REWARDS ======================
    def record_reward(self, symbol: str, state_hash: str, action: int,
                      reward: float, next_state_hash: str = None,
                      episode: int = 0):
        """Registra reward para Q-learning"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {SCHEMA}.learning_rewards
                    (timestamp, symbol, state_hash, action, reward,
                     next_state_hash, episode)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (time.time(), symbol, state_hash, action, reward,
                  next_state_hash, episode))

    def get_learning_stats(self, symbol: str) -> Dict:
        """Estatísticas de aprendizado"""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(f"""
                SELECT
                    COUNT(*) as total_episodes,
                    COALESCE(SUM(reward), 0) as total_reward,
                    COALESCE(AVG(reward), 0) as avg_reward,
                    COALESCE(MAX(reward), 0) as max_reward,
                    COALESCE(MIN(reward), 0) as min_reward,
                    SUM(CASE WHEN action = 0 THEN 1 ELSE 0 END) as hold_count,
                    SUM(CASE WHEN action = 1 THEN 1 ELSE 0 END) as buy_count,
                    SUM(CASE WHEN action = 2 THEN 1 ELSE 0 END) as sell_count
                FROM {SCHEMA}.learning_rewards
                WHERE symbol = %s
            """, (symbol,))
            row = cur.fetchone()
            return dict(row) if row else {}

    # ====================== CANDLES ======================
    def store_candles(self, symbol: str, ktype: str, candles: List[Dict]):
        """Armazena candles para backtesting"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            batch = []
            for c in candles:
                batch.append((
                    c["timestamp"], symbol, ktype,
                    c["open"], c["high"], c["low"], c["close"], c["volume"]
                ))

            if batch:
                psycopg2.extras.execute_batch(cur, f"""
                    INSERT INTO {SCHEMA}.candles
                        (timestamp, symbol, ktype, open, high, low, close, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (timestamp, symbol, ktype) DO NOTHING
                """, batch)

    def get_candles(self, symbol: str, ktype: str = "1min",
                    start_ts: int = None, end_ts: int = None,
                    limit: int = 1000) -> List[Dict]:
        """Obtém candles armazenados"""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            query = f"SELECT * FROM {SCHEMA}.candles WHERE symbol = %s AND ktype = %s"
            params = [symbol, ktype]

            if start_ts:
                query += " AND timestamp >= %s"
                params.append(start_ts)
            if end_ts:
                query += " AND timestamp <= %s"
                params.append(end_ts)

            query += " ORDER BY timestamp ASC LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    # ====================== PERFORMANCE ======================
    def calculate_performance(self, symbol: str, days: int = 7) -> Dict:
        """Calcula métricas de performance"""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cutoff = time.time() - (days * 86400)

            cur.execute(f"""
                SELECT * FROM {SCHEMA}.trades
                WHERE symbol = %s AND timestamp > %s AND dry_run = FALSE
                ORDER BY timestamp ASC
            """, (symbol, cutoff))

            trades = [dict(row) for row in cur.fetchall()]

            if not trades:
                return {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "win_rate": 0.0,
                    "total_pnl": 0.0,
                    "avg_pnl": 0.0
                }

            total_trades = len(trades)
            winning_trades = sum(1 for t in trades if (t.get("pnl") or 0) > 0)
            total_pnl = sum(t.get("pnl") or 0 for t in trades)

            return {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "win_rate": winning_trades / total_trades if total_trades > 0 else 0,
                "total_pnl": total_pnl,
                "avg_pnl": total_pnl / total_trades if total_trades > 0 else 0
            }

    def record_performance_snapshot(self, symbol: str, period: str = "1d"):
        """Registra snapshot de performance"""
        days_map = {"1h": 1/24, "4h": 4/24, "1d": 1, "7d": 7, "30d": 30}
        days = days_map.get(period, 1)
        stats = self.calculate_performance(symbol, int(days) or 1)

        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {SCHEMA}.performance_stats
                    (timestamp, symbol, period, total_trades, winning_trades,
                     total_pnl, win_rate, avg_trade_pnl)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                time.time(), symbol, period,
                stats["total_trades"], stats["winning_trades"],
                stats["total_pnl"], stats["win_rate"], stats["avg_pnl"]
            ))

    # ====================== CONVERSION (intermoedas) ======================
    def enqueue_conversion(
        self,
        asset_in: str,
        asset_out: str,
        amount_in: float,
        *,
        requested_by: str = "manual",
        min_out: float = None,
        dry_run: bool = True,
        profile: str = "conservative",
        symbol_owner: str = "USDT-BRL",
    ) -> int:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.conversion_requests
                    (requested_by, asset_in, asset_out, amount_in, min_out,
                     status, dry_run, profile, symbol_owner)
                VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s, %s)
                RETURNING id
                """,
                (
                    requested_by,
                    asset_in.upper(),
                    asset_out.upper(),
                    float(amount_in),
                    min_out,
                    bool(dry_run),
                    profile,
                    symbol_owner,
                ),
            )
            return int(cur.fetchone()[0])

    def has_pending_conversion(self, asset_in: str, asset_out: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT 1 FROM {SCHEMA}.conversion_requests
                WHERE asset_in=%s AND asset_out=%s
                  AND status IN ('pending', 'planned')
                LIMIT 1
                """,
                (asset_in.upper(), asset_out.upper()),
            )
            return cur.fetchone() is not None

    def get_recent_conversion(
        self,
        asset_in: str,
        asset_out: str,
        *,
        within_seconds: int = 21600,
        requested_by: Optional[str] = None,
    ) -> Optional[Dict]:
        """Última conversão do par dentro da janela (qualquer status terminal ou ativa).

        Usado pelo on-ramp para cooldown e dedupe por saldo, evitando re-enfileirar
        a cada ciclo em dry_run ou após falha no_route.
        """
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            params: List[Any] = [asset_in.upper(), asset_out.upper(), int(within_seconds)]
            by_clause = ""
            if requested_by:
                by_clause = " AND requested_by=%s"
                params.append(str(requested_by))
            cur.execute(
                f"""
                SELECT id, created_at, amount_in, status, dry_run, requested_by,
                       result_json, plan_json
                FROM {SCHEMA}.conversion_requests
                WHERE asset_in=%s AND asset_out=%s
                  AND created_at >= NOW() - (%s * INTERVAL '1 second')
                  {by_clause}
                ORDER BY id DESC
                LIMIT 1
                """,
                tuple(params),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_pending_conversions(self, limit: int = 10) -> List[Dict]:
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                f"""
                SELECT * FROM {SCHEMA}.conversion_requests
                WHERE status = 'pending'
                ORDER BY id ASC
                LIMIT %s
                """,
                (int(limit),),
            )
            return [dict(row) for row in cur.fetchall()]

    def update_conversion_request(
        self,
        request_id: int,
        *,
        status: str,
        plan_json: Dict = None,
        result_json: Dict = None,
    ) -> None:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                UPDATE {SCHEMA}.conversion_requests
                SET status=%s,
                    plan_json=COALESCE(%s::jsonb, plan_json),
                    result_json=COALESCE(%s::jsonb, result_json)
                WHERE id=%s
                """,
                (
                    status,
                    json.dumps(plan_json) if plan_json is not None else None,
                    json.dumps(result_json) if result_json is not None else None,
                    int(request_id),
                ),
            )

    def insert_conversion_leg(
        self,
        request_id: int,
        leg_index: int,
        symbol: str,
        side: str,
        amount_in: float,
        amount_out: float,
        fee: float = 0.0,
        order_id: str = None,
        status: str = "ok",
    ) -> int:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.conversion_legs
                    (request_id, leg_index, symbol, side, amount_in, amount_out,
                     fee, order_id, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    int(request_id),
                    int(leg_index),
                    symbol,
                    side,
                    amount_in,
                    amount_out,
                    fee,
                    order_id,
                    status,
                ),
            )
            return int(cur.fetchone()[0])

    def try_acquire_conversion_lock(self, owner: str, stale_seconds: int = 300) -> bool:
        """Lock simples via linha singleton; libera se stale."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                UPDATE {SCHEMA}.conversion_lock
                SET owner=%s, held_at=NOW()
                WHERE id=1
                  AND (
                    owner IS NULL
                    OR owner = %s
                    OR held_at IS NULL
                    OR held_at < NOW() - (%s || ' seconds')::interval
                  )
                RETURNING id
                """,
                (owner, owner, str(int(stale_seconds))),
            )
            return cur.fetchone() is not None

    def release_conversion_lock(self, owner: str) -> None:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                UPDATE {SCHEMA}.conversion_lock
                SET owner=NULL, held_at=NULL
                WHERE id=1 AND (owner=%s OR owner IS NULL)
                """,
                (owner,),
            )

    def conversion_metrics_snapshot(self, profile: str = None) -> Dict[str, Any]:
        """Agrega contadores para o prometheus exporter."""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                f"""
                SELECT status, COUNT(*) AS n
                FROM {SCHEMA}.conversion_requests
                GROUP BY status
                """
            )
            by_status = {row["status"]: int(row["n"]) for row in cur.fetchall()}
            cur.execute(
                f"""
                SELECT plan_json, EXTRACT(EPOCH FROM created_at) AS ts
                FROM {SCHEMA}.conversion_requests
                WHERE status IN ('done', 'simulated')
                ORDER BY id DESC
                LIMIT 1
                """
            )
            last = cur.fetchone()
            last_plan = last["plan_json"] if last else None
            if isinstance(last_plan, str):
                try:
                    last_plan = json.loads(last_plan)
                except Exception:
                    last_plan = {}
            last_plan = last_plan or {}
            cur.execute(
                f"SELECT owner IS NOT NULL AS held FROM {SCHEMA}.conversion_lock WHERE id=1"
            )
            lock_row = cur.fetchone()
            return {
                "by_status": by_status,
                "last_cost_pct": float(last_plan.get("total_cost_pct") or 0),
                "last_hops": float(last_plan.get("hops") or 0),
                "last_savings_bps": float(last_plan.get("savings_vs_usdt_bps") or 0)
                if last_plan.get("savings_vs_usdt_bps") is not None
                else 0.0,
                "last_success_ts": float(last["ts"]) if last else 0.0,
                "lock_held": 1 if lock_row and lock_row.get("held") else 0,
            }

    # ====================== CLEANUP ======================
    def cleanup_old_data(self, days: int = 30):
        """Remove dados antigos"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cutoff = time.time() - (days * 86400)

            cur.execute(f"DELETE FROM {SCHEMA}.market_states WHERE timestamp < %s", (cutoff,))
            deleted_states = cur.rowcount
            cur.execute(f"DELETE FROM {SCHEMA}.learning_rewards WHERE timestamp < %s", (cutoff,))
            deleted_rewards = cur.rowcount

            logger.info(f"🧹 Cleaned up {deleted_states + deleted_rewards} old records")


# ====================== TRAINING UTILITIES ======================
class TrainingManager:
    """Gerenciador de treinamento do agente"""

    def __init__(self, db: TrainingDatabase = None):
        self.db = db or TrainingDatabase()

    @staticmethod
    def _retro_score_sample(state: Dict[str, Any], next_state: Dict[str, Any]) -> Tuple[int, float, Dict[str, Any]]:
        """Aplica penalidades/bonificações retroativas a uma transição de mercado."""
        price = float(state.get("price") or 0.0)
        next_price = float(next_state.get("price") or 0.0)
        if price <= 0:
            return 0, 0.0, {"reason": "invalid_price"}

        price_change = (next_price - price) / price
        fee_drag = 0.002  # ida + volta aproximada
        actionable_edge = max(abs(price_change) - fee_drag, 0.0)

        rsi = float(state.get("rsi") or 50.0)
        momentum = float(state.get("momentum") or 0.0)
        imbalance = float(state.get("orderbook_imbalance") or 0.0)
        flow = float(state.get("trade_flow") or 0.0)
        trend = float(state.get("trend") or 0.0)
        volatility = float(state.get("volatility") or 0.0)

        penalties: list[str] = []
        bonuses: list[str] = []
        regime = "BULLISH" if trend > 0.12 else "BEARISH" if trend < -0.12 else "RANGING"

        def add_penalty(score: float, label: str, current_reward: float) -> float:
            penalties.append(label)
            return current_reward - score

        def add_bonus(score: float, label: str, current_reward: float) -> float:
            bonuses.append(label)
            return current_reward + score

        if price_change > fee_drag:
            best_action = 1
            reward_multiplier = 50.0 if regime == "BULLISH" else 34.0 if regime == "RANGING" else 30.0
            reward = actionable_edge * reward_multiplier
            if regime == "BULLISH":
                reward = add_bonus(0.06, "regime_aligned", reward)
            elif regime == "BEARISH":
                reward = add_penalty(0.12, "counter_regime_buy", reward)
            if actionable_edge >= 0.004:
                reward = add_bonus(0.10, "strong_edge", reward)
            elif actionable_edge < 0.0015:
                reward = add_penalty(0.12, "thin_edge", reward)
            if rsi < 35:
                reward = add_bonus(0.08, "rsi_oversold", reward)
            if imbalance > 0:
                reward = add_bonus(0.06, "bid_pressure", reward)
            if flow > 0:
                reward = add_bonus(0.06, "buying_pressure", reward)
            if momentum > 0:
                reward = add_bonus(0.05, "positive_momentum", reward)
            if trend > 0:
                reward = add_bonus(0.04, "trend_up", reward)
            if rsi > 68:
                reward = add_penalty(0.12, "rsi_overbought", reward)
            if imbalance < 0:
                reward = add_penalty(0.08, "ask_pressure", reward)
            if flow < 0:
                reward = add_penalty(0.08, "selling_pressure", reward)
            if momentum < 0:
                reward = add_penalty(0.10, "negative_momentum", reward)
            if volatility > 0.02 and regime != "BULLISH":
                reward = add_penalty(0.05, "volatile_buy", reward)
        elif price_change < -fee_drag:
            best_action = 2
            reward_multiplier = 50.0 if regime == "BEARISH" else 34.0 if regime == "RANGING" else 30.0
            reward = actionable_edge * reward_multiplier
            if regime == "BEARISH":
                reward = add_bonus(0.06, "regime_aligned", reward)
            elif regime == "BULLISH":
                reward = add_penalty(0.12, "counter_regime_sell", reward)
            if actionable_edge >= 0.004:
                reward = add_bonus(0.10, "strong_edge", reward)
            elif actionable_edge < 0.0015:
                reward = add_penalty(0.12, "thin_edge", reward)
            if rsi > 65:
                reward = add_bonus(0.08, "rsi_high_for_sell", reward)
            if imbalance < 0:
                reward = add_bonus(0.06, "ask_pressure", reward)
            if flow < 0:
                reward = add_bonus(0.06, "selling_pressure", reward)
            if momentum < 0:
                reward = add_bonus(0.05, "negative_momentum", reward)
            if trend < 0:
                reward = add_bonus(0.04, "trend_down", reward)
            if rsi < 35:
                reward = add_penalty(0.08, "rsi_oversold", reward)
            if imbalance > 0:
                reward = add_penalty(0.08, "bid_pressure", reward)
            if flow > 0:
                reward = add_penalty(0.08, "buying_pressure", reward)
            if momentum > 0:
                reward = add_penalty(0.10, "positive_momentum", reward)
            if volatility > 0.02 and regime == "BEARISH":
                reward = add_bonus(0.03, "volatile_breakdown", reward)
        else:
            best_action = 0
            reward = 0.05 if regime == "RANGING" else 0.015
            if regime == "RANGING":
                reward = add_bonus(0.02, "range_patience", reward)
            if abs(momentum) < 0.0015:
                reward = add_bonus(0.02, "flat_momentum", reward)
            if abs(imbalance) < 0.05:
                reward = add_bonus(0.02, "neutral_imbalance", reward)
            if abs(flow) < 0.05:
                reward = add_bonus(0.02, "neutral_flow", reward)
            if volatility > 0.02:
                reward = add_penalty(0.02, "high_vol_noise", reward)

        reward = float(round(reward, 6))
        context = {
            "price_change": round(price_change, 6),
            "best_action": best_action,
            "penalties": penalties,
            "bonuses": bonuses,
            "rsi": round(rsi, 4),
            "momentum": round(momentum, 6),
            "orderbook_imbalance": round(imbalance, 6),
            "trade_flow": round(flow, 6),
            "trend": round(trend, 6),
            "volatility": round(volatility, 6),
            "regime": regime,
        }
        return best_action, reward, context

    def generate_training_batch(self, symbol: str,
                                 batch_size: int = 100) -> List[Dict]:
        """Gera batch de dados para treinamento"""
        states = self.db.get_market_history(symbol, hours=72, limit=batch_size * 2)

        if len(states) < 10:
            return []

        batch = []
        for i in range(len(states) - 1):
            current = states[i]
            next_state = states[i + 1]
            price_change = (next_state["price"] - current["price"]) / current["price"]
            best_action, retro_reward, reward_context = self._retro_score_sample(current, next_state)

            batch.append({
                "state": current,
                "next_state": next_state,
                "price_change": price_change,
                "potential_reward": price_change * 100,
                "best_action": best_action,
                "retro_reward": retro_reward,
                "reward_context": reward_context,
            })

        return batch[:batch_size]

    def export_training_data(self, symbol: str, output_path: Path) -> int:
        """Exporta dados de treinamento para arquivo"""
        states = self.db.get_market_history(symbol, hours=168)
        candles = self.db.get_candles(symbol, "1min", limit=10000)
        trades = self.db.get_recent_trades(symbol, limit=1000, include_dry=True)
        rewards = self.db.get_learning_stats(symbol)

        data = {
            "symbol": symbol,
            "exported_at": datetime.now().isoformat(),
            "market_states": states,
            "candles": candles,
            "trades": trades,
            "learning_stats": rewards
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        total_records = len(states) + len(candles) + len(trades)
        logger.info(f"📤 Exported {total_records} records to {output_path}")
        return total_records

    def import_training_data(self, input_path: Path) -> int:
        """Importa dados de treinamento de arquivo"""
        with open(input_path, "r") as f:
            data = json.load(f)

        symbol = data.get("symbol", "BTC-USDT")
        imported = 0

        candles = data.get("candles", [])
        if candles:
            self.db.store_candles(symbol, "1min", candles)
            imported += len(candles)

        logger.info(f"📥 Imported {imported} records from {input_path}")
        return imported


# ====================== TEST ======================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 50)
    print("📦 Training Database Test (PostgreSQL)")
    print("=" * 50)

    db = TrainingDatabase()

    # Testar registro de trade
    trade_id = db.record_trade(
        symbol="BTC-USDT", side="buy", price=95000.0,
        funds=100.0, dry_run=True
    )
    print(f"✅ Trade recorded: ID={trade_id}")

    # Testar registro de decisão
    decision_id = db.record_decision(
        symbol="BTC-USDT", action="BUY", confidence=0.75,
        price=95000.0, reason="RSI oversold, positive flow"
    )
    print(f"✅ Decision recorded: ID={decision_id}")

    # Testar estado do mercado
    state_id = db.record_market_state(
        symbol="BTC-USDT", price=95000.0,
        rsi=35.0, momentum=1.5,
        orderbook_imbalance=0.3, trade_flow=0.25
    )
    print(f"✅ Market state recorded: ID={state_id}")

    # Testar reward
    db.record_reward(
        symbol="BTC-USDT", state_hash="abc123",
        action=1, reward=0.5, episode=1
    )
    print("✅ Reward recorded")

    # Estatísticas
    stats = db.get_learning_stats("BTC-USDT")
    print(f"\n📊 Learning Stats: {stats}")

    # Performance
    perf = db.calculate_performance("BTC-USDT", days=7)
    print(f"📈 Performance: {perf}")

    # Cleanup teste
    recent = db.get_recent_trades("BTC-USDT", limit=5, include_dry=True)
    print(f"\n📝 Recent trades: {len(recent)}")

    db.close()
    print("\n✅ All tests passed! PostgreSQL backend working.")
