#!/usr/bin/env python3
"""
KuCoin Full Data Importer → PostgreSQL
Importa dados históricos completos de candles da KuCoin para todas as 6 moedas
e múltiplos timeframes, depois executa o treinamento do trading agent.

Uso:
    python3 import_kucoin_data.py                  # Import + treinar
    python3 import_kucoin_data.py --import-only     # Só importar
    python3 import_kucoin_data.py --train-only      # Só treinar (com dados existentes)
    python3 import_kucoin_data.py --days 90          # Importar últimos 90 dias
    python3 import_kucoin_data.py --symbols BTC-USDT ETH-USDT  # Moedas específicas
"""

import os
import sys
import time
import json
import logging
import argparse
import requests
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

# Adicionar diretório ao path
sys.path.insert(0, str(Path(__file__).parent))

import psycopg2
import psycopg2.extras
import psycopg2.pool

# ====================== CONFIGURAÇÃO ======================
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "import_kucoin.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

KUCOIN_BASE = os.getenv("KUCOIN_BASE", "https://api.kucoin.com").rstrip("/")

# PostgreSQL — homelab
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/postgres"
)
SCHEMA = "btc"

# Moedas suportadas
ALL_SYMBOLS = [
    "BTC-USDT", "ETH-USDT", "XRP-USDT",
    "SOL-USDT", "DOGE-USDT", "ADA-USDT"
]

# Timeframes para importar (KuCoin ktype → intervalo em segundos)
TIMEFRAMES = {
    "1min":   60,
    "5min":   300,
    "15min":  900,
    "1hour":  3600,
    "4hour":  14400,
    "1day":   86400,
}

# Max candles por request KuCoin
MAX_CANDLES_PER_REQUEST = 1500

# Rate limiting
MIN_REQUEST_INTERVAL = 0.15  # 150ms entre requests


