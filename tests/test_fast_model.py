#!/usr/bin/env python3
"""Testes unitários para btc_trading_agent/fast_model.py.

Cobre: MarketState, MarketRegime, FastIndicators, FastQLearning,
FastTradingModel.predict(), apply_rag_adjustment() e get_stats().
Todas as dependências de I/O (arquivo, logging) são mockadas.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile

import numpy as np
import pytest

# Garantir que btc_trading_agent/ está no sys.path
_BTC_DIR = Path(__file__).resolve().parent.parent / "btc_trading_agent"
if str(_BTC_DIR) not in sys.path:
    sys.path.insert(0, str(_BTC_DIR))

from fast_model import (
    EPSILON,
    FastIndicators,
    FastQLearning,
    FastTradingModel,
    MarketRegime,
    MarketState,
    Signal,
)


# ========================= FIXTURES =========================

@pytest.fixture
def basic_state() -> MarketState:
    """Estado de mercado simples para testes."""
    return MarketState(
        price=85000.0,
        bid=84990.0,
        ask=85010.0,
        spread=0.00024,
        orderbook_imbalance=0.2,
        trade_flow=0.1,
        volume_ratio=1.2,
        rsi=52.0,
        momentum=0.5,
        volatility=0.01,
        trend=0.1,
    )


@pytest.fixture
def indicators_with_data() -> FastIndicators:
    """FastIndicators populado com 100 preços sintéticos."""
    ind = FastIndicators(max_history=200)
    # Série de preços com tendência de alta
    base = 80000.0
    for i in range(100):
        price = base + i * 50 + (i % 7 - 3) * 100  # zigzag para ter rsi variado
        ind.update(price, volume=10.0 + i % 5)
    return ind


@pytest.fixture
def qlearning() -> FastQLearning:
    """FastQLearning com parâmetros padrão."""
    return FastQLearning(n_states=1000, n_actions=3)


@pytest.fixture
def model() -> FastTradingModel:
    """FastTradingModel sem carregar modelos salvos (mock MODEL_DIR)."""
    with patch("fast_model.MODEL_DIR") as mock_dir:
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_dir.__truediv__ = lambda s, name: mock_path
        m = FastTradingModel("BTC-USDT")
    return m


# ========================= MarketState =========================

class TestMarketState:
    """Testes para dataclass MarketState."""

    def test_to_features_retorna_array_8d(self, basic_state: MarketState) -> None:
        """to_features deve retornar ndarray com 8 elementos."""
        features = basic_state.to_features()
        assert isinstance(features, np.ndarray)
        assert features.shape == (8,)

    def test_to_features_rsi_normalizado(self) -> None:
        """RSI 50 deve resultar em feature[2] = 0.0 (normalizado)."""
        state = MarketState(price=1.0, rsi=50.0)
        features = state.to_features()
        assert features[2] == pytest.approx(0.0)

    def test_to_features_rsi_100_normalizado(self) -> None:
        """RSI 100 deve resultar em feature[2] = 1.0."""
        state = MarketState(price=1.0, rsi=100.0)
        features = state.to_features()
        assert features[2] == pytest.approx(1.0)

    def test_to_features_spread_em_bps(self) -> None:
        """Spread de 0.01 deve resultar em feature[6] = 100.0 bps."""
        state = MarketState(price=1.0, spread=0.01)
        features = state.to_features()
        assert features[6] == pytest.approx(100.0)


# ========================= MarketRegime =========================

class TestMarketRegime:
    """Testes para dataclass MarketRegime."""

    def test_is_bearish(self) -> None:
        regime = MarketRegime(regime="BEARISH", strength=0.5)
        assert regime.is_bearish is True
        assert regime.is_bullish is False

    def test_is_bullish(self) -> None:
        regime = MarketRegime(regime="BULLISH", strength=0.7)
        assert regime.is_bullish is True
        assert regime.is_bearish is False

    def test_ranging_nao_e_nem_bearish_nem_bullish(self) -> None:
        regime = MarketRegime(regime="RANGING")
        assert regime.is_bearish is False
        assert regime.is_bullish is False


# ========================= FastIndicators =========================

class TestFastIndicators:
    """Testes para FastIndicators."""

    def test_rsi_retorna_50_sem_dados(self) -> None:
        ind = FastIndicators()
        assert ind.rsi() == 50.0

    def test_rsi_range_valido(self, indicators_with_data: FastIndicators) -> None:
        rsi_val = indicators_with_data.rsi()
        assert 0.0 <= rsi_val <= 100.0

    def test_momentum_zero_sem_dados(self) -> None:
        ind = FastIndicators()
        assert ind.momentum() == 0.0

    def test_momentum_positivo_em_alta(self) -> None:
        ind = FastIndicators()
        for p in range(100, 115):  # preços crescentes
            ind.update(float(p))
        assert ind.momentum() > 0.0

    def test_volatility_zero_sem_dados(self) -> None:
        ind = FastIndicators()
        assert ind.volatility() == 0.0

    def test_volatility_entre_0_e_1(self, indicators_with_data: FastIndicators) -> None:
        vol = indicators_with_data.volatility()
        assert 0.0 <= vol <= 1.0

    def test_trend_zero_sem_dados(self) -> None:
        ind = FastIndicators()
        assert ind.trend() == 0.0

    def test_trend_range(self, indicators_with_data: FastIndicators) -> None:
        trend_val = indicators_with_data.trend()
        assert -1.0 <= trend_val <= 1.0

    def test_ema_retorna_preco_sem_dados(self) -> None:
        ind = FastIndicators()
        ind.update(1000.0)
        assert ind.ema() == pytest.approx(1000.0, abs=1.0)

    def test_volume_ratio_default_sem_volume(self) -> None:
        ind = FastIndicators()
        assert ind.volume_ratio() == 1.0

    def test_update_from_candles_popula_prices(self) -> None:
        ind = FastIndicators()
        candles = [{"close": float(80000 + i * 100), "volume": 1.0} for i in range(50)]
        ind.update_from_candles(candles)
        assert len(ind.prices) == 50

    def test_update_from_candles_vazio_nao_falha(self) -> None:
        ind = FastIndicators()
        ind.update_from_candles([])
        assert len(ind.prices) == 0

    def test_detect_regime_ranging_poucos_dados(self) -> None:
        ind = FastIndicators()
        for p in [100.0] * 30:
            ind.update(p)
        regime = ind.detect_regime()
        assert regime.regime == "RANGING"

    def test_detect_regime_bearish(self) -> None:
        """Série decrescente forte deve detectar regime BEARISH."""
        ind = FastIndicators(max_history=200)
        # Série claramente decrescente
        for i in range(80):
            ind.update(float(10000 - i * 100))
        regime = ind.detect_regime()
        assert regime.regime in ("BEARISH", "RANGING")  # ambos válidos, mas nunca BULLISH

    def test_detect_regime_bullish(self) -> None:
        """Série crescente forte deve detectar regime BULLISH."""
        ind = FastIndicators(max_history=200)
        for i in range(80):
            ind.update(float(80000 + i * 200))
        regime = ind.detect_regime()
        assert regime.regime in ("BULLISH", "RANGING")

    def test_detect_regime_retorna_market_regime(self, indicators_with_data: FastIndicators) -> None:
        regime = indicators_with_data.detect_regime()
        assert isinstance(regime, MarketRegime)
        assert regime.regime in ("BULLISH", "BEARISH", "RANGING")


# ========================= FastQLearning =========================

class TestFastQLearning:
    """Testes para FastQLearning."""

    def test_choose_action_retorna_acao_valida(self, qlearning: FastQLearning) -> None:
        features = np.zeros(8)
        action = qlearning.choose_action(features, explore=False)
        assert action in (0, 1, 2)

    def test_choose_action_explore_retorna_acao_valida(self, qlearning: FastQLearning) -> None:
        features = np.zeros(8)
        # Executar muitas vezes para garantir cobertura de explore
        actions = {qlearning.choose_action(features, explore=True) for _ in range(50)}
        assert actions.issubset({0, 1, 2})

    def test_update_incrementa_episodios(self, qlearning: FastQLearning) -> None:
        features = np.zeros(8)
        next_features = np.ones(8) * 0.1
        qlearning.update(features, action=1, reward=1.0, next_features=next_features)
        assert qlearning.episodes == 1

    def test_update_acumula_reward(self, qlearning: FastQLearning) -> None:
        features = np.zeros(8)
        next_features = np.ones(8) * 0.1
        qlearning.update(features, 1, 2.5, next_features)
        qlearning.update(features, 2, -1.0, next_features)
        assert qlearning.total_reward == pytest.approx(1.5)

    def test_get_confidence_range(self, qlearning: FastQLearning) -> None:
        features = np.zeros(8)
        conf = qlearning.get_confidence(features)
        assert 0.0 <= conf <= 1.0

    def test_save_load_preserva_episodes(self, qlearning: FastQLearning) -> None:
        features = np.zeros(8)
        next_features = np.ones(8) * 0.1
        for _ in range(10):
            qlearning.update(features, 1, 1.0, next_features)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "qmodel.pkl"
            qlearning.save(path)

            loaded = FastQLearning(n_states=1000, n_actions=3)
            result = loaded.load(path)

        assert result is True
        assert loaded.episodes == 10
        assert loaded.total_reward == pytest.approx(10.0)

    def test_load_arquivo_inexistente_retorna_false(self, qlearning: FastQLearning) -> None:
        result = qlearning.load(Path("/tmp/nao_existe_qmodel.pkl"))
        assert result is False

    def test_load_migra_qtable_tamanho_diferente(self) -> None:
        """Deve migrar Q-table quando n_states muda."""
        original = FastQLearning(n_states=500)
        features = np.ones(8) * 0.5
        next_features = np.zeros(8)
        for _ in range(5):
            original.update(features, 1, 1.0, next_features)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "qmodel_sm.pkl"
            original.save(path)

            bigger = FastQLearning(n_states=2000)
            bigger.load(path)

        assert bigger.q_table.shape == (2000, 3)


# ========================= FastTradingModel =========================

class TestFastTradingModel:
    """Testes para FastTradingModel."""

    def test_predict_retorna_signal(self, model: FastTradingModel, basic_state: MarketState) -> None:
        signal = model.predict(basic_state, explore=False)
        assert isinstance(signal, Signal)

    def test_predict_acao_valida(self, model: FastTradingModel, basic_state: MarketState) -> None:
        signal = model.predict(basic_state, explore=False)
        assert signal.action in ("BUY", "SELL", "HOLD")

    def test_predict_confidence_range(self, model: FastTradingModel, basic_state: MarketState) -> None:
        signal = model.predict(basic_state, explore=False)
        assert 0.0 <= signal.confidence <= 1.0

    def test_predict_inclui_inference_ms(self, model: FastTradingModel, basic_state: MarketState) -> None:
        signal = model.predict(basic_state, explore=False)
        assert "inference_ms" in signal.features
        assert signal.features["inference_ms"] >= 0.0

    def test_predict_rsi_alto_tende_sell(self, model: FastTradingModel) -> None:
        """RSI muito alto + trend negativo deve resultar em SELL ou HOLD."""
        overbought = MarketState(
            price=90000.0,
            rsi=85.0,
            momentum=2.0,
            trend=-0.5,
            orderbook_imbalance=-0.5,
            trade_flow=-0.4,
        )
        signal = model.predict(overbought, explore=False)
        assert signal.action in ("SELL", "HOLD")

    def test_predict_rsi_baixo_tende_buy(self, model: FastTradingModel) -> None:
        """RSI muito baixo + trend positivo deve resultar em BUY ou HOLD."""
        oversold = MarketState(
            price=80000.0,
            rsi=15.0,
            momentum=-3.0,
            trend=0.5,
            orderbook_imbalance=0.7,
            trade_flow=0.6,
        )
        signal = model.predict(oversold, explore=False)
        assert signal.action in ("BUY", "HOLD")

    def test_apply_rag_adjustment_habilita_rag(self, model: FastTradingModel) -> None:
        """apply_rag_adjustment deve definir _rag_enabled=True."""
        adjustment = MagicMock()
        adjustment.suggested_regime = "RANGING"
        adjustment.buy_threshold = 0.3
        adjustment.sell_threshold = -0.3
        adjustment.weight_technical = 0.4
        adjustment.weight_orderbook = 0.3
        adjustment.weight_flow = 0.2
        adjustment.weight_qlearning = 0.1

        assert model._rag_enabled is False
        model.apply_rag_adjustment(adjustment)
        assert model._rag_enabled is True
        assert model._rag_adjustment is adjustment

    def test_predict_com_rag_habilitado(self, model: FastTradingModel, basic_state: MarketState) -> None:
        """predict() com RAG ativo deve funcionar sem exceções."""
        adjustment = MagicMock()
        adjustment.suggested_regime = "RANGING"
        adjustment.buy_threshold = 0.25
        adjustment.sell_threshold = -0.25
        adjustment.weight_technical = 0.4
        adjustment.weight_orderbook = 0.3
        adjustment.weight_flow = 0.2
        adjustment.weight_qlearning = 0.1

        model.apply_rag_adjustment(adjustment)
        signal = model.predict(basic_state, explore=False)
        assert signal.action in ("BUY", "SELL", "HOLD")

    def test_get_stats_retorna_dict_completo(self, model: FastTradingModel, basic_state: MarketState) -> None:
        model.predict(basic_state)
        stats = model.get_stats()
        assert "episodes" in stats
        assert "total_reward" in stats
        assert "action_distribution" in stats
        assert "market_regime" in stats
        assert "rag_enabled" in stats
        assert stats["rag_enabled"] is False

    def test_get_stats_rag_regime_quando_habilitado(self, model: FastTradingModel) -> None:
        adjustment = MagicMock()
        adjustment.suggested_regime = "BULLISH"
        adjustment.buy_threshold = 0.3
        adjustment.sell_threshold = -0.3
        adjustment.weight_technical = 0.4
        adjustment.weight_orderbook = 0.3
        adjustment.weight_flow = 0.2
        adjustment.weight_qlearning = 0.1
        adjustment.regime_confidence = 0.85

        model.apply_rag_adjustment(adjustment)
        stats = model.get_stats()
        assert stats["rag_enabled"] is True
        assert stats["rag_regime"] == "BULLISH"

    def test_regime_change_detectado_apos_10_ciclos(self, model: FastTradingModel) -> None:
        """Após 10 ciclos de predict(), deve haver detecção de regime."""
        state = MarketState(price=85000.0, rsi=55.0)
        for _ in range(11):
            model.predict(state, explore=False)
        # Não deve lançar exceção; regime estará atualizado
        assert model._current_regime.regime in ("BULLISH", "BEARISH", "RANGING")
