#!/usr/bin/env python3
"""
Market RAG (Retrieval-Augmented Generation) — Inteligência de Mercado B3.

Adaptado de btc_trading_agent/market_rag.py para bolsa brasileira (Clear/MT5).

Módulo autônomo que:
  1. Coleta dados de múltiplas fontes e timeframes (via MT5 Bridge)
  2. Armazena snapshots como documentos vetorizados
  3. Recupera padrões similares ao estado atual via busca vetorial
  4. Ajusta dinamicamente os thresholds de bull/bear do modelo

Diferenças do modelo crypto:
  - Horário de mercado B3 (10:00–17:55 BRT, dias úteis)
  - Preços em BRL
  - Sem orderbook profundo (MT5 fornece apenas bid/ask L1)
  - Volatilidade e momentum calibrados para equities
"""
from __future__ import annotations

import json
import logging
import os
import pickle
import shutil
import tempfile
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ====================== CONSTANTES ======================
RAG_DIR = Path(__file__).parent / "data" / "market_rag"
RAG_DIR.mkdir(parents=True, exist_ok=True)

SNAPSHOT_FILE = RAG_DIR / "snapshots.pkl"
INDEX_FILE = RAG_DIR / "index.pkl"
ADJUSTMENTS_FILE = RAG_DIR / "regime_adjustments.json"

# Dimensão do vetor de embedding de mercado
EMBEDDING_DIM = 20

# Intervalo padrão de recalibração (5 minutos)
DEFAULT_RECALIBRATE_INTERVAL = 300

# Máximo de snapshots (30 dias × 8h × 60 snaps/h ≈ 14k)
MAX_SNAPSHOTS = 30_000

# Top-K resultados para busca de similaridade
TOP_K = 20

# Horário B3
BRT = timezone(timedelta(hours=-3))


# ====================== DATA CLASSES ======================
@dataclass
class MarketSnapshot:
    """Snapshot completo do mercado B3 em um instante."""

    timestamp: float
    symbol: str

    # Preço e OHLCV
    price: float
    open_1m: float = 0.0
    high_1m: float = 0.0
    low_1m: float = 0.0
    close_1m: float = 0.0
    volume_1m: float = 0.0

    # Indicadores técnicos
    rsi: float = 50.0
    momentum: float = 0.0
    volatility: float = 0.0
    trend: float = 0.0

    # Spread (L1 apenas — bid/ask do MT5)
    spread: float = 0.0
    spread_pct: float = 0.0

    # Trade flow
    trade_flow: float = 0.0

    # Multi-timeframe
    sma_10: float = 0.0
    sma_30: float = 0.0
    sma_60: float = 0.0
    ema_20: float = 0.0

    # Resultado futuro (preenchido retrospectivamente)
    price_change_5m: Optional[float] = None
    price_change_15m: Optional[float] = None
    price_change_60m: Optional[float] = None
    outcome: Optional[str] = None  # "BULL", "BEAR", "FLAT"

    def to_embedding(self) -> np.ndarray:
        """Converte snapshot para vetor numérico normalizado (20-dim)."""
        raw = np.array([
            (self.rsi - 50.0) / 50.0,
            np.clip(self.momentum / 2.0, -1, 1),
            np.clip(self.volatility * 20, 0, 1),
            np.clip(self.trend, -1, 1),
            np.clip(self.spread_pct * 100, 0, 1),
            np.clip(self.trade_flow, -1, 1),
            # Multi-timeframe: posição relativa do preço
            self._pct_diff(self.price, self.sma_10),
            self._pct_diff(self.price, self.sma_30),
            self._pct_diff(self.price, self.sma_60),
            self._pct_diff(self.price, self.ema_20),
            # OHLCV patterns
            self._pct_diff(self.close_1m, self.open_1m),
            self._safe_ratio(
                self.high_1m - max(self.open_1m, self.close_1m),
                self.high_1m - self.low_1m + 1e-10,
            ),
            self._safe_ratio(
                min(self.open_1m, self.close_1m) - self.low_1m,
                self.high_1m - self.low_1m + 1e-10,
            ),
            np.clip(self.volume_1m / 10_000, 0, 1),
            # Range %
            self._pct_diff(self.high_1m, self.low_1m),
            # Hora do dia (cíclico — B3 10:00-17:55)
            np.sin(2 * np.pi * self._hour_of_day_brt() / 8),
            np.cos(2 * np.pi * self._hour_of_day_brt() / 8),
            # Dia da semana (cíclico — dias úteis)
            np.sin(2 * np.pi * self._day_of_week() / 5),
            # RSI zone
            self._rsi_zone(),
            # Volatility regime
            self._vol_regime(),
        ], dtype=np.float32)
        return raw

    def _safe_ratio(self, a: float, b: float) -> float:
        """Razão segura normalizada para [-1, 1]."""
        total = abs(a) + abs(b)
        if total < 1e-10:
            return 0.0
        return float(np.clip((a - b) / total, -1, 1))

    def _pct_diff(self, a: float, b: float) -> float:
        """Diferença percentual clipada."""
        if b < 1e-10:
            return 0.0
        return float(np.clip(((a / b) - 1) * 100, -5, 5) / 5.0)

    def _hour_of_day_brt(self) -> float:
        """Hora BRT relativa à abertura (0=10h, 8=18h)."""
        dt = datetime.fromtimestamp(self.timestamp, tz=BRT)
        return max(0.0, dt.hour - 10 + dt.minute / 60)

    def _day_of_week(self) -> int:
        """Dia da semana (0=seg, 4=sex)."""
        return datetime.fromtimestamp(self.timestamp, tz=BRT).weekday()

    def _rsi_zone(self) -> float:
        """Zona RSI: -1 (oversold), 0 (neutro), +1 (overbought)."""
        if self.rsi < 30:
            return -1.0
        if self.rsi < 40:
            return -0.5
        if self.rsi > 70:
            return 1.0
        if self.rsi > 60:
            return 0.5
        return 0.0

    def _vol_regime(self) -> float:
        """Regime de volatilidade: -1 (baixa), 0 (normal), +1 (alta)."""
        if self.volatility < 0.005:
            return -1.0
        if self.volatility > 0.03:
            return 1.0
        return 0.0

    def to_dict(self) -> Dict:
        """Serializa para dicionário."""
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "price": self.price,
            "rsi": self.rsi,
            "momentum": self.momentum,
            "volatility": self.volatility,
            "trend": self.trend,
            "spread_pct": self.spread_pct,
            "trade_flow": self.trade_flow,
            "price_change_5m": self.price_change_5m,
            "price_change_15m": self.price_change_15m,
            "price_change_60m": self.price_change_60m,
            "outcome": self.outcome,
        }


