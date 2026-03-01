#!/usr/bin/env python3
"""
Treinamento do Trading Agent via Ollama (GPU)
=============================================
Usa o LLM local (Ollama na GPU RTX 2060 SUPER) para:
1. Analisar padrões de mercado nos candles históricos
2. Gerar rewards inteligentes baseados em análise contextual
3. Otimizar parâmetros do modelo Q-Learning
4. Gerar regras de trading baseadas em análise de preço/volume

Execução: No HOMELAB (192.168.15.2) via SSH
    ssh homelab@192.168.15.2 "cd ~/eddie-auto-dev/btc_trading_agent && \
        DATABASE_URL='postgresql://postgres:eddie_memory_2026@localhost:5433/postgres' \
        python3 train_with_ollama.py"
"""

import os
import sys
import json
import time
import logging
import hashlib
import numpy as np
import psycopg2
import psycopg2.extras
import httpx
import pickle
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ====================== CONFIG ======================
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:eddie_memory_2026@localhost:5433/postgres"
)
SCHEMA = "btc"
MODEL_DIR = Path(__file__).parent / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

ALL_SYMBOLS = ["BTC-USDT", "ETH-USDT", "XRP-USDT", "SOL-USDT", "DOGE-USDT", "ADA-USDT"]

# ====================== OLLAMA CLIENT ======================
class OllamaTrainer:
    """Usa Ollama para análise de mercado e geração de estratégias"""

    def __init__(self, host: str = OLLAMA_HOST, model: str = OLLAMA_MODEL):
        self.host = host.rstrip("/")
        self.model = model
        self.client = httpx.Client(timeout=300.0)
        self._verify_connection()

    def _verify_connection(self):
        """Verifica conectividade com Ollama"""
        try:
            resp = self.client.get(f"{self.host}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            if not any(self.model in m for m in models):
                logger.warning(f"⚠️ Modelo {self.model} não encontrado. Disponíveis: {models}")
            else:
                logger.info(f"✅ Ollama conectado: {self.model} na GPU")
        except Exception as e:
            logger.error(f"❌ Ollama indisponível em {self.host}: {e}")
            sys.exit(1)

    def ask(self, prompt: str, system: str = "", temperature: float = 0.3) -> str:
        """Envia prompt ao Ollama e retorna resposta"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 128,
                "num_ctx": 1024,
            }
        }
        if system:
            payload["system"] = system

        try:
            resp = self.client.post(f"{self.host}/api/generate", json=payload)
            return resp.json().get("response", "")
        except Exception as e:
            logger.error(f"❌ Ollama error: {e}")
            return ""

    def analyze_market_window(self, candles: List[Dict], symbol: str) -> Dict:
        """Analisa uma janela de mercado e retorna análise estruturada"""
        # Preparar dados compactos para o LLM
        prices = [c["close"] for c in candles]
        volumes = [c["volume"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]

        price_change = ((prices[-1] - prices[0]) / prices[0]) * 100
        max_price = max(highs)
        min_price = min(lows)
        avg_volume = sum(volumes) / len(volumes)
        vol_change = ((volumes[-1] - avg_volume) / avg_volume) * 100 if avg_volume > 0 else 0

        # Calcular RSI simples
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        avg_gain = sum(gains) / max(len(gains), 1)
        avg_loss = sum(losses) / max(len(losses), 1)
        rsi = 100 - (100 / (1 + avg_gain / max(avg_loss, 1e-10)))

        # Últimas 10 candles resumidas
        recent = []
        step = max(1, len(candles) // 10)
        for i in range(0, len(candles), step):
            c = candles[i]
            recent.append(f"O:{c['open']:.2f} H:{c['high']:.2f} L:{c['low']:.2f} C:{c['close']:.2f} V:{c['volume']:.0f}")

        prompt = f"""{symbol} {len(candles)}x5min: ${prices[0]:.0f}→${prices[-1]:.0f} ({price_change:+.1f}%) RSI={rsi:.0f} VolChg={vol_change:+.0f}%
JSON only: {{"signal":"BUY/SELL/HOLD","confidence":0.0-1.0,"trend":"bullish/bearish/sideways","reward_multiplier":0.5-2.0}}"""

        system = "Crypto trader. Respond with JSON only, no markdown."

        response = self.ask(prompt, system=system)

        # Parse JSON da resposta
        parsed = None
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(response[json_start:json_end])
        except json.JSONDecodeError:
            pass

        if not parsed:
            parsed = {
                "signal": "HOLD",
                "confidence": 0.5,
                "reason": "parse_error",
                "reward_multiplier": 1.0,
                "trend": "sideways"
            }

        # Sanitizar campos numéricos (Ollama pode retornar null/string)
        return self._sanitize_analysis(parsed)

    @staticmethod
    def _sanitize_analysis(data: Dict) -> Dict:
        """Garante que campos numéricos são float válidos"""
        def safe_float(v, default=0.0):
            if v is None:
                return default
            try:
                return float(v)
            except (ValueError, TypeError):
                return default

        data["confidence"] = safe_float(data.get("confidence"), 0.5)
        data["reward_multiplier"] = safe_float(data.get("reward_multiplier"), 1.0)
        data["support"] = safe_float(data.get("support"), 0.0)
        data["resistance"] = safe_float(data.get("resistance"), 0.0)
        data["optimal_entry"] = safe_float(data.get("optimal_entry"), 0.0)
        data["stop_loss"] = safe_float(data.get("stop_loss"), 0.0)
        data["take_profit"] = safe_float(data.get("take_profit"), 0.0)

        # Garantir signal válido
        if data.get("signal") not in ("BUY", "SELL", "HOLD"):
            data["signal"] = "HOLD"
        if data.get("trend") not in ("bullish", "bearish", "sideways"):
            data["trend"] = "sideways"

        return data

    def generate_trading_rules(self, symbol: str, stats: Dict) -> Dict:
        """Gera regras de trading otimizadas baseadas em estatísticas históricas"""
        prompt = f"""{symbol} stats: {stats.get('total_candles',0)} candles, ${stats.get('price_min',0):.0f}-${stats.get('price_max',0):.0f}, vol={stats.get('avg_volatility',0):.4f}, trend={stats.get('trend_30d','?')}, RSI={stats.get('avg_rsi',50):.0f}
JSON: {{"buy_threshold":0.1-0.5,"sell_threshold":-0.1--0.5,"rsi_oversold":20-35,"rsi_overbought":65-80,"stop_loss_pct":0.5-3.0,"take_profit_pct":1.0-5.0}}"""

        system = "Quant trader. JSON only, no markdown."
        response = self.ask(prompt, system=system, temperature=0.2)

        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(response[json_start:json_end])
                return parsed
        except json.JSONDecodeError:
            pass

        return {
            "buy_threshold": 0.30,
            "sell_threshold": -0.30,
            "min_confidence": 0.45,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 3.0,
        }

    def evaluate_trade_sequence(self, trades: List[Dict], symbol: str) -> Dict:
        """Avalia uma sequência de trades e sugere melhorias"""
        trade_summary = []
        for t in trades[:20]:  # Max 20 trades para caber no contexto
            trade_summary.append(
                f"{t.get('action','?')} @ {t.get('price',0):.2f} "
                f"(conf={t.get('confidence',0):.2f}, reward={t.get('reward',0):.4f})"
            )

        prompt = f"""{symbol} {len(trades)} trades: {chr(10).join(t.get('action','?')+' conf='+str(round(t.get('confidence',0),2)) for t in trades[:10])}
JSON: {{"overall_score":0-10,"adjusted_epsilon":0.05-0.3,"adjusted_learning_rate":0.01-0.2}}"""

        system = "Trading analyst. JSON only."
        response = self.ask(prompt, system=system)

        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(response[json_start:json_end])
        except json.JSONDecodeError:
            pass

        return {"overall_score": 5.0, "adjusted_epsilon": 0.15, "adjusted_learning_rate": 0.1}


# ====================== DATABASE ======================
class TrainingDB:
    """Acesso ao PostgreSQL para dados de treinamento"""

    def __init__(self, dsn: str = DATABASE_URL):
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = True
        self._setup()

    def _setup(self):
        cur = self.conn.cursor()
        cur.execute(f"SET search_path TO {SCHEMA}, public")
        # Tabela para armazenar análises Ollama
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.ollama_analyses (
                id SERIAL PRIMARY KEY,
                timestamp DOUBLE PRECISION NOT NULL,
                symbol TEXT NOT NULL,
                window_start BIGINT,
                window_end BIGINT,
                signal TEXT,
                confidence DOUBLE PRECISION,
                trend TEXT,
                reason TEXT,
                full_analysis JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.ollama_trading_rules (
                id SERIAL PRIMARY KEY,
                symbol TEXT NOT NULL,
                rules JSONB NOT NULL,
                stats JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_ollama_analyses_sym
            ON {SCHEMA}.ollama_analyses(symbol, timestamp)
        """)
        logger.info("✅ Tabelas Ollama criadas/verificadas")

    def get_candle_windows(self, symbol: str, ktype: str = "5min",
                           window_size: int = 100, stride: int = 50,
                           limit: int = 200) -> List[List[Dict]]:
        """Retorna janelas de candles para análise"""
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"""
            SELECT timestamp, open, high, low, close, volume
            FROM {SCHEMA}.candles
            WHERE symbol = %s AND ktype = %s
            ORDER BY timestamp ASC
        """, (symbol, ktype))
        all_candles = [dict(r) for r in cur.fetchall()]

        windows = []
        for i in range(0, len(all_candles) - window_size, stride):
            if len(windows) >= limit:
                break
            windows.append(all_candles[i:i + window_size])

        return windows

    def get_symbol_stats(self, symbol: str) -> Dict:
        """Retorna estatísticas do símbolo"""
        cur = self.conn.cursor()
        cur.execute(f"""
            SELECT
                COUNT(*) as total,
                MIN(close) as price_min,
                MAX(close) as price_max,
                AVG(close) as price_avg,
                AVG(volume) as avg_volume,
                STDDEV(close) / NULLIF(AVG(close), 0) as avg_volatility
            FROM {SCHEMA}.candles
            WHERE symbol = %s AND ktype = '5min'
        """, (symbol,))
        row = cur.fetchone()

        # Trend últimos 30 dias
        cur.execute(f"""
            SELECT close FROM {SCHEMA}.candles
            WHERE symbol = %s AND ktype = '1day'
            ORDER BY timestamp DESC LIMIT 30
        """, (symbol,))
        daily = [r[0] for r in cur.fetchall()]
        trend = "unknown"
        if len(daily) >= 2:
            change = (daily[0] - daily[-1]) / daily[-1] * 100
            if change > 5:
                trend = "bullish"
            elif change < -5:
                trend = "bearish"
            else:
                trend = "sideways"

        # RSI médio
        cur.execute(f"""
            SELECT AVG(rsi) FROM {SCHEMA}.market_states
            WHERE symbol = %s AND rsi IS NOT NULL
        """, (symbol,))
        avg_rsi_row = cur.fetchone()
        avg_rsi = float(avg_rsi_row[0]) if avg_rsi_row and avg_rsi_row[0] else 50.0

        return {
            "total_candles": row[0],
            "price_min": float(row[1]) if row[1] else 0,
            "price_max": float(row[2]) if row[2] else 0,
            "price_avg": float(row[3]) if row[3] else 0,
            "avg_volume": float(row[4]) if row[4] else 0,
            "avg_volatility": float(row[5]) if row[5] else 0,
            "trend_30d": trend,
            "avg_rsi": avg_rsi,
        }

    def store_analysis(self, symbol: str, window_start: int, window_end: int,
                       analysis: Dict):
        """Armazena análise do Ollama no DB"""
        cur = self.conn.cursor()
        conf = analysis.get("confidence")
        conf = float(conf) if conf is not None else 0.5
        cur.execute(f"""
            INSERT INTO {SCHEMA}.ollama_analyses
                (timestamp, symbol, window_start, window_end, signal, confidence,
                 trend, reason, full_analysis)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            time.time(), symbol, window_start, window_end,
            analysis.get("signal", "HOLD"),
            conf,
            analysis.get("trend", "unknown"),
            str(analysis.get("reason", ""))[:500],
            json.dumps(analysis, default=str)
        ))

    def store_rules(self, symbol: str, rules: Dict, stats: Dict):
        """Armazena regras de trading otimizadas"""
        cur = self.conn.cursor()
        cur.execute(f"""
            INSERT INTO {SCHEMA}.ollama_trading_rules (symbol, rules, stats)
            VALUES (%s, %s, %s)
        """, (symbol, json.dumps(rules), json.dumps(stats)))

    def close(self):
        self.conn.close()


# ====================== Q-TABLE UPDATER ======================
class QTableUpdater:
    """Atualiza a Q-table usando rewards gerados pelo Ollama"""

    ACTIONS = {"HOLD": 0, "BUY": 1, "SELL": 2}

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.model_path = MODEL_DIR / f"fast_model_{symbol.replace('-', '_')}.pkl"
        self.q_table = None
        self.n_states = 5000
        self.n_actions = 3
        self.lr = 0.1
        self.gamma = 0.95
        self.episodes = 0
        self._load_model()

    def _load_model(self):
        """Carrega Q-table existente"""
        if self.model_path.exists():
            try:
                with open(self.model_path, "rb") as f:
                    data = pickle.load(f)
                loaded_q = data["q_table"]
                if loaded_q.shape[0] != self.n_states:
                    new_q = np.zeros((self.n_states, self.n_actions))
                    copy_size = min(loaded_q.shape[0], self.n_states)
                    new_q[:copy_size] = loaded_q[:copy_size]
                    self.q_table = new_q
                else:
                    self.q_table = loaded_q
                self.episodes = data.get("episodes", 0)
                logger.info(f"📂 Q-table carregada: {self.symbol} ({self.episodes} episodes)")
            except Exception as e:
                logger.warning(f"⚠️ Falha ao carregar modelo: {e}")
                self.q_table = np.zeros((self.n_states, self.n_actions))
        else:
            self.q_table = np.zeros((self.n_states, self.n_actions))
            logger.info(f"🆕 Nova Q-table: {self.symbol}")

    def _discretize(self, features: np.ndarray) -> int:
        """Converte features em estado discreto"""
        normalized = np.clip(features, -1, 1)
        bins = np.linspace(-1, 1, 10)
        indices = np.digitize(normalized, bins)
        state = 0
        for i, idx in enumerate(indices):
            state += idx * (10 ** i)
        return state % self.n_states

    def _candle_to_features(self, candles: List[Dict], idx: int) -> np.ndarray:
        """Converte candle em features para o Q-table"""
        closes = [c["close"] for c in candles[max(0, idx-30):idx+1]]
        volumes = [c["volume"] for c in candles[max(0, idx-30):idx+1]]

        if len(closes) < 5:
            return np.zeros(8)

        prices = np.array(closes)
        vols = np.array(volumes)

        # RSI
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else np.mean(gains)
        avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else np.mean(losses)
        rsi = 100 - (100 / (1 + avg_gain / max(avg_loss, 1e-10)))

        # Momentum
        if len(prices) >= 10:
            momentum = (prices[-1] - prices[-10]) / prices[-10] * 100
        else:
            momentum = 0

        # Volatilidade
        volatility = float(np.std(prices[-20:]) / np.mean(prices[-20:])) if len(prices) >= 20 else 0

        # Trend
        if len(prices) >= 30:
            sma_short = np.mean(prices[-10:])
            sma_long = np.mean(prices[-30:])
            trend = (sma_short - sma_long) / sma_long
        else:
            trend = 0

        # Volume ratio
        vol_ratio = vols[-1] / max(np.mean(vols), 1e-10) - 1

        return np.array([
            0.0,                    # orderbook_imbalance (N/A para histórico)
            0.0,                    # trade_flow (N/A)
            (rsi - 50) / 50,        # RSI normalizado
            momentum / 10,          # Momentum normalizado
            volatility,
            float(trend),
            0.0,                    # Spread (N/A)
            float(vol_ratio)
        ])

    def update_from_ollama(self, candles: List[Dict], analysis: Dict,
                           window_start_idx: int):
        """Atualiza Q-table baseado na análise do Ollama"""
        signal = analysis.get("signal", "HOLD")
        confidence = float(analysis.get("confidence") or 0.5)
        reward_mult = float(analysis.get("reward_multiplier") or 1.0)

        action = self.ACTIONS.get(signal, 0)

        # Processar cada candle na janela com reward ponderado pelo Ollama
        for i in range(window_start_idx + 5, min(window_start_idx + len(candles), len(candles) - 1)):
            features = self._candle_to_features(candles, i)
            next_features = self._candle_to_features(candles, i + 1)

            if np.all(features == 0) or np.all(next_features == 0):
                continue

            state = self._discretize(features)
            next_state = self._discretize(next_features)

            # Reward baseado na variação de preço + multiplicador Ollama
            price_change = (candles[i+1]["close"] - candles[i]["close"]) / candles[i]["close"]

            if signal == "BUY":
                reward = price_change * 100 * reward_mult * confidence
            elif signal == "SELL":
                reward = -price_change * 100 * reward_mult * confidence
            else:
                reward = -abs(price_change) * 10 * reward_mult  # Penalidade por HOLD em mercado volátil

            # Q-Learning update
            best_next = float(np.max(self.q_table[next_state]))
            td_target = float(reward) + self.gamma * best_next
            td_error = td_target - float(self.q_table[state, action])
            self.q_table[state, action] += self.lr * td_error

            self.episodes += 1

    def save(self):
        """Salva Q-table atualizada"""
        action_counts = np.sum(self.q_table != 0, axis=0)
        data = {
            "q_table": self.q_table,
            "action_counts": action_counts.astype(float),
            "total_reward": float(np.sum(self.q_table)),
            "episodes": self.episodes,
            "params": {
                "n_states": self.n_states,
                "n_actions": self.n_actions,
                "lr": self.lr,
                "gamma": self.gamma,
                "epsilon": 0.15
            }
        }
        with open(self.model_path, "wb") as f:
            pickle.dump(data, f)
        logger.info(f"💾 Q-table salva: {self.symbol} ({self.episodes} episodes)")


# ====================== MAIN TRAINING PIPELINE ======================
def train_symbol_with_ollama(ollama: OllamaTrainer, db: TrainingDB,
                              symbol: str, max_windows: int = 100) -> Dict:
    """Pipeline completo de treinamento para um símbolo"""
    logger.info(f"\n{'='*60}")
    logger.info(f"🎯 TREINAMENTO OLLAMA: {symbol}")
    logger.info(f"{'='*60}")

    start = time.time()
    results = {"symbol": symbol, "analyses": 0, "errors": 0}

    # 1. Obter estatísticas do símbolo
    stats = db.get_symbol_stats(symbol)
    logger.info(f"📊 Stats: {stats['total_candles']:,} candles, "
                f"${stats['price_min']:.2f}-${stats['price_max']:.2f}, "
                f"trend={stats['trend_30d']}")

    # 2. Gerar regras otimizadas via Ollama
    logger.info("🧠 Gerando regras de trading otimizadas via Ollama...")
    rules = ollama.generate_trading_rules(symbol, stats)
    db.store_rules(symbol, rules, stats)
    logger.info(f"📋 Regras: {json.dumps(rules, indent=2)[:200]}...")
    results["rules"] = rules

    # 3. Obter janelas de candles para análise
    windows = db.get_candle_windows(symbol, window_size=100, stride=50,
                                     limit=max_windows)
    logger.info(f"📦 {len(windows)} janelas de 100 candles para análise")

    # 4. Carregar Q-table
    updater = QTableUpdater(symbol)

    # 5. Analisar cada janela com Ollama e atualizar Q-table
    all_candles_flat = []
    seen = set()
    for w in windows:
        for c in w:
            key = (c["timestamp"], c["close"])
            if key not in seen:
                seen.add(key)
                all_candles_flat.append(c)
    all_candles_flat.sort(key=lambda x: x["timestamp"])

    analyses = []
    for i, window in enumerate(windows):
        try:
            analysis = ollama.analyze_market_window(window, symbol)
            
            # Armazenar no DB
            db.store_analysis(
                symbol,
                int(window[0]["timestamp"]),
                int(window[-1]["timestamp"]),
                analysis
            )

            # Atualizar Q-table
            # Encontrar índice do início da janela nos candles flat
            start_ts = window[0]["timestamp"]
            start_idx = next(
                (j for j, c in enumerate(all_candles_flat) if c["timestamp"] == start_ts),
                None
            )
            if start_idx is not None:
                updater.update_from_ollama(all_candles_flat, analysis, start_idx)

            analyses.append(analysis)
            results["analyses"] += 1

            signal = analysis.get("signal", "?")
            conf = analysis.get("confidence", 0)
            trend = analysis.get("trend", "?")

            if (i + 1) % 10 == 0 or i == 0:
                logger.info(
                    f"  [{i+1}/{len(windows)}] {signal} (conf={conf:.2f}, "
                    f"trend={trend}) | Episodes: {updater.episodes:,}"
                )

        except Exception as e:
            results["errors"] += 1
            logger.warning(f"  ⚠️ Window {i+1} error: {e}")

    # 6. Salvar Q-table atualizada
    updater.save()

    # 7. Avaliação final via Ollama
    if analyses:
        trade_sequence = [
            {"action": a.get("signal", "HOLD"),
             "price": 0,
             "confidence": a.get("confidence", 0),
             "reward": a.get("reward_multiplier", 1.0)}
            for a in analyses
        ]
        evaluation = ollama.evaluate_trade_sequence(trade_sequence, symbol)
        results["evaluation"] = evaluation
        logger.info(f"📈 Score final: {evaluation.get('overall_score', 'N/A')}/10")
        logger.info(f"   Pontos fortes: {evaluation.get('strengths', [])}")
        logger.info(f"   Melhorias: {evaluation.get('improvements', [])}")

    # 8. Estatísticas
    elapsed = time.time() - start
    signal_counts = {}
    for a in analyses:
        s = a.get("signal", "HOLD")
        signal_counts[s] = signal_counts.get(s, 0) + 1

    results["elapsed_sec"] = elapsed
    results["signal_distribution"] = signal_counts
    results["final_episodes"] = updater.episodes

    logger.info(f"\n✅ {symbol} concluído em {elapsed:.1f}s")
    logger.info(f"   Análises: {results['analyses']}, Erros: {results['errors']}")
    logger.info(f"   Sinais: {signal_counts}")
    logger.info(f"   Episodes Q-table: {updater.episodes:,}")

    return results


def main():
    print("\n" + "=" * 70)
    print("🧠 TREINAMENTO VIA OLLAMA (GPU)")
    print(f"   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Ollama: {OLLAMA_HOST} | Modelo: {OLLAMA_MODEL}")
    print("=" * 70)

    # Parse args
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=ALL_SYMBOLS)
    parser.add_argument("--max-windows", type=int, default=100,
                        help="Max janelas por símbolo (default: 100)")
    parser.add_argument("--model", default=OLLAMA_MODEL)
    args = parser.parse_args()

    # Conectar
    ollama = OllamaTrainer(model=args.model)
    db = TrainingDB()

    all_results = {}
    total_start = time.time()

    for symbol in args.symbols:
        try:
            result = train_symbol_with_ollama(ollama, db, symbol,
                                              max_windows=args.max_windows)
            all_results[symbol] = result
        except Exception as e:
            logger.error(f"❌ Erro em {symbol}: {e}")
            all_results[symbol] = {"error": str(e)}

    total_elapsed = time.time() - total_start

    # Resumo final
    print("\n" + "=" * 70)
    print("📊 RESUMO DO TREINAMENTO OLLAMA")
    print("=" * 70)
    for symbol, result in all_results.items():
        if "error" in result:
            print(f"  ❌ {symbol}: {result['error']}")
        else:
            print(f"  ✅ {symbol}: {result['analyses']} análises, "
                  f"{result.get('final_episodes', 0):,} episodes, "
                  f"{result.get('elapsed_sec', 0):.1f}s")
            if "evaluation" in result:
                print(f"     Score: {result['evaluation'].get('overall_score', 'N/A')}/10")
    print(f"\n⏱️  Tempo total: {total_elapsed:.1f}s ({total_elapsed/60:.1f}min)")
    print("=" * 70)

    # Salvar resultado completo
    result_path = MODEL_DIR / "ollama_training_result.json"
    with open(result_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"📁 Resultado salvo em: {result_path}")

    db.close()


if __name__ == "__main__":
    main()
