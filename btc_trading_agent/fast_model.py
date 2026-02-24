#!/usr/bin/env python3
"""
Fast Trading Model - Modelo Ultra-Rápido para Decisões de Trading
Utiliza indicadores técnicos leves + machine learning para decisões em milliseconds
"""

import numpy as np
import time
import json
import pickle
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import deque

logger = logging.getLogger(__name__)

# ====================== CONSTANTES ======================
EPSILON = 1e-10
MODEL_DIR = Path(__file__).parent / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# ====================== DATA CLASSES ======================
@dataclass
class MarketState:
    """Estado atual do mercado"""
    price: float
    bid: float = 0.0
    ask: float = 0.0
    spread: float = 0.0
    orderbook_imbalance: float = 0.0  # -1 a +1
    trade_flow: float = 0.0           # -1 a +1
    volume_ratio: float = 1.0         # volume atual / média
    rsi: float = 50.0                 # 0-100
    momentum: float = 0.0             # % mudança
    volatility: float = 0.0           # desvio padrão normalizado
    trend: float = 0.0                # -1 (down) a +1 (up)
    timestamp: float = field(default_factory=time.time)
    
    def to_features(self) -> np.ndarray:
        """Converte para array de features"""
        return np.array([
            self.orderbook_imbalance,
            self.trade_flow,
            (self.rsi - 50) / 50,  # Normalizado -1 a +1
            self.momentum / 10,     # Normalizado
            self.volatility,
            self.trend,
            self.spread * 10000,    # Em bps
            self.volume_ratio - 1   # Desvio da média
        ])

@dataclass
class Signal:
    """Sinal de trading gerado pelo modelo"""
    action: str        # "BUY", "SELL", "HOLD"
    confidence: float  # 0.0 a 1.0
    price: float
    reason: str
    features: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

# ====================== INDICADORES TÉCNICOS RÁPIDOS ======================
class FastIndicators:
    """Indicadores técnicos otimizados para velocidade"""
    
    def __init__(self, max_history: int = 500):
        self.prices = deque(maxlen=max_history)
        self.volumes = deque(maxlen=max_history)
        self.timestamps = deque(maxlen=max_history)
        self._candles_loaded = False
    
    def update(self, price: float, volume: float = 0):
        """Atualiza histórico com um tick"""
        self.prices.append(price)
        self.volumes.append(volume)
        self.timestamps.append(time.time())
    
    def update_from_candles(self, candles: list):
        """
        Popula o histórico a partir de candles reais (OHLCV).
        Cada candle deve ter: close, volume, timestamp.
        Substitui os ticks de 5s por dados reais de candles de 1min.
        """
        if not candles:
            return
        
        # Só repopular se ainda não carregou ou se recebeu mais candles
        if self._candles_loaded and len(self.prices) >= len(candles):
            # Apenas atualizar o último candle
            last = candles[-1]
            if self.prices and abs(self.prices[-1] - last['close']) > 0.01:
                self.prices[-1] = last['close']
                self.volumes[-1] = last.get('volume', 0)
            return
        
        # Reset e popular com candles reais
        self.prices.clear()
        self.volumes.clear()
        self.timestamps.clear()
        
        for c in candles:
            self.prices.append(c['close'])
            self.volumes.append(c.get('volume', 0))
            self.timestamps.append(c.get('timestamp', time.time()))
        
        self._candles_loaded = True
        logger.debug(f"📊 Indicators loaded from {len(candles)} candles")
    
    def rsi(self, period: int = 14) -> float:
        """RSI otimizado"""
        if len(self.prices) < period + 1:
            return 50.0
        
        prices = list(self.prices)[-period-1:]
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i-1]
            if diff > 0:
                gains.append(diff)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(diff))
        
        avg_gain = np.mean(gains) if gains else EPSILON
        avg_loss = np.mean(losses) if losses else EPSILON
        
        rs = avg_gain / (avg_loss + EPSILON)
        return 100 - (100 / (1 + rs))
    
    def momentum(self, period: int = 10) -> float:
        """Momentum como % de mudança"""
        if len(self.prices) < period:
            return 0.0
        
        current = self.prices[-1]
        past = self.prices[-period]
        return ((current / past) - 1) * 100 if past > 0 else 0.0
    
    def volatility(self, period: int = 20) -> float:
        """Volatilidade normalizada (0-1)"""
        if len(self.prices) < period:
            return 0.0
        
        prices = list(self.prices)[-period:]
        returns = np.diff(prices) / (np.array(prices[:-1]) + EPSILON)
        vol = np.std(returns)
        return min(vol * 100, 1.0)  # Cap em 1.0
    
    def trend(self, short: int = 10, long: int = 30) -> float:
        """Trend como diferença de médias móveis normalizada"""
        if len(self.prices) < long:
            return 0.0
        
        prices = list(self.prices)
        sma_short = np.mean(prices[-short:])
        sma_long = np.mean(prices[-long:])
        
        diff_pct = ((sma_short / sma_long) - 1) * 100
        return np.clip(diff_pct, -1, 1)
    
    def ema(self, period: int = 20) -> float:
        """EMA rápida"""
        if len(self.prices) < 2:
            return self.prices[-1] if self.prices else 0.0
        
        prices = list(self.prices)[-period:]
        alpha = 2 / (period + 1)
        ema_val = prices[0]
        for p in prices[1:]:
            ema_val = alpha * p + (1 - alpha) * ema_val
        return ema_val
    
    def volume_ratio(self, period: int = 20) -> float:
        """Ratio volume atual / média"""
        if len(self.volumes) < period or not self.volumes[-1]:
            return 1.0
        
        avg_vol = np.mean(list(self.volumes)[-period:])
        if avg_vol <= 0:
            return 1.0
        return self.volumes[-1] / avg_vol

