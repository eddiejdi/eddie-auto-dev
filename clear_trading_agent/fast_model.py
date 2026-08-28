#!/usr/bin/env python3
"""
Fast Trading Model — Modelo para decisões de trading B3.
Adaptado do btc_trading_agent/fast_model.py para mercado brasileiro.

Indicadores técnicos + Q-learning para sinais BUY/SELL/HOLD em ações e minicontratos.
Diferenças do modelo crypto:
  - Horário de mercado B3 (10:00–17:55 BRT)
  - Preços em BRL
  - Volatilidade e momentum calibrados para equities
"""
from __future__ import annotations

import json
import logging
import pickle
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ====================== CONSTANTES ======================
EPSILON = 1e-10
MODEL_DIR = Path(__file__).parent / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Horário de pregão B3 (BRT = UTC-3)
B3_OPEN_HOUR = 10   # 10:00
B3_OPEN_MIN = 0
B3_CLOSE_HOUR = 17  # 17:55
B3_CLOSE_MIN = 55


# ====================== DATA CLASSES ======================
@dataclass
class MarketState:
    """Estado atual do mercado B3."""

    price: float
    bid: float = 0.0
    ask: float = 0.0
    spread: float = 0.0
    spread_pct: float = 0.0
    trade_flow: float = 0.0        # -1 a +1
    volume_ratio: float = 1.0      # volume atual / média
    rsi: float = 50.0              # 0-100
    momentum: float = 0.0          # % mudança
    volatility: float = 0.0        # desvio padrão normalizado
    trend: float = 0.0             # -1 (down) a +1 (up)
    timestamp: float = field(default_factory=time.time)

    def to_features(self) -> np.ndarray:
        """Converte para array de features (8-dim)."""
        return np.array([
            self.spread_pct * 100,     # Spread em %
            self.trade_flow,
            (self.rsi - 50) / 50,      # Normalizado -1 a +1
            self.momentum / 10,         # Normalizado
            self.volatility,
            self.trend,
            self.spread * 100,          # Em centavos (BRL)
            self.volume_ratio - 1,      # Desvio da média
        ])


@dataclass
class Signal:
    """Sinal de trading gerado pelo modelo."""

    action: str        # "BUY", "SELL", "HOLD"
    confidence: float  # 0.0 a 1.0
    price: float
    reason: str
    features: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class MarketRegime:
    """Regime atual do mercado detectado automaticamente."""

    regime: str = "RANGING"   # BULLISH, BEARISH, RANGING
    strength: float = 0.0     # 0.0 (fraco) a 1.0 (forte)
    duration: int = 0         # Ciclos nesse regime

    @property
    def is_bearish(self) -> bool:
        """Indica se o regime é bearish."""
        return self.regime == "BEARISH"

    @property
    def is_bullish(self) -> bool:
        """Indica se o regime é bullish."""
        return self.regime == "BULLISH"


# ====================== HORÁRIO DE MERCADO ======================
def is_market_open() -> bool:
    """Verifica se o mercado B3 está aberto (10:00–17:55 BRT, dias úteis)."""
    from datetime import datetime, timezone, timedelta

    brt = timezone(timedelta(hours=-3))
    now = datetime.now(brt)

    # Fins de semana
    if now.weekday() >= 5:
        return False

    # Horário de pregão
    market_open = now.replace(hour=B3_OPEN_HOUR, minute=B3_OPEN_MIN, second=0)
    market_close = now.replace(hour=B3_CLOSE_HOUR, minute=B3_CLOSE_MIN, second=0)
    return market_open <= now <= market_close


def minutes_to_market_open() -> int:
    """Retorna minutos até a próxima abertura do mercado (0 se já aberto)."""
    if is_market_open():
        return 0

    from datetime import datetime, timezone, timedelta

    brt = timezone(timedelta(hours=-3))
    now = datetime.now(brt)

    # Próxima abertura
    next_open = now.replace(hour=B3_OPEN_HOUR, minute=B3_OPEN_MIN, second=0, microsecond=0)
    if now >= next_open:
        # Próximo dia útil
        next_open += timedelta(days=1)
    while next_open.weekday() >= 5:
        next_open += timedelta(days=1)

    delta = next_open - now
    return int(delta.total_seconds() / 60)


