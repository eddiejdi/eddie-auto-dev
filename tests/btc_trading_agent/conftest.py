"""
Configuração compartilhada de testes para btc_trading_agent.

Fixtures para mockar APIs externas, banco de dados, e dependências pesadas.
"""

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta


# =============== FIXTURES: KuCoin API ===============


@pytest.fixture
def mock_kucoin_get_price(monkeypatch):
    """Mock kucoin_api.get_price para retornar preço fixo."""
    def _get_price(symbol: str) -> float:
        prices = {"BTC-USDT": 45000.0, "ETH-USDT": 2500.0}
        return prices.get(symbol, 45000.0)
    
    monkeypatch.setattr(
        "btc_trading_agent.kucoin_api.get_price",
        _get_price
    )
    return _get_price


@pytest.fixture
def mock_kucoin_get_balance(monkeypatch):
    """Mock kucoin_api.get_balance para retornar saldo fixo."""
    def _get_balance(currency: str) -> float:
        balances = {"BTC": 1.5, "USDT": 50000.0}
        return balances.get(currency, 0.0)
    
    monkeypatch.setattr(
        "btc_trading_agent.kucoin_api.get_balance",
        _get_balance
    )
    return _get_balance


@pytest.fixture
def mock_kucoin_get_balances(monkeypatch):
    """Mock kucoin_api.get_balances para retornar múltiplos saldos."""
    def _get_balances(account_type: str = "trade") -> list:
        return [
            {"currency": "BTC", "available": 1.5, "balance": 1.5},
            {"currency": "USDT", "available": 50000.0, "balance": 50000.0},
        ]
    
    monkeypatch.setattr(
        "btc_trading_agent.kucoin_api.get_balances",
        _get_balances
    )
    return _get_balances


@pytest.fixture
def mock_kucoin_place_market_order(monkeypatch):
    """Mock kucoin_api.place_market_order para retornar order ID."""
    def _place_market_order(
        symbol: str, side: str, funds: float = None, size: float = None
    ) -> dict:
        return {
            "orderId": "mock_order_123456",
            "symbol": symbol,
            "side": side,
            "status": "done"
        }
    
    monkeypatch.setattr(
        "btc_trading_agent.kucoin_api.place_market_order",
        _place_market_order
    )
    return _place_market_order


@pytest.fixture
def mock_kucoin_inner_transfer(monkeypatch):
    """Mock kucoin_api.inner_transfer para simular transferência entre contas."""
    def _inner_transfer(
        currency: str, amount: float, from_account: str, to_account: str
    ) -> dict:
        return {"success": True, "orderId": "transfer_mock_123"}
    
    monkeypatch.setattr(
        "btc_trading_agent.kucoin_api.inner_transfer",
        _inner_transfer
    )
    return _inner_transfer


@pytest.fixture
def mock_kucoin_get_candles(monkeypatch):
    """Mock kucoin_api.get_candles para retornar histórico de candles."""
    def _get_candles(symbol: str, ktype: str = "1min", limit: int = 500) -> list:
        # Gera candles de teste com preços crescentes
        candles = []
        base_price = 45000.0
        for i in range(limit):
            price = base_price + i * 10
            candles.append({
                "time": 1700000000 + i * 60,
                "open": price,
                "high": price + 50,
                "low": price - 50,
                "close": price + 25,
                "volume": 10.0
            })
        return candles
    
    monkeypatch.setattr(
        "btc_trading_agent.kucoin_api.get_candles",
        _get_candles
    )
    return _get_candles


@pytest.fixture
def mock_kucoin_all(
    mock_kucoin_get_price,
    mock_kucoin_get_balance,
    mock_kucoin_get_balances,
    mock_kucoin_place_market_order,
    mock_kucoin_inner_transfer,
    mock_kucoin_get_candles
):
    """Combo fixture: mocka todas as funções KuCoin de uma vez."""
    return {
        "get_price": mock_kucoin_get_price,
        "get_balance": mock_kucoin_get_balance,
        "get_balances": mock_kucoin_get_balances,
        "place_market_order": mock_kucoin_place_market_order,
        "inner_transfer": mock_kucoin_inner_transfer,
        "get_candles": mock_kucoin_get_candles,
    }


# =============== FIXTURES: Database (TrainingDatabase) ===============


@pytest.fixture
def mock_training_db(monkeypatch):
    """Mock TrainingDatabase para simular operações de banco sem usar PostgreSQL real."""
    
    class MockTrainingDB:
        def __init__(self):
            self.trades = []
            self.ai_plans = []
            
        def record_trade(
            self, symbol: str, side: str, price: float, size: float,
            funds: float, dry_run: bool, metadata: dict = None
        ) -> int:
            trade_id = len(self.trades) + 1
            self.trades.append({
                "id": trade_id,
                "symbol": symbol,
                "side": side,
                "price": price,
                "size": size,
                "funds": funds,
                "timestamp": 1700000000 + len(self.trades),
                "dry_run": dry_run,
                "metadata": metadata or {},
                "pnl": 0.0
            })
            return trade_id
        
        def get_recent_trades(self, symbol: str, limit: int = 50, include_dry: bool = True) -> list:
            result = [t for t in self.trades if t["symbol"] == symbol]
            if not include_dry:
                result = [t for t in result if not t["dry_run"]]
            return sorted(result, key=lambda x: x["timestamp"], reverse=True)[:limit]
        
        def _get_conn(self):
            return MagicMock()
        
        def __enter__(self):
            return self
        
        def __exit__(self, *args):
            pass
    
    db = MockTrainingDB()
    monkeypatch.setattr(
        "btc_trading_agent.trading_agent.TrainingDatabase",
        lambda: db
    )
    return db


