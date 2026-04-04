#!/usr/bin/env python3
"""Testes unitários para mt5_bridge/bridge_api.py.

Cobre: modelos Pydantic, endpoints REST (order, positions, account,
tick, rates, health, deals, orders), autenticação, retcode mapping.
MetaTrader5 é completamente mockado — testes rodam em Linux.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ====================== SETUP: mockando o pacote MetaTrader5 ======================
# Cria mock do MT5 antes de importar bridge_api
_mt5_mock = MagicMock()
_mt5_mock.ORDER_TYPE_BUY = 0
_mt5_mock.ORDER_TYPE_SELL = 1
_mt5_mock.ORDER_TYPE_BUY_LIMIT = 2
_mt5_mock.ORDER_TYPE_SELL_LIMIT = 3
_mt5_mock.ORDER_FILLING_IOC = 2
_mt5_mock.TRADE_ACTION_DEAL = 1
_mt5_mock.TRADE_ACTION_PENDING = 5
_mt5_mock.ORDER_TIME_GTC = 0
_mt5_mock.TIMEFRAME_M1 = 1
_mt5_mock.TIMEFRAME_M5 = 5
_mt5_mock.TIMEFRAME_M15 = 15
_mt5_mock.TIMEFRAME_M30 = 30
_mt5_mock.TIMEFRAME_H1 = 60
_mt5_mock.TIMEFRAME_H4 = 240
_mt5_mock.TIMEFRAME_D1 = 1440
_mt5_mock.TIMEFRAME_W1 = 10080
_mt5_mock.TIMEFRAME_MN1 = 43200
sys.modules["MetaTrader5"] = _mt5_mock

# Preservar env vars
os.environ.setdefault("MT5_BRIDGE_API_KEY", "test-bridge-key-123")
os.environ.setdefault("MT5_LOGIN", "12345")
os.environ.setdefault("MT5_PASSWORD", "testpass")
os.environ.setdefault("MT5_SERVER", "TestServer")

_BRIDGE_DIR = Path(__file__).resolve().parent.parent / "mt5_bridge"
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))

from bridge_api import (
    OrderRequest,
    OrderResponse,
    PositionInfo,
    AccountInfo,
    TickInfo,
    CandleInfo,
    HealthResponse,
    DealInfo,
    OrderInfo,
    _MT5_RETCODES,
    app,
    verify_api_key,
)

# ASGI test client
from fastapi.testclient import TestClient

VALID_KEY = os.environ["MT5_BRIDGE_API_KEY"]


# ========================= Fixtures =========================

@pytest.fixture
def client() -> TestClient:
    """TestClient do FastAPI sem lifespan (MT5 mock)."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Headers com API key válida."""
    return {"X-API-KEY": VALID_KEY}


@pytest.fixture
def _terminal_connected():
    """Mock MT5 terminal como conectado com trade habilitado."""
    info = SimpleNamespace(
        connected=True,
        name="MetaTrader 5 Test",
        build=3456,
        trade_allowed=True,
    )
    _mt5_mock.terminal_info.return_value = info
    _mt5_mock.initialize.return_value = True
    yield info
    _mt5_mock.reset_mock()


@pytest.fixture
def _account_info():
    """Mock de account_info."""
    acc = SimpleNamespace(
        login=12345,
        balance=50000.0,
        equity=48500.0,
        margin=5000.0,
        margin_free=43500.0,
        margin_level=970.0,
        profit=-1500.0,
        currency="BRL",
        server="ClearCorretora-Server",
        name="Test Account",
    )
    _mt5_mock.account_info.return_value = acc
    yield acc


# ========================= Pydantic Models =========================