# ====================== INDICADORES TÉCNICOS ======================
class FastIndicators:
    """Indicadores técnicos otimizados para velocidade."""

    def __init__(self, max_history: int = 500) -> None:
        self.prices: deque[float] = deque(maxlen=max_history)
        self.volumes: deque[float] = deque(maxlen=max_history)
        self.timestamps: deque[float] = deque(maxlen=max_history)
        self._candles_loaded = False

    def update(self, price: float, volume: float = 0) -> None:
        """Atualiza histórico com um tick."""
        self.prices.append(price)
        self.volumes.append(volume)
        self.timestamps.append(time.time())

    def update_from_candles(self, candles: list) -> None:
        """Popula histórico a partir de candles OHLCV."""
        if not candles:
            return

        if self._candles_loaded and len(self.prices) >= len(candles):
            last = candles[-1]
            if self.prices and abs(self.prices[-1] - last["close"]) > 0.001:
                self.prices[-1] = last["close"]
                self.volumes[-1] = last.get("volume", 0)
            return

        self.prices.clear()
        self.volumes.clear()
        self.timestamps.clear()

        for c in candles:
            self.prices.append(c["close"])
            self.volumes.append(c.get("volume", 0))
            self.timestamps.append(c.get("timestamp", time.time()))

        self._candles_loaded = True
        logger.debug("📊 Indicadores carregados de %d candles", len(candles))

    def rsi(self, period: int = 14) -> float:
        """RSI otimizado."""
        if len(self.prices) < period + 1:
            return 50.0

        prices = list(self.prices)[-(period + 1):]
        gains = []
        losses = []

        for i in range(1, len(prices)):
            diff = prices[i] - prices[i - 1]
            if diff > 0:
                gains.append(diff)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(diff))

        avg_gain = np.mean(gains) if gains else EPSILON
        avg_loss = np.mean(losses) if losses else EPSILON

        rs = avg_gain / (avg_loss + EPSILON)
        return float(100 - (100 / (1 + rs)))

    def momentum(self, period: int = 10) -> float:
        """Momentum como % de mudança."""
        if len(self.prices) < period:
            return 0.0
        current = self.prices[-1]
        past = self.prices[-period]
        return float(((current / past) - 1) * 100) if past > 0 else 0.0

    def volatility(self, period: int = 20) -> float:
        """Volatilidade normalizada (0–1)."""
        if len(self.prices) < period:
            return 0.0
        prices = list(self.prices)[-period:]
        returns = np.diff(prices) / (np.array(prices[:-1]) + EPSILON)
        vol = float(np.std(returns))
        return min(vol * 100, 1.0)

    def trend(self, short: int = 10, long: int = 30) -> float:
        """Trend como diferença de médias móveis normalizada."""
        if len(self.prices) < long:
            return 0.0
        prices = list(self.prices)
        sma_short = float(np.mean(prices[-short:]))
        sma_long = float(np.mean(prices[-long:]))
        diff_pct = ((sma_short / sma_long) - 1) * 100
        return float(np.clip(diff_pct, -1, 1))

    def ema(self, period: int = 20) -> float:
        """EMA rápida."""
        if len(self.prices) < 2:
            return float(self.prices[-1]) if self.prices else 0.0
        prices = list(self.prices)[-period:]
        alpha = 2 / (period + 1)
        ema_val = prices[0]
        for p in prices[1:]:
            ema_val = alpha * p + (1 - alpha) * ema_val
        return float(ema_val)

    def volume_ratio(self, period: int = 20) -> float:
        """Ratio volume atual / média."""
        if len(self.volumes) < period or not self.volumes[-1]:
            return 1.0
        avg_vol = float(np.mean(list(self.volumes)[-period:]))
        if avg_vol <= 0:
            return 1.0
        return float(self.volumes[-1] / avg_vol)

    def detect_regime(self, short: int = 10, mid: int = 30, long: int = 60) -> MarketRegime:
        """Detecta regime de mercado baseado em múltiplos timeframes."""
        n = len(self.prices)
        if n < long:
            return MarketRegime("RANGING", 0.0, 0)

        prices = list(self.prices)

        sma_short = float(np.mean(prices[-short:]))
        sma_mid = float(np.mean(prices[-mid:]))
        sma_long = float(np.mean(prices[-long:]))
        current = prices[-1]

        bearish_signals = 0
        bullish_signals = 0

        # 1. Alinhamento de SMAs
        if sma_short < sma_mid < sma_long:
            bearish_signals += 2
        elif sma_short > sma_mid > sma_long:
            bullish_signals += 2

        # 2. Preço vs SMAs
        if current < sma_short and current < sma_mid:
            bearish_signals += 1
        elif current > sma_short and current > sma_mid:
            bullish_signals += 1

        # 3. Momentum
        mom = self.momentum(period=min(20, n - 1))
        if mom < -0.3:
            bearish_signals += 1
        elif mom > 0.3:
            bullish_signals += 1

        # 4. Lower highs / higher lows
        if n >= 40:
            chunk_size = n // 4
            quarters = [prices[i * chunk_size:(i + 1) * chunk_size] for i in range(4)]
            highs = [max(q) for q in quarters if q]
            lows = [min(q) for q in quarters if q]

            if len(highs) >= 3 and all(highs[i] > highs[i + 1] for i in range(len(highs) - 1)):
                bearish_signals += 1
            if len(lows) >= 3 and all(lows[i] < lows[i + 1] for i in range(len(lows) - 1)):
                bullish_signals += 1

        # Classificação
        total = bearish_signals + bullish_signals
        if total == 0:
            return MarketRegime("RANGING", 0.0, 0)

        if bearish_signals > bullish_signals:
            strength = bearish_signals / (total + 1)
            return MarketRegime("BEARISH", min(strength, 1.0), 0)
        elif bullish_signals > bearish_signals:
            strength = bullish_signals / (total + 1)
            return MarketRegime("BULLISH", min(strength, 1.0), 0)
        else:
            return MarketRegime("RANGING", 0.3, 0)


