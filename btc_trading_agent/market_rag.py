#!/usr/bin/env python3
"""
Market RAG (Retrieval-Augmented Generation) — Inteligência de Mercado
=====================================================================
Módulo autônomo que:
  1. Coleta dados de múltiplas fontes e timeframes
  2. Armazena snapshots como documentos vetorizados
  3. Recupera padrões similares ao estado atual via busca vetorial
  4. Ajusta dinamicamente os thresholds de bull/bear do modelo

Integra-se ao FastTradingModel para recalibrar o regime de mercado
a cada N minutos baseado no conhecimento acumulado.
"""

import json
import os
import tempfile
import time
import logging
import threading
import hashlib
import pickle
import shutil
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import deque
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# ====================== CONSTANTES ======================
RAG_DIR = Path(__file__).parent / "data" / "market_rag"
RAG_DIR.mkdir(parents=True, exist_ok=True)

SNAPSHOT_FILE = RAG_DIR / "snapshots.pkl"
INDEX_FILE = RAG_DIR / "index.pkl"
ADJUSTMENTS_FILE = RAG_DIR / "regime_adjustments.json"

# Dimensão do vetor de embedding de mercado
EMBEDDING_DIM = 24

# Intervalo padrão de recalibração (5 minutos)
DEFAULT_RECALIBRATE_INTERVAL = 300

# Máximo de snapshots mantidos (30 dias de dados a 1 snap/min ≈ 43k)
MAX_SNAPSHOTS = 50_000

# Top-K resultados para busca de similaridade
TOP_K = 20


# ====================== DATA CLASSES ======================
@dataclass
class MarketSnapshot:
    """Snapshot completo do mercado em um instante."""

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

    # Orderbook
    orderbook_imbalance: float = 0.0
    spread: float = 0.0
    bid_volume: float = 0.0
    ask_volume: float = 0.0

    # Trade flow
    trade_flow: float = 0.0
    buy_volume: float = 0.0
    sell_volume: float = 0.0

    # Multi-timeframe (derivados)
    sma_10: float = 0.0
    sma_30: float = 0.0
    sma_60: float = 0.0
    ema_20: float = 0.0

    # Resultado futuro (preenchido retrospectivamente)
    price_change_5m: Optional[float] = None   # Variação % em 5 min
    price_change_15m: Optional[float] = None  # Variação % em 15 min
    price_change_60m: Optional[float] = None  # Variação % em 60 min
    outcome: Optional[str] = None             # "BULL", "BEAR", "FLAT"

    def to_embedding(self) -> np.ndarray:
        """Converte snapshot para vetor numérico normalizado."""
        raw = np.array([
            (self.rsi - 50.0) / 50.0,                     # [-1, 1]
            np.clip(self.momentum / 2.0, -1, 1),           # [-1, 1]
            np.clip(self.volatility * 20, 0, 1),           # [0, 1]
            np.clip(self.trend, -1, 1),                    # [-1, 1]
            np.clip(self.orderbook_imbalance, -1, 1),      # [-1, 1]
            np.clip(self.spread * 10_000, 0, 1),           # normalizado em bps
            np.clip(self.trade_flow, -1, 1),               # [-1, 1]
            # Razões de volume
            self._safe_ratio(self.bid_volume, self.ask_volume),
            self._safe_ratio(self.buy_volume, self.sell_volume),
            # Multi-timeframe: posição relativa do preço
            self._pct_diff(self.price, self.sma_10),
            self._pct_diff(self.price, self.sma_30),
            self._pct_diff(self.price, self.sma_60),
            self._pct_diff(self.price, self.ema_20),
            # OHLCV patterns
            self._pct_diff(self.close_1m, self.open_1m),   # candle body
            self._safe_ratio(
                self.high_1m - max(self.open_1m, self.close_1m),
                self.high_1m - self.low_1m + 1e-10,
            ),  # upper wick ratio
            self._safe_ratio(
                min(self.open_1m, self.close_1m) - self.low_1m,
                self.high_1m - self.low_1m + 1e-10,
            ),  # lower wick ratio
            np.clip(self.volume_1m / 100.0, 0, 1),         # volume normalizado
            # Derivados de preço
            self._pct_diff(self.high_1m, self.low_1m),     # range %
            # Hora do dia (ciclico)
            np.sin(2 * np.pi * self._hour_of_day() / 24),
            np.cos(2 * np.pi * self._hour_of_day() / 24),
            # Dia da semana (ciclico)
            np.sin(2 * np.pi * self._day_of_week() / 7),
            np.cos(2 * np.pi * self._day_of_week() / 7),
            # RSI zones: oversold(-1), neutral(0), overbought(+1)
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
        return np.clip((a - b) / total, -1, 1)

    def _pct_diff(self, a: float, b: float) -> float:
        """Diferença percentual clipada."""
        if b < 1e-10:
            return 0.0
        return np.clip(((a / b) - 1) * 100, -5, 5) / 5.0

    def _hour_of_day(self) -> float:
        """Hora UTC do snapshot."""
        return datetime.fromtimestamp(self.timestamp, tz=timezone.utc).hour

    def _day_of_week(self) -> int:
        """Dia da semana (0=seg, 6=dom)."""
        return datetime.fromtimestamp(self.timestamp, tz=timezone.utc).weekday()

    def _rsi_zone(self) -> float:
        """Zona RSI: -1 (oversold), 0 (neutro), +1 (overbought)."""
        if self.rsi < 30:
            return -1.0
        elif self.rsi < 40:
            return -0.5
        elif self.rsi > 70:
            return 1.0
        elif self.rsi > 60:
            return 0.5
        return 0.0

    def _vol_regime(self) -> float:
        """Regime de volatilidade: -1 (baixa), 0 (normal), +1 (alta)."""
        if self.volatility < 0.005:
            return -1.0
        elif self.volatility > 0.03:
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
            "orderbook_imbalance": self.orderbook_imbalance,
            "trade_flow": self.trade_flow,
            "price_change_5m": self.price_change_5m,
            "price_change_15m": self.price_change_15m,
            "price_change_60m": self.price_change_60m,
            "outcome": self.outcome,
        }


@dataclass
class RegimeAdjustment:
    """Ajuste calculado pelo RAG para os thresholds do modelo.

    Inclui trade gating dinâmico: a IA controla confiança mínima,
    cooldown e rebuy lock em vez de regras estáticas.
    """

    timestamp: float
    symbol: str

    # Thresholds ajustados
    buy_threshold: float = 0.30
    sell_threshold: float = -0.30

    # Pesos ajustados do ensemble
    weight_technical: float = 0.35
    weight_orderbook: float = 0.30
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

    # ── AI Trade Gating (controlado pela IA, não por regras fixas) ──
    ai_min_confidence: float = 0.60      # Confiança mínima dinâmica
    ai_min_trade_interval: int = 180     # Cooldown dinâmico (segundos)
    ai_rebuy_lock_enabled: bool = True   # Trava de recompra ativa?
    ai_rebuy_margin_pct: float = 0.0     # Margem sobre last_sell_entry (0=preço exato)
    ai_aggressiveness: float = 0.5       # 0.0=conservador, 1.0=agressivo

    # ── AI Buy Target (preço alvo de compra calculado pela IA) ──
    ai_buy_target_price: float = 0.0      # Preço alvo dinâmico
    ai_buy_target_reason: str = ""        # Razão textual do cálculo

    # ── AI Take-Profit dinâmico (calculado pela IA, revisado a cada recalibração) ──
    ai_take_profit_pct: float = 0.025     # % de lucro para auto TP (default 2.5%)
    ai_take_profit_reason: str = ""       # Razão textual do cálculo

    # ── AI Position Sizing (tamanho e nº de entradas controlados pela IA) ──
    ai_position_size_pct: float = 0.04    # % do saldo por entrada (default 4%)
    ai_max_entries: int = 20              # Máximo de entradas permitidas pela IA
    ai_position_size_reason: str = ""     # Razão textual do cálculo

    # AI Profile Allocation (split conservador/arrojado)
    ai_conservative_pct: float = 0.5       # % do saldo para perfil conservador (0.0-1.0)

    # ── Baseline/aplicação efetiva de controles de risco ──
    baseline_min_confidence: float = 0.60
    baseline_min_trade_interval: int = 180
    baseline_max_position_pct: float = 0.50
    baseline_max_positions: int = 3
    applied_min_confidence: float = 0.60
    applied_min_trade_interval: int = 180
    applied_max_position_pct: float = 0.50
    applied_max_positions: int = 3

    # ── Sugestão do Ollama (shadow/apply) ──
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
            "weight_orderbook": round(self.weight_orderbook, 3),
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
            "ai_conservative_pct": round(self.ai_conservative_pct, 3),
            "baseline_min_confidence": round(self.baseline_min_confidence, 3),
            "baseline_min_trade_interval": self.baseline_min_trade_interval,
            "baseline_max_position_pct": round(self.baseline_max_position_pct, 4),
            "baseline_max_positions": self.baseline_max_positions,
            "applied_min_confidence": round(self.applied_min_confidence, 3),
            "applied_min_trade_interval": self.applied_min_trade_interval,
            "applied_max_position_pct": round(self.applied_max_position_pct, 4),
            "applied_max_positions": self.applied_max_positions,
            "ollama_mode": self.ollama_mode,
            "ollama_last_update": round(self.ollama_last_update, 3),
            "ollama_trigger": self.ollama_trigger,
            "ollama_model": self.ollama_model,
            "ollama_reason": self.ollama_reason,
            "ollama_suggested_min_confidence": round(self.ollama_suggested_min_confidence, 3),
            "ollama_suggested_min_trade_interval": self.ollama_suggested_min_trade_interval,
            "ollama_suggested_max_position_pct": round(self.ollama_suggested_max_position_pct, 4),
            "ollama_suggested_max_positions": self.ollama_suggested_max_positions,
        }