@dataclass
class RegimeAdjustment:
    """Ajuste calculado pelo RAG para os thresholds do modelo.

    Inclui trade gating dinâmico controlado pela IA.
    """

    timestamp: float
    symbol: str

    # Thresholds ajustados
    buy_threshold: float = 0.30
    sell_threshold: float = -0.30

    # Pesos ajustados do ensemble
    weight_technical: float = 0.40
    weight_spread: float = 0.25
    weight_flow: float = 0.25
    weight_qlearning: float = 0.10

    # Regime sugerido
    suggested_regime: str = "RANGING"
    regime_confidence: float = 0.0

    # Métricas de base
    similar_count: int = 0
    bull_pct: float = 0.0
    bear_pct: float = 0.0
    flat_pct: float = 0.0
    avg_return_5m: float = 0.0
    avg_return_15m: float = 0.0

    # AI Trade Gating
    ai_min_confidence: float = 0.60
    ai_min_trade_interval: int = 180
    ai_rebuy_lock_enabled: bool = True
    ai_rebuy_margin_pct: float = 0.0
    ai_aggressiveness: float = 0.5

    # AI Buy Target
    ai_buy_target_price: float = 0.0
    ai_buy_target_reason: str = ""

    # AI Take-Profit dinâmico
    ai_take_profit_pct: float = 0.025
    ai_take_profit_reason: str = ""

    # AI Position Sizing
    ai_position_size_pct: float = 0.04
    ai_max_entries: int = 10
    ai_position_size_reason: str = ""

    # Baseline/aplicação
    baseline_min_confidence: float = 0.60
    baseline_min_trade_interval: int = 180
    baseline_max_position_pct: float = 0.50
    baseline_max_positions: int = 3
    applied_min_confidence: float = 0.60
    applied_min_trade_interval: int = 180
    applied_max_position_pct: float = 0.50
    applied_max_positions: int = 3

    # Ollama shadow/apply
    ollama_mode: str = "shadow"
    ollama_last_update: float = 0.0
    ollama_trigger: str = ""
    ollama_model: str = ""
    ollama_reason: str = ""
    ollama_suggested_min_confidence: float = 0.0
    ollama_suggested_min_trade_interval: int = 0
    ollama_suggested_max_position_pct: float = 0.0
    ollama_suggested_max_positions: int = 0

    def to_dict(self) -> Dict:
        """Serializa para dicionário."""
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "buy_threshold": round(self.buy_threshold, 4),
            "sell_threshold": round(self.sell_threshold, 4),
            "weight_technical": round(self.weight_technical, 3),
            "weight_spread": round(self.weight_spread, 3),
            "weight_flow": round(self.weight_flow, 3),
            "weight_qlearning": round(self.weight_qlearning, 3),
            "suggested_regime": self.suggested_regime,
            "regime_confidence": round(self.regime_confidence, 3),
            "similar_count": self.similar_count,
            "bull_pct": round(self.bull_pct, 3),
            "bear_pct": round(self.bear_pct, 3),
            "flat_pct": round(self.flat_pct, 3),
            "avg_return_5m": round(self.avg_return_5m, 5),
            "avg_return_15m": round(self.avg_return_15m, 5),
            "ai_min_confidence": round(self.ai_min_confidence, 3),
            "ai_min_trade_interval": self.ai_min_trade_interval,
            "ai_rebuy_lock_enabled": self.ai_rebuy_lock_enabled,
            "ai_rebuy_margin_pct": round(self.ai_rebuy_margin_pct, 4),
            "ai_aggressiveness": round(self.ai_aggressiveness, 3),
            "ai_buy_target_price": round(self.ai_buy_target_price, 2),
            "ai_buy_target_reason": self.ai_buy_target_reason,
            "ai_take_profit_pct": round(self.ai_take_profit_pct, 5),
            "ai_take_profit_reason": self.ai_take_profit_reason,
            "ai_position_size_pct": round(self.ai_position_size_pct, 4),
            "ai_max_entries": self.ai_max_entries,
            "ai_position_size_reason": self.ai_position_size_reason,
            "applied_min_confidence": round(self.applied_min_confidence, 3),
            "applied_min_trade_interval": self.applied_min_trade_interval,
            "applied_max_position_pct": round(self.applied_max_position_pct, 4),
            "applied_max_positions": self.applied_max_positions,
            "ollama_mode": self.ollama_mode,
        }