# ====================== MODELO Q-LEARNING SIMPLIFICADO ======================
class FastQLearning:
    """Q-Learning ultra-rápido com estados discretizados"""
    
    def __init__(self, n_states: int = 5000, n_actions: int = 3,
                 learning_rate: float = 0.1, discount: float = 0.95,
                 epsilon: float = 0.15):
        self.n_states = n_states
        self.n_actions = n_actions  # 0=HOLD, 1=BUY, 2=SELL
        self.lr = learning_rate
        self.gamma = discount
        self.epsilon = epsilon
        
        # Q-table inicializada com zeros
        self.q_table = np.zeros((n_states, n_actions))
        
        # Contadores para estatísticas
        self.action_counts = np.zeros(n_actions)
        self.total_reward = 0.0
        self.episodes = 0
    
    def _discretize(self, features: np.ndarray) -> int:
        """Converte features contínuas em estado discreto"""
        # Hash simples para discretização
        # Features esperados: [-1, 1] range
        normalized = np.clip(features, -1, 1)
        
        # Quantizar cada feature em bins
        bins = np.linspace(-1, 1, 10)
        indices = np.digitize(normalized, bins)
        
        # Combinar em único índice
        state = 0
        for i, idx in enumerate(indices):
            state += idx * (10 ** i)
        
        return state % self.n_states
    
    def choose_action(self, features: np.ndarray, explore: bool = True) -> int:
        """Escolhe ação com epsilon-greedy"""
        state = self._discretize(features)
        
        if explore and np.random.random() < self.epsilon:
            return np.random.randint(self.n_actions)
        
        return int(np.argmax(self.q_table[state]))
    
    def update(self, features: np.ndarray, action: int, 
               reward: float, next_features: np.ndarray):
        """Atualiza Q-table"""
        state = self._discretize(features)
        next_state = self._discretize(next_features)
        
        # Q-learning update
        best_next = np.max(self.q_table[next_state])
        td_target = reward + self.gamma * best_next
        td_error = td_target - self.q_table[state, action]
        
        self.q_table[state, action] += self.lr * td_error
        
        # Estatísticas
        self.action_counts[action] += 1
        self.total_reward += reward
        self.episodes += 1
    
    def get_confidence(self, features: np.ndarray) -> float:
        """Calcula confiança da decisão (0-1)"""
        state = self._discretize(features)
        q_values = self.q_table[state]
        
        # Softmax para probabilidades
        exp_q = np.exp(q_values - np.max(q_values))
        probs = exp_q / (np.sum(exp_q) + EPSILON)
        
        return float(np.max(probs))
    
    def save(self, path: Path):
        """Salva modelo"""
        data = {
            "q_table": self.q_table,
            "action_counts": self.action_counts,
            "total_reward": self.total_reward,
            "episodes": self.episodes,
            "params": {
                "n_states": self.n_states,
                "n_actions": self.n_actions,
                "lr": self.lr,
                "gamma": self.gamma,
                "epsilon": self.epsilon
            }
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)
        logger.info(f"💾 Model saved to {path}")
    
    def load(self, path: Path) -> bool:
        """Carrega modelo"""
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            
            loaded_q = data["q_table"]
            loaded_n_states = loaded_q.shape[0]
            
            # Se n_states mudou, migrar: copiar estados existentes para nova tabela
            if loaded_n_states != self.n_states:
                logger.info(f"🔄 Migrating Q-table: {loaded_n_states} → {self.n_states} states")
                new_q = np.zeros((self.n_states, self.n_actions))
                copy_size = min(loaded_n_states, self.n_states)
                new_q[:copy_size] = loaded_q[:copy_size]
                self.q_table = new_q
            else:
                self.q_table = loaded_q
            
            self.action_counts = data["action_counts"]
            self.total_reward = data["total_reward"]
            self.episodes = data["episodes"]
            
            logger.info(f"📂 Model loaded: {self.episodes} episodes, "
                       f"reward={self.total_reward:.2f}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Failed to load model: {e}")
            return False

