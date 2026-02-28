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

import psycopg2
import psycopg2.extras
import psycopg2.pool

logger = logging.getLogger(__name__)

# ====================== CONFIGURAÇÃO ======================
def _fetch_database_url_from_secrets():
    """Tenta obter DATABASE_URL via Secrets Agent (prioridade), senão usa env var."""
    try:
        from kucoin_api import _fetch_from_secrets_agent
    except Exception:
        _fetch_from_secrets_agent = None

    candidates = [
        ("DATABASE_URL", "password"),
        ("postgres", "dsn"),
        ("database/postgres", "dsn"),
        ("eddie/postgres", "dsn"),
    ]

    if _fetch_from_secrets_agent:
        for name, field in candidates:
            try:
                val = _fetch_from_secrets_agent(name, field)
                if val:
                    return val
            except Exception:
                continue

    # Fallback para variável de ambiente (valor antigo preservado)
    val = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:eddie_memory_2026@172.17.0.2:5432/postgres"
    )
    return val

DATABASE_URL = _fetch_database_url_from_secrets()
print(f"🔧 DEBUG: DATABASE_URL = {DATABASE_URL}")
SCHEMA = "btc"

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

            # Índices
            indices = [
                f"CREATE INDEX IF NOT EXISTS idx_btc_trades_symbol ON {SCHEMA}.trades(symbol)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_trades_timestamp ON {SCHEMA}.trades(timestamp)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_trades_dry_run ON {SCHEMA}.trades(dry_run)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_decisions_timestamp ON {SCHEMA}.decisions(timestamp)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_decisions_symbol ON {SCHEMA}.decisions(symbol)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_market_states_timestamp ON {SCHEMA}.market_states(timestamp)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_market_states_symbol ON {SCHEMA}.market_states(symbol, timestamp)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_candles_lookup ON {SCHEMA}.candles(symbol, ktype, timestamp)",
                f"CREATE INDEX IF NOT EXISTS idx_btc_learning_rewards_symbol ON {SCHEMA}.learning_rewards(symbol)",
            ]
            for idx in indices:
                cur.execute(idx)

            conn.commit()
            logger.info("✅ PostgreSQL schema btc.* initialized")

    # ====================== TRADES ======================
    def record_trade(self, symbol: str, side: str, price: float,
                     size: float = None, funds: float = None,
                     order_id: str = None, dry_run: bool = False,
                     metadata: Dict = None) -> int:
        """Registra um trade executado"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {SCHEMA}.trades
                    (timestamp, symbol, side, price, size, funds,
                     order_id, dry_run, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                time.time(), symbol, side, price, size, funds,
                order_id, dry_run,
                json.dumps(metadata) if metadata else None
            ))
            return cur.fetchone()[0]

    def update_trade_pnl(self, trade_id: int, pnl: float, pnl_pct: float):
        """Atualiza PnL de um trade"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                UPDATE {SCHEMA}.trades SET pnl = %s, pnl_pct = %s WHERE id = %s
            """, (pnl, pnl_pct, trade_id))

    def get_recent_trades(self, symbol: str = None, limit: int = 100,
                          include_dry: bool = False) -> List[Dict]:
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

            query += " ORDER BY timestamp DESC LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    # ====================== DECISIONS ======================
    def record_decision(self, symbol: str, action: str, confidence: float,
                        price: float, reason: str = None,
                        features: Dict = None) -> int:
        """Registra uma decisão do modelo"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {SCHEMA}.decisions
                    (timestamp, symbol, action, confidence, price, reason, features)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                time.time(), symbol, action, confidence, price, reason,
                json.dumps(features) if features else None
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

    # ====================== MARKET STATES ======================
    def record_market_state(self, symbol: str, price: float, **kwargs) -> int:
        """Registra estado do mercado"""
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
                time.time(), symbol, price,
                kwargs.get("bid"), kwargs.get("ask"), kwargs.get("spread"),
                kwargs.get("orderbook_imbalance"), kwargs.get("trade_flow"),
                kwargs.get("rsi"), kwargs.get("momentum"),
                kwargs.get("volatility"), kwargs.get("trend"),
                kwargs.get("volume")
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

            batch.append({
                "state": current,
                "next_state": next_state,
                "price_change": price_change,
                "potential_reward": price_change * 100
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