# ====================== MOTOR DE BUSCA VETORIAL ======================
class VectorStore:
    """Armazenamento vetorial leve baseado em numpy.

    Usa similaridade de cosseno para busca de vizinhos mais próximos.
    Persiste em disco via pickle com escrita atômica.
    """

    def __init__(self, dim: int = EMBEDDING_DIM, max_size: int = MAX_SNAPSHOTS) -> None:
        self.dim = dim
        self.max_size = max_size
        self._embeddings: np.ndarray = np.empty((0, dim), dtype=np.float32)
        self._metadata: List[Dict] = []
        self._dirty = False

    @property
    def size(self) -> int:
        """Número de vetores armazenados."""
        return len(self._metadata)

    def add(self, embedding: np.ndarray, metadata: Dict) -> None:
        """Adiciona um vetor ao store."""
        vec = embedding.reshape(1, -1).astype(np.float32)
        if self._embeddings.shape[0] == 0:
            self._embeddings = vec
        else:
            self._embeddings = np.vstack([self._embeddings, vec])
        self._metadata.append(metadata)
        self._dirty = True

        if self.size > self.max_size:
            self._embeddings = self._embeddings[-self.max_size:]
            self._metadata = self._metadata[-self.max_size:]

    def search(self, query: np.ndarray, top_k: int = TOP_K) -> List[Tuple[float, Dict]]:
        """Busca os top_k vetores mais similares por cosseno."""
        if self.size == 0:
            return []

        q = query.reshape(1, -1).astype(np.float32)
        q_norm = np.linalg.norm(q, axis=1, keepdims=True) + 1e-10
        e_norms = np.linalg.norm(self._embeddings, axis=1, keepdims=True) + 1e-10

        similarities = (self._embeddings @ q.T).flatten() / (e_norms.flatten() * q_norm.flatten())

        k = min(top_k, self.size)
        top_indices = np.argpartition(similarities, -k)[-k:]
        top_indices = top_indices[np.argsort(similarities[top_indices])[::-1]]

        return [(float(similarities[idx]), self._metadata[idx]) for idx in top_indices]

    def save(self, path: Path = INDEX_FILE) -> None:
        """Persiste o índice em disco com escrita atômica."""
        if not self._dirty:
            return
        data = {
            "embeddings": self._embeddings,
            "metadata": self._metadata,
            "dim": self.dim,
        }
        tmp_fd = None
        tmp_path = None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=path.parent, suffix=".tmp", prefix="index_"
            )
            with os.fdopen(tmp_fd, "wb") as f:
                tmp_fd = None
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
            tmp_path = None
            self._dirty = False
            logger.debug("💾 VectorStore salvo: %d vetores em %s", self.size, path)
        except Exception as e:
            logger.error("❌ Erro ao salvar VectorStore: %s", e)
        finally:
            if tmp_fd is not None:
                try:
                    os.close(tmp_fd)
                except OSError:
                    pass
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def load(self, path: Path = INDEX_FILE) -> bool:
        """Carrega índice do disco com validação de integridade."""
        if not path.exists():
            return False
        try:
            file_size = path.stat().st_size
            if file_size == 0:
                logger.warning("⚠️ VectorStore corrompido (0 bytes) — removendo")
                self._quarantine_corrupted(path)
                return False
        except OSError:
            return False

        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self._embeddings = data["embeddings"]
            self._metadata = data["metadata"]
            self.dim = data.get("dim", EMBEDDING_DIM)
            self._dirty = False
            logger.info("📂 VectorStore carregado: %d vetores", self.size)
            return True
        except Exception as e:
            logger.warning("⚠️ Falha ao carregar VectorStore: %s", e)
            self._quarantine_corrupted(path)
            return False

    @staticmethod
    def _quarantine_corrupted(path: Path) -> None:
        """Move arquivo corrompido para .corrupted para análise posterior."""
        try:
            backup = path.with_suffix(f".corrupted.{int(time.time())}")
            shutil.move(str(path), str(backup))
            logger.warning("📦 Arquivo corrompido movido para %s", backup)
        except Exception as e:
            logger.debug("Quarantine move falhou: %s", e)
            try:
                path.unlink(missing_ok=True)
            except Exception as e2:
                logger.debug("Quarantine unlink falhou: %s", e2)


# ====================== DADOS MULTI-SOURCE COLLECTOR ======================
class MarketDataCollector:
    """Coleta dados do MT5 Bridge para gerar snapshots enriquecidos."""

    def __init__(self, symbol: str = "PETR4") -> None:
        self.symbol = symbol
        self._price_history: deque = deque(maxlen=500)
        self._last_candles: List[Dict] = []
        self._last_candle_fetch: float = 0.0

    def collect_snapshot(
        self,
        price: Optional[float] = None,
        indicators: Optional[object] = None,
        spread_analysis: Optional[Dict] = None,
        flow_analysis: Optional[Dict] = None,
    ) -> Optional[MarketSnapshot]:
        """Coleta um snapshot completo do mercado B3.

        Args:
            price: Preço atual (opcional, coleta da API se None).
            indicators: FastIndicators instance (opcional).
            spread_analysis: Resultado de analyze_spread (opcional).
            flow_analysis: Resultado de analyze_trade_flow (opcional).

        Returns:
            MarketSnapshot ou None se falhar.
        """
        try:
            if price is None:
                from clear_trading_agent.mt5_api import get_price_fast
                price = get_price_fast(self.symbol, timeout=2)
            if price is None:
                return None

            self._price_history.append(price)

            # Spread analysis
            if spread_analysis is None:
                try:
                    from clear_trading_agent.mt5_api import analyze_spread
                    spread_analysis = analyze_spread(self.symbol)
                except Exception as e:
                    logger.debug("Spread analysis fallback: %s", e)
                    spread_analysis = {}

            # Trade flow
            if flow_analysis is None:
                try:
                    from clear_trading_agent.mt5_api import analyze_trade_flow
                    flow_analysis = analyze_trade_flow(self.symbol)
                except Exception as e:
                    logger.debug("Trade flow fallback: %s", e)
                    flow_analysis = {}

            # Candles de 1min (recarga a cada 60s)
            now = time.time()
            if now - self._last_candle_fetch > 60:
                try:
                    from clear_trading_agent.mt5_api import get_candles
                    self._last_candles = get_candles(self.symbol, "1m", limit=100)
                    self._last_candle_fetch = now
                except Exception as e:
                    logger.debug("Candles fetch error: %s", e)

            # Indicadores
            rsi_val = 50.0
            mom_val = 0.0
            vol_val = 0.0
            trend_val = 0.0
            sma10 = sma30 = sma60 = ema20 = price

            if indicators is not None:
                rsi_val = indicators.rsi()
                mom_val = indicators.momentum()
                vol_val = indicators.volatility()
                trend_val = indicators.trend()
                if len(indicators.prices) >= 10:
                    sma10 = float(np.mean(list(indicators.prices)[-10:]))
                if len(indicators.prices) >= 30:
                    sma30 = float(np.mean(list(indicators.prices)[-30:]))
                if len(indicators.prices) >= 60:
                    sma60 = float(np.mean(list(indicators.prices)[-60:]))
                ema20 = indicators.ema(20)
            elif len(self._price_history) >= 10:
                prices = list(self._price_history)
                sma10 = float(np.mean(prices[-10:]))
                if len(prices) >= 30:
                    sma30 = float(np.mean(prices[-30:]))
                if len(prices) >= 60:
                    sma60 = float(np.mean(prices[-60:]))

            # Último candle OHLCV
            o1m = h1m = l1m = c1m = price
            v1m = 0.0
            if self._last_candles:
                last_c = self._last_candles[-1]
                o1m = last_c.get("open", price)
                h1m = last_c.get("high", price)
                l1m = last_c.get("low", price)
                c1m = last_c.get("close", price)
                v1m = last_c.get("volume", 0)

            spread = spread_analysis.get("spread", 0) if spread_analysis else 0
            mid = (spread_analysis.get("bid", 0) + spread_analysis.get("ask", 0)) / 2 if spread_analysis else price
            spread_pct = (spread / mid) if mid > 0 else 0

            snapshot = MarketSnapshot(
                timestamp=now,
                symbol=self.symbol,
                price=price,
                open_1m=o1m,
                high_1m=h1m,
                low_1m=l1m,
                close_1m=c1m,
                volume_1m=v1m,
                rsi=rsi_val,
                momentum=mom_val,
                volatility=vol_val,
                trend=trend_val,
                spread=spread,
                spread_pct=spread_pct,
                trade_flow=flow_analysis.get("flow_bias", 0) if flow_analysis else 0,
                sma_10=sma10,
                sma_30=sma30,
                sma_60=sma60,
                ema_20=ema20,
            )
            return snapshot

        except Exception as e:
            logger.warning("⚠️ Erro ao coletar snapshot: %s", e)
            return None