# ====================== Q-LEARNING ======================
class FastQLearning:
    """Q-learning compacto para ações discretizadas."""

    def __init__(self, n_states: int = 5000, n_actions: int = 3) -> None:
        self.n_states = n_states
        self.n_actions = n_actions
        self.q_table = np.zeros((n_states, n_actions))
        self.learning_rate = 0.1
        self.discount = 0.95
        self.epsilon = 0.1

    def discretize(self, features: np.ndarray) -> int:
        """Discretiza features em um índice de estado."""
        h = hash(tuple(np.round(features, 2).tolist()))
        return abs(h) % self.n_states

    def get_action(self, state: int) -> int:
        """Seleciona ação (0=HOLD, 1=BUY, 2=SELL) com epsilon-greedy."""
        if np.random.random() < self.epsilon:
            return int(np.random.randint(self.n_actions))
        return int(np.argmax(self.q_table[state]))

    def update(self, state: int, action: int, reward: float, next_state: int) -> None:
        """Atualiza Q-value."""
        best_next = float(np.max(self.q_table[next_state]))
        current = self.q_table[state, action]
        self.q_table[state, action] = current + self.learning_rate * (
            reward + self.discount * best_next - current
        )

    def save(self, path: Path) -> None:
        """Salva Q-table em disco."""
        with open(path, "wb") as f:
            pickle.dump({"q_table": self.q_table, "n_states": self.n_states}, f)
        logger.debug("💾 Q-table salva: %s", path)

    def load(self, path: Path) -> bool:
        """Carrega Q-table do disco."""
        if not path.exists():
            return False
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self.q_table = data["q_table"]
            self.n_states = data["n_states"]
            logger.info("📂 Q-table carregada: %s", path)
            return True
        except Exception as e:
            logger.warning("⚠️ Falha ao carregar Q-table: %s", e)
            return False