# ====================== MOTOR DE BUSCA VETORIAL ======================
class VectorStore:
    """Armazenamento vetorial leve baseado em numpy (sem dependências externas).

    Usa similaridade de cosseno para busca de vizinhos mais próximos.
    Persiste em disco via pickle.
    """

    def __init__(self, dim: int = EMBEDDING_DIM, max_size: int = MAX_SNAPSHOTS):
        """Inicializa o VectorStore.

        Args:
            dim: Dimensão dos vetores de embedding.
            max_size: Número máximo de vetores armazenados.
        """
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
        """Adiciona um vetor ao store.

        Args:
            embedding: Vetor de embedding (dim,).
            metadata: Dados associados ao vetor.
        """
        vec = embedding.reshape(1, -1).astype(np.float32)
        if self._embeddings.shape[0] == 0:
            self._embeddings = vec
        else:
            self._embeddings = np.vstack([self._embeddings, vec])
        self._metadata.append(metadata)
        self._dirty = True

        # Evicção FIFO se exceder limite
        if self.size > self.max_size:
            self._embeddings = self._embeddings[-self.max_size:]
            self._metadata = self._metadata[-self.max_size:]

    def search(self, query: np.ndarray, top_k: int = TOP_K) -> List[Tuple[float, Dict]]:
        """Busca os top_k vetores mais similares por similaridade de cosseno.

        Args:
            query: Vetor de consulta (dim,).
            top_k: Número de resultados.

        Returns:
            Lista de (similaridade, metadata) ordenada por similaridade descendente.
        """
        if self.size == 0:
            return []

        q = query.reshape(1, -1).astype(np.float32)
        # Normas
        q_norm = np.linalg.norm(q, axis=1, keepdims=True) + 1e-10
        e_norms = np.linalg.norm(self._embeddings, axis=1, keepdims=True) + 1e-10

        # Cosseno similarity
        similarities = (self._embeddings @ q.T).flatten() / (e_norms.flatten() * q_norm.flatten())

        # Top-K
        k = min(top_k, self.size)
        top_indices = np.argpartition(similarities, -k)[-k:]
        top_indices = top_indices[np.argsort(similarities[top_indices])[::-1]]

        results = []
        for idx in top_indices:
            results.append((float(similarities[idx]), self._metadata[idx]))
        return results

    def save(self, path: Path = INDEX_FILE) -> None:
        """Persiste o índice em disco com escrita atômica.

        Usa temp file + rename para evitar corrupção se o processo
        for interrompido (SIGTERM/SIGKILL) durante a escrita.
        """
        if not self._dirty:
            return
        data = {
            "embeddings": self._embeddings,
            "metadata": self._metadata,
            "dim": self.dim,
        }
        # Escrita atômica: gravar em arquivo temporário, depois renomear
        tmp_fd = None
        tmp_path = None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=path.parent, suffix=".tmp", prefix="index_"
            )
            with os.fdopen(tmp_fd, "wb") as f:
                tmp_fd = None  # fdopen assume ownership do fd
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
                f.flush()
                os.fsync(f.fileno())
            # Rename atômico (mesmo filesystem)
            os.replace(tmp_path, path)
            tmp_path = None  # Sucesso — não precisa cleanup
            self._dirty = False
            logger.debug(f"💾 VectorStore salvo: {self.size} vetores em {path}")
        except Exception as e:
            logger.error(f"❌ Erro ao salvar VectorStore: {e}")
        finally:
            # Limpar temp file se falhou
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
        """Carrega índice do disco com validação de integridade.

        Se o arquivo estiver corrompido (0 bytes, pickle inválido),
        faz backup do corrompido e retorna False.

        Returns:
            True se carregou com sucesso.
        """
        if not path.exists():
            return False

        # Validar tamanho mínimo (arquivo vazio = corrompido)
        try:
            file_size = path.stat().st_size
            if file_size == 0:
                logger.warning(
                    "⚠️ VectorStore corrompido (0 bytes) — removendo arquivo"
                )
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
            logger.info(f"📂 VectorStore carregado: {self.size} vetores")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Falha ao carregar VectorStore: {e}")
            self._quarantine_corrupted(path)
            return False

    @staticmethod
    def _quarantine_corrupted(path: Path) -> None:
        """Move arquivo corrompido para .corrupted para análise posterior."""
        try:
            backup = path.with_suffix(
                f".corrupted.{int(time.time())}"
            )
            shutil.move(str(path), str(backup))
            logger.warning(f"📦 Arquivo corrompido movido para {backup}")
        except Exception as e:
            logger.warning(f"⚠️ Não conseguiu mover corrompido: {e}")
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass


# ====================== DADOS MULTI-SOURCE COLLECTOR ======================
class MarketDataCollector:
    """Coleta dados de múltiplas fontes para gerar snapshots enriquecidos.

    Fontes:
      - KuCoin API (preço, orderbook, trade flow, candles)
      - Indicadores técnicos internos (FastIndicators)
      - CoinGecko (tendência macro via MCP, opcional)
    """

    def __init__(self, symbol: str = "BTC-USDT"):
        """Inicializa o coletor.

        Args:
            symbol: Par de trading principal.
        """
        self.symbol = symbol
        self._price_history: deque = deque(maxlen=500)
        self._last_candles: List[Dict] = []
        self._last_candle_fetch: float = 0.0

    def collect_snapshot(
        self,
        price: Optional[float] = None,
        indicators: Optional[object] = None,
        ob_analysis: Optional[Dict] = None,
        flow_analysis: Optional[Dict] = None,
    ) -> Optional[MarketSnapshot]:
        """Coleta um snapshot completo do mercado.

        Pode receber dados já coletados pelo trading loop (evita chamadas
        duplicadas à API). Se não fornecidos, coleta autonomamente.

        Args:
            price: Preço atual (opcional, coleta da API se None).
            indicators: FastIndicators instance (opcional).
            ob_analysis: Resultado de analyze_orderbook (opcional).
            flow_analysis: Resultado de analyze_trade_flow (opcional).

        Returns:
            MarketSnapshot ou None se falhar.
        """
        try:
            # Preço
            if price is None:
                from kucoin_api import get_price_fast
                price = get_price_fast(self.symbol, timeout=2)
            if price is None:
                return None

            self._price_history.append(price)

            # Orderbook
            if ob_analysis is None:
                from kucoin_api import analyze_orderbook
                ob_analysis = analyze_orderbook(self.symbol)

            # Trade flow
            if flow_analysis is None:
                from kucoin_api import analyze_trade_flow
                flow_analysis = analyze_trade_flow(self.symbol)

            # Candles de 1min (recarrega a cada 60s)
            now = time.time()
            if now - self._last_candle_fetch > 60:
                try:
                    from kucoin_api import get_candles
                    self._last_candles = get_candles(self.symbol, "1min", limit=100)
                    self._last_candle_fetch = now
                except Exception as e:
                    logger.debug(f"Candles fetch error: {e}")

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
                orderbook_imbalance=ob_analysis.get("imbalance", 0),
                spread=ob_analysis.get("spread", 0),
                bid_volume=ob_analysis.get("bid_volume", 0),
                ask_volume=ob_analysis.get("ask_volume", 0),
                trade_flow=flow_analysis.get("flow_bias", 0),
                buy_volume=flow_analysis.get("buy_volume", 0),
                sell_volume=flow_analysis.get("sell_volume", 0),
                sma_10=sma10,
                sma_30=sma30,
                sma_60=sma60,
                ema_20=ema20,
            )
            return snapshot

        except Exception as e:
            logger.warning(f"⚠️ Erro ao coletar snapshot: {e}")
            return None