# ====================== REGIME ADJUSTER ======================
class RegimeAdjuster:
    """Ajusta thresholds de bull/bear baseado em padrões históricos similares."""

    BUY_TH_MIN = 0.20
    BUY_TH_MAX = 0.50
    SELL_TH_MIN = -0.50
    SELL_TH_MAX = -0.15

    def __init__(self, symbol: str = "PETR4") -> None:
        self.symbol = symbol
        self._last_adjustment: Optional[RegimeAdjustment] = None
        self._adjustment_history: deque = deque(maxlen=100)

    def calculate_adjustment(
        self,
        current_snapshot: MarketSnapshot,
        similar_results: List[Tuple[float, Dict]],
    ) -> RegimeAdjustment:
        """Calcula ajuste de regime baseado em padrões similares."""
        adjustment = RegimeAdjustment(
            timestamp=time.time(),
            symbol=self.symbol,
        )

        if not similar_results:
            self._last_adjustment = adjustment
            return adjustment

        valid = [
            (sim, meta) for sim, meta in similar_results
            if meta.get("outcome") is not None and sim > 0.5
        ]

        if len(valid) < 3:
            self._last_adjustment = adjustment
            return adjustment

        adjustment.similar_count = len(valid)

        bull_count = sum(1 for _, m in valid if m.get("outcome") == "BULL")
        bear_count = sum(1 for _, m in valid if m.get("outcome") == "BEAR")
        flat_count = sum(1 for _, m in valid if m.get("outcome") == "FLAT")
        total = bull_count + bear_count + flat_count

        if total > 0:
            adjustment.bull_pct = bull_count / total
            adjustment.bear_pct = bear_count / total
            adjustment.flat_pct = flat_count / total

        returns_5m = [m["price_change_5m"] for _, m in valid if m.get("price_change_5m") is not None]
        returns_15m = [m["price_change_15m"] for _, m in valid if m.get("price_change_15m") is not None]

        if returns_5m:
            adjustment.avg_return_5m = float(np.mean(returns_5m))
        if returns_15m:
            adjustment.avg_return_15m = float(np.mean(returns_15m))

        # Determinar regime
        if adjustment.bull_pct > 0.55:
            adjustment.suggested_regime = "BULLISH"
            adjustment.regime_confidence = adjustment.bull_pct
        elif adjustment.bear_pct > 0.55:
            adjustment.suggested_regime = "BEARISH"
            adjustment.regime_confidence = adjustment.bear_pct
        else:
            adjustment.suggested_regime = "RANGING"
            adjustment.regime_confidence = adjustment.flat_pct

        # Ajustar thresholds
        base_buy = 0.30
        base_sell = -0.30

        if adjustment.suggested_regime == "BULLISH":
            buy_adj = -0.08 * adjustment.regime_confidence
            sell_adj = -0.05 * adjustment.regime_confidence
            adjustment.buy_threshold = float(np.clip(base_buy + buy_adj, self.BUY_TH_MIN, self.BUY_TH_MAX))
            adjustment.sell_threshold = float(np.clip(base_sell + sell_adj, self.SELL_TH_MIN, self.SELL_TH_MAX))
        elif adjustment.suggested_regime == "BEARISH":
            buy_adj = 0.15 * adjustment.regime_confidence
            sell_adj = 0.10 * adjustment.regime_confidence
            adjustment.buy_threshold = float(np.clip(base_buy + buy_adj, self.BUY_TH_MIN, self.BUY_TH_MAX))
            adjustment.sell_threshold = float(np.clip(base_sell + sell_adj, self.SELL_TH_MIN, self.SELL_TH_MAX))
        else:
            adjustment.buy_threshold = base_buy
            adjustment.sell_threshold = base_sell

        # Ajustar pesos do ensemble
        if adjustment.suggested_regime == "BEARISH":
            adjustment.weight_technical = 0.45
            adjustment.weight_spread = 0.20
            adjustment.weight_flow = 0.30
            adjustment.weight_qlearning = 0.05
        elif adjustment.suggested_regime == "BULLISH":
            adjustment.weight_technical = 0.35
            adjustment.weight_spread = 0.25
            adjustment.weight_flow = 0.25
            adjustment.weight_qlearning = 0.15
        else:
            adjustment.weight_technical = 0.40
            adjustment.weight_spread = 0.25
            adjustment.weight_flow = 0.25
            adjustment.weight_qlearning = 0.10

        # Normalizar pesos
        total_w = (
            adjustment.weight_technical + adjustment.weight_spread
            + adjustment.weight_flow + adjustment.weight_qlearning
        )
        if abs(total_w - 1.0) > 0.001:
            adjustment.weight_technical /= total_w
            adjustment.weight_spread /= total_w
            adjustment.weight_flow /= total_w
            adjustment.weight_qlearning /= total_w

        # AI Trade Gating
        self._calculate_ai_gating(adjustment)

        self._last_adjustment = adjustment
        self._adjustment_history.append(adjustment)

        return adjustment

    def _calculate_ai_gating(self, adj: RegimeAdjustment) -> None:
        """Calcula parâmetros de trade gating baseado no regime."""
        regime = adj.suggested_regime
        conf = adj.regime_confidence

        if regime == "BULLISH":
            adj.ai_aggressiveness = 0.55 + 0.20 * conf
            adj.ai_min_confidence = max(0.56, 0.66 - 0.10 * conf)
            adj.ai_min_trade_interval = max(90, int(210 - 90 * conf))
            adj.ai_rebuy_lock_enabled = False
            adj.ai_rebuy_margin_pct = 0.0
        elif regime == "BEARISH":
            adj.ai_aggressiveness = max(0.08, 0.30 - 0.16 * conf)
            adj.ai_min_confidence = min(0.88, 0.70 + 0.12 * conf)
            adj.ai_min_trade_interval = min(720, int(240 + 240 * conf))
            adj.ai_rebuy_lock_enabled = True
            adj.ai_rebuy_margin_pct = 0.003 * conf
        else:
            ret_signal = 1.0 if adj.avg_return_5m > 0.0001 else (-1.0 if adj.avg_return_5m < -0.0001 else 0.0)
            adj.ai_aggressiveness = 0.42 + 0.08 * ret_signal
            adj.ai_min_confidence = 0.64
            adj.ai_min_trade_interval = 150
            adj.ai_rebuy_lock_enabled = True
            adj.ai_rebuy_margin_pct = 0.0015

        # Ajuste pela qualidade dos dados
        if adj.similar_count >= 10:
            adj.ai_min_confidence = max(0.50, adj.ai_min_confidence - 0.03)
        elif adj.similar_count < 3:
            adj.ai_min_confidence = min(0.80, adj.ai_min_confidence + 0.10)
            adj.ai_min_trade_interval = max(adj.ai_min_trade_interval, 300)

        # Safety clamps
        adj.ai_min_confidence = float(np.clip(adj.ai_min_confidence, 0.40, 0.85))
        adj.ai_min_trade_interval = int(np.clip(adj.ai_min_trade_interval, 30, 900))
        adj.ai_rebuy_margin_pct = float(np.clip(adj.ai_rebuy_margin_pct, 0.0, 0.01))

    def _calculate_ai_buy_target(
        self, adj: RegimeAdjustment, current_price: float,
        store: Optional[VectorStore] = None,
    ) -> None:
        """Calcula preço alvo de compra baseado em análise técnica."""
        try:
            if current_price <= 0:
                return

            if not store or store.size < 10:
                adj.ai_buy_target_price = round(current_price * 1.001, 2)
                adj.ai_buy_target_reason = "sem_dados:aceitar_preco_atual"
                return

            recent_prices: List[float] = []
            n = min(200, store.size)
            for i in range(store.size - n, store.size):
                meta = store._metadata[i]
                if isinstance(meta, dict):
                    p = meta.get("price", 0)
                    if p > 0:
                        recent_prices.append(float(p))

            if not recent_prices:
                adj.ai_buy_target_price = round(current_price * 1.001, 2)
                adj.ai_buy_target_reason = "sem_precos:aceitar_preco_atual"
                return

            prices_window = recent_prices[-100:]
            price_min = min(prices_window)
            price_max = max(prices_window)
            price_range = price_max - price_min if price_max > price_min else current_price * 0.001

            regime = adj.suggested_regime
            confidence = adj.regime_confidence
            aggressiveness = adj.ai_aggressiveness

            if regime == "BULLISH":
                regime_discount = 0.0008 + (0.0012 * (1.0 - confidence))
                target = current_price * (1.0 - regime_discount)
                reason = f"bull:desconto_{regime_discount * 100:.2f}%"
            elif regime == "BEARISH":
                bear_severity = adj.bear_pct if adj.bear_pct > 0 else 0.5
                regime_discount = 0.004 + (0.009 * bear_severity * confidence)
                target = current_price * (1.0 - regime_discount)
                support_level = price_min + (price_range * 0.20)
                if target < support_level:
                    target = support_level
                    reason = f"bear:suporte_{support_level:.2f}"
                else:
                    reason = f"bear:desconto_{regime_discount * 100:.2f}%"
            else:
                lower_third = price_min + (price_range * 0.25)
                target = lower_third + (current_price - lower_third) * min(aggressiveness, 0.40)
                reason = f"ranging:lower_{lower_third:.2f}_aggr_{aggressiveness:.0%}"

            # Limites de segurança
            max_discount = current_price * 0.98
            target = max(target, max_discount)

            if regime == "BULLISH":
                upper_limit = current_price * 1.001
            elif regime == "BEARISH":
                upper_limit = current_price * 0.995
            else:
                upper_limit = current_price * 0.9995
            target = min(target, upper_limit)

            adj.ai_buy_target_price = round(target, 2)
            adj.ai_buy_target_reason = reason

        except Exception as e:
            logger.error("❌ Erro ao calcular buy target: %s", e)
            adj.ai_buy_target_price = round(current_price * 0.998, 2)
            adj.ai_buy_target_reason = "erro_fallback:0.2%"

    def _calculate_ai_take_profit(
        self, adj: RegimeAdjustment, current_price: float,
        store: Optional[VectorStore] = None,
    ) -> None:
        """Calcula take-profit dinâmico baseado em regime e volatilidade."""
        try:
            if current_price <= 0:
                return

            regime = adj.suggested_regime
            confidence = adj.regime_confidence

            if regime == "BULLISH":
                base_tp = 0.022 + 0.018 * confidence
                reason = f"bull:base_{base_tp*100:.1f}%"
            elif regime == "BEARISH":
                base_tp = 0.018 - 0.008 * confidence
                reason = f"bear:base_{base_tp*100:.1f}%"
            else:
                base_tp = 0.012 + 0.008 * adj.ai_aggressiveness
                reason = f"ranging:base_{base_tp*100:.1f}%"

            tp = base_tp

            # Ajuste por retornos históricos
            if adj.avg_return_15m > 0.003:
                tp += 0.003
                reason += f"|hist_bull_{adj.avg_return_15m*100:.2f}%"
            elif adj.avg_return_15m < -0.003:
                tp *= 0.70
                reason += f"|hist_bear_{adj.avg_return_15m*100:.2f}%"

            tp = float(np.clip(tp, 0.006, 0.05))

            adj.ai_take_profit_pct = round(tp, 5)
            adj.ai_take_profit_reason = reason

        except Exception as e:
            logger.error("❌ Erro ao calcular AI take-profit: %s", e)
            adj.ai_take_profit_pct = 0.025
            adj.ai_take_profit_reason = "erro_fallback:2.5%"

    def _calculate_ai_position_size(
        self, adj: RegimeAdjustment, current_price: float,
        avg_entry_price: float = 0.0, position_count: int = 0,
        brl_balance: float = 0.0, store: Optional[VectorStore] = None,
    ) -> None:
        """Calcula tamanho e nº máximo de entradas controlado pela IA."""
        try:
            if current_price <= 0:
                return

            regime = adj.suggested_regime
            confidence = adj.regime_confidence
            aggressiveness = adj.ai_aggressiveness
            reason_parts: list[str] = []

            if regime == "BULLISH":
                base_pct = 0.045 + 0.020 * confidence
                base_max_entries = 8
                reason_parts.append(f"bull:{base_pct*100:.1f}%")
            elif regime == "BEARISH":
                base_pct = 0.02 + 0.015 * (1.0 - confidence)
                base_max_entries = 12
                reason_parts.append(f"bear:{base_pct*100:.1f}%")
            else:
                base_pct = 0.03 + 0.015 * aggressiveness
                base_max_entries = 8
                reason_parts.append(f"ranging:{base_pct*100:.1f}%")

            size_pct = base_pct
            max_entries = base_max_entries

            # DCA boost
            if avg_entry_price > 0 and current_price < avg_entry_price:
                discount = (avg_entry_price - current_price) / avg_entry_price
                dca_mult = 1.0 + min(discount * 30, 1.5)
                size_pct *= dca_mult
                max_entries = max(max_entries, int(15 + discount * 100))
                reason_parts.append(f"dca:{discount*100:.1f}%→{dca_mult:.1f}x")

            # Ajuste por saldo
            if brl_balance > 0:
                if brl_balance < 500:
                    size_pct = max(size_pct, 0.10)
                    max_entries = min(max_entries, 4)
                    reason_parts.append(f"saldo_baixo:R${brl_balance:.0f}")

            # Redução por muitas entradas
            if position_count > 6:
                reduction = min(position_count * 0.03, 0.5)
                size_pct *= (1.0 - reduction)
                reason_parts.append(f"entries:{position_count}→-{reduction*100:.0f}%")

            # Limites de segurança
            size_pct = float(np.clip(size_pct, 0.02, 0.15))
            max_entries = max(2, min(max_entries, 15))

            adj.ai_position_size_pct = round(size_pct, 4)
            adj.ai_max_entries = max_entries
            adj.ai_position_size_reason = "|".join(reason_parts)

        except Exception as e:
            logger.error("❌ Erro ao calcular AI position size: %s", e)
            adj.ai_position_size_pct = 0.04
            adj.ai_max_entries = 10
            adj.ai_position_size_reason = "erro_fallback:4%"


