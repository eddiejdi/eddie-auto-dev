#!/usr/bin/env python3
"""
Training Database - Sistema de Armazenamento e Treinamento do Agente
Gerencia histórico de trades, recompensas e estatísticas de aprendizado
"""

import sqlite3
import os
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# ====================== CONFIGURAÇÃO ======================
# Allow overriding DB path via environment for single canonical DB
# Prefer `BTC_DB_PATH`, fallback to `TRAINING_DB_PATH`. If not set,
# use the repo-local `data/trading_agent.db`.
env_db = os.getenv("BTC_DB_PATH") or os.getenv("TRAINING_DB_PATH")
if env_db:
    DB_PATH = Path(env_db).expanduser().resolve()
    DB_DIR = DB_PATH.parent
    DB_DIR.mkdir(parents=True, exist_ok=True)
else:
    DB_DIR = Path(__file__).parent / "data"
    DB_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH = DB_DIR / "trading_agent.db"

# ====================== DATABASE MANAGER ======================
class TrainingDatabase:
    """Gerenciador do banco de dados de treinamento"""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    @contextmanager
    def _get_conn(self):
        """Context manager para conexões

        Ensures `WAL` mode is enabled for better concurrency and durability.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            # Enable WAL for improved concurrency (idempotent)
            # If any of these PRAGMA statements fail, allow the exception to
            # propagate so callers can observe and handle it (no silent fallback).
            conn.execute("PRAGMA journal_mode=WAL;")
            # Enable foreign keys, reasonable synchronous, and busy timeout to
            # reduce locking and improve durability. These are safe defaults.
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_db(self):
        """Inicializa tabelas do banco"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # Tabela de trades executados
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    size REAL,
                    funds REAL,
                    order_id TEXT,
                    status TEXT DEFAULT 'executed',
                    pnl REAL,
                    pnl_pct REAL,
                    dry_run INTEGER DEFAULT 0,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabela de decisões do modelo
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    price REAL NOT NULL,
                    reason TEXT,
                    executed INTEGER DEFAULT 0,
                    trade_id INTEGER,
                    features TEXT,
                    FOREIGN KEY (trade_id) REFERENCES trades(id)
                )
            """)
            
            # Tabela de estados do mercado (para replay)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    bid REAL,
                    ask REAL,
                    spread REAL,
                    orderbook_imbalance REAL,
                    trade_flow REAL,
                    rsi REAL,
                    momentum REAL,
                    volatility REAL,
                    trend REAL,
                    volume REAL
                )
            """)
            
            # Tabela de Q-learning rewards
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learning_rewards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    symbol TEXT NOT NULL,
                    state_hash TEXT NOT NULL,
                    action INTEGER NOT NULL,
                    reward REAL NOT NULL,
                    next_state_hash TEXT,
                    episode INTEGER DEFAULT 0
                )
            """)
            
            # Tabela de estatísticas de performance
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    symbol TEXT NOT NULL,
                    period TEXT NOT NULL,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    sharpe_ratio REAL,
                    win_rate REAL,
                    avg_trade_pnl REAL,
                    metadata TEXT
                )
            """)
            
            # Tabela de candles para backtesting
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS candles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    ktype TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    UNIQUE(timestamp, symbol, ktype)
                )
            """)
            
            # Índices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_states_timestamp ON market_states(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_candles_lookup ON candles(symbol, ktype, timestamp)")
            
            conn.commit()
            logger.info(f"✅ Database initialized: {self.db_path}")
    
    # ====================== TRADES ======================
    def record_trade(self, symbol: str, side: str, price: float,
                    size: float = None, funds: float = None,
                    order_id: str = None, dry_run: bool = False,
                    metadata: Dict = None) -> int:
        """Registra um trade executado"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            logger.info(
                "Writing trade to DB %s: symbol=%s side=%s price=%s size=%s funds=%s dry_run=%s metadata=%s",
                self.db_path, symbol, side, price, size, funds, dry_run, metadata,
            )
            cursor.execute("""
                INSERT INTO trades (timestamp, symbol, side, price, size, funds,
                                   order_id, dry_run, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                time.time(), symbol, side, price, size, funds,
                order_id, 1 if dry_run else 0,
                json.dumps(metadata) if metadata else None
            ))
            trade_id = cursor.lastrowid
            logger.debug("Trade recorded id=%s", trade_id)
            return trade_id
    
    def update_trade_pnl(self, trade_id: int, pnl: float, pnl_pct: float):
        """Atualiza PnL de um trade"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE trades SET pnl = ?, pnl_pct = ? WHERE id = ?
            """, (pnl, pnl_pct, trade_id))
    
    def get_recent_trades(self, symbol: str = None, limit: int = 100,
                         include_dry: bool = False) -> List[Dict]:
        """Obtém trades recentes"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM trades WHERE 1=1"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if not include_dry:
                query += " AND dry_run = 0"
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    # ====================== DECISIONS ======================
    def record_decision(self, symbol: str, action: str, confidence: float,
                       price: float, reason: str = None, features: Dict = None) -> int:
        """Registra uma decisão do modelo"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO decisions (timestamp, symbol, action, confidence,
                                      price, reason, features)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                time.time(), symbol, action, confidence, price, reason,
                json.dumps(features) if features else None
            ))
            return cursor.lastrowid
    
    def mark_decision_executed(self, decision_id: int, trade_id: int):
        """Marca decisão como executada"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE decisions SET executed = 1, trade_id = ? WHERE id = ?
            """, (trade_id, decision_id))
    
    # ====================== MARKET STATES ======================
    def record_market_state(self, symbol: str, price: float, **kwargs) -> int:
        """Registra estado do mercado"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO market_states (timestamp, symbol, price, bid, ask,
                    spread, orderbook_imbalance, trade_flow, rsi, momentum,
                    volatility, trend, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                time.time(), symbol, price,
                kwargs.get("bid"), kwargs.get("ask"), kwargs.get("spread"),
                kwargs.get("orderbook_imbalance"), kwargs.get("trade_flow"),
                kwargs.get("rsi"), kwargs.get("momentum"),
                kwargs.get("volatility"), kwargs.get("trend"),
                kwargs.get("volume")
            ))
            return cursor.lastrowid
    
    def get_market_history(self, symbol: str, hours: int = 24,
                          limit: int = 1000) -> List[Dict]:
        """Obtém histórico de estados do mercado"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cutoff = time.time() - (hours * 3600)
            
            cursor.execute("""
                SELECT * FROM market_states
                WHERE symbol = ? AND timestamp > ?
                ORDER BY timestamp ASC
                LIMIT ?
            """, (symbol, cutoff, limit))
            
            return [dict(row) for row in cursor.fetchall()]
    
    # ====================== LEARNING REWARDS ======================
    def record_reward(self, symbol: str, state_hash: str, action: int,
                     reward: float, next_state_hash: str = None,
                     episode: int = 0):
        """Registra reward para Q-learning"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO learning_rewards (timestamp, symbol, state_hash,
                    action, reward, next_state_hash, episode)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (time.time(), symbol, state_hash, action, reward,
                  next_state_hash, episode))
    
    def get_learning_stats(self, symbol: str) -> Dict:
        """Estatísticas de aprendizado"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_episodes,
                    SUM(reward) as total_reward,
                    AVG(reward) as avg_reward,
                    MAX(reward) as max_reward,
                    MIN(reward) as min_reward,
                    SUM(CASE WHEN action = 0 THEN 1 ELSE 0 END) as hold_count,
                    SUM(CASE WHEN action = 1 THEN 1 ELSE 0 END) as buy_count,
                    SUM(CASE WHEN action = 2 THEN 1 ELSE 0 END) as sell_count
                FROM learning_rewards
                WHERE symbol = ?
            """, (symbol,))
            
            row = cursor.fetchone()
            return dict(row) if row else {}
    
    # ====================== CANDLES ======================
    def store_candles(self, symbol: str, ktype: str, candles: List[Dict]):
        """Armazena candles para backtesting"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            for c in candles:
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO candles 
                        (timestamp, symbol, ktype, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        c["timestamp"], symbol, ktype,
                        c["open"], c["high"], c["low"], c["close"], c["volume"]
                    ))
                except Exception as e:
                    logger.warning(f"⚠️ Failed to store candle: {e}")
    
    def get_candles(self, symbol: str, ktype: str = "1min",
                   start_ts: int = None, end_ts: int = None,
                   limit: int = 1000) -> List[Dict]:
        """Obtém candles armazenados"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM candles WHERE symbol = ? AND ktype = ?"
            params = [symbol, ktype]
            
            if start_ts:
                query += " AND timestamp >= ?"
                params.append(start_ts)
            if end_ts:
                query += " AND timestamp <= ?"
                params.append(end_ts)
            
            query += " ORDER BY timestamp ASC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    # ====================== PERFORMANCE ======================
    def calculate_performance(self, symbol: str, days: int = 7) -> Dict:
        """Calcula métricas de performance"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cutoff = time.time() - (days * 86400)
            
            # Buscar trades do período
            cursor.execute("""
                SELECT * FROM trades
                WHERE symbol = ? AND timestamp > ? AND dry_run = 0
                ORDER BY timestamp ASC
            """, (symbol, cutoff))
            
            trades = [dict(row) for row in cursor.fetchall()]
            
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
        days = {"1h": 1/24, "4h": 4/24, "1d": 1, "7d": 7, "30d": 30}.get(period, 1)
        stats = self.calculate_performance(symbol, int(days) or 1)
        
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO performance_stats 
                (timestamp, symbol, period, total_trades, winning_trades,
                 total_pnl, win_rate, avg_trade_pnl)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                time.time(), symbol, period,
                stats["total_trades"], stats["winning_trades"],
                stats["total_pnl"], stats["win_rate"], stats["avg_pnl"]
            ))
    
    # ====================== CLEANUP ======================
    def cleanup_old_data(self, days: int = 30):
        """Remove dados antigos"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cutoff = time.time() - (days * 86400)
            
            cursor.execute("DELETE FROM market_states WHERE timestamp < ?", (cutoff,))
            cursor.execute("DELETE FROM learning_rewards WHERE timestamp < ?", (cutoff,))
            
            deleted = cursor.rowcount
            logger.info(f"🧹 Cleaned up {deleted} old records")

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
            
            # Calcular reward baseado em movimento de preço
            price_change = (next_state["price"] - current["price"]) / current["price"]
            
            batch.append({
                "state": current,
                "next_state": next_state,
                "price_change": price_change,
                "potential_reward": price_change * 100  # Em %
            })
        
        return batch[:batch_size]
    
    def export_training_data(self, symbol: str, output_path: Path) -> int:
        """Exporta dados de treinamento para arquivo"""
        states = self.db.get_market_history(symbol, hours=168)  # 7 dias
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
            json.dump(data, f, indent=2)
        
        total_records = len(states) + len(candles) + len(trades)
        logger.info(f"📤 Exported {total_records} records to {output_path}")
        return total_records
    
    def import_training_data(self, input_path: Path) -> int:
        """Importa dados de treinamento de arquivo"""
        with open(input_path, "r") as f:
            data = json.load(f)
        
        symbol = data.get("symbol", "BTC-USDT")
        imported = 0
        
        # Importar candles
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
    print("📦 Training Database Test")
    print("=" * 50)
    
    db = TrainingDatabase()
    
    # Testar registro de trade
    trade_id = db.record_trade(
        symbol="BTC-USDT",
        side="buy",
        price=95000.0,
        funds=100.0,
        dry_run=True
    )
    print(f"✅ Trade recorded: ID={trade_id}")
    
    # Testar registro de decisão
    decision_id = db.record_decision(
        symbol="BTC-USDT",
        action="BUY",
        confidence=0.75,
        price=95000.0,
        reason="RSI oversold, positive flow"
    )
    print(f"✅ Decision recorded: ID={decision_id}")
    
    # Testar estado do mercado
    state_id = db.record_market_state(
        symbol="BTC-USDT",
        price=95000.0,
        rsi=35.0,
        momentum=1.5,
        orderbook_imbalance=0.3,
        trade_flow=0.25
    )
    print(f"✅ Market state recorded: ID={state_id}")
    
    # Testar reward
    db.record_reward(
        symbol="BTC-USDT",
        state_hash="abc123",
        action=1,
        reward=0.5,
        episode=1
    )
    print("✅ Reward recorded")
    
    # Estatísticas
    stats = db.get_learning_stats("BTC-USDT")
    print(f"\n📊 Learning Stats: {stats}")
    
    # Performance
    perf = db.calculate_performance("BTC-USDT", days=7)
    print(f"📈 Performance: {perf}")
    
    print("\n✅ Database test complete!")