# ====================== REGIME ADJUSTER (CÉREBRO) ======================
class RegimeAdjuster:
    """Ajusta thresholds de bull/bear baseado em padrões históricos similares.

    Fluxo:
      1. Recebe snapshot atual
      2. Busca TOP_K snapshots mais similares no VectorStore
      3. Analisa os outcomes (price_change_5m/15m) desses similares
      4. Calcula distribuição bull/bear/flat
      5. Gera RegimeAdjustment com novos thresholds

    Limites de segurança:
      - buy_threshold: [0.20, 0.50]
      - sell_threshold: [-0.50, -0.15]
      - Pesos ensemble: cada [0.05, 0.60], soma = 1.0
    """

    # Limites de segurança para thresholds
    BUY_TH_MIN = 0.20
    BUY_TH_MAX = 0.50
    SELL_TH_MIN = -0.50
    SELL_TH_MAX = -0.15

    # Limites de peso
    WEIGHT_MIN = 0.05
    WEIGHT_MAX = 0.60

    def __init__(self, symbol: str = "BTC-USDT"):
        """Inicializa o ajustador.

        Args:
            symbol: Par de trading.
        """
        self.symbol = symbol
        self._last_adjustment: Optional[RegimeAdjustment] = None
        self._adjustment_history: deque = deque(maxlen=100)

    def calculate_adjustment(
        self,
        current_snapshot: MarketSnapshot,
        similar_results: List[Tuple[float, Dict]],
    ) -> RegimeAdjustment:
        """Calcula ajuste de regime baseado em padrões similares.

        Args:
            current_snapshot: Snapshot atual do mercado.
            similar_results: Resultados da busca vetorial [(similaridade, metadata)].

        Returns:
            RegimeAdjustment com novos thresholds.
        """
        adjustment = RegimeAdjustment(
            timestamp=time.time(),
            symbol=self.symbol,
        )

        if not similar_results:
            logger.debug("⚠️ Sem resultados similares — usando defaults")
            self._last_adjustment = adjustment
            return adjustment

        # Filtrar apenas resultados com outcome definido
        valid = [
            (sim, meta) for sim, meta in similar_results
            if meta.get("outcome") is not None and sim > 0.5
        ]

        if len(valid) < 3:
            logger.debug(f"⚠️ Apenas {len(valid)} resultados válidos — usando defaults")
            self._last_adjustment = adjustment
            return adjustment

        adjustment.similar_count = len(valid)

        # Contar outcomes
        bull_count = sum(1 for _, m in valid if m.get("outcome") == "BULL")
        bear_count = sum(1 for _, m in valid if m.get("outcome") == "BEAR")
        flat_count = sum(1 for _, m in valid if m.get("outcome") == "FLAT")
        total = bull_count + bear_count + flat_count

        if total > 0:
            adjustment.bull_pct = bull_count / total
            adjustment.bear_pct = bear_count / total
            adjustment.flat_pct = flat_count / total

        # Retornos médios dos similares
        returns_5m = [m["price_change_5m"] for _, m in valid if m.get("price_change_5m") is not None]
        returns_15m = [m["price_change_15m"] for _, m in valid if m.get("price_change_15m") is not None]

        if returns_5m:
            adjustment.avg_return_5m = float(np.mean(returns_5m))
        if returns_15m:
            adjustment.avg_return_15m = float(np.mean(returns_15m))

        # ===== DETERMINAR REGIME =====
        if adjustment.bull_pct > 0.55:
            adjustment.suggested_regime = "BULLISH"
            adjustment.regime_confidence = adjustment.bull_pct
        elif adjustment.bear_pct > 0.55:
            adjustment.suggested_regime = "BEARISH"
            adjustment.regime_confidence = adjustment.bear_pct
        else:
            adjustment.suggested_regime = "RANGING"
            adjustment.regime_confidence = adjustment.flat_pct

        # ===== AJUSTAR THRESHOLDS =====
        # Lógica: em mercado bullish historicamente, reduzir threshold de compra
        # Em bearish, aumentar threshold de compra (mais cauteloso)
        base_buy = 0.30
        base_sell = -0.30

        if adjustment.suggested_regime == "BULLISH":
            # Mais fácil comprar, mais difícil vender
            buy_adj = -0.08 * adjustment.regime_confidence
            sell_adj = -0.05 * adjustment.regime_confidence
            adjustment.buy_threshold = np.clip(
                base_buy + buy_adj, self.BUY_TH_MIN, self.BUY_TH_MAX
            )
            adjustment.sell_threshold = np.clip(
                base_sell + sell_adj, self.SELL_TH_MIN, self.SELL_TH_MAX
            )

        elif adjustment.suggested_regime == "BEARISH":
            # Mais difícil comprar, mais fácil vender
            buy_adj = 0.15 * adjustment.regime_confidence
            sell_adj = 0.10 * adjustment.regime_confidence
            adjustment.buy_threshold = np.clip(
                base_buy + buy_adj, self.BUY_TH_MIN, self.BUY_TH_MAX
            )
            adjustment.sell_threshold = np.clip(
                base_sell + sell_adj, self.SELL_TH_MIN, self.SELL_TH_MAX
            )

        else:
            # RANGING: defaults inalterados
            adjustment.buy_threshold = base_buy
            adjustment.sell_threshold = base_sell

        # ===== AJUSTAR PESOS DO ENSEMBLE =====
        # Em mercados com padrão claro, dar mais peso aos técnicos
        # Em mercados ruidosos, dar mais peso ao orderbook (reativo)
        if adjustment.suggested_regime == "BEARISH":
            adjustment.weight_technical = 0.45
            adjustment.weight_orderbook = 0.25
            adjustment.weight_flow = 0.25
            adjustment.weight_qlearning = 0.05
        elif adjustment.suggested_regime == "BULLISH":
            adjustment.weight_technical = 0.30
            adjustment.weight_orderbook = 0.30
            adjustment.weight_flow = 0.25
            adjustment.weight_qlearning = 0.15
        else:
            adjustment.weight_technical = 0.35
            adjustment.weight_orderbook = 0.30
            adjustment.weight_flow = 0.25
            adjustment.weight_qlearning = 0.10

        # Garantir soma = 1.0
        total_w = (
            adjustment.weight_technical
            + adjustment.weight_orderbook
            + adjustment.weight_flow
            + adjustment.weight_qlearning
        )
        if abs(total_w - 1.0) > 0.001:
            adjustment.weight_technical /= total_w
            adjustment.weight_orderbook /= total_w
            adjustment.weight_flow /= total_w
            adjustment.weight_qlearning /= total_w

        # ===== AI TRADE GATING — parâmetros dinâmicos controlados pela IA =====
        self._calculate_ai_gating(adjustment)

        # ===== AI BUY TARGET — movido para MarketRAG._recalibrate() =====

        self._last_adjustment = adjustment
        self._adjustment_history.append(adjustment)

        return adjustment

    def _calculate_ai_gating(self, adj: RegimeAdjustment) -> None:
        """Calcula parâmetros de trade gating baseado no regime e padrões históricos.

        A IA ajusta dinamicamente:
        - Confiança mínima para executar trade
        - Cooldown entre trades
        - Se rebuy lock deve estar ativo
        - Margem do rebuy lock (compra antes mesmo de cair abaixo)
        - Agressividade geral

        Substitui as regras estáticas do config.json por decisão inteligente.
        """
        regime = adj.suggested_regime
        conf = adj.regime_confidence
        avg_5m = adj.avg_return_5m
        avg_15m = adj.avg_return_15m

        # ── Agressividade base por regime ──
        if regime == "BULLISH":
            # Mercado subindo: ser mais agressivo (comprar rápido, cooldown baixo)
            adj.ai_aggressiveness = 0.55 + 0.20 * conf  # 0.55 – 0.75
            adj.ai_min_confidence = max(0.56, 0.66 - 0.10 * conf)  # 56% – 66%
            adj.ai_min_trade_interval = max(90, int(210 - 90 * conf))  # 120s – 210s
            adj.ai_rebuy_lock_enabled = False  # Em bull, não esperar queda
            adj.ai_rebuy_margin_pct = 0.0

        elif regime == "BEARISH":
            # Mercado caindo: ser conservador mas permitir operações
            adj.ai_aggressiveness = max(0.08, 0.30 - 0.16 * conf)  # 0.14 – 0.30
            adj.ai_min_confidence = min(0.88, 0.70 + 0.12 * conf)  # 70% – 82%
            adj.ai_min_trade_interval = min(720, int(240 + 240 * conf))  # 240s – 480s
            adj.ai_rebuy_lock_enabled = True
            adj.ai_rebuy_margin_pct = 0.003 * conf  # 0% – 0.3% de margem extra

        else:
            # RANGING: moderado, usar padrões históricos para decidir
            # Retorno médio positivo → mais agressivo; negativo → mais cauteloso
            ret_signal = 1.0 if avg_5m > 0.0001 else (-1.0 if avg_5m < -0.0001 else 0.0)
            adj.ai_aggressiveness = 0.42 + 0.08 * ret_signal
            adj.ai_min_confidence = 0.64  # Padrão neutro mais seletivo
            adj.ai_min_trade_interval = 150  # 2.5 minutos
            adj.ai_rebuy_lock_enabled = True
            adj.ai_rebuy_margin_pct = 0.0015  # 0.15% margem — compra mais perto do nível

        # ── Ajuste fino pela qualidade dos dados (muitos similares = mais confiança) ──
        if adj.similar_count >= 10:
            # Bom histórico: confiar mais na decisão, reduzir confiança mínima
            adj.ai_min_confidence = max(0.50, adj.ai_min_confidence - 0.03)
        elif adj.similar_count < 3:
            # Pouco histórico: ser mais conservador
            adj.ai_min_confidence = min(0.80, adj.ai_min_confidence + 0.10)
            adj.ai_min_trade_interval = max(adj.ai_min_trade_interval, 300)

        # ── Safety clamps: nunca ultrapassar limites de segurança ──
        adj.ai_min_confidence = float(np.clip(adj.ai_min_confidence, 0.40, 0.85))
        adj.ai_min_trade_interval = int(np.clip(adj.ai_min_trade_interval, 30, 900))
        adj.ai_rebuy_margin_pct = float(np.clip(adj.ai_rebuy_margin_pct, 0.0, 0.01))

    def _calculate_ai_buy_target(self, adj: RegimeAdjustment,
                                  current_price: float,
                                  store: Optional['VectorStore'] = None) -> None:
        """Calcula o preço alvo de compra baseado em análise técnica da IA.

        Usa suporte recente, volatilidade, momentum e regime para determinar
        o melhor preço de entrada dinamicamente, substituindo o rebuy lock fixo.

        Args:
            adj: RegimeAdjustment a ser preenchido com buy_target.
            current_price: Preço atual do ativo.
            store: VectorStore com snapshots históricos.
        """
        try:
            if current_price <= 0:
                return

            if not store or store.size < 10:
                # Sem dados suficientes: aceitar preço atual (IA sem opinião)
                adj.ai_buy_target_price = round(current_price * 1.001, 2)
                adj.ai_buy_target_reason = "sem_dados:aceitar_preco_atual"
                return

            # --- 1. Coletar preços e indicadores dos snapshots recentes ---
            recent_prices: List[float] = []
            recent_volatilities: List[float] = []
            recent_momentums: List[float] = []

            n = min(200, store.size)
            for i in range(store.size - n, store.size):
                meta = store._metadata[i]
                if isinstance(meta, dict):
                    p = meta.get('price', 0)
                    if p > 0:
                        recent_prices.append(float(p))
                    recent_volatilities.append(float(meta.get('volatility', 0.01)))
                    recent_momentums.append(float(meta.get('momentum', 0.0)))

            if not recent_prices:
                adj.ai_buy_target_price = round(current_price * 1.001, 2)
                adj.ai_buy_target_reason = "sem_precos:aceitar_preco_atual"
                return

            # --- 2. Níveis técnicos ---
            prices_window = recent_prices[-100:]
            price_min = min(prices_window)
            price_max = max(prices_window)
            price_range = price_max - price_min if price_max > price_min else current_price * 0.001
            support_level = price_min + (price_range * 0.20)

            avg_vol = (
                sum(recent_volatilities[-50:]) / len(recent_volatilities[-50:])
                if recent_volatilities else 0.01
            )
            avg_mom = (
                sum(recent_momentums[-50:]) / len(recent_momentums[-50:])
                if recent_momentums else 0.0
            )

            regime = adj.suggested_regime
            confidence = adj.regime_confidence
            aggressiveness = adj.ai_aggressiveness

            # --- 3. Ajustar por regime ---
            if regime == "BULLISH":
                # Bull: comprar perto ou acima do preço atual (confirma tendência)
                regime_discount = 0.0008 + (0.0012 * (1.0 - confidence))
                target = current_price * (1.0 - regime_discount)
                reason = f"bull:desconto_{regime_discount * 100:.2f}%"

                # Momentum forte positivo → aceitar comprar ligeiramente acima
                if avg_mom > 0.003 and confidence > 0.6:
                    target = current_price * 1.0005
                    reason = f"bull_forte:mom_{avg_mom*100:.1f}%_conf_{confidence:.0%}"
                elif avg_mom > 0 and confidence > 0.5:
                    target = current_price * 0.9998
                    reason = f"bull:mom_positivo_{avg_mom*100:.2f}%"

            elif regime == "BEARISH":
                # Bear: esperar queda maior, mirar no suporte
                bear_severity = adj.bear_pct if adj.bear_pct > 0 else 0.5
                regime_discount = 0.004 + (0.009 * bear_severity * confidence)
                target = current_price * (1.0 - regime_discount)

                if target < support_level:
                    target = support_level
                    reason = f"bear:suporte_{support_level:.0f}"
                else:
                    reason = f"bear:desconto_{regime_discount * 100:.2f}%"

            else:  # RANGING
                # Comprar no terço inferior do range, com margem dinâmica
                lower_third = price_min + (price_range * 0.25)
                target = lower_third + (current_price - lower_third) * min(aggressiveness, 0.40)
                # Permitir target próximo do preço atual (a IA controla)
                # O clamp de segurança no final limita o teto
                reason = f"ranging:lower_{lower_third:.0f}_aggr_{aggressiveness:.0%}"

            # --- 4. Ajustar por volatilidade alta ---
            if avg_vol > 0.02:
                vol_adj = avg_vol * 0.3
                target *= (1.0 - vol_adj)
                reason += f"|vol_{avg_vol * 100:.1f}%"

            # --- 5. Limites de segurança (variáveis por regime) ---
            max_discount = current_price * 0.98  # piso: máximo 2% abaixo
            target = max(target, max_discount)

            # Teto: depende do regime — a IA decide o valor de entrada
            if regime == "BULLISH":
                # Em alta, permitir comprar até 0.3% acima do preço de
                # recalibração (confirmação de tendência)
                upper_limit = current_price * 1.001
            elif regime == "BEARISH":
                # Em queda, exigir desconto real — só comprar abaixo
                upper_limit = current_price * 0.995
            else:  # RANGING
                # Lateral, exigir leve desconto
                upper_limit = current_price * 0.9995
            target = min(target, upper_limit)

            adj.ai_buy_target_price = round(target, 2)
            adj.ai_buy_target_reason = reason

        except Exception as e:
            logger.error(f"❌ Erro ao calcular buy target: {e}")
            adj.ai_buy_target_price = round(current_price * 0.998, 2)
            adj.ai_buy_target_reason = "erro_fallback:0.2%"

    def _calculate_ai_take_profit(self, adj: RegimeAdjustment,
                                   current_price: float,
                                   store: Optional['VectorStore'] = None) -> None:
        """Calcula o take-profit dinâmico baseado em análise de regime, volatilidade e padrões.

        A IA define o percentual ideal de take-profit que é revisado a cada
        recalibração (~5min). Substitui o valor fixo do config.json.

        Fatores considerados:
          - Regime de mercado (BULL→TP mais amplo, BEAR→TP mais estreito)
          - Volatilidade recente (alta vol → TP mais largo para capturar swings)
          - Momentum (forte positivo → TP mais ambicioso)
          - Retornos históricos dos padrões similares (avg_return_5m/15m)
          - Resistência técnica (distância ao topo recente)

        Args:
            adj: RegimeAdjustment a ser preenchido com ai_take_profit_pct.
            current_price: Preço atual do ativo.
            store: VectorStore com snapshots históricos.
        """
        try:
            if current_price <= 0:
                return

            # --- 1. Base por regime ---
            regime = adj.suggested_regime
            confidence = adj.regime_confidence

            if regime == "BULLISH":
                # Mercado em alta: TP mais ambicioso, mas ainda realizável
                base_tp = 0.022 + 0.018 * confidence  # 2.2% → 4.0%
                reason = f"bull:base_{base_tp*100:.1f}%"
            elif regime == "BEARISH":
                # Mercado em queda: TP curto e defensivo
                base_tp = 0.018 - 0.008 * confidence  # 1.8% → 1.0%
                reason = f"bear:base_{base_tp*100:.1f}%"
            else:
                # RANGING: TP moderado e mais compatível com scalp/reversão curta
                base_tp = 0.012 + 0.008 * adj.ai_aggressiveness  # 1.2% → 2.0%
                reason = f"ranging:base_{base_tp*100:.1f}%"

            tp = base_tp

            # --- 2. Ajuste por volatilidade recente ---
            if store and store.size >= 20:
                recent_vols: list[float] = []
                n = min(100, store.size)
                for i in range(store.size - n, store.size):
                    meta = store._metadata[i]
                    if isinstance(meta, dict):
                        v = meta.get('volatility', 0.01)
                        if v > 0:
                            recent_vols.append(float(v))

                if recent_vols:
                    avg_vol = sum(recent_vols) / len(recent_vols)
                    # Alta volatilidade → TP mais largo (capturar swings maiores)
                    # Baixa volatilidade → TP mais estreito (mercado não se move muito)
                    if avg_vol > 0.02:
                        vol_adj = min(avg_vol * 0.35, 0.02)  # até +2%
                        tp += vol_adj
                        reason += f"|vol_alta_{avg_vol*100:.1f}%"
                    elif avg_vol < 0.005:
                        tp *= 0.8  # reduzir 20% em vol muito baixa
                        reason += f"|vol_baixa_{avg_vol*100:.2f}%"

            # --- 3. Ajuste por momentum ---
            if store and store.size >= 30:
                recent_moms: list[float] = []
                n = min(50, store.size)
                for i in range(store.size - n, store.size):
                    meta = store._metadata[i]
                    if isinstance(meta, dict):
                        m = meta.get('momentum', 0.0)
                        recent_moms.append(float(m))

                if recent_moms:
                    avg_mom = sum(recent_moms) / len(recent_moms)
                    if avg_mom > 0.003:
                        # Momentum forte positivo: ser mais ambicioso
                        tp += 0.003  # +0.3%
                        reason += f"|mom_forte_{avg_mom*100:.1f}%"
                    elif avg_mom < -0.003:
                        # Momentum negativo: realizar mais cedo
                        tp *= 0.75
                        reason += f"|mom_neg_{avg_mom*100:.1f}%"

            # --- 4. Ajuste por retornos históricos dos similares ---
            if adj.avg_return_15m > 0.003:
                # Padrões similares historicamente tiveram alta de >0.3% em 15min
                tp += 0.003
                reason += f"|hist_bull_{adj.avg_return_15m*100:.2f}%"
            elif adj.avg_return_15m < -0.003:
                # Padrões similares historicamente caíram — TP estreito
                tp *= 0.70
                reason += f"|hist_bear_{adj.avg_return_15m*100:.2f}%"

            # --- 5. Resistência técnica (distância ao topo recente) ---
            if store and store.size >= 50:
                recent_prices: list[float] = []
                n = min(200, store.size)
                for i in range(store.size - n, store.size):
                    meta = store._metadata[i]
                    if isinstance(meta, dict):
                        p = meta.get('price', 0)
                        if p > 0:
                            recent_prices.append(float(p))

                if recent_prices:
                    price_max = max(recent_prices)
                    # Distância ao topo: se preço está perto do máximo,
                    # limitar TP à distância ao topo (resistência natural)
                    dist_to_top = (price_max / current_price) - 1.0
                    if 0 < dist_to_top < tp and regime != "BULLISH":
                        # Não ser mais ambicioso que a resistência (exceto em BULL)
                        tp = max(dist_to_top * 0.9, 0.008)  # TP ≥ 0.8%
                        reason += f"|resist_{dist_to_top*100:.2f}%"

            # --- 6. Limites de segurança ---
            tp = float(np.clip(tp, 0.006, 0.05))  # Mínimo 0.6%, máximo 5%

            adj.ai_take_profit_pct = round(tp, 5)
            adj.ai_take_profit_reason = reason

        except Exception as e:
            logger.error(f"❌ Erro ao calcular AI take-profit: {e}")
            adj.ai_take_profit_pct = 0.025  # fallback ao config padrão
            adj.ai_take_profit_reason = "erro_fallback:2.5%"

    def _calculate_ai_position_size(self, adj: RegimeAdjustment,
                                     current_price: float,
                                     avg_entry_price: float = 0.0,
                                     position_count: int = 0,
                                     usdt_balance: float = 0.0,
                                     store: Optional['VectorStore'] = None) -> None:
        """Calcula tamanho e nº máximo de entradas controlado pela IA.

        A IA decide dinamicamente:
          - ai_position_size_pct: % do saldo USDT para cada entrada
          - ai_max_entries: nº máximo de entradas permitidas

        Fatores considerados:
          - Regime de mercado (BEAR → DCA conservador, BULL → entradas maiores)
          - Oportunidade de DCA (preço abaixo da média → entradas maiores)
          - Volatilidade (alta → entradas menores e mais frequentes)
          - Saldo disponível (adapta sizing ao capital real)
          - Confiança no regime

        Args:
            adj: RegimeAdjustment a ser preenchido.
            current_price: Preço atual do ativo.
            avg_entry_price: Preço médio de entrada da posição atual (0 se sem posição).
            position_count: Número de entradas já realizadas.
            usdt_balance: Saldo USDT disponível.
            store: VectorStore com snapshots históricos.
        """
        try:
            if current_price <= 0:
                return

            regime = adj.suggested_regime
            confidence = adj.regime_confidence
            aggressiveness = adj.ai_aggressiveness
            reason_parts: list[str] = []

            # --- 1. Base size % por regime ---
            if regime == "BULLISH":
                # Em alta: entradas maiores para capitalizar tendência
                base_pct = 0.045 + 0.020 * confidence  # 4.5% → 6.5%
                base_max_entries = 12
                reason_parts.append(f"bull:{base_pct*100:.1f}%")
            elif regime == "BEARISH":
                # Em queda: entradas menores e mais frequentes (DCA conservador)
                base_pct = 0.02 + 0.015 * (1.0 - confidence)  # 2.0% → 3.5%
                base_max_entries = 16
                reason_parts.append(f"bear:{base_pct*100:.1f}%")
            else:
                # RANGING: entradas moderadas
                base_pct = 0.03 + 0.015 * aggressiveness  # 3.0% → 4.5%
                base_max_entries = 12
                reason_parts.append(f"ranging:{base_pct*100:.1f}%")

            size_pct = base_pct
            max_entries = base_max_entries

            # --- 2. Boost de DCA: preço abaixo da média → entradas maiores ---
            if avg_entry_price > 0 and current_price < avg_entry_price:
                discount = (avg_entry_price - current_price) / avg_entry_price
                # Multiplicador DCA: até 2.5x para desconto de 5%+
                dca_mult = 1.0 + min(discount * 30, 1.5)  # 1% desconto → 1.3x, 5% → 2.5x
                size_pct *= dca_mult
                max_entries = max(max_entries, int(20 + discount * 100))  # mais entradas
                reason_parts.append(f"dca:{discount*100:.1f}%→{dca_mult:.1f}x")

            # --- 3. Ajuste por volatilidade ---
            if store and store.size >= 20:
                recent_vols: list[float] = []
                n = min(100, store.size)
                for i in range(store.size - n, store.size):
                    meta = store._metadata[i]
                    if isinstance(meta, dict):
                        v = meta.get('volatility', 0.01)
                        if v > 0:
                            recent_vols.append(float(v))

                if recent_vols:
                    avg_vol = sum(recent_vols) / len(recent_vols)
                    if avg_vol > 0.025:
                        # Alta volatilidade: entradas menores mas mais frequentes
                        size_pct *= 0.7
                        max_entries = min(max_entries + 5, 30)
                        reason_parts.append(f"vol_alta:{avg_vol*100:.1f}%")
                    elif avg_vol < 0.005:
                        # Baixa volatilidade: entradas maiores (mercado estável)
                        size_pct *= 1.3
                        reason_parts.append(f"vol_baixa:{avg_vol*100:.2f}%")

            # --- 4. Ajuste por saldo disponível ---
            if usdt_balance > 0:
                # Se saldo é pequeno, usar porção maior por entrada
                if usdt_balance < 20:
                    size_pct = max(size_pct, 0.08)
                    max_entries = min(max_entries, 6)
                    reason_parts.append(f"saldo_baixo:${usdt_balance:.1f}")
                elif usdt_balance < 50:
                    size_pct = max(size_pct, 0.06)
                    reason_parts.append(f"saldo_moderado:${usdt_balance:.1f}")

            # --- 5. Ajuste por número de entradas já realizadas ---
            if position_count > 10:
                # Reduzir tamanho progressivamente (mais cauteloso com muitas entradas)
                reduction = min(position_count * 0.02, 0.5)  # até 50% redução
                size_pct *= (1.0 - reduction)
                reason_parts.append(f"entries:{position_count}→-{reduction*100:.0f}%")

            # --- 6. Limites de segurança ---
            size_pct = float(np.clip(size_pct, 0.015, 0.12))  # 1.5% a 12% do saldo
            max_entries = max(4, min(max_entries, 24))  # 4 a 24 entradas

            adj.ai_position_size_pct = round(size_pct, 4)
            adj.ai_max_entries = max_entries
            adj.ai_position_size_reason = "|".join(reason_parts)

        except Exception as e:
            logger.error(f"❌ Erro ao calcular AI position size: {e}")
            adj.ai_position_size_pct = 0.04
            adj.ai_max_entries = 20
            adj.ai_position_size_reason = "erro_fallback:4%"