# ====================== DATABASE ======================
class ImportDatabase:
    """Gerencia conexões e inserções no PostgreSQL"""

    def __init__(self, dsn: str = None):
        self.dsn = dsn or DATABASE_URL
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1, maxconn=3, dsn=self.dsn
        )
        self._ensure_tables()

    def close(self):
        if self._pool:
            self._pool.closeall()

    def _get_conn(self):
        conn = self._pool.getconn()
        conn.autocommit = True
        return conn

    def _put_conn(self, conn):
        self._pool.putconn(conn)

    def _ensure_tables(self):
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

            # Tabela de candles (mesma do training_db.py)
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
                    turnover DOUBLE PRECISION DEFAULT 0,
                    UNIQUE(timestamp, symbol, ktype)
                )
            """)

            # Índice para lookups rápidos
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_candles_symbol_ktype_ts
                ON {SCHEMA}.candles(symbol, ktype, timestamp)
            """)

            # Tabela de market_states (para treinamento)
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
                CREATE INDEX IF NOT EXISTS idx_market_states_sym_ts
                ON {SCHEMA}.market_states(symbol, timestamp)
            """)

            # Tabela de learning_rewards
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

            logger.info("✅ Tabelas verificadas/criadas no PostgreSQL")
        finally:
            self._put_conn(conn)

    def get_latest_candle_ts(self, symbol: str, ktype: str) -> Optional[int]:
        """Retorna o timestamp da candle mais recente para continuar de onde parou"""
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            cur.execute(f"""
                SELECT MAX(timestamp) FROM {SCHEMA}.candles
                WHERE symbol = %s AND ktype = %s
            """, (symbol, ktype))
            row = cur.fetchone()
            return row[0] if row and row[0] else None
        finally:
            self._put_conn(conn)

    def store_candles_batch(self, symbol: str, ktype: str,
                            candles: List[Dict]) -> int:
        """Insere candles em batch (ON CONFLICT DO NOTHING para idempotência).
        Chunks de 2000 para evitar timeout em redes lentas."""
        if not candles:
            return 0

        total_stored = 0
        CHUNK = 2000

        for i in range(0, len(candles), CHUNK):
            chunk = candles[i:i+CHUNK]
            conn = self._get_conn()
            try:
                cur = conn.cursor()
                batch = []
                for c in chunk:
                    batch.append((
                        c["timestamp"], symbol, ktype,
                        c["open"], c["high"], c["low"], c["close"],
                        c["volume"], c.get("turnover", 0)
                    ))

                psycopg2.extras.execute_batch(cur, f"""
                    INSERT INTO {SCHEMA}.candles
                        (timestamp, symbol, ktype, open, high, low, close, volume, turnover)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (timestamp, symbol, ktype) DO NOTHING
                """, batch, page_size=500)

                total_stored += len(batch)
                if i > 0 and i % 10000 == 0:
                    logger.info(f"  💾 Stored {total_stored}/{len(candles)} candles...")
            finally:
                self._put_conn(conn)

        return total_stored

    def get_candle_count(self, symbol: str = None, ktype: str = None) -> int:
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            query = f"SELECT count(*) FROM {SCHEMA}.candles WHERE 1=1"
            params = []
            if symbol:
                query += " AND symbol = %s"
                params.append(symbol)
            if ktype:
                query += " AND ktype = %s"
                params.append(ktype)
            cur.execute(query, params)
            return cur.fetchone()[0]
        finally:
            self._put_conn(conn)

    def get_candles_for_training(self, symbol: str, ktype: str = "1min",
                                 limit: int = 50000) -> List[Dict]:
        """Busca candles para treinamento"""
        conn = self._get_conn()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(f"""
                SELECT timestamp, open, high, low, close, volume, turnover
                FROM {SCHEMA}.candles
                WHERE symbol = %s AND ktype = %s
                ORDER BY timestamp ASC
                LIMIT %s
            """, (symbol, ktype, limit))
            return [dict(row) for row in cur.fetchall()]
        finally:
            self._put_conn(conn)

    def store_market_states_batch(self, states: List[Dict]) -> int:
        """Insere market_states derivados de candles"""
        if not states:
            return 0
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            batch = []
            for s in states:
                batch.append((
                    s["timestamp"], s["symbol"], s["price"],
                    s.get("bid"), s.get("ask"), s.get("spread"),
                    s.get("orderbook_imbalance"), s.get("trade_flow"),
                    s.get("rsi"), s.get("momentum"),
                    s.get("volatility"), s.get("trend"),
                    s.get("volume")
                ))
            psycopg2.extras.execute_batch(cur, f"""
                INSERT INTO {SCHEMA}.market_states
                    (timestamp, symbol, price, bid, ask, spread,
                     orderbook_imbalance, trade_flow, rsi, momentum,
                     volatility, trend, volume)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, batch, page_size=500)
            return len(batch)
        finally:
            self._put_conn(conn)

    def store_learning_rewards_batch(self, rewards: List[Dict]) -> int:
        if not rewards:
            return 0
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            batch = []
            for r in rewards:
                batch.append((
                    float(r["timestamp"]), r["symbol"], str(r["state_hash"]),
                    int(r["action"]), float(r["reward"]),
                    str(r.get("next_state_hash")) if r.get("next_state_hash") else None,
                    int(r.get("episode", 0))
                ))
            psycopg2.extras.execute_batch(cur, f"""
                INSERT INTO {SCHEMA}.learning_rewards
                    (timestamp, symbol, state_hash, action, reward, next_state_hash, episode)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, batch, page_size=500)
            return len(batch)
        finally:
            self._put_conn(conn)

    def get_summary(self) -> Dict:
        """Resumo geral de dados no banco"""
        conn = self._get_conn()
        try:
            cur = conn.cursor()
            summary = {}

            cur.execute(f"""
                SELECT symbol, ktype, count(*), min(timestamp), max(timestamp)
                FROM {SCHEMA}.candles
                GROUP BY symbol, ktype
                ORDER BY symbol, ktype
            """)
            candle_stats = []
            for row in cur.fetchall():
                candle_stats.append({
                    "symbol": row[0], "ktype": row[1], "count": row[2],
                    "from": datetime.fromtimestamp(row[3]).strftime("%Y-%m-%d") if row[3] else "?",
                    "to": datetime.fromtimestamp(row[4]).strftime("%Y-%m-%d") if row[4] else "?"
                })
            summary["candles"] = candle_stats

            cur.execute(f"SELECT count(*) FROM {SCHEMA}.market_states")
            summary["market_states"] = cur.fetchone()[0]

            cur.execute(f"SELECT count(*) FROM {SCHEMA}.learning_rewards")
            summary["learning_rewards"] = cur.fetchone()[0]

            return summary
        finally:
            self._put_conn(conn)


# ====================== KUCOIN FETCHER ======================
class KuCoinFetcher:
    """Busca dados da API KuCoin com paginação e rate limiting"""

    def __init__(self):
        self._last_request = 0
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "eddie-trading-agent/1.0"})

    def _rate_limit(self):
        now = time.time()
        elapsed = now - self._last_request
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self._last_request = time.time()

    def fetch_candles(self, symbol: str, ktype: str,
                      start_ts: int, end_ts: int) -> List[Dict]:
        """Busca candles de um período específico (max 1500)"""
        url = (
            f"{KUCOIN_BASE}/api/v1/market/candles"
            f"?type={ktype}&symbol={symbol}"
            f"&startAt={start_ts}&endAt={end_ts}"
        )

        self._rate_limit()
        try:
            r = self._session.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()

            if data.get("code") != "200000":
                logger.warning(f"⚠️ API error: {data.get('msg', 'unknown')}")
                return []

            raw = data.get("data", [])
            candles = []
            for c in raw:
                if len(c) >= 7:
                    candles.append({
                        "timestamp": int(c[0]),
                        "open": float(c[1]),
                        "close": float(c[2]),
                        "high": float(c[3]),
                        "low": float(c[4]),
                        "volume": float(c[5]),
                        "turnover": float(c[6])
                    })

            return candles

        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ Request error ({symbol}/{ktype}): {e}")
            return []

    def fetch_all_candles(self, symbol: str, ktype: str,
                          days: int = 365,
                          resume_from: int = None) -> Tuple[int, int]:
        """
        Busca TODAS as candles históricas com paginação automática.
        Retorna (total_fetched, total_stored).
        """
        interval_sec = TIMEFRAMES[ktype]
        now = int(time.time())

        # Ponto de partida: resume ou N dias atrás
        if resume_from:
            start = resume_from + interval_sec  # Não repetir última candle
            logger.info(f"📌 Resuming {symbol}/{ktype} from {datetime.fromtimestamp(start).strftime('%Y-%m-%d %H:%M')}")
        else:
            start = now - (days * 86400)
            logger.info(f"📥 Fetching {symbol}/{ktype} from {datetime.fromtimestamp(start).strftime('%Y-%m-%d')}")

        all_candles = []
        page = 0

        # Paginar de trás para frente (KuCoin retorna mais recentes primeiro)
        # Vamos paginar do start para o now em blocos
        current_start = start
        window = MAX_CANDLES_PER_REQUEST * interval_sec

        while current_start < now:
            current_end = min(current_start + window, now)
            page += 1

            candles = self.fetch_candles(symbol, ktype, current_start, current_end)

            if not candles:
                # Pode não ter dados nesse período, avançar
                current_start = current_end
                continue

            all_candles.extend(candles)
            fetched_count = len(candles)

            # Log progresso
            if page % 10 == 0:
                pct = min(100, (current_start - start) / max(now - start, 1) * 100)
                logger.info(
                    f"  📊 {symbol}/{ktype} page {page}: "
                    f"+{fetched_count} candles ({pct:.0f}% completo, "
                    f"total: {len(all_candles)})"
                )

            current_start = current_end

        # Deduplicar por timestamp
        seen = set()
        unique = []
        for c in all_candles:
            key = c["timestamp"]
            if key not in seen:
                seen.add(key)
                unique.append(c)

        # Ordenar cronologicamente
        unique.sort(key=lambda x: x["timestamp"])

        logger.info(f"✅ {symbol}/{ktype}: {len(unique)} candles únicos fetched")
        return unique


# ====================== INDICADORES TÉCNICOS (offline) ======================
class OfflineIndicators:
    """Calcula indicadores técnicos a partir de arrays de candles"""

    @staticmethod
    def rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
        """RSI vetorizado"""
        deltas = np.diff(closes, prepend=closes[0])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.zeros_like(closes)
        avg_loss = np.zeros_like(closes)

        # SMA inicial
        if len(closes) > period:
            avg_gain[period] = np.mean(gains[1:period+1])
            avg_loss[period] = np.mean(losses[1:period+1])

            # EMA recursivo
            for i in range(period + 1, len(closes)):
                avg_gain[i] = (avg_gain[i-1] * (period-1) + gains[i]) / period
                avg_loss[i] = (avg_loss[i-1] * (period-1) + losses[i]) / period

        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        rsi[:period] = 50  # Default para período insuficiente
        return rsi

    @staticmethod
    def momentum(closes: np.ndarray, period: int = 10) -> np.ndarray:
        """Momentum como % de mudança"""
        mom = np.zeros_like(closes)
        for i in range(period, len(closes)):
            if closes[i - period] > 0:
                mom[i] = ((closes[i] / closes[i - period]) - 1) * 100
        return mom

    @staticmethod
    def volatility(closes: np.ndarray, period: int = 20) -> np.ndarray:
        """Volatilidade (desvio padrão dos retornos)"""
        vol = np.zeros_like(closes)
        for i in range(period, len(closes)):
            window = closes[i-period:i]
            returns = np.diff(window) / (window[:-1] + 1e-10)
            vol[i] = min(np.std(returns) * 100, 1.0)
        return vol

    @staticmethod
    def trend(closes: np.ndarray, short: int = 10, long: int = 30) -> np.ndarray:
        """Trend (diferença de médias móveis)"""
        tr = np.zeros_like(closes)
        for i in range(long, len(closes)):
            sma_short = np.mean(closes[i-short:i])
            sma_long = np.mean(closes[i-long:i])
            diff_pct = ((sma_short / sma_long) - 1) * 100
            tr[i] = np.clip(diff_pct, -1, 1)
        return tr

    @staticmethod
    def ema(closes: np.ndarray, period: int = 20) -> np.ndarray:
        """EMA vetorizada"""
        alpha = 2 / (period + 1)
        result = np.zeros_like(closes)
        result[0] = closes[0]
        for i in range(1, len(closes)):
            result[i] = alpha * closes[i] + (1 - alpha) * result[i-1]
        return result


# ====================== TREINADOR ======================
class AgentTrainer:
    """Treina o modelo Q-Learning usando dados históricos de candles"""

    def __init__(self, db: ImportDatabase):
        self.db = db
        self.indicators = OfflineIndicators()

    def generate_market_states(self, symbol: str, ktype: str = "5min") -> int:
        """Gera market_states a partir de candles e salva no DB"""
        logger.info(f"🧮 Generating market states for {symbol}/{ktype}...")

        candles = self.db.get_candles_for_training(symbol, ktype, limit=100000)
        if len(candles) < 50:
            logger.warning(f"⚠️ {symbol}/{ktype}: poucos candles ({len(candles)})")
            return 0

        closes = np.array([c["close"] for c in candles])
        volumes = np.array([c["volume"] for c in candles])
        timestamps = np.array([c["timestamp"] for c in candles])

        # Calcular indicadores
        rsi_arr = self.indicators.rsi(closes)
        mom_arr = self.indicators.momentum(closes)
        vol_arr = self.indicators.volatility(closes)
        trend_arr = self.indicators.trend(closes)

        # Gerar market_states (converter np.float64 → float nativo para psycopg2)
        states = []
        for i in range(30, len(candles)):  # Skip warm-up
            states.append({
                "timestamp": float(timestamps[i]),
                "symbol": symbol,
                "price": float(closes[i]),
                "rsi": float(rsi_arr[i]),
                "momentum": float(mom_arr[i]),
                "volatility": float(vol_arr[i]),
                "trend": float(trend_arr[i]),
                "volume": float(volumes[i]),
                "orderbook_imbalance": 0.0,
                "trade_flow": 0.0,
            })

        stored = self.db.store_market_states_batch(states)
        logger.info(f"✅ {symbol}/{ktype}: {stored} market_states gerados")
        return stored

    def train_qlearning(self, symbol: str, ktype: str = "5min",
                         epochs: int = 5) -> Dict:
        """Treina modelo Q-Learning com replay offline"""
        from fast_model import FastTradingModel

        logger.info(f"🎓 Training Q-Learning for {symbol} (ktype={ktype}, epochs={epochs})...")

        # Carregar candles
        candles = self.db.get_candles_for_training(symbol, ktype, limit=100000)
        if len(candles) < 100:
            logger.warning(f"⚠️ Insufficient data for {symbol}: {len(candles)} candles")
            return {"error": "insufficient_data", "candles": len(candles)}

        closes = np.array([c["close"] for c in candles])
        volumes = np.array([c["volume"] for c in candles])

        # Calcular indicadores
        rsi_arr = self.indicators.rsi(closes)
        mom_arr = self.indicators.momentum(closes)
        vol_arr = self.indicators.volatility(closes)
        trend_arr = self.indicators.trend(closes)

        # Inicializar modelo
        model = FastTradingModel(symbol)
        logger.info(f"📂 Model loaded: {model.q_model.episodes} episodes anteriores")

        # Training loop
        total_reward = 0.0
        total_samples = 0
        rewards_batch = []
        episode_rewards = []

        for epoch in range(epochs):
            epoch_reward = 0.0
            epoch_samples = 0

            for i in range(31, len(candles) - 1):
                # Features do estado atual
                features = np.array([
                    0.0,  # orderbook_imbalance (não disponível offline)
                    0.0,  # trade_flow
                    (rsi_arr[i] - 50) / 50,
                    mom_arr[i] / 10,
                    vol_arr[i],
                    trend_arr[i],
                    0.0,  # spread em bps
                    (volumes[i] / (np.mean(volumes[max(0,i-20):i]) + 1e-10)) - 1
                ], dtype=np.float32)

                # Features do próximo estado
                next_features = np.array([
                    0.0,
                    0.0,
                    (rsi_arr[i+1] - 50) / 50,
                    mom_arr[i+1] / 10,
                    vol_arr[i+1],
                    trend_arr[i+1],
                    0.0,
                    (volumes[i+1] / (np.mean(volumes[max(0,i-19):i+1]) + 1e-10)) - 1
                ], dtype=np.float32)

                # Variação de preço → melhor ação retrospectiva
                price_change = (closes[i+1] - closes[i]) / closes[i]

                if price_change > 0.001:
                    best_action = 1  # BUY era o correto
                    reward = float(price_change * 50)
                elif price_change < -0.001:
                    best_action = 2  # SELL era o correto
                    reward = float(-price_change * 50)
                else:
                    best_action = 0  # HOLD
                    reward = 0.01

                model.q_model.update(features, best_action, reward, next_features)
                epoch_reward += reward
                epoch_samples += 1

                # Registrar para batch DB (apenas 1o epoch)
                if epoch == 0:
                    state_hash = str(hash(features.tobytes()))[:16]
                    next_hash = str(hash(next_features.tobytes()))[:16]
                    rewards_batch.append({
                        "timestamp": float(candles[i]["timestamp"]),
                        "symbol": symbol,
                        "state_hash": state_hash,
                        "action": best_action,
                        "reward": reward,
                        "next_state_hash": next_hash,
                        "episode": model.q_model.episodes
                    })

            total_reward += epoch_reward
            total_samples += epoch_samples
            episode_rewards.append(epoch_reward)

            logger.info(
                f"  📈 Epoch {epoch+1}/{epochs}: "
                f"samples={epoch_samples}, reward={epoch_reward:.2f}, "
                f"episodes={model.q_model.episodes}"
            )

        # Salvar rewards no DB
        if rewards_batch:
            # Limitar a 10000 para não sobrecarregar
            stored = self.db.store_learning_rewards_batch(rewards_batch[:10000])
            logger.info(f"💾 Stored {stored} learning rewards")

        # Salvar modelo atualizado
        model.save()

        stats = model.get_stats()
        result = {
            "symbol": symbol,
            "ktype": ktype,
            "epochs": epochs,
            "total_samples": total_samples,
            "total_reward": total_reward,
            "avg_reward_per_epoch": total_reward / epochs if epochs > 0 else 0,
            "model_episodes": model.q_model.episodes,
            "action_distribution": stats["action_distribution"],
            "epoch_rewards": episode_rewards
        }

        logger.info(f"✅ Training complete for {symbol}: {json.dumps(result, indent=2, default=str)}")
        return result


# ====================== ORCHESTRATOR ======================
def run_import(db: ImportDatabase, fetcher: KuCoinFetcher,
               symbols: List[str], timeframes: List[str],
               days: int = 365) -> Dict:
    """Executa importação completa de dados"""

    results = {}
    total_candles = 0
    start_time = time.time()

    print("\n" + "=" * 70)
    print("📥 IMPORTAÇÃO DE DADOS KUCOIN → PostgreSQL")
    print("=" * 70)
    print(f"Moedas: {', '.join(symbols)}")
    print(f"Timeframes: {', '.join(timeframes)}")
    print(f"Período: últimos {days} dias")
    print(f"DB: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    print("=" * 70 + "\n")

    for symbol in symbols:
        symbol_results = {}
        symbol_candles = 0

        for ktype in timeframes:
            key = f"{symbol}/{ktype}"
            logger.info(f"📥 [{key}] Iniciando importação...")

            # Verificar se já tem dados (resumir)
            latest = db.get_latest_candle_ts(symbol, ktype)
            if latest:
                existing = db.get_candle_count(symbol, ktype)
                logger.info(f"  📌 {existing} candles existentes, última: {datetime.fromtimestamp(latest).strftime('%Y-%m-%d %H:%M')}")

            # Fetch com paginação
            candles = fetcher.fetch_all_candles(
                symbol, ktype, days=days, resume_from=latest
            )

            if candles:
                stored = db.store_candles_batch(symbol, ktype, candles)
                logger.info(f"  💾 {stored} candles armazenados")
                symbol_candles += stored
            else:
                logger.info(f"  📭 Nenhum candle novo")
                stored = 0

            final_count = db.get_candle_count(symbol, ktype)
            symbol_results[ktype] = {
                "fetched": len(candles),
                "stored": stored,
                "total_in_db": final_count
            }

        results[symbol] = symbol_results
        total_candles += symbol_candles
        logger.info(f"✅ {symbol}: {symbol_candles} novos candles importados")

    elapsed = time.time() - start_time
    logger.info(f"\n📊 IMPORTAÇÃO COMPLETA: {total_candles} candles em {elapsed:.1f}s")

    return results


def run_training(db: ImportDatabase, symbols: List[str],
                 training_ktype: str = "5min",
                 epochs: int = 5) -> Dict:
    """Executa treinamento para todas as moedas"""

    trainer = AgentTrainer(db)
    results = {}
    start_time = time.time()

    print("\n" + "=" * 70)
    print("🎓 TREINAMENTO DO TRADING AGENT")
    print("=" * 70)
    print(f"Moedas: {', '.join(symbols)}")
    print(f"Timeframe de treino: {training_ktype}")
    print(f"Epochs: {epochs}")
    print("=" * 70 + "\n")

    for symbol in symbols:
        logger.info(f"\n{'='*50}")
        logger.info(f"🎓 Treinando {symbol}...")
        logger.info(f"{'='*50}")

        # 1. Gerar market_states a partir dos candles
        states_count = trainer.generate_market_states(symbol, training_ktype)

        # 2. Treinar Q-Learning
        train_result = trainer.train_qlearning(
            symbol, ktype=training_ktype, epochs=epochs
        )

        # 3. Treinar também com 1min para maior granularidade (se disponível)
        candles_1min = db.get_candle_count(symbol, "1min")
        if candles_1min > 500:
            logger.info(f"  🔬 Training also with 1min data ({candles_1min} candles)...")
            train_1min = trainer.train_qlearning(symbol, ktype="1min", epochs=2)
            train_result["1min_training"] = train_1min

        results[symbol] = {
            "market_states_generated": states_count,
            "training": train_result
        }

    elapsed = time.time() - start_time
    logger.info(f"\n🎓 TREINAMENTO COMPLETO em {elapsed:.1f}s")

    return results


# ====================== MAIN ======================
def main():
    parser = argparse.ArgumentParser(description="KuCoin Data Importer + Agent Trainer")
    parser.add_argument("--symbols", nargs="+", default=None,
                        help="Símbolos específicos (ex: BTC-USDT ETH-USDT)")
    parser.add_argument("--timeframes", nargs="+", default=None,
                        help="Timeframes específicos (ex: 1min 5min 1hour)")
    parser.add_argument("--days", type=int, default=365,
                        help="Dias de histórico para importar (default: 365)")
    parser.add_argument("--epochs", type=int, default=5,
                        help="Epochs de treinamento (default: 5)")
    parser.add_argument("--training-ktype", default="5min",
                        help="Timeframe principal para treinamento (default: 5min)")
    parser.add_argument("--import-only", action="store_true",
                        help="Só importar, não treinar")
    parser.add_argument("--train-only", action="store_true",
                        help="Só treinar com dados existentes")
    parser.add_argument("--summary", action="store_true",
                        help="Mostrar resumo dos dados e sair")

    args = parser.parse_args()

    symbols = args.symbols or ALL_SYMBOLS
    timeframes = args.timeframes or list(TIMEFRAMES.keys())

    # Sinalizar estado de processamento
    try:
        os.system("python3 tools/vscode_window_state.py processing --agent-id kucoin-importer 2>/dev/null")
    except:
        pass

    print("\n" + "=" * 70)
    print("🚀 KUCOIN DATA IMPORTER & AGENT TRAINER")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    db = ImportDatabase()

    try:
        if args.summary:
            summary = db.get_summary()
            print("\n📊 RESUMO DOS DADOS NO POSTGRESQL:")
            print("-" * 60)
            for cs in summary.get("candles", []):
                print(f"  {cs['symbol']:12s} {cs['ktype']:8s} → {cs['count']:>8,} candles "
                      f"({cs['from']} → {cs['to']})")
            print(f"\n  Market States: {summary['market_states']:,}")
            print(f"  Learning Rewards: {summary['learning_rewards']:,}")
            return

        import_results = None
        train_results = None

        if not args.train_only:
            fetcher = KuCoinFetcher()
            import_results = run_import(db, fetcher, symbols, timeframes, args.days)

        if not args.import_only:
            train_results = run_training(
                db, symbols,
                training_ktype=args.training_ktype,
                epochs=args.epochs
            )

        # Resumo final
        print("\n" + "=" * 70)
        print("📊 RESUMO FINAL")
        print("=" * 70)

        summary = db.get_summary()
        for cs in summary.get("candles", []):
            print(f"  {cs['symbol']:12s} {cs['ktype']:8s} → {cs['count']:>8,} candles ({cs['from']} → {cs['to']})")
        print(f"\n  Market States: {summary['market_states']:,}")
        print(f"  Learning Rewards: {summary['learning_rewards']:,}")

        if train_results:
            print("\n🎓 RESULTADOS DO TREINAMENTO:")
            print("-" * 60)
            for sym, tr in train_results.items():
                t = tr.get("training", {})
                print(f"  {sym:12s} → episodes: {t.get('model_episodes', 0):,}, "
                      f"reward: {t.get('total_reward', 0):.2f}, "
                      f"samples: {t.get('total_samples', 0):,}")

        # Sinalizar conclusão
        try:
            os.system("python3 tools/vscode_window_state.py done --agent-id kucoin-importer 2>/dev/null")
        except:
            pass

        print("\n✅ PROCESSO COMPLETO!")

    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}", exc_info=True)
        try:
            os.system("python3 tools/vscode_window_state.py error --agent-id kucoin-importer 2>/dev/null")
        except:
            pass
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