# ====================== MODELO PRINCIPAL ======================
class FastTradingModel:
    """Modelo de trading rápido para B3: indicadores + Q-learning."""

    def __init__(self, symbol: str = "PETR4") -> None:
        self.symbol = symbol
        self.indicators = FastIndicators()
        self.qlearning = FastQLearning()
        self._last_state: Optional[int] = None
        self._last_action: Optional[int] = None
        self._signal_count = 0

        # Tentar carregar Q-table existente
        qt_path = MODEL_DIR / f"qtable_{symbol}.pkl"
        self.qlearning.load(qt_path)

    def update(self, price: float, volume: float = 0) -> None:
        """Atualiza indicadores com novo tick."""
        self.indicators.update(price, volume)

    def update_from_candles(self, candles: list) -> None:
        """Atualiza indicadores a partir de candles OHLCV."""
        self.indicators.update_from_candles(candles)

    def generate_signal(self, market_state: MarketState) -> Signal:
        """Gera sinal de trading a partir do estado de mercado."""
        features = market_state.to_features()
        state = self.qlearning.discretize(features)
        action = self.qlearning.get_action(state)

        # Mapear ação para sinal
        action_map = {0: "HOLD", 1: "BUY", 2: "SELL"}
        action_name = action_map[action]

        # Calcular confiança baseada em Q-values
        q_values = self.qlearning.q_table[state]
        q_range = float(np.max(q_values) - np.min(q_values))
        confidence = min(q_range / 10, 1.0)  # Normalizar

        # Boost de confiança baseado em indicadores
        rsi = market_state.rsi
        if action_name == "BUY" and rsi < 30:
            confidence = min(confidence + 0.2, 1.0)
        elif action_name == "SELL" and rsi > 70:
            confidence = min(confidence + 0.2, 1.0)

        # Verificar horário de mercado
        if not is_market_open() and action_name != "HOLD":
            action_name = "HOLD"
            confidence = 0.0

        # Gerar razão
        regime = self.indicators.detect_regime()
        reason = (
            f"{action_name} | RSI={rsi:.1f} mom={market_state.momentum:.2f}% "
            f"vol={market_state.volatility:.3f} trend={market_state.trend:.3f} "
            f"regime={regime.regime}({regime.strength:.2f})"
        )

        self._last_state = state
        self._last_action = action
        self._signal_count += 1

        return Signal(
            action=action_name,
            confidence=confidence,
            price=market_state.price,
            reason=reason,
            features={
                "rsi": rsi,
                "momentum": market_state.momentum,
                "volatility": market_state.volatility,
                "trend": market_state.trend,
                "trade_flow": market_state.trade_flow,
                "regime": regime.regime,
                "regime_strength": regime.strength,
            },
        )

    def learn(self, reward: float, new_state: MarketState) -> None:
        """Atualiza Q-learning com recompensa."""
        if self._last_state is None or self._last_action is None:
            return
        features = new_state.to_features()
        next_state = self.qlearning.discretize(features)
        self.qlearning.update(self._last_state, self._last_action, reward, next_state)

    def save(self) -> None:
        """Salva modelo em disco."""
        qt_path = MODEL_DIR / f"qtable_{self.symbol}.pkl"
        self.qlearning.save(qt_path)

    def get_market_state(
        self,
        price: float,
        bid: float = 0,
        ask: float = 0,
        trade_flow: float = 0,
    ) -> MarketState:
        """Constrói MarketState a partir de dados de mercado."""
        spread = ask - bid if (bid and ask) else 0
        mid = (bid + ask) / 2 if (bid and ask) else price
        spread_pct = (spread / mid * 100) if mid > 0 else 0

        return MarketState(
            price=price,
            bid=bid,
            ask=ask,
            spread=spread,
            spread_pct=spread_pct,
            trade_flow=trade_flow,
            volume_ratio=self.indicators.volume_ratio(),
            rsi=self.indicators.rsi(),
            momentum=self.indicators.momentum(),
            volatility=self.indicators.volatility(),
            trend=self.indicators.trend(),
        )