# ====================== MARKET RAG ENGINE ======================
class MarketRAG:
    """Motor principal do RAG de mercado.

    Integra VectorStore + Collector + Adjuster em um pipeline contínuo.
    Roda em thread separada, coletando snapshots e recalibrando
    periodicamente.

    Uso:
        rag = MarketRAG("BTC-USDT")
        rag.start()

        # No loop de trading:
        adj = rag.get_current_adjustment()
        model.buy_threshold = adj.buy_threshold
        ...

        rag.stop()
    """

    def __init__(
        self,
        symbol: str = "BTC-USDT",
        profile: str = "default",
        recalibrate_interval: int = DEFAULT_RECALIBRATE_INTERVAL,
        snapshot_interval: int = 30,
    ):
        """Inicializa o MarketRAG.

        Args:
            symbol: Par de trading.
            recalibrate_interval: Segundos entre recalibrações (default: 300 = 5min).
            snapshot_interval: Segundos entre coletas de snapshot (default: 30s).
        """
        self.symbol = symbol
        self.profile = profile or "default"
        self.recalibrate_interval = recalibrate_interval
        self.snapshot_interval = snapshot_interval
        suffix = "" if self.profile == "default" else f"_{self.profile}"
        self.adjustments_file = RAG_DIR / f"regime_adjustments{suffix}.json"

        self.store = VectorStore(dim=EMBEDDING_DIM, max_size=MAX_SNAPSHOTS)
        self.collector = MarketDataCollector(symbol)
        self.adjuster = RegimeAdjuster(symbol)

        # Buffer de snapshots recentes (para atualização retrospectiva)
        self._recent_snapshots: deque = deque(maxlen=200)

        # Estado
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

        # Contexto de trading (atualizado pelo trading agent)
        self._trading_context: Dict = {
            "avg_entry_price": 0.0,
            "position_count": 0,
            "usdt_balance": 0.0,
            "max_position_pct": 0.5,
            "max_positions": 3,
            "profile": "default",
        }
        self._ollama_trade_controls: Dict = {}

        # Carregar dados persistidos
        self.store.load()

    def start(self) -> None:
        """Inicia o thread de coleta e recalibração."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("⚠️ MarketRAG já está rodando")
            return

        self._stop_event.clear()
        # Thread NÃO-daemon: garante que save() complete antes do exit
        self._thread = threading.Thread(
            target=self._run_loop, daemon=False, name="MarketRAG"
        )
        self._thread.start()
        logger.info(
            f"🧠 MarketRAG iniciado: {self.symbol} "
            f"(snapshot={self.snapshot_interval}s, recalibrate={self.recalibrate_interval}s)"
        )

    def stop(self) -> None:
        """Para o thread e persiste dados.

        Aguarda o thread finalizar com timeout generoso para evitar
        truncamento do VectorStore durante escrita.
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=30)  # 30s para garantir save completo
            if self._thread.is_alive():
                logger.warning("⚠️ MarketRAG thread não finalizou em 30s")
        self.store.save()
        self._save_adjustments()
        logger.info("🛑 MarketRAG parado e dados salvos")

    def get_current_adjustment(self) -> RegimeAdjustment:
        """Retorna o ajuste atual de regime (thread-safe).

        Returns:
            RegimeAdjustment mais recente.
        """
        with self._lock:
            return self._current_adjustment

    def set_trading_context(
        self,
        avg_entry_price: float = 0.0,
        position_count: int = 0,
        usdt_balance: float = 0.0,
        max_position_pct: float = 0.5,
        max_positions: int = 3,
        profile: str = "default",
    ) -> None:
        """Atualiza contexto de trading para cálculo de position sizing pela IA.

        Deve ser chamado periodicamente pelo trading agent para que o RAG
        tenha informações da posição atual ao calcular sizing dinâmico.

        Args:
            avg_entry_price: Preço médio de entrada da posição atual.
            position_count: Número de entradas já realizadas.
            usdt_balance: Saldo USDT disponível.
            max_position_pct: Cap hard de exposição total permitido pelo perfil.
            max_positions: Cap hard de entradas simultâneas permitido pelo perfil.
            profile: Perfil lógico da instância.
        """
        self._trading_context = {
            "avg_entry_price": avg_entry_price,
            "position_count": position_count,
            "usdt_balance": usdt_balance,
            "max_position_pct": max(0.01, float(max_position_pct or 0.5)),
            "max_positions": max(1, int(max_positions or 3)),
            "profile": str(profile or "default"),
        }

    def feed_snapshot(
        self,
        price: Optional[float] = None,
        indicators: Optional[object] = None,
        ob_analysis: Optional[Dict] = None,
        flow_analysis: Optional[Dict] = None,
    ) -> Optional[MarketSnapshot]:
        """Alimenta o RAG com dados do loop de trading (evita chamadas duplicadas).

        Pode ser chamado diretamente do trading loop para reutilizar dados coletados.

        Args:
            price: Preço atual.
            indicators: FastIndicators instance.
            ob_analysis: Resultado de analyze_orderbook.
            flow_analysis: Resultado de analyze_trade_flow.

        Returns:
            MarketSnapshot gerado ou None.
        """
        now = time.time()
        if now - self._last_snapshot_time < self.snapshot_interval:
            return None

        snapshot = self.collector.collect_snapshot(
            price=price,
            indicators=indicators,
            ob_analysis=ob_analysis,
            flow_analysis=flow_analysis,
        )
        if snapshot is None:
            return None

        self._ingest_snapshot(snapshot)
        return snapshot

    def force_recalibrate(self) -> RegimeAdjustment:
        """Força uma recalibração imediata.

        Returns:
            Novo RegimeAdjustment.
        """
        return self._recalibrate()

    def get_stats(self) -> Dict:
        """Retorna estatísticas do RAG.

        Returns:
            Dicionário com métricas.
        """
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
        """Registra sugestão estruturada do Ollama e recalcula os controles efetivos."""
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
        self,
        adjustment: RegimeAdjustment,
        suggestion: Optional[Dict],
    ) -> None:
        """Aplica sugestão do Ollama sobre o baseline do RAG, respeitando clamps."""
        if not suggestion:
            return

        mode = str(suggestion.get("mode") or "shadow").strip().lower()
        if mode not in {"shadow", "apply"}:
            mode = "shadow"

        baseline_conf = float(adjustment.baseline_min_confidence or adjustment.ai_min_confidence or 0.60)
        baseline_interval = int(adjustment.baseline_min_trade_interval or adjustment.ai_min_trade_interval or 180)
        baseline_cap_pct = max(0.01, float(adjustment.baseline_max_position_pct or 0.5))
        baseline_max_positions = max(1, int(adjustment.baseline_max_positions or 3))

        conf_floor = max(0.40, baseline_conf - 0.10)
        conf_ceiling = min(0.92, baseline_conf + 0.10)
        interval_floor = max(30, int(round(baseline_interval * 0.50)))
        interval_ceiling = min(900, int(round(baseline_interval * 1.80)))
        cap_pct_floor = max(0.01, baseline_cap_pct * 0.25)

        suggested_conf = float(np.clip(
            float(suggestion.get("min_confidence") or baseline_conf),
            conf_floor,
            conf_ceiling,
        ))
        suggested_interval = int(np.clip(
            int(round(float(suggestion.get("min_trade_interval") or baseline_interval))),
            interval_floor,
            interval_ceiling,
        ))
        suggested_cap_pct = float(np.clip(
            float(suggestion.get("max_position_pct") or baseline_cap_pct),
            cap_pct_floor,
            baseline_cap_pct,
        ))
        suggested_max_positions = int(np.clip(
            int(round(float(suggestion.get("max_positions") or baseline_max_positions))),
            1,
            baseline_max_positions,
        ))

        adjustment.ollama_mode = mode
        adjustment.ollama_last_update = float(suggestion.get("timestamp") or time.time())
        adjustment.ollama_trigger = str(suggestion.get("trigger") or "")
        adjustment.ollama_model = str(suggestion.get("model") or "")
        adjustment.ollama_reason = str(suggestion.get("rationale") or "")[:500]
        adjustment.ollama_suggested_min_confidence = suggested_conf
        adjustment.ollama_suggested_min_trade_interval = suggested_interval
        adjustment.ollama_suggested_max_position_pct = suggested_cap_pct
        adjustment.ollama_suggested_max_positions = suggested_max_positions

        if mode == "apply":
            adjustment.applied_min_confidence = float(np.clip(
                baseline_conf + (suggested_conf - baseline_conf) * 0.35,
                0.40,
                0.92,
            ))
            adjustment.applied_min_trade_interval = int(np.clip(
                round(baseline_interval + (suggested_interval - baseline_interval) * 0.50),
                30,
                900,
            ))
            adjustment.applied_max_position_pct = min(baseline_cap_pct, suggested_cap_pct)
            adjustment.applied_max_positions = max(1, min(baseline_max_positions, suggested_max_positions))
        else:
            adjustment.applied_min_confidence = baseline_conf
            adjustment.applied_min_trade_interval = baseline_interval
            adjustment.applied_max_position_pct = baseline_cap_pct
            adjustment.applied_max_positions = baseline_max_positions

    def _ingest_snapshot(self, snapshot: MarketSnapshot) -> None:
        """Ingere um snapshot: adiciona ao store e ao buffer recente."""
        embedding = snapshot.to_embedding()
        metadata = snapshot.to_dict()
        self.store.add(embedding, metadata)
        self._recent_snapshots.append(snapshot)
        self._last_snapshot_time = snapshot.timestamp
        self._stats["snapshots_collected"] += 1

    def _update_outcomes(self) -> None:
        """Atualiza os outcomes dos snapshots antigos com dados futuros.

        Para cada snapshot no buffer recente que ainda não tem outcome,
        verifica se já passou tempo suficiente para calcular price_change.
        """
        now = time.time()
        updated = 0

        for snap in self._recent_snapshots:
            if snap.outcome is not None:
                continue

            elapsed = now - snap.timestamp

            # Precisa de pelo menos 5 min de dados futuros
            if elapsed < 300:
                continue

            # Buscar preço 5 min depois
            target_time_5m = snap.timestamp + 300
            price_5m = self._find_price_at(target_time_5m)

            if price_5m is not None and snap.price > 0:
                snap.price_change_5m = (price_5m / snap.price) - 1

            # 15 min
            if elapsed >= 900:
                price_15m = self._find_price_at(snap.timestamp + 900)
                if price_15m is not None and snap.price > 0:
                    snap.price_change_15m = (price_15m / snap.price) - 1

            # 60 min
            if elapsed >= 3600:
                price_60m = self._find_price_at(snap.timestamp + 3600)
                if price_60m is not None and snap.price > 0:
                    snap.price_change_60m = (price_60m / snap.price) - 1

            # Determinar outcome baseado em 5m
            if snap.price_change_5m is not None:
                if snap.price_change_5m > 0.002:       # > +0.2%
                    snap.outcome = "BULL"
                elif snap.price_change_5m < -0.002:     # < -0.2%
                    snap.outcome = "BEAR"
                else:
                    snap.outcome = "FLAT"

                # Atualizar metadata no VectorStore
                self._update_store_metadata(snap)
                updated += 1

        if updated > 0:
            self._stats["outcomes_updated"] += updated
            logger.debug(f"📊 Outcomes atualizados: {updated} snapshots")

    def _find_price_at(self, target_time: float) -> Optional[float]:
        """Encontra o preço mais próximo de um timestamp alvo.

        Args:
            target_time: Unix timestamp alvo.

        Returns:
            Preço mais próximo ou None se não encontrado.
        """
        best_price = None
        best_diff = float("inf")

        for snap in self._recent_snapshots:
            diff = abs(snap.timestamp - target_time)
            if diff < best_diff and diff < 60:  # Tolerância de 60s
                best_diff = diff
                best_price = snap.price

        return best_price

    def _update_store_metadata(self, snapshot: MarketSnapshot) -> None:
        """Atualiza metadata de um snapshot existente no VectorStore.

        Args:
            snapshot: Snapshot com outcome atualizado.
        """
        # Busca por timestamp para encontrar o entry existente
        for meta in self.store._metadata:
            if abs(meta.get("timestamp", 0) - snapshot.timestamp) < 1.0:
                meta["price_change_5m"] = snapshot.price_change_5m
                meta["price_change_15m"] = snapshot.price_change_15m
                meta["price_change_60m"] = snapshot.price_change_60m
                meta["outcome"] = snapshot.outcome
                self.store._dirty = True
                break

    def _recalibrate(self) -> RegimeAdjustment:
        """Executa recalibração: busca similares e calcula novo ajuste.

        Returns:
            Novo RegimeAdjustment.
        """
        # Atualizar outcomes pendentes primeiro
        self._update_outcomes()

        # Gerar snapshot atual para busca
        snapshot = self.collector.collect_snapshot()
        if snapshot is None:
            return self._current_adjustment

        # Busca vetorial
        query = snapshot.to_embedding()
        similar = self.store.search(query, top_k=TOP_K)

        # Calcular ajuste
        adjustment = self.adjuster.calculate_adjustment(snapshot, similar)

        # ===== AI BUY TARGET — preço alvo de compra calculado pela IA =====
        if snapshot.price > 0:
            self.adjuster._calculate_ai_buy_target(
                adjustment, snapshot.price, store=self.store
            )

        # ===== AI TAKE-PROFIT — % dinâmico calculado pela IA =====
        if snapshot.price > 0:
            self.adjuster._calculate_ai_take_profit(
                adjustment, snapshot.price, store=self.store
            )

        # ===== AI POSITION SIZING — tamanho e nº de entradas controlados pela IA =====
        if snapshot.price > 0:
            ctx = self._trading_context
            self.adjuster._calculate_ai_position_size(
                adjustment,
                snapshot.price,
                avg_entry_price=ctx.get("avg_entry_price", 0.0),
                position_count=ctx.get("position_count", 0),
                usdt_balance=ctx.get("usdt_balance", 0.0),
                store=self.store,
            )

        self._apply_trade_control_baselines(adjustment)
        if self._ollama_trade_controls:
            self._apply_ollama_trade_controls(adjustment, self._ollama_trade_controls)

        # Atualizar thread-safe
        with self._lock:
            self._current_adjustment = adjustment

        self._last_recalibrate_time = time.time()
        self._stats["recalibrations"] += 1

        # Persistir snapshots a cada 5 recalibrações, ajustes sempre
        self._save_adjustments()
        if self._stats["recalibrations"] % 5 == 0:
            self.store.save()

        logger.info(
            f"🎯 RAG Adjustment: regime={adjustment.suggested_regime} "
            f"(conf={adjustment.regime_confidence:.1%}), "
            f"buy_th={adjustment.buy_threshold:.3f}, "
            f"sell_th={adjustment.sell_threshold:.3f}, "
            f"bull={adjustment.bull_pct:.1%}/bear={adjustment.bear_pct:.1%}/flat={adjustment.flat_pct:.1%}, "
            f"similares={adjustment.similar_count}, "
            f"ai_conf={adjustment.applied_min_confidence:.0%}, "
            f"ai_cooldown={adjustment.applied_min_trade_interval}s, "
            f"rebuy={'ON' if adjustment.ai_rebuy_lock_enabled else 'OFF'}, "
            f"buy_target=${adjustment.ai_buy_target_price:,.2f} ({adjustment.ai_buy_target_reason}), "
            f"ai_tp={adjustment.ai_take_profit_pct*100:.2f}% ({adjustment.ai_take_profit_reason}), "
            f"sizing={adjustment.ai_position_size_pct*100:.1f}%×{adjustment.ai_max_entries} ({adjustment.ai_position_size_reason}), "
            f"risk_cap={adjustment.applied_max_position_pct*100:.1f}%/{adjustment.applied_max_positions}, "
            f"ollama={adjustment.ollama_mode}"
        )

        return adjustment

    def _run_loop(self) -> None:
        """Loop principal do thread de RAG."""
        logger.info("🧠 MarketRAG loop iniciado")

        while not self._stop_event.is_set():
            try:
                now = time.time()

                # Coletar snapshot
                if now - self._last_snapshot_time >= self.snapshot_interval:
                    snapshot = self.collector.collect_snapshot()
                    if snapshot is not None:
                        self._ingest_snapshot(snapshot)

                # Recalibrar
                if now - self._last_recalibrate_time >= self.recalibrate_interval:
                    self._recalibrate()

                # Sleep curto para responsividade
                self._stop_event.wait(timeout=5)

            except Exception as e:
                logger.error(f"❌ MarketRAG loop error: {e}")
                self._stop_event.wait(timeout=10)

        # Salvar ao sair
        self.store.save()
        self._save_adjustments()
        logger.info("🧠 MarketRAG loop finalizado")

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
                        "history": history[-50:],  # Últimos 50
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.warning(f"⚠️ Erro ao salvar ajustes: {e}")