# ====================== MARKET RAG ENGINE ======================
class MarketRAG:
    """Motor principal do RAG de mercado B3.

    Integra VectorStore + Collector + Adjuster em pipeline contínuo.
    Roda em thread separada durante horário de pregão.
    """

    def __init__(
        self,
        symbol: str = "PETR4",
        profile: str = "default",
        recalibrate_interval: int = DEFAULT_RECALIBRATE_INTERVAL,
        snapshot_interval: int = 30,
    ) -> None:
        self.symbol = symbol
        self.profile = profile or "default"
        self.recalibrate_interval = recalibrate_interval
        self.snapshot_interval = snapshot_interval
        suffix = "" if self.profile == "default" else f"_{self.profile}"
        self.adjustments_file = RAG_DIR / f"regime_adjustments{suffix}.json"

        self.store = VectorStore(dim=EMBEDDING_DIM, max_size=MAX_SNAPSHOTS)
        self.collector = MarketDataCollector(symbol)
        self.adjuster = RegimeAdjuster(symbol)

        self._recent_snapshots: deque = deque(maxlen=200)
        self._current_adjustment = RegimeAdjustment(
            timestamp=time.time(), symbol=symbol
        )
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_snapshot_time: float = 0.0
        self._last_recalibrate_time: float = 0.0
        self._stats = {
            "snapshots_collected": 0,
            "recalibrations": 0,
            "outcomes_updated": 0,
        }
        self._trading_context: Dict = {
            "avg_entry_price": 0.0,
            "position_count": 0,
            "brl_balance": 0.0,
            "max_position_pct": 0.5,
            "max_positions": 3,
            "profile": "default",
        }
        self._ollama_trade_controls: Dict = {}

        self.store.load()

    def start(self) -> None:
        """Inicia o thread de coleta e recalibração."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("⚠️ MarketRAG já está rodando")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=False, name="MarketRAG-B3"
        )
        self._thread.start()
        logger.info(
            "🧠 MarketRAG B3 iniciado: %s (snapshot=%ds, recalibrate=%ds)",
            self.symbol, self.snapshot_interval, self.recalibrate_interval,
        )

    def stop(self) -> None:
        """Para o thread e persiste dados."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=30)
        self.store.save()
        self._save_adjustments()
        logger.info("🛑 MarketRAG B3 parado e dados salvos")

    def get_current_adjustment(self) -> RegimeAdjustment:
        """Retorna o ajuste atual de regime (thread-safe)."""
        with self._lock:
            return self._current_adjustment

    def set_trading_context(
        self,
        avg_entry_price: float = 0.0,
        position_count: int = 0,
        brl_balance: float = 0.0,
        max_position_pct: float = 0.5,
        max_positions: int = 3,
        profile: str = "default",
    ) -> None:
        """Atualiza contexto de trading para cálculo de sizing."""
        self._trading_context = {
            "avg_entry_price": avg_entry_price,
            "position_count": position_count,
            "brl_balance": brl_balance,
            "max_position_pct": max(0.01, float(max_position_pct or 0.5)),
            "max_positions": max(1, int(max_positions or 3)),
            "profile": str(profile or "default"),
        }

    def feed_snapshot(
        self,
        price: Optional[float] = None,
        indicators: Optional[object] = None,
        spread_analysis: Optional[Dict] = None,
        flow_analysis: Optional[Dict] = None,
    ) -> Optional[MarketSnapshot]:
        """Alimenta o RAG com dados do loop de trading."""
        now = time.time()
        if now - self._last_snapshot_time < self.snapshot_interval:
            return None
        snapshot = self.collector.collect_snapshot(
            price=price, indicators=indicators,
            spread_analysis=spread_analysis, flow_analysis=flow_analysis,
        )
        if snapshot is None:
            return None
        self._ingest_snapshot(snapshot)
        return snapshot

    def force_recalibrate(self) -> RegimeAdjustment:
        """Força uma recalibração imediata."""
        return self._recalibrate()

    def get_stats(self) -> Dict:
        """Retorna estatísticas do RAG."""
        adj = self.get_current_adjustment()
        return {
            "store_size": self.store.size,
            "snapshots_collected": self._stats["snapshots_collected"],
            "recalibrations": self._stats["recalibrations"],
            "outcomes_updated": self._stats["outcomes_updated"],
            "current_regime": adj.suggested_regime,
            "regime_confidence": adj.regime_confidence,
            "buy_threshold": adj.buy_threshold,
            "sell_threshold": adj.sell_threshold,
            "bull_pct": adj.bull_pct,
            "bear_pct": adj.bear_pct,
        }

    def set_ollama_trade_controls(
        self,
        suggestion: Dict,
        *,
        mode: str = "shadow",
        trigger: str = "periodic",
        model: str = "",
    ) -> RegimeAdjustment:
        """Registra sugestão do Ollama e recalcula controles efetivos."""
        payload = dict(suggestion or {})
        payload["mode"] = mode
        payload["trigger"] = trigger
        payload["model"] = model
        payload["timestamp"] = float(payload.get("timestamp") or time.time())
        self._ollama_trade_controls = payload

        with self._lock:
            self._apply_trade_control_baselines(self._current_adjustment)
            self._apply_ollama_trade_controls(self._current_adjustment, payload)
            current = self._current_adjustment

        self._save_adjustments()
        return current

    # ====================== INTERNALS ======================

    def _apply_trade_control_baselines(self, adjustment: RegimeAdjustment) -> None:
        """Sincroniza baseline/applied com o estado determinístico atual."""
        ctx = self._trading_context
        adjustment.baseline_min_confidence = float(adjustment.ai_min_confidence or 0.60)
        adjustment.baseline_min_trade_interval = int(adjustment.ai_min_trade_interval or 180)
        adjustment.baseline_max_position_pct = max(0.01, float(ctx.get("max_position_pct") or 0.5))
        adjustment.baseline_max_positions = max(1, int(ctx.get("max_positions") or 3))
        adjustment.applied_min_confidence = adjustment.baseline_min_confidence
        adjustment.applied_min_trade_interval = adjustment.baseline_min_trade_interval
        adjustment.applied_max_position_pct = adjustment.baseline_max_position_pct
        adjustment.applied_max_positions = adjustment.baseline_max_positions
        adjustment.ollama_mode = str(self._ollama_trade_controls.get("mode") or "shadow")

    def _apply_ollama_trade_controls(
        self, adjustment: RegimeAdjustment, suggestion: Optional[Dict],
    ) -> None:
        """Aplica sugestão do Ollama sobre o baseline do RAG."""
        if not suggestion:
            return

        mode = str(suggestion.get("mode") or "shadow").strip().lower()
        if mode not in {"shadow", "apply"}:
            mode = "shadow"

        baseline_conf = float(adjustment.baseline_min_confidence or 0.60)
        baseline_interval = int(adjustment.baseline_min_trade_interval or 180)
        baseline_cap_pct = max(0.01, float(adjustment.baseline_max_position_pct or 0.5))
        baseline_max_positions = max(1, int(adjustment.baseline_max_positions or 3))

        suggested_conf = float(np.clip(
            float(suggestion.get("min_confidence") or baseline_conf),
            max(0.40, baseline_conf - 0.10),
            min(0.92, baseline_conf + 0.10),
        ))
        suggested_interval = int(np.clip(
            int(round(float(suggestion.get("min_trade_interval") or baseline_interval))),
            max(30, int(round(baseline_interval * 0.50))),
            min(900, int(round(baseline_interval * 1.80))),
        ))

        adjustment.ollama_mode = mode
        adjustment.ollama_last_update = float(suggestion.get("timestamp") or time.time())
        adjustment.ollama_trigger = str(suggestion.get("trigger") or "")
        adjustment.ollama_model = str(suggestion.get("model") or "")
        adjustment.ollama_reason = str(suggestion.get("rationale") or "")[:500]
        adjustment.ollama_suggested_min_confidence = suggested_conf
        adjustment.ollama_suggested_min_trade_interval = suggested_interval

        if mode == "apply":
            adjustment.applied_min_confidence = float(np.clip(
                baseline_conf + (suggested_conf - baseline_conf) * 0.35, 0.40, 0.92,
            ))
            adjustment.applied_min_trade_interval = int(np.clip(
                round(baseline_interval + (suggested_interval - baseline_interval) * 0.50),
                30, 900,
            ))
        else:
            adjustment.applied_min_confidence = baseline_conf
            adjustment.applied_min_trade_interval = baseline_interval

    def _ingest_snapshot(self, snapshot: MarketSnapshot) -> None:
        """Ingere um snapshot no store e buffer recente."""
        embedding = snapshot.to_embedding()
        metadata = snapshot.to_dict()
        self.store.add(embedding, metadata)
        self._recent_snapshots.append(snapshot)
        self._last_snapshot_time = snapshot.timestamp
        self._stats["snapshots_collected"] += 1

    def _update_outcomes(self) -> None:
        """Atualiza outcomes dos snapshots antigos com dados futuros."""
        now = time.time()
        updated = 0

        for snap in self._recent_snapshots:
            if snap.outcome is not None:
                continue
            elapsed = now - snap.timestamp
            if elapsed < 300:
                continue

            price_5m = self._find_price_at(snap.timestamp + 300)
            if price_5m is not None and snap.price > 0:
                snap.price_change_5m = (price_5m / snap.price) - 1

            if elapsed >= 900:
                price_15m = self._find_price_at(snap.timestamp + 900)
                if price_15m is not None and snap.price > 0:
                    snap.price_change_15m = (price_15m / snap.price) - 1

            if elapsed >= 3600:
                price_60m = self._find_price_at(snap.timestamp + 3600)
                if price_60m is not None and snap.price > 0:
                    snap.price_change_60m = (price_60m / snap.price) - 1

            if snap.price_change_5m is not None:
                if snap.price_change_5m > 0.002:
                    snap.outcome = "BULL"
                elif snap.price_change_5m < -0.002:
                    snap.outcome = "BEAR"
                else:
                    snap.outcome = "FLAT"
                self._update_store_metadata(snap)
                updated += 1

        if updated > 0:
            self._stats["outcomes_updated"] += updated

    def _find_price_at(self, target_time: float) -> Optional[float]:
        """Encontra o preço mais próximo de um timestamp alvo."""
        best_price = None
        best_diff = float("inf")
        for snap in self._recent_snapshots:
            diff = abs(snap.timestamp - target_time)
            if diff < best_diff and diff < 60:
                best_diff = diff
                best_price = snap.price
        return best_price

    def _update_store_metadata(self, snapshot: MarketSnapshot) -> None:
        """Atualiza metadata de um snapshot existente no VectorStore."""
        for meta in self.store._metadata:
            if abs(meta.get("timestamp", 0) - snapshot.timestamp) < 1.0:
                meta["price_change_5m"] = snapshot.price_change_5m
                meta["price_change_15m"] = snapshot.price_change_15m
                meta["price_change_60m"] = snapshot.price_change_60m
                meta["outcome"] = snapshot.outcome
                self.store._dirty = True
                break

    def _recalibrate(self) -> RegimeAdjustment:
        """Executa recalibração completa."""
        self._update_outcomes()

        snapshot = self.collector.collect_snapshot()
        if snapshot is None:
            return self._current_adjustment

        query = snapshot.to_embedding()
        similar = self.store.search(query, top_k=TOP_K)
        adjustment = self.adjuster.calculate_adjustment(snapshot, similar)

        if snapshot.price > 0:
            self.adjuster._calculate_ai_buy_target(
                adjustment, snapshot.price, store=self.store,
            )
            self.adjuster._calculate_ai_take_profit(
                adjustment, snapshot.price, store=self.store,
            )
            ctx = self._trading_context
            self.adjuster._calculate_ai_position_size(
                adjustment, snapshot.price,
                avg_entry_price=ctx.get("avg_entry_price", 0.0),
                position_count=ctx.get("position_count", 0),
                brl_balance=ctx.get("brl_balance", 0.0),
                store=self.store,
            )

        self._apply_trade_control_baselines(adjustment)
        if self._ollama_trade_controls:
            self._apply_ollama_trade_controls(adjustment, self._ollama_trade_controls)

        with self._lock:
            self._current_adjustment = adjustment

        self._last_recalibrate_time = time.time()
        self._stats["recalibrations"] += 1

        self._save_adjustments()
        if self._stats["recalibrations"] % 5 == 0:
            self.store.save()

        logger.info(
            "🎯 RAG B3 Adjustment: regime=%s (conf=%.1f%%), buy_th=%.3f, sell_th=%.3f, "
            "bull=%.0f%%/bear=%.0f%%/flat=%.0f%%, similares=%d, ai_conf=%.0f%%",
            adjustment.suggested_regime, adjustment.regime_confidence * 100,
            adjustment.buy_threshold, adjustment.sell_threshold,
            adjustment.bull_pct * 100, adjustment.bear_pct * 100,
            adjustment.flat_pct * 100, adjustment.similar_count,
            adjustment.applied_min_confidence * 100,
        )

        return adjustment

    def _run_loop(self) -> None:
        """Loop principal do thread de RAG (respeita horário B3)."""
        from clear_trading_agent.fast_model import is_market_open, minutes_to_market_open

        logger.info("🧠 MarketRAG B3 loop iniciado")

        while not self._stop_event.is_set():
            try:
                if not is_market_open():
                    mins = minutes_to_market_open()
                    wait = min(mins * 60, 300)  # Espera até 5min, checa de novo
                    logger.debug("⏳ Mercado fechado — próxima abertura em %d min", mins)
                    self._stop_event.wait(timeout=max(wait, 30))
                    continue

                now = time.time()

                if now - self._last_snapshot_time >= self.snapshot_interval:
                    snapshot = self.collector.collect_snapshot()
                    if snapshot is not None:
                        self._ingest_snapshot(snapshot)

                if now - self._last_recalibrate_time >= self.recalibrate_interval:
                    self._recalibrate()

                self._stop_event.wait(timeout=5)

            except Exception as e:
                logger.error("❌ MarketRAG B3 loop error: %s", e)
                self._stop_event.wait(timeout=10)

        self.store.save()
        self._save_adjustments()
        logger.info("🧠 MarketRAG B3 loop finalizado")

    def _save_adjustments(self) -> None:
        """Persiste histórico de ajustes em JSON."""
        try:
            history = [a.to_dict() for a in self.adjuster._adjustment_history]
            with open(self.adjustments_file, "w") as f:
                json.dump(
                    {
                        "last_update": time.time(),
                        "symbol": self.symbol,
                        "profile": self.profile,
                        "current": self._current_adjustment.to_dict(),
                        "history": history[-50:],
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.warning("⚠️ Erro ao salvar ajustes: %s", e)