class TestPydanticModels:
    """Testes dos modelos Pydantic do bridge."""

    def test_order_request_valid(self) -> None:
        """OrderRequest aceita payload válido."""
        req = OrderRequest(
            symbol="PETR4",
            side="buy",
            volume=100,
            order_type="market",
            deviation=20,
            magic=234000,
            comment="test",
        )
        assert req.symbol == "PETR4"
        assert req.side == "buy"
        assert req.volume == 100

    def test_order_request_invalid_side(self) -> None:
        """OrderRequest rejeita side inválido."""
        with pytest.raises(Exception):
            OrderRequest(symbol="PETR4", side="hold", volume=100)

    def test_order_request_invalid_volume(self) -> None:
        """OrderRequest rejeita volume <= 0."""
        with pytest.raises(Exception):
            OrderRequest(symbol="PETR4", side="buy", volume=0)

    def test_order_response_success(self) -> None:
        """OrderResponse com sucesso."""
        resp = OrderResponse(
            success=True,
            order_id=123456,
            retcode=10009,
            retcode_str="TRADE_RETCODE_DONE",
            price=28.50,
            volume=100,
        )
        assert resp.success is True
        assert resp.order_id == 123456

    def test_order_response_failure(self) -> None:
        """OrderResponse com falha."""
        resp = OrderResponse(
            success=False,
            error="Market closed",
            retcode=10018,
            retcode_str="TRADE_RETCODE_MARKET_CLOSED",
        )
        assert resp.success is False
        assert resp.error == "Market closed"

    def test_position_info(self) -> None:
        """PositionInfo serializa corretamente."""
        pos = PositionInfo(
            ticket=1001,
            symbol="PETR4",
            type="buy",
            volume=100,
            price_open=28.50,
            price_current=29.10,
            profit=60.0,
            swap=0.0,
            time=1700000000,
            magic=234000,
            comment="clear_agent",
        )
        assert pos.profit == 60.0
        assert pos.type == "buy"

    def test_account_info_model(self) -> None:
        """AccountInfo serializa corretamente."""
        acc = AccountInfo(
            login=12345,
            balance=50000.0,
            equity=48500.0,
            margin=5000.0,
            margin_free=43500.0,
            profit=-1500.0,
            currency="BRL",
            server="ClearCorretora-Server",
            name="Test",
        )
        assert acc.currency == "BRL"
        assert acc.margin_free == 43500.0

    def test_tick_info(self) -> None:
        """TickInfo serializa corretamente."""
        tick = TickInfo(
            symbol="VALE3",
            bid=62.50,
            ask=62.55,
            last=62.52,
            volume=5000.0,
            time=1700000000,
            spread=0.05,
        )
        assert tick.bid == 62.50
        assert tick.ask == 62.55

    def test_candle_info(self) -> None:
        """CandleInfo serializa corretamente."""
        candle = CandleInfo(
            timestamp=1700000000,
            open=28.50,
            high=28.90,
            low=28.30,
            close=28.70,
            tick_volume=1500,
            spread=5,
            real_volume=50000,
        )
        assert candle.close == 28.70

    def test_health_response(self) -> None:
        """HealthResponse serializa corretamente."""
        health = HealthResponse(
            status="ok",
            mt5_connected=True,
            uptime_seconds=3600.0,
        )
        assert health.mt5_connected is True

    def test_deal_info(self) -> None:
        """DealInfo serializa corretamente."""
        deal = DealInfo(
            ticket=2001,
            order=1001,
            symbol="PETR4",
            type=0,
            volume=100,
            price=28.50,
            profit=0.0,
            commission=0.85,
            swap=0.0,
            fee=0.0,
            time=1700000000,
            comment="clear_agent",
        )
        assert deal.commission == 0.85

    def test_order_info(self) -> None:
        """OrderInfo serializa corretamente."""
        order = OrderInfo(
            ticket=3001,
            symbol="WINFUT",
            type=2,
            volume_initial=5.0,
            volume_current=5.0,
            price_open=128500.0,
            price_current=128600.0,
            time_setup=1700000000,
            time_done=0,
            state=0,
            comment="clear_agent",
        )
        assert order.symbol == "WINFUT"


# ========================= Retcode Mapping =========================

class TestRetcodes:
    """Testes do mapeamento de retcodes MT5."""

    def test_retcode_done(self) -> None:
        """Retcode 10009 = DONE."""
        assert _MT5_RETCODES[10009] == "TRADE_RETCODE_DONE"

    def test_retcode_market_closed(self) -> None:
        """Retcode 10018 = MARKET_CLOSED."""
        assert _MT5_RETCODES[10018] == "TRADE_RETCODE_MARKET_CLOSED"

    def test_retcode_no_money(self) -> None:
        """Retcode 10019 = NO_MONEY."""
        assert _MT5_RETCODES[10019] == "TRADE_RETCODE_NO_MONEY"

    def test_retcode_reject(self) -> None:
        """Retcode 10006 = REJECT."""
        assert _MT5_RETCODES[10006] == "TRADE_RETCODE_REJECT"

    def test_all_known_retcodes(self) -> None:
        """Todos os retcodes mapeados são strings não-vazias."""
        for code, name in _MT5_RETCODES.items():
            assert isinstance(code, int)
            assert isinstance(name, str)
            assert name.startswith("TRADE_RETCODE_")


# ========================= Auth =========================

class TestAuth:
    """Testes de autenticação."""

    def test_missing_api_key(self, client: TestClient) -> None:
        """Request sem API key retorna 422 (header obrigatório)."""
        resp = client.get("/positions")
        assert resp.status_code == 422

    def test_invalid_api_key(self, client: TestClient) -> None:
        """Request com API key inválida retorna 401."""
        resp = client.get("/positions", headers={"X-API-KEY": "wrong-key"})
        assert resp.status_code == 401

    def test_health_no_auth(self, client: TestClient) -> None:
        """Health check NÃO requer autenticação."""
        _mt5_mock.terminal_info.return_value = None
        _mt5_mock.account_info.return_value = None
        resp = client.get("/health")
        assert resp.status_code == 200