# ====================== TESTE ======================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("🧠 Market RAG — Teste de Componentes")
    print("=" * 60)

    # 1. Teste VectorStore
    print("\n--- VectorStore ---")
    vs = VectorStore(dim=EMBEDDING_DIM)
    for i in range(100):
        vec = np.random.randn(EMBEDDING_DIM).astype(np.float32)
        meta = {
            "timestamp": time.time() - (100 - i) * 60,
            "price": 70000 + i * 10,
            "outcome": np.random.choice(["BULL", "BEAR", "FLAT"]),
            "price_change_5m": (np.random.random() - 0.5) * 0.01,
        }
        vs.add(vec, meta)
    print(f"  Vetores: {vs.size}")

    query = np.random.randn(EMBEDDING_DIM).astype(np.float32)
    results = vs.search(query, top_k=5)
    print(f"  Top 5 similaridades: {[f'{s:.3f}' for s, _ in results]}")

    # 2. Teste MarketSnapshot embedding
    print("\n--- MarketSnapshot ---")
    snap = MarketSnapshot(
        timestamp=time.time(),
        symbol="BTC-USDT",
        price=71000,
        rsi=35,
        momentum=-0.5,
        volatility=0.015,
        trend=-0.2,
        orderbook_imbalance=-0.3,
        trade_flow=0.1,
        sma_10=71100,
        sma_30=71500,
        sma_60=72000,
    )
    emb = snap.to_embedding()
    print(f"  Embedding shape: {emb.shape}")
    print(f"  Embedding range: [{emb.min():.3f}, {emb.max():.3f}]")

    # 3. Teste RegimeAdjuster
    print("\n--- RegimeAdjuster ---")
    adjuster = RegimeAdjuster("BTC-USDT")
    mock_similar = [
        (0.85, {"outcome": "BEAR", "price_change_5m": -0.003}),
        (0.82, {"outcome": "BEAR", "price_change_5m": -0.005}),
        (0.78, {"outcome": "BEAR", "price_change_5m": -0.002}),
        (0.75, {"outcome": "FLAT", "price_change_5m": 0.001}),
        (0.72, {"outcome": "BULL", "price_change_5m": 0.004}),
    ]
    adj = adjuster.calculate_adjustment(snap, mock_similar)
    print(f"  Regime: {adj.suggested_regime} ({adj.regime_confidence:.1%})")
    print(f"  Buy threshold: {adj.buy_threshold:.3f}")
    print(f"  Sell threshold: {adj.sell_threshold:.3f}")
    print(f"  Bull/Bear/Flat: {adj.bull_pct:.0%}/{adj.bear_pct:.0%}/{adj.flat_pct:.0%}")

    print("\n✅ Todos os componentes validados!")