# ====================== MODELO DE DECISÃO ENSEMBLE ======================
class FastTradingModel:
    """Modelo ensemble combinando múltiplas estratégias"""
    
    ACTIONS = {0: "HOLD", 1: "BUY", 2: "SELL"}
    
    def __init__(self, symbol: str = "BTC-USDT"):
        self.symbol = symbol
        self.indicators = FastIndicators()
        self.q_model = FastQLearning()
        
        # Pesos do ensemble - ajustados para melhor performance
        self.weights = {
            "technical": 0.35,
            "orderbook": 0.30,
            "flow": 0.25,
            "qlearning": 0.10
        }
        
        # Thresholds - mais conservadores para maior precisão
        self.buy_threshold = 0.30   # subido de 0.20 para 0.30
        self.sell_threshold = -0.30  # subido de -0.20 para -0.30
        self.min_confidence = 0.45  # subido de 0.30 para 0.45
        
        # Filtros adicionais
        self.use_volatility_filter = True
        self.min_volatility = 0.001
        self.max_volatility = 0.05
        
        # Estado anterior para rewards
        self._last_state: Optional[MarketState] = None
        self._last_action: Optional[int] = None
        self._last_price: Optional[float] = None
        
        # Histórico de sinais para evitar flip-flopping
        self._signal_history = deque(maxlen=10)
        
        # Carregar modelo se existir
        model_path = MODEL_DIR / f"qmodel_{symbol.replace('-', '_')}.pkl"
        if model_path.exists():
            self.q_model.load(model_path)
    
    def _technical_signal(self, state: MarketState) -> Tuple[float, str]:
        """Sinal baseado em indicadores técnicos - OTIMIZADO"""
        score = 0.0
        reasons = []
        
        # RSI - zonas mais amplas para scalping
        if state.rsi < 35:
            score += 0.5
            reasons.append("RSI oversold")
        elif state.rsi < 45:
            score += 0.2
            reasons.append("RSI low")
        elif state.rsi > 65:
            score -= 0.5
            reasons.append("RSI overbought")
        elif state.rsi > 55:
            score -= 0.2
            reasons.append("RSI high")
        
        # Momentum - mais sensível
        if state.momentum > 0.2:
            score += 0.4
            reasons.append("positive momentum")
        elif state.momentum < -0.2:
            score -= 0.4
            reasons.append("negative momentum")
        
        # Trend - peso maior
        score += state.trend * 0.4
        if abs(state.trend) > 0.2:
            reasons.append(f"{'up' if state.trend > 0 else 'down'}trend")
        
        # Volatilidade - fator multiplicador
        vol_factor = 1.0
        if state.volatility > 0.03:
            vol_factor = 1.3  # Mais agressivo em alta volatilidade
        elif state.volatility < 0.01:
            vol_factor = 0.7  # Mais conservador em baixa vol
        
        score *= vol_factor
        
        return np.clip(score, -1, 1), ", ".join(reasons) if reasons else "neutral"
    
    def _orderbook_signal(self, state: MarketState) -> Tuple[float, str]:
        """Sinal baseado no order book - OTIMIZADO"""
        imb = state.orderbook_imbalance
        
        # Thresholds mais sensíveis
        if imb > 0.2:
            return imb * 1.2, "bid pressure"
        elif imb < -0.2:
            return imb * 1.2, "ask pressure"
        return imb, "balanced book"
    
    def _flow_signal(self, state: MarketState) -> Tuple[float, str]:
        """Sinal baseado no fluxo de trades - OTIMIZADO"""
        flow = state.trade_flow
        
        if flow > 0.2:
            return flow * 1.2, "buying pressure"
        elif flow < -0.2:
            return flow * 1.2, "selling pressure"
        return flow, "neutral flow"
    
    def _check_flip_flop(self, action: str) -> bool:
        """Verifica se está fazendo flip-flopping (trocas frequentes)"""
        if len(self._signal_history) < 3:
            return False
        
        recent = list(self._signal_history)[-3:]
        changes = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i-1])
        return changes >= 2 and action != "HOLD"
    
    def predict(self, state: MarketState, explore: bool = False) -> Signal:
        """Gera sinal de trading - VERSÃO OTIMIZADA"""
        start = time.time()
        
        # Atualizar indicadores
        self.indicators.update(state.price)
        
        # Calcular features
        features = state.to_features()
        
        # Componentes do ensemble
        tech_score, tech_reason = self._technical_signal(state)
        ob_score, ob_reason = self._orderbook_signal(state)
        flow_score, flow_reason = self._flow_signal(state)
        
        # Q-Learning decision
        q_action = self.q_model.choose_action(features, explore=explore)
        q_confidence = self.q_model.get_confidence(features)
        q_score = (q_action - 1)  # -1 (SELL), 0 (HOLD), 1 (BUY)
        
        # Ensemble com pesos dinâmicos baseados em volatilidade
        vol = state.volatility
        weights = self.weights.copy()
        
        # Em alta volatilidade, dar mais peso ao orderbook
        if vol > 0.03:
            weights["orderbook"] += 0.1
            weights["technical"] -= 0.05
            weights["qlearning"] -= 0.05
        
        final_score = (
            tech_score * weights["technical"] +
            ob_score * weights["orderbook"] +
            flow_score * weights["flow"] +
            q_score * weights["qlearning"]
        )
        
        # Filtro de volatilidade
        if self.use_volatility_filter:
            if vol < self.min_volatility:
                final_score *= 0.5  # Reduzir confiança em mercado parado
            elif vol > self.max_volatility:
                final_score *= 0.7  # Reduzir em volatilidade extrema
        
        # Decidir ação
        if final_score > self.buy_threshold:
            action = "BUY"
        elif final_score < self.sell_threshold:
            action = "SELL"
        else:
            action = "HOLD"
        
        # Anti flip-flopping
        if self._check_flip_flop(action):
            action = "HOLD"
            final_score *= 0.5
        
        # Adicionar ao histórico
        self._signal_history.append(action)
        
        # Calcular confiança - fórmula melhorada
        base_confidence = min(abs(final_score) * 1.5, 1.0)
        confidence = base_confidence * 0.6 + q_confidence * 0.2 + (1 - vol) * 0.2
        confidence = min(max(confidence, 0), 1.0)
        
        # Montar razão
        reasons = []
        if tech_reason != "neutral":
            reasons.append(tech_reason)
        if "pressure" in ob_reason:
            reasons.append(ob_reason)
        if "pressure" in flow_reason:
            reasons.append(flow_reason)
        
        signal = Signal(
            action=action,
            confidence=confidence,
            price=state.price,
            reason=", ".join(reasons) if reasons else "low conviction",
            features={
                "technical_score": tech_score,
                "orderbook_score": ob_score,
                "flow_score": flow_score,
                "q_score": q_score,
                "final_score": final_score,
                "volatility": vol,
                "inference_ms": (time.time() - start) * 1000
            }
        )
        
        # Guardar para aprendizado
        action_idx = {"HOLD": 0, "BUY": 1, "SELL": 2}[action]
        if self._last_state is not None and self._last_action is not None:
            # Reward melhorado: baseado em variação de preço acumulada,
            # não em ticks de 5s (que são ruído)
            price_change = (state.price - self._last_price) / self._last_price
            
            # Só recompensar se variação significativa (> 0.01%)
            if abs(price_change) < 0.0001:
                reward = 0.0  # Ignora ruído
            elif self._last_action == 1:  # BUY
                reward = price_change * 50  # Recompensa moderada (era 100)
            elif self._last_action == 2:  # SELL
                reward = -price_change * 50
            else:  # HOLD
                reward = -0.01  # Penalidade fixa pequena (era -abs*10 que incentivava over-trading)
            
            # Update Q-learning
            self.q_model.update(
                self._last_state.to_features(),
                self._last_action,
                reward,
                features
            )
        
        self._last_state = state
        self._last_action = action_idx
        self._last_price = state.price
        
        return signal
    
    def save(self):
        """Salva modelo"""
        model_path = MODEL_DIR / f"qmodel_{self.symbol.replace('-', '_')}.pkl"
        self.q_model.save(model_path)
    
    def get_stats(self) -> Dict:
        """Estatísticas do modelo"""
        total = np.sum(self.q_model.action_counts)
        return {
            "episodes": self.q_model.episodes,
            "total_reward": self.q_model.total_reward,
            "avg_reward": self.q_model.total_reward / max(self.q_model.episodes, 1),
            "action_distribution": {
                "HOLD": self.q_model.action_counts[0] / max(total, 1),
                "BUY": self.q_model.action_counts[1] / max(total, 1),
                "SELL": self.q_model.action_counts[2] / max(total, 1)
            }
        }