# ========================= Endpoints =========================

class TestHealthEndpoint:
    """Testes do endpoint /health."""

    def test_health_degraded_no_mt5(self, client: TestClient) -> None:
        """Health retorna 'degraded' quando MT5 não está conectado."""
        _mt5_mock.terminal_info.return_value = None
        _mt5_mock.account_info.return_value = None
        resp = client.get("/health")
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["mt5_connected"] is False

    def test_health_ok_connected(
        self, client: TestClient, _terminal_connected, _account_info,
    ) -> None:
        """Health retorna 'ok' quando MT5 está conectado."""
        resp = client.get("/health")
        body = resp.json()
        assert body["status"] == "ok"
        assert body["mt5_connected"] is True
        assert body["account_login"] == 12345
        assert body["uptime_seconds"] >= 0


class TestOrderEndpoint:
    """Testes do endpoint POST /order."""

    def test_order_buy_success(
        self, client: TestClient, auth_headers, _terminal_connected,
    ) -> None:
        """Ordem de compra executada com sucesso."""
        # Mock symbol_info
        sym_info = SimpleNamespace(visible=True)
        _mt5_mock.symbol_info.return_value = sym_info

        # Mock tick
        tick = SimpleNamespace(ask=28.60, bid=28.50)
        _mt5_mock.symbol_info_tick.return_value = tick

        # Mock order_send
        result = SimpleNamespace(
            retcode=10009,
            order=123456,
            price=28.60,
            volume=100.0,
            comment="OK",
        )
        _mt5_mock.order_send.return_value = result

        resp = client.post(
            "/order",
            json={"symbol": "PETR4", "side": "buy", "volume": 100},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["order_id"] == 123456
        assert body["retcode"] == 10009

    def test_order_sell_success(
        self, client: TestClient, auth_headers, _terminal_connected,
    ) -> None:
        """Ordem de venda executada com sucesso."""
        sym_info = SimpleNamespace(visible=True)
        _mt5_mock.symbol_info.return_value = sym_info

        tick = SimpleNamespace(ask=28.60, bid=28.50)
        _mt5_mock.symbol_info_tick.return_value = tick

        result = SimpleNamespace(
            retcode=10009,
            order=123457,
            price=28.50,
            volume=100.0,
            comment="OK",
        )
        _mt5_mock.order_send.return_value = result

        resp = client.post(
            "/order",
            json={"symbol": "PETR4", "side": "sell", "volume": 100},
            headers=auth_headers,
        )
        body = resp.json()
        assert body["success"] is True

    def test_order_rejected(
        self, client: TestClient, auth_headers, _terminal_connected,
    ) -> None:
        """Ordem rejeitada (sem dinheiro)."""
        sym_info = SimpleNamespace(visible=True)
        _mt5_mock.symbol_info.return_value = sym_info
        _mt5_mock.symbol_info_tick.return_value = SimpleNamespace(ask=28.60, bid=28.50)

        result = SimpleNamespace(
            retcode=10019,
            order=0,
            price=0,
            volume=0,
            comment="No money",
        )
        _mt5_mock.order_send.return_value = result

        resp = client.post(
            "/order",
            json={"symbol": "PETR4", "side": "buy", "volume": 100},
            headers=auth_headers,
        )
        body = resp.json()
        assert body["success"] is False
        assert "NO_MONEY" in (body.get("retcode_str") or "")

    def test_order_symbol_not_found(
        self, client: TestClient, auth_headers, _terminal_connected,
    ) -> None:
        """Símbolo inexistente retorna erro."""
        _mt5_mock.symbol_info.return_value = None

        resp = client.post(
            "/order",
            json={"symbol": "INVALID", "side": "buy", "volume": 100},
            headers=auth_headers,
        )
        body = resp.json()
        assert body["success"] is False
        assert "não encontrado" in (body.get("error") or "")

    def test_order_no_tick(
        self, client: TestClient, auth_headers, _terminal_connected,
    ) -> None:
        """Sem cotação retorna erro."""
        _mt5_mock.symbol_info.return_value = SimpleNamespace(visible=True)
        _mt5_mock.symbol_info_tick.return_value = None

        resp = client.post(
            "/order",
            json={"symbol": "PETR4", "side": "buy", "volume": 100},
            headers=auth_headers,
        )
        body = resp.json()
        assert body["success"] is False

    def test_limit_order(
        self, client: TestClient, auth_headers, _terminal_connected,
    ) -> None:
        """Ordem limitada usa preço do payload."""
        _mt5_mock.symbol_info.return_value = SimpleNamespace(visible=True)
        _mt5_mock.symbol_info_tick.return_value = SimpleNamespace(ask=28.60, bid=28.50)

        result = SimpleNamespace(
            retcode=10008,  # PLACED
            order=123460,
            price=28.00,
            volume=100.0,
            comment="OK",
        )
        _mt5_mock.order_send.return_value = result

        resp = client.post(
            "/order",
            json={
                "symbol": "PETR4",
                "side": "buy",
                "volume": 100,
                "order_type": "limit",
                "price": 28.00,
            },
            headers=auth_headers,
        )
        body = resp.json()
        assert body["success"] is True
        assert body["retcode"] == 10008


class TestPositionsEndpoint:
    """Testes do endpoint GET /positions."""

    def test_positions_empty(
        self, client: TestClient, auth_headers, _terminal_connected,
    ) -> None:
        """Retorna lista vazia quando sem posições."""
        _mt5_mock.positions_get.return_value = None
        resp = client.get("/positions", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_positions_with_data(
        self, client: TestClient, auth_headers, _terminal_connected,
    ) -> None:
        """Retorna posições abertas."""
        pos = SimpleNamespace(
            ticket=1001,
            symbol="PETR4",
            type=0,  # buy
            volume=100,
            price_open=28.50,
            price_current=29.00,
            profit=50.0,
            swap=0.0,
            time=1700000000,
            magic=234000,
            comment="clear_agent",
        )
        _mt5_mock.positions_get.return_value = [pos]

        resp = client.get("/positions", headers=auth_headers)
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "PETR4"
        assert data[0]["type"] == "buy"
        assert data[0]["profit"] == 50.0

    def test_positions_filtered_by_symbol(
        self, client: TestClient, auth_headers, _terminal_connected,
    ) -> None:
        """Filtra posições por símbolo."""
        _mt5_mock.positions_get.return_value = []
        resp = client.get("/positions?symbol=VALE3", headers=auth_headers)
        _mt5_mock.positions_get.assert_called_with(symbol="VALE3")


class TestAccountEndpoint:
    """Testes do endpoint GET /account."""

    def test_account_success(
        self, client: TestClient, auth_headers, _terminal_connected, _account_info,
    ) -> None:
        """Retorna info da conta."""
        resp = client.get("/account", headers=auth_headers)
        body = resp.json()
        assert body["balance"] == 50000.0
        assert body["currency"] == "BRL"
        assert body["login"] == 12345

    def test_account_failure(
        self, client: TestClient, auth_headers, _terminal_connected,
    ) -> None:
        """Retorna 503 se não conseguir info da conta."""
        _mt5_mock.account_info.return_value = None
        resp = client.get("/account", headers=auth_headers)
        assert resp.status_code == 503


class TestTickEndpoint:
    """Testes do endpoint GET /symbol/{symbol}/tick."""

    def test_tick_success(
        self, client: TestClient, auth_headers, _terminal_connected,
    ) -> None:
        """Retorna tick de um ativo."""
        _mt5_mock.symbol_info.return_value = SimpleNamespace(visible=True, spread=5)
        _mt5_mock.symbol_info_tick.return_value = SimpleNamespace(
            bid=28.50, ask=28.55, last=28.52, volume=10000.0, time=1700000000,
        )

        resp = client.get("/symbol/PETR4/tick", headers=auth_headers)
        body = resp.json()
        assert body["symbol"] == "PETR4"
        assert body["bid"] == 28.50
        assert body["ask"] == 28.55

    def test_tick_symbol_not_found(
        self, client: TestClient, auth_headers, _terminal_connected,
    ) -> None:
        """Retorna 404 para símbolo inexistente."""
        _mt5_mock.symbol_info.return_value = None
        resp = client.get("/symbol/INVALID/tick", headers=auth_headers)
        assert resp.status_code == 404


class TestRatesEndpoint:
    """Testes do endpoint GET /symbol/{symbol}/rates."""

    def test_rates_empty(
        self, client: TestClient, auth_headers, _terminal_connected,
    ) -> None:
        """Retorna lista vazia quando sem dados."""
        _mt5_mock.copy_rates_from_pos.return_value = None
        resp = client.get("/symbol/PETR4/rates?timeframe=M1&count=10", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_rates_invalid_timeframe(
        self, client: TestClient, auth_headers, _terminal_connected,
    ) -> None:
        """Retorna 400 para timeframe inválido."""
        resp = client.get("/symbol/PETR4/rates?timeframe=INVALID", headers=auth_headers)
        assert resp.status_code == 400