# =============== FIXTURES: HTTP Client (httpx) ===============


@pytest.fixture
def mock_httpx_client(monkeypatch):
    """Mock httpx.Client para simular requisições HTTP sem rede real."""
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": "Plano de IA simulado: monitorar preço"
    }
    
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.get.return_value = mock_response
    mock_client.__enter__ = lambda self: self
    mock_client.__exit__ = lambda self, *args: None
    
    monkeypatch.setattr(
        "httpx.Client",
        lambda **kwargs: mock_client
    )
    return mock_client


# =============== FIXTURES: MarketRAG ===============


@pytest.fixture
def mock_market_rag(monkeypatch):
    """Mock MarketRAG para evitar inicialização pesada de vector DB."""
    
    class MockMarketRAG:
        def __init__(self, symbol: str, **kwargs):
            self.symbol = symbol
            
        def get_current_adjustment(self):
            mock_adj = MagicMock()
            mock_adj.ai_buy_target_price = 44500.0
            mock_adj.ai_take_profit_pct = 0.05
            mock_adj.ai_position_size_pct = 0.05
            mock_adj.ai_max_entries = 3
            mock_adj.ai_aggressiveness = 0.6
            return mock_adj
        
        def get_stats(self):
            return {
                "current_regime": "uptrend",
                "regime_confidence": 0.75,
                "volatility": 0.025
            }
        
        def snapshot(self):
            pass
        
        def recalibrate(self):
            pass
    
    monkeypatch.setattr(
        "btc_trading_agent.trading_agent.MarketRAG",
        MockMarketRAG
    )
    return MockMarketRAG


# =============== FIXTURES: FastTradingModel ===============


@pytest.fixture
def mock_fast_model(monkeypatch):
    """Mock FastTradingModel para simular modelo ML sem GPU."""
    
    class MockIndicators:
        def rsi(self) -> float:
            return 55.0
        
        def momentum(self) -> float:
            return 0.002
        
        def volatility(self) -> float:
            return 0.025
    
    class MockSignal:
        def __init__(self, action: str, confidence: float):
            self.action = action  # "buy", "sell", "hold"
            self.confidence = confidence
    
    class MockFastModel:
        def __init__(self, symbol: str):
            self.symbol = symbol
            self.indicators = MockIndicators()
        
        def predict(self, market_state) -> MockSignal:
            return MockSignal("hold", 0.5)
        
        def update(self, candle):
            pass
    
    monkeypatch.setattr(
        "btc_trading_agent.trading_agent.FastTradingModel",
        MockFastModel
    )
    return MockFastModel


# =============== FIXTURES: Time & Freezegun ===============


@pytest.fixture
def frozen_time(monkeypatch):
    """Fixture para congelar time.time() em um valor fixo."""
    frozen_timestamp = 1700000000.0  # 2023-11-15 08:26:40 UTC
    
    def mock_time():
        return frozen_timestamp
    
    monkeypatch.setattr("time.time", mock_time)
    return frozen_timestamp


# =============== FIXTURES: Logging ===============


@pytest.fixture
def caplog_trading(caplog):
    """Captura logs de trading para assertions."""
    caplog.set_level("INFO", logger="btc_trading_agent.trading_agent")
    return caplog


# =============== TEST DATA BUILDERS ===============


@pytest.fixture
def sample_market_state():
    """Factory para criar objeto MarketState simulado."""
    class MockMarketState:
        def __init__(
            self,
            price: float = 45000.0,
            volume: float = 100.0,
            orderbook_imbalance: float = 0.5,
            spread: float = 0.02
        ):
            self.price = price
            self.volume = volume
            self.orderbook_imbalance = orderbook_imbalance
            self.spread = spread
    
    return MockMarketState()


@pytest.fixture
def sample_trade_entry():
    """Factory para criar entrada de posição simulada."""
    return {
        "price": 44500.0,
        "size": 0.5,
        "ts": 1700000000
    }


@pytest.fixture
def sample_candle():
    """Factory para criar candle simulado."""
    return {
        "time": 1700000000,
        "open": 45000.0,
        "high": 45100.0,
        "low": 44900.0,
        "close": 45050.0,
        "volume": 50.0
    }


@pytest.fixture
def sample_trade_record():
    """Factory para criar registro de trade do banco simulado."""
    return {
        "id": 1,
        "symbol": "BTC-USDT",
        "side": "buy",
        "price": 44500.0,
        "size": 0.5,
        "funds": 22250.0,
        "timestamp": 1700000000,
        "dry_run": True,
        "metadata": {},
        "pnl": 0.0
    }