# ====================== TEST ======================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 50)
    print("🧠 Fast Trading Model Test")
    print("=" * 50)
    
    model = FastTradingModel("BTC-USDT")
    
    # Simular estados de mercado
    test_states = [
        MarketState(price=95000, rsi=25, momentum=-2.0, orderbook_imbalance=0.5, 
                   trade_flow=0.4, trend=-0.3),
        MarketState(price=95500, rsi=35, momentum=0.5, orderbook_imbalance=0.3, 
                   trade_flow=0.3, trend=0.1),
        MarketState(price=96000, rsi=55, momentum=1.5, orderbook_imbalance=0.1, 
                   trade_flow=0.1, trend=0.3),
        MarketState(price=97000, rsi=75, momentum=2.5, orderbook_imbalance=-0.3, 
                   trade_flow=-0.2, trend=0.5),
        MarketState(price=96500, rsi=65, momentum=-0.5, orderbook_imbalance=-0.4, 
                   trade_flow=-0.4, trend=0.2),
    ]
    
    print("\n📊 Test Predictions:")
    print("-" * 70)
    
    for i, state in enumerate(test_states):
        signal = model.predict(state, explore=False)
        print(f"State {i+1}: ${state.price:,.0f} | RSI={state.rsi:.0f}")
        print(f"  → {signal.action} ({signal.confidence:.1%}) - {signal.reason}")
        print(f"    Inference: {signal.features['inference_ms']:.2f}ms")
        print()
    
    # Stats
    stats = model.get_stats()
    print(f"📈 Model Stats:")
    print(f"  Episodes: {stats['episodes']}")
    print(f"  Total Reward: {stats['total_reward']:.2f}")
    
    # Salvar
    model.save()
    print("\n✅ Model saved!")
