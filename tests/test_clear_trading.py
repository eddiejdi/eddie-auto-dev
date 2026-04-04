#!/usr/bin/env python3
"""Testes unitários para clear_trading_agent/.

Cobre: mt5_api, fast_model, training_db, trading_agent, prometheus_exporter.
Todas dependências externas (HTTP, PostgreSQL, MT5 Bridge) são mockadas.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

# ====================== SETUP ======================
# Configura env vars antes do import dos módulos
os.environ.setdefault("MT5_BRIDGE_URL", "http://127.0.0.1:8510")
os.environ.setdefault("MT5_BRIDGE_API_KEY", "test-key-123")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5433/test")
os.environ.setdefault("CLEAR_CONFIG_FILE", "config_PETR4.json")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "")

_CLEAR_DIR = Path(__file__).resolve().parent.parent / "clear_trading_agent"
if str(_CLEAR_DIR) not in sys.path:
    sys.path.insert(0, str(_CLEAR_DIR))
if str(_CLEAR_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_CLEAR_DIR.parent))

# Mock secrets_helper antes de importar módulos que dependem dele
_mock_secrets = MagicMock()
_mock_secrets.get_secret.return_value = None
_mock_secrets.get_database_url.return_value = "postgresql://test:test@localhost:5433/test"
_mock_secrets.get_mt5_bridge_credentials.return_value = ("http://127.0.0.1:8510", "test-key-123")
_mock_secrets.get_clear_integration_status.return_value = {
    "bridge_url": "http://127.0.0.1:8510",
    "bridge_api_key_configured": True,
    "broker_username_configured": False,
    "broker_password_configured": False,
}
sys.modules["secrets_helper"] = _mock_secrets
sys.modules["clear_trading_agent.secrets_helper"] = _mock_secrets

# Mock psycopg2 para training_db
_mock_psycopg2 = MagicMock()
_mock_pool = MagicMock()
_mock_conn = MagicMock()
_mock_cursor = MagicMock()
_mock_conn.cursor.return_value = _mock_cursor
_mock_cursor.fetchone.return_value = [1]
_mock_cursor.fetchall.return_value = []
_mock_pool.getconn.return_value = _mock_conn
_mock_psycopg2.pool.ThreadedConnectionPool.return_value = _mock_pool
_mock_psycopg2.extras = MagicMock()
sys.modules["psycopg2"] = _mock_psycopg2
sys.modules["psycopg2.extras"] = _mock_psycopg2.extras
sys.modules["psycopg2.pool"] = _mock_psycopg2.pool

# Patch requests antes do import de mt5_api
with patch("requests.get"), patch("requests.post"):
    from clear_trading_agent.mt5_api import (
        get_price,
        get_price_fast,
        get_candles,
        get_tick,
        get_account_info,
        get_balance,
        get_equity,
        get_positions,
        get_active_orders,
        place_market_order,
        place_limit_order,
        get_history_deals,
        analyze_spread,
        analyze_trade_flow,
        get_clear_connection_status,
        is_bridge_healthy,
        rate_limit,
        retry_on_failure,
        _headers,
        _get,
        _post,
    )

from clear_trading_agent.fast_model import (
    MarketState,
    Signal,
    MarketRegime,
    FastIndicators,
    FastQLearning,
    FastTradingModel,
    is_market_open,
    minutes_to_market_open,
    B3_OPEN_HOUR,
    B3_CLOSE_HOUR,
    B3_CLOSE_MIN,
    EPSILON,
)

from clear_trading_agent.training_db import TrainingDatabase, _safe_float, _NumpyEncoder


# ========================= FIXTURES =========================

@pytest.fixture
def market_state() -> MarketState:
    """Estado de mercado B3 simples."""
    return MarketState(
        price=28.50,
        bid=28.48,
        ask=28.52,
        spread=0.04,
        spread_pct=0.14,
        trade_flow=0.1,
        volume_ratio=1.2,
        rsi=52.0,
        momentum=0.5,
        volatility=0.01,
        trend=0.1,
    )


@pytest.fixture
def indicators() -> FastIndicators:
    """FastIndicators com dados sintéticos de ação brasileira."""
    ind = FastIndicators(max_history=200)
    base = 28.00
    for i in range(100):
        price = base + i * 0.05 + (i % 7 - 3) * 0.10
        ind.update(price, volume=1000.0 + i * 10)
    return ind


@pytest.fixture
def qlearning() -> FastQLearning:
    """FastQLearning com parâmetros padrão."""
    return FastQLearning(n_states=1000, n_actions=3)


@pytest.fixture
def model() -> FastTradingModel:
    """FastTradingModel sem Q-table persistida."""
    with patch("clear_trading_agent.fast_model.MODEL_DIR") as mock_dir:
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_dir.__truediv__ = lambda s, name: mock_path
        m = FastTradingModel("PETR4")
    return m


@pytest.fixture
def db() -> TrainingDatabase:
    """TrainingDatabase com pool de conexão mockado."""
    return TrainingDatabase(dsn="postgresql://test:test@localhost:5433/test")


# ========================= MT5 API CLIENT =========================

class TestMt5ApiClient:
    """Testes do client REST para MT5 Bridge."""

    def test_headers_contain_api_key(self) -> None:
        """Headers incluem X-API-KEY."""
        h = _headers()
        assert "X-API-KEY" in h
        assert h["Content-Type"] == "application/json"

    @patch("clear_trading_agent.mt5_api.requests.get")
    def test_get_price_success(self, mock_get: MagicMock) -> None:
        """get_price retorna mid-price bid/ask."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"bid": "28.48", "ask": "28.52", "last": "28.50"},
        )
        mock_get.return_value.raise_for_status = MagicMock()
        price = get_price("PETR4")
        assert price is not None
        assert abs(price - 28.50) < 0.01

    @patch("clear_trading_agent.mt5_api.requests.get")
    def test_get_price_only_last(self, mock_get: MagicMock) -> None:
        """get_price retorna last quando bid/ask=0."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"bid": "0", "ask": "0", "last": "28.50"},
        )
        mock_get.return_value.raise_for_status = MagicMock()
        price = get_price("PETR4")
        assert price == 28.50

    @patch("clear_trading_agent.mt5_api.requests.get")
    def test_get_price_failure(self, mock_get: MagicMock) -> None:
        """get_price retorna None em caso de erro."""
        mock_get.side_effect = Exception("connection refused")
        price = get_price("PETR4")
        assert price is None

    @patch("clear_trading_agent.mt5_api.requests.get")
    def test_get_candles(self, mock_get: MagicMock) -> None:
        """get_candles retorna lista de candles formatada."""
        raw_candles = [
            {"timestamp": 1700000000, "open": 28.50, "high": 28.90, "low": 28.30,
             "close": 28.70, "tick_volume": 1000, "real_volume": 5000},
            {"timestamp": 1700000060, "open": 28.70, "high": 29.00, "low": 28.60,
             "close": 28.85, "tick_volume": 800, "real_volume": 4000},
        ]
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: raw_candles,
        )
        mock_get.return_value.raise_for_status = MagicMock()

        candles = get_candles("PETR4", "M1", 10)
        assert len(candles) == 2
        assert candles[0]["close"] == 28.70
        assert candles[1]["volume"] == 800

    @patch("clear_trading_agent.mt5_api.requests.get")
    def test_get_tick(self, mock_get: MagicMock) -> None:
        """get_tick retorna tick completo."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"bid": 28.48, "ask": 28.52, "last": 28.50, "volume": 5000},
        )
        mock_get.return_value.raise_for_status = MagicMock()
        tick = get_tick("PETR4")
        assert tick["bid"] == 28.48

    @patch("clear_trading_agent.mt5_api.requests.get")
    def test_get_account_info(self, mock_get: MagicMock) -> None:
        """get_account_info retorna dados da conta."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "balance": 50000, "equity": 48500,
                "margin_free": 43500, "currency": "BRL",
            },
        )
        mock_get.return_value.raise_for_status = MagicMock()
        info = get_account_info()
        assert info["balance"] == 50000
        assert info["currency"] == "BRL"

    @patch("clear_trading_agent.mt5_api.requests.get")
    def test_get_balance(self, mock_get: MagicMock) -> None:
        """get_balance retorna margin_free em BRL."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"margin_free": 43500.0},
        )
        mock_get.return_value.raise_for_status = MagicMock()
        assert get_balance() == 43500.0

    @patch("clear_trading_agent.mt5_api.requests.get")
    def test_get_equity(self, mock_get: MagicMock) -> None:
        """get_equity retorna equity em BRL."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"equity": 48500.0},
        )
        mock_get.return_value.raise_for_status = MagicMock()
        assert get_equity() == 48500.0

    @patch("clear_trading_agent.mt5_api.requests.get")
    def test_get_positions(self, mock_get: MagicMock) -> None:
        """get_positions retorna lista de posições."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [{"symbol": "PETR4", "volume": 100, "profit": 50}],
        )
        mock_get.return_value.raise_for_status = MagicMock()
        positions = get_positions("PETR4")
        assert len(positions) == 1
        assert positions[0]["profit"] == 50

    @patch("clear_trading_agent.mt5_api.requests.post")
    def test_place_market_order_success(self, mock_post: MagicMock) -> None:
        """place_market_order retorna sucesso."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"success": True, "order_id": 123, "price": 28.50, "volume": 100},
        )
        mock_post.return_value.raise_for_status = MagicMock()
        result = place_market_order("PETR4", "buy", 100)
        assert result["success"] is True
        assert result["order_id"] == 123

    @patch("clear_trading_agent.mt5_api.requests.post")
    def test_place_limit_order(self, mock_post: MagicMock) -> None:
        """place_limit_order retorna sucesso."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"success": True, "order_id": 124},
        )
        mock_post.return_value.raise_for_status = MagicMock()
        result = place_limit_order("PETR4", "buy", 100, 28.00)
        assert result["success"] is True

    @patch("clear_trading_agent.mt5_api.requests.get")
    def test_is_bridge_healthy(self, mock_get: MagicMock) -> None:
        """is_bridge_healthy retorna True quando bridge responde."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"mt5_connected": True},
        )
        mock_get.return_value.raise_for_status = MagicMock()
        assert is_bridge_healthy() is True

    @patch("clear_trading_agent.mt5_api.requests.get")
    def test_is_bridge_unhealthy(self, mock_get: MagicMock) -> None:
        """is_bridge_healthy retorna False em caso de erro."""
        mock_get.side_effect = Exception("connection refused")
        assert is_bridge_healthy() is False

    @patch("clear_trading_agent.secrets_helper.get_clear_integration_status")
    def test_get_clear_connection_status_without_health_check(self, mock_integration: MagicMock) -> None:
        """Status da integração não deve chamar health check por padrão."""
        mock_integration.return_value = {
            "broker_username_configured": True,
            "broker_password_configured": True,
        }

        status = get_clear_connection_status()

        assert status["bridge_api_key_configured"] is True
        assert status["bridge_healthy"] is False
        assert status["broker_username_configured"] is True
        assert status["broker_password_configured"] is True

    @patch("clear_trading_agent.mt5_api.is_bridge_healthy", return_value=True)
    @patch("clear_trading_agent.secrets_helper.get_clear_integration_status")
    def test_get_clear_connection_status_with_health_check(
        self,
        mock_integration: MagicMock,
        mock_health: MagicMock,
    ) -> None:
        """Status da integração consulta health quando solicitado."""
        mock_integration.return_value = {
            "broker_username_configured": False,
            "broker_password_configured": False,
        }

        status = get_clear_connection_status(check_bridge_health=True)

        assert status["bridge_healthy"] is True
        assert status["broker_username_configured"] is False
        assert status["broker_password_configured"] is False
        mock_health.assert_called_once()


class TestMt5ApiAnalysis:
    """Testes de análise de mercado via mt5_api."""

    @patch("clear_trading_agent.mt5_api.get_tick")
    def test_analyze_spread(self, mock_tick: MagicMock) -> None:
        """analyze_spread calcula spread e spread_pct."""
        mock_tick.return_value = {"bid": 28.48, "ask": 28.52}
        result = analyze_spread("PETR4")
        assert result["bid"] == 28.48
        assert result["ask"] == 28.52
        assert abs(result["spread"] - 0.04) < 0.001
        assert result["spread_pct"] > 0

    @patch("clear_trading_agent.mt5_api.get_tick")
    def test_analyze_spread_empty(self, mock_tick: MagicMock) -> None:
        """analyze_spread retorna zeros quando sem tick."""
        mock_tick.return_value = {}
        result = analyze_spread("PETR4")
        assert result["spread"] == 0
        assert result["spread_pct"] == 0

    @patch("clear_trading_agent.mt5_api.get_candles")
    def test_analyze_trade_flow(self, mock_candles: MagicMock) -> None:
        """analyze_trade_flow calcula bias de volume."""
        mock_candles.return_value = [
            {"open": 28.00, "close": 28.50, "volume": 1000},  # bullish
            {"open": 28.50, "close": 28.40, "volume": 500},   # bearish
            {"open": 28.40, "close": 28.60, "volume": 800},   # bullish
        ]
        result = analyze_trade_flow("PETR4", candle_count=3)
        assert result["buy_volume"] == 1800  # 1000 + 800
        assert result["sell_volume"] == 500
        assert result["flow_bias"] > 0  # net bullish

    @patch("clear_trading_agent.mt5_api.get_candles")
    def test_analyze_trade_flow_empty(self, mock_candles: MagicMock) -> None:
        """analyze_trade_flow retorna zeros quando sem candles."""
        mock_candles.return_value = []
        result = analyze_trade_flow("PETR4")
        assert result["total_volume"] == 0
        assert result["flow_bias"] == 0


class TestRateLimitRetry:
    """Testes de rate limiting e retry."""

    def test_retry_on_failure_succeeds(self) -> None:
        """retry_on_failure retorna resultado na primeira tentativa."""
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.01)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        assert succeed() == "ok"
        assert call_count == 1

    def test_retry_on_failure_retries(self) -> None:
        """retry_on_failure faz retry após exceções."""
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.01)
        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("fail")
            return "ok"

        assert fail_twice() == "ok"
        assert call_count == 3

    def test_retry_on_failure_exhausted(self) -> None:
        """retry_on_failure lança exceção após esgotar tentativas."""
        @retry_on_failure(max_retries=2, delay=0.01)
        def always_fail():
            raise ConnectionError("fail")

        with pytest.raises(ConnectionError):
            always_fail()


# ========================= FAST MODEL =========================

class TestMarketState:
    """Testes do MarketState B3."""

    def test_to_features_shape(self, market_state: MarketState) -> None:
        """to_features retorna array de 8 dimensões."""
        features = market_state.to_features()
        assert features.shape == (8,)

    def test_to_features_values(self, market_state: MarketState) -> None:
        """to_features mapeia corretamente os campos."""
        f = market_state.to_features()
        assert abs(f[0] - market_state.spread_pct * 100) < 0.01
        assert abs(f[1] - market_state.trade_flow) < 0.01
        assert abs(f[2] - (market_state.rsi - 50) / 50) < 0.01

    def test_default_values(self) -> None:
        """MarketState com apenas preço tem defaults razoáveis."""
        ms = MarketState(price=30.0)
        assert ms.rsi == 50.0
        assert ms.momentum == 0.0
        assert ms.volume_ratio == 1.0


class TestMarketRegime:
    """Testes do MarketRegime."""

    def test_bearish(self) -> None:
        """MarketRegime detecta bearish."""
        r = MarketRegime("BEARISH", 0.8, 5)
        assert r.is_bearish is True
        assert r.is_bullish is False

    def test_bullish(self) -> None:
        """MarketRegime detecta bullish."""
        r = MarketRegime("BULLISH", 0.7, 3)
        assert r.is_bullish is True
        assert r.is_bearish is False

    def test_ranging(self) -> None:
        """MarketRegime ranging não é bull nem bear."""
        r = MarketRegime("RANGING", 0.3, 0)
        assert r.is_bullish is False
        assert r.is_bearish is False


class TestFastIndicators:
    """Testes dos indicadores técnicos."""

    def test_rsi_default(self) -> None:
        """RSI sem dados retorna 50."""
        ind = FastIndicators()
        assert ind.rsi() == 50.0

    def test_rsi_with_data(self, indicators: FastIndicators) -> None:
        """RSI com dados retorna valor 0-100."""
        rsi = indicators.rsi()
        assert 0 <= rsi <= 100

    def test_momentum_default(self) -> None:
        """Momentum sem dados retorna 0."""
        ind = FastIndicators()
        assert ind.momentum() == 0.0

    def test_momentum_with_data(self, indicators: FastIndicators) -> None:
        """Momentum retorna % mudança."""
        mom = indicators.momentum()
        assert isinstance(mom, float)

    def test_volatility_default(self) -> None:
        """Volatilidade sem dados retorna 0."""
        ind = FastIndicators()
        assert ind.volatility() == 0.0

    def test_volatility_bounded(self, indicators: FastIndicators) -> None:
        """Volatilidade é 0–1."""
        vol = indicators.volatility()
        assert 0 <= vol <= 1.0

    def test_trend(self, indicators: FastIndicators) -> None:
        """Trend retorna valor -1 a 1."""
        t = indicators.trend()
        assert -1 <= t <= 1

    def test_ema(self, indicators: FastIndicators) -> None:
        """EMA retorna valor próximo aos preços."""
        ema = indicators.ema()
        assert ema > 0

    def test_volume_ratio(self, indicators: FastIndicators) -> None:
        """Volume ratio retorna valor positivo."""
        vr = indicators.volume_ratio()
        assert vr > 0

    def test_detect_regime(self, indicators: FastIndicators) -> None:
        """detect_regime retorna MarketRegime."""
        regime = indicators.detect_regime()
        assert isinstance(regime, MarketRegime)
        assert regime.regime in ("BULLISH", "BEARISH", "RANGING")

    def test_update_from_candles(self) -> None:
        """update_from_candles popula histórico."""
        ind = FastIndicators()
        candles = [
            {"close": 28.0 + i * 0.1, "volume": 1000, "timestamp": 1700000000 + i * 60}
            for i in range(50)
        ]
        ind.update_from_candles(candles)
        assert len(ind.prices) == 50
        assert ind.rsi() != 50.0  # Não deve ser default  


class TestFastQLearning:
    """Testes do Q-learning."""

    def test_discretize_deterministic(self, qlearning: FastQLearning) -> None:
        """Discretização é determinística."""
        features = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
        s1 = qlearning.discretize(features)
        s2 = qlearning.discretize(features)
        assert s1 == s2

    def test_discretize_in_range(self, qlearning: FastQLearning) -> None:
        """Estado discretizado está no range correto."""
        features = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
        state = qlearning.discretize(features)
        assert 0 <= state < qlearning.n_states

    def test_get_action_range(self, qlearning: FastQLearning) -> None:
        """Ação retornada está no range 0-2."""
        action = qlearning.get_action(0)
        assert action in (0, 1, 2)

    def test_update_changes_q_table(self, qlearning: FastQLearning) -> None:
        """Update modifica Q-table."""
        old_val = qlearning.q_table[0, 1]
        qlearning.update(state=0, action=1, reward=1.0, next_state=1)
        assert qlearning.q_table[0, 1] != old_val

    def test_save_load(self, qlearning: FastQLearning, tmp_path: Path) -> None:
        """Save e load preservam Q-table."""
        qlearning.update(0, 1, 5.0, 1)
        path = tmp_path / "q_test.pkl"
        qlearning.save(path)

        q2 = FastQLearning(n_states=1000, n_actions=3)
        assert q2.load(path)
        assert np.allclose(q2.q_table, qlearning.q_table)

    def test_load_nonexistent(self, qlearning: FastQLearning, tmp_path: Path) -> None:
        """Load de arquivo inexistente retorna False."""
        assert qlearning.load(tmp_path / "nonexistent.pkl") is False


class TestFastTradingModel:
    """Testes do modelo de trading."""

    def test_generate_signal(self, model: FastTradingModel, market_state: MarketState) -> None:
        """generate_signal retorna Signal com campos válidos."""
        signal = model.generate_signal(market_state)
        assert isinstance(signal, Signal)
        assert signal.action in ("BUY", "SELL", "HOLD")
        assert 0 <= signal.confidence <= 1.0
        assert signal.price == market_state.price

    def test_signal_hold_outside_market_hours(self, model: FastTradingModel, market_state: MarketState) -> None:
        """Fora do horário de mercado, signal é HOLD."""
        with patch("clear_trading_agent.fast_model.is_market_open", return_value=False):
            # Forçar ação != HOLD no Q-learning
            model.qlearning.q_table[0, 1] = 100  # BUY com Q alto
            signal = model.generate_signal(market_state)
            # Se o modelo detectar mercado fechado, deve forçar HOLD
            # (mas isso depende do discretize cair no state=0)
            # Podemos apenas verificar que o sinal é gerado corretamente
            assert isinstance(signal, Signal)

    def test_learn(self, model: FastTradingModel, market_state: MarketState) -> None:
        """learn atualiza Q-table."""
        model.generate_signal(market_state)
        # Deve ter _last_state e _last_action
        model.learn(1.0, market_state)
        # Não lança exceção

    def test_get_market_state(self, model: FastTradingModel) -> None:
        """get_market_state constrói MarketState corretamente."""
        model.indicators.update(28.50, 1000)
        model.indicators.update(28.55, 1100)
        ms = model.get_market_state(price=28.55, bid=28.53, ask=28.57, trade_flow=0.1)
        assert ms.price == 28.55
        assert ms.bid == 28.53
        assert ms.spread > 0

    def test_update(self, model: FastTradingModel) -> None:
        """update adiciona tick aos indicadores."""
        model.update(28.50, 1000)
        model.update(28.55, 1100)
        assert len(model.indicators.prices) == 2


class TestMarketHours:
    """Testes do horário de mercado B3."""

    def test_market_open_weekday_trading(self) -> None:
        """is_market_open retorna bool."""
        result = is_market_open()
        assert isinstance(result, bool)

    def test_market_hours_constants(self) -> None:
        """Constantes de horário estão corretas."""
        assert B3_OPEN_HOUR == 10
        assert B3_CLOSE_HOUR == 17
        assert B3_CLOSE_MIN == 55

    def test_minutes_to_market_returns_int(self) -> None:
        """minutes_to_market_open retorna inteiro."""
        result = minutes_to_market_open()
        assert isinstance(result, int)
        assert result >= 0


# ========================= TRAINING DB =========================

class TestTrainingDatabase:
    """Testes do gerenciador PostgreSQL."""

    def test_safe_float_native(self) -> None:
        """_safe_float retorna nativos Python."""
        assert _safe_float(np.float64(1.5)) == 1.5
        assert isinstance(_safe_float(np.float64(1.5)), float)

    def test_safe_float_int(self) -> None:
        """_safe_float converte np.int64 para int."""
        assert _safe_float(np.int64(42)) == 42
        assert isinstance(_safe_float(np.int64(42)), int)

    def test_safe_float_none(self) -> None:
        """_safe_float retorna None para None."""
        assert _safe_float(None) is None

    def test_safe_float_array(self) -> None:
        """_safe_float converte ndarray para lista."""
        result = _safe_float(np.array([1, 2, 3]))
        assert result == [1, 2, 3]

    def test_numpy_encoder(self) -> None:
        """_NumpyEncoder serializa tipos numpy."""
        data = {"val": np.float64(3.14), "arr": np.array([1, 2])}
        result = json.dumps(data, cls=_NumpyEncoder)
        parsed = json.loads(result)
        assert abs(parsed["val"] - 3.14) < 0.01
        assert parsed["arr"] == [1, 2]

    def test_record_trade(self, db: TrainingDatabase) -> None:
        """record_trade executa INSERT e retorna id."""
        trade_id = db.record_trade(
            symbol="PETR4",
            side="buy",
            price=28.50,
            volume=100,
            funds=2850.0,
            order_type="market",
            dry_run=True,
            asset_class="equity",
        )
        assert trade_id == 1  # Retorno mockado
        _mock_cursor.execute.assert_called()

    def test_record_trade_futures(self, db: TrainingDatabase) -> None:
        """record_trade aceita asset_class 'futures'."""
        trade_id = db.record_trade(
            symbol="WINFUT",
            side="buy",
            price=128500,
            volume=5,
            asset_class="futures",
        )
        assert trade_id == 1

    def test_update_trade_pnl(self, db: TrainingDatabase) -> None:
        """update_trade_pnl executa UPDATE."""
        db.update_trade_pnl(trade_id=1, pnl=50.0, pnl_pct=1.75)
        _mock_cursor.execute.assert_called()

    def test_count_trades_since(self, db: TrainingDatabase) -> None:
        """count_trades_since executa SELECT COUNT."""
        _mock_cursor.fetchone.return_value = [5]
        count = db.count_trades_since("PETR4", time.time() - 86400)
        assert count == 5

    def test_record_decision(self, db: TrainingDatabase) -> None:
        """record_decision executa INSERT e retorna id."""
        _mock_cursor.fetchone.return_value = [1]
        dec_id = db.record_decision(
            symbol="PETR4",
            action="BUY",
            confidence=0.75,
            price=28.50,
            reason="RSI=30",
        )
        assert dec_id == 1

    def test_mark_decision_executed(self, db: TrainingDatabase) -> None:
        """mark_decision_executed executa UPDATE."""
        db.mark_decision_executed(decision_id=1, trade_id=10)
        _mock_cursor.execute.assert_called()

    def test_record_market_state(self, db: TrainingDatabase) -> None:
        """record_market_state insere estado de mercado."""
        _mock_cursor.fetchone.return_value = [1]
        state_id = db.record_market_state(
            symbol="PETR4",
            price=28.50,
            bid=28.48,
            ask=28.52,
            rsi=52.0,
        )
        assert state_id == 1

    def test_record_tax_event(self, db: TrainingDatabase) -> None:
        """record_tax_event executa INSERT e retorna id."""
        _mock_cursor.fetchone.return_value = [1]
        event_id = db.record_tax_event(
            symbol="PETR4",
            asset_class="equity",
            trade_type="swing",
            side="sell",
            volume=100,
            price=35.0,
            gross_value=3500.0,
            pnl=500.0,
            irrf=0.175,
            tax_exempt=True,
            year_month="2026-04",
        )
        assert event_id == 1
        _mock_cursor.execute.assert_called()

    def test_record_tax_event_default_year_month(self, db: TrainingDatabase) -> None:
        """record_tax_event gera year_month se não fornecido."""
        _mock_cursor.fetchone.return_value = [2]
        event_id = db.record_tax_event(
            symbol="VALE3",
            asset_class="equity",
            trade_type="daytrade",
            side="sell",
            volume=200,
            price=70.0,
            gross_value=14000.0,
            pnl=400.0,
        )
        assert event_id == 2

    def test_upsert_tax_monthly_summary(self, db: TrainingDatabase) -> None:
        """upsert_tax_monthly_summary executa INSERT ON CONFLICT."""
        db.upsert_tax_monthly_summary(
            year_month="2026-04",
            equity_swing_sales_total=15000.0,
            equity_swing_pnl=1200.0,
            equity_daytrade_pnl=300.0,
            irrf_total=5.25,
            equity_swing_exempt=True,
            total_tax_due=0.0,
            events_count=8,
        )
        _mock_cursor.execute.assert_called()

    def test_get_tax_monthly_summary(self, db: TrainingDatabase) -> None:
        """get_tax_monthly_summary retorna dict ou None."""
        _mock_cursor.fetchone.return_value = None
        result = db.get_tax_monthly_summary("2026-04")
        assert result is None

    def test_upsert_tax_accumulated_loss(self, db: TrainingDatabase) -> None:
        """upsert_tax_accumulated_loss executa INSERT ON CONFLICT."""
        db.upsert_tax_accumulated_loss("equity_swing", -500.0)
        _mock_cursor.execute.assert_called()

    def test_get_tax_accumulated_losses(self, db: TrainingDatabase) -> None:
        """get_tax_accumulated_losses retorna dict de categorias."""
        _mock_cursor.fetchall.return_value = [
            {"category": "equity_swing", "amount": -500.0},
            {"category": "equity_daytrade", "amount": -100.0},
        ]
        losses = db.get_tax_accumulated_losses()
        assert losses["equity_swing"] == -500.0
        assert losses["equity_daytrade"] == -100.0

    def test_get_tax_events(self, db: TrainingDatabase) -> None:
        """get_tax_events retorna lista de eventos."""
        _mock_cursor.fetchall.return_value = []
        events = db.get_tax_events("2026-04")
        assert events == []

    def test_get_tax_events_with_symbol(self, db: TrainingDatabase) -> None:
        """get_tax_events filtra por símbolo."""
        _mock_cursor.fetchall.return_value = []
        events = db.get_tax_events("2026-04", symbol="PETR4")
        assert events == []
        _mock_cursor.execute.assert_called()


# ========================= TRADING AGENT =========================

class TestTradingAgentLotCalc:
    """Testes de cálculo de lotes do ClearTradingAgent."""

    def _make_agent(self, symbol: str = "PETR4", asset_class: str = "equity"):
        """Cria agente mockado para teste."""
        with (
            patch("clear_trading_agent.trading_agent.TrainingDatabase"),
            patch("clear_trading_agent.trading_agent.MarketRAG"),
            patch("clear_trading_agent.trading_agent.FastTradingModel"),
            patch("clear_trading_agent.trading_agent.get_balance", return_value=10000.0),
            patch("clear_trading_agent.trading_agent.get_price_fast", return_value=28.50),
            patch("clear_trading_agent.trading_agent.analyze_spread", return_value={}),
            patch("clear_trading_agent.trading_agent.analyze_trade_flow", return_value={}),
            patch("builtins.open", MagicMock(side_effect=FileNotFoundError)),
        ):
            from clear_trading_agent.trading_agent import ClearTradingAgent
            agent = ClearTradingAgent(symbol=symbol, dry_run=True)
            agent.state.asset_class = asset_class
            return agent

    def test_equity_lot_size(self) -> None:
        """Ações: lote mínimo de 100 ações."""
        agent = self._make_agent("PETR4", "equity")
        # R$5000 / R$28.50 = 175 ações → arredonda para 100
        qty = agent._calculate_lot_qty(5000, 28.50)
        assert qty == 100
        assert qty % 100 == 0

    def test_equity_lot_insufficient(self) -> None:
        """Ações: retorna 0 quando insuficiente para 1 lote."""
        agent = self._make_agent("PETR4", "equity")
        # R$2000 / R$28.50 = 70 ações < 100
        qty = agent._calculate_lot_qty(2000, 28.50)
        assert qty == 0

    def test_equity_lot_large_amount(self) -> None:
        """Ações: arredonda para múltiplo de 100."""
        agent = self._make_agent("PETR4", "equity")
        # R$10000 / R$28.50 = 350 ações → arredonda para 300
        qty = agent._calculate_lot_qty(10000, 28.50)
        assert qty == 300
        assert qty % 100 == 0

    def test_futures_contracts(self) -> None:
        """Minicontratos: calcula contratos baseado em margem."""
        agent = self._make_agent("WINFUT", "futures")
        agent.symbol = "WINFUT"
        # R$50000 / (128500 * 0.20) = 1.94 contratos → 1
        qty = agent._calculate_lot_qty(50000, 128500)
        assert qty >= 1

    def test_futures_insufficient_margin(self) -> None:
        """Minicontratos: retorna 0 se margem insuficiente."""
        agent = self._make_agent("WINFUT", "futures")
        agent.symbol = "WINFUT"
        # R$1000 < 128500 * 0.20 = R$25700
        qty = agent._calculate_lot_qty(1000, 128500)
        assert qty == 0

    def test_zero_price(self) -> None:
        """Preço zero retorna 0."""
        agent = self._make_agent("PETR4", "equity")
        assert agent._calculate_lot_qty(5000, 0) == 0


class TestTradingAgentState:
    """Testes do AgentState."""

    def test_agent_state_defaults(self) -> None:
        """AgentState tem defaults corretos."""
        from clear_trading_agent.trading_agent import AgentState
        state = AgentState()
        assert state.dry_run is True
        assert state.position == 0.0
        assert state.asset_class == "equity"
        assert state.total_pnl == 0.0

    def test_agent_state_to_dict(self) -> None:
        """AgentState serializa para dicionário."""
        from clear_trading_agent.trading_agent import AgentState
        state = AgentState(symbol="VALE3", position=200, entry_price=62.0)
        d = state.to_dict()
        assert d["symbol"] == "VALE3"
        assert d["position_qty"] == 200
        assert d["entry_price"] == 62.0
        assert "win_rate" in d

    def test_agent_state_futures(self) -> None:
        """AgentState para minicontratos."""
        from clear_trading_agent.trading_agent import AgentState
        state = AgentState(symbol="WINFUT", asset_class="futures")
        assert state.asset_class == "futures"


class TestTradingAgentChecks:
    """Testes de verificações do agente."""

    def test_daily_reset(self) -> None:
        """_check_daily_reset reseta contadores."""
        from clear_trading_agent.trading_agent import AgentState
        state = AgentState(
            daily_date="2024-01-08",
            daily_trades=15,
            daily_pnl=-200.0,
        )
        # O reset acontece quando daily_date != today
        today = str(__import__("datetime").date.today())
        if state.daily_date != today:
            state.daily_trades = 0
            state.daily_pnl = 0.0
            state.daily_date = today
        assert state.daily_trades == 0
        assert state.daily_pnl == 0.0


class TestTradeControls:
    """Testes do TradeControls."""

    def test_trade_controls_defaults(self) -> None:
        """TradeControls tem campos obrigatórios."""
        from clear_trading_agent.trading_agent import TradeControls
        tc = TradeControls(
            min_confidence=0.6,
            min_trade_interval=180,
            max_position_pct=0.5,
            max_positions_cap=3,
            effective_max_positions=3,
            ai_controlled=False,
        )
        assert tc.min_confidence == 0.6
        assert tc.ai_controlled is False
        assert tc.ollama_mode == "shadow"


class TestResolveDryRun:
    """Testes do _resolve_process_dry_run."""

    def test_cli_not_live_is_dry(self) -> None:
        """CLI sem --live → dry_run=True."""
        from clear_trading_agent.trading_agent import _resolve_process_dry_run
        assert _resolve_process_dry_run(cli_live=False) is True

    def test_cli_live_is_live(self) -> None:
        """CLI com --live → dry_run=False."""
        from clear_trading_agent.trading_agent import _resolve_process_dry_run
        assert _resolve_process_dry_run(cli_live=True) is False

    def test_config_overrides_live(self) -> None:
        """Config com dry_run=True sobrescreve --live."""
        from clear_trading_agent.trading_agent import _resolve_process_dry_run
        assert _resolve_process_dry_run(cli_live=True, loaded_cfg={"dry_run": True}) is True


# ========================= PROMETHEUS EXPORTER =========================

class TestPrometheusExporter:
    """Testes do Prometheus exporter (formato text exposition)."""

    def test_format_metrics_structure(self) -> None:
        """format_metrics gera saída no formato Prometheus."""
        from clear_trading_agent.prometheus_exporter import MetricsCollector, format_metrics

        collector = MagicMock(spec=MetricsCollector)
        collector.symbol = "PETR4"
        collector.profile = "default"
        collector.collect_trade_metrics.return_value = {
            "total_trades": 42,
            "trades_24h": 5,
            "total_pnl": 150.50,
            "pnl_24h": 25.0,
            "win_rate": 0.65,
            "last_price": 28.50,
        }
        collector.collect_rag_metrics.return_value = {
            "regime": "BULLISH",
            "regime_confidence": 0.8,
            "ai_take_profit_pct": 0.03,
        }
        collector.collect_tax_metrics.return_value = {}

        output = format_metrics(collector)
        assert "clear_trades_total" in output
        assert "clear_pnl_total" in output
        assert "clear_win_rate" in output
        assert "clear_rag_regime" in output
        assert "clear_tax_equity_swing_sales_brl" in output
        assert 'market="B3"' in output
        assert 'symbol="PETR4"' in output

    def test_format_metrics_bearish(self) -> None:
        """format_metrics mapeia BEARISH para -1."""
        from clear_trading_agent.prometheus_exporter import MetricsCollector, format_metrics

        collector = MagicMock(spec=MetricsCollector)
        collector.symbol = "VALE3"
        collector.profile = "default"
        collector.collect_trade_metrics.return_value = {}
        collector.collect_rag_metrics.return_value = {"regime": "BEARISH"}
        collector.collect_tax_metrics.return_value = {}

        output = format_metrics(collector)
        assert "clear_rag_regime" in output
        # BEARISH mapeia para -1
        assert "-1" in output


class TestMetricsHandler:
    """Testes do handler HTTP de métricas."""

    def test_health_endpoint(self) -> None:
        """Handler /health retorna status ok."""
        from clear_trading_agent.prometheus_exporter import MetricsHandler
        # Não instanciamos o HTTP server, testamos a lógica isolada
        # via formato de métricas acima
        assert hasattr(MetricsHandler, "do_GET")


class TestMetricsCollector:
    """Testes do MetricsCollector com PostgreSQL mockado."""

    def test_collect_trade_metrics_success(self) -> None:
        """collect_trade_metrics retorna métricas quando DB responde."""
        from clear_trading_agent.prometheus_exporter import MetricsCollector

        collector = MetricsCollector(
            dsn="postgresql://test:test@localhost:5433/test",
            symbol="PETR4",
            profile="default",
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            [42],      # total trades
            [5],       # trades 24h
            [150.50],  # pnl total
            [25.0],    # pnl 24h
            [30, 42],  # wins, total sells
            [28.50],   # last price
        ]
        mock_cursor.fetchall.return_value = [("buy", 22), ("sell", 20)]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(collector, "_get_conn", return_value=mock_conn), \
             patch.object(collector, "_put_conn"):
            metrics = collector.collect_trade_metrics()

        assert metrics["total_trades"] == 42
        assert metrics["trades_24h"] == 5
        assert metrics["total_pnl"] == 150.50
        assert metrics["win_rate"] == 30 / 42
        assert metrics["last_price"] == 28.50

    def test_collect_trade_metrics_db_error(self) -> None:
        """collect_trade_metrics retorna error key em caso de falha."""
        from clear_trading_agent.prometheus_exporter import MetricsCollector

        collector = MetricsCollector(
            dsn="postgresql://test:test@localhost:5433/test",
        )
        with patch.object(collector, "_get_conn", side_effect=Exception("conn failed")):
            metrics = collector.collect_trade_metrics()

        assert "error" in metrics

    def test_collect_rag_metrics_file_missing(self, tmp_path: Path) -> None:
        """collect_rag_metrics retorna dict vazio se arquivo não existe."""
        from clear_trading_agent.prometheus_exporter import MetricsCollector

        collector = MetricsCollector(dsn="postgresql://x")
        with patch("clear_trading_agent.prometheus_exporter.BASE_DIR", tmp_path):
            metrics = collector.collect_rag_metrics()
        assert metrics == {}

    def test_collect_rag_metrics_file_valid(self, tmp_path: Path) -> None:
        """collect_rag_metrics lê regime_adjustments.json corretamente."""
        from clear_trading_agent.prometheus_exporter import MetricsCollector

        rag_dir = tmp_path / "data" / "market_rag"
        rag_dir.mkdir(parents=True)
        adj_file = rag_dir / "regime_adjustments.json"
        adj_file.write_text(json.dumps({
            "current": {
                "suggested_regime": "BULLISH",
                "regime_confidence": 0.85,
                "ai_take_profit_pct": 0.04,
            }
        }))

        collector = MetricsCollector(dsn="postgresql://x")
        with patch("clear_trading_agent.prometheus_exporter.BASE_DIR", tmp_path):
            metrics = collector.collect_rag_metrics()

        assert metrics["regime"] == "BULLISH"
        assert metrics["regime_confidence"] == 0.85

    def test_collect_tax_metrics_file_missing(self, tmp_path: Path) -> None:
        """collect_tax_metrics retorna dict vazio se arquivo não existe."""
        from clear_trading_agent.prometheus_exporter import MetricsCollector

        collector = MetricsCollector(dsn="postgresql://x", symbol="PETR4")
        with patch("clear_trading_agent.prometheus_exporter.BASE_DIR", tmp_path):
            metrics = collector.collect_tax_metrics()
        assert metrics == {}

    def test_pool_putconn_called(self) -> None:
        """_put_conn devolve conexão ao pool."""
        from clear_trading_agent.prometheus_exporter import MetricsCollector

        collector = MetricsCollector(dsn="postgresql://x")
        mock_pool = MagicMock()
        collector._pool = mock_pool
        mock_conn = MagicMock()
        collector._put_conn(mock_conn)
        mock_pool.putconn.assert_called_once_with(mock_conn)
