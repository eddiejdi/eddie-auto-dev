#!/usr/bin/env python3
"""Testes unitários para btc_trading_agent/kucoin_api.py.

Cobre: _build_headers (HMAC), get_price, get_candles, get_orderbook,
analyze_orderbook, analyze_trade_flow, _has_keys, rate_limit, retry_on_failure.
Todas as dependências externas (HTTP, Secrets Agent) são mockadas.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import Any

import pytest

# ====================== SETUP: antes do import do módulo ======================
# Configura env vars para que _load_credentials() não tente o secrets-agent
# e não envie alertas Telegram. O módulo deve carregar com credenciais vazias.
import os

os.environ.setdefault("KUCOIN_API_KEY", "test_key_abc123")
os.environ.setdefault("KUCOIN_API_SECRET", "test_secret_xyz789")
os.environ.setdefault("KUCOIN_API_PASSPHRASE", "x")
os.environ.setdefault("SECRETS_AGENT_API_KEY", "")  # desativa tentativa ao secrets-agent

# Garantir que btc_trading_agent/ está no sys.path
_BTC_DIR = Path(__file__).resolve().parent.parent / "btc_trading_agent"
if str(_BTC_DIR) not in sys.path:
    sys.path.insert(0, str(_BTC_DIR))

# Importar com mock das funções de I/O para evitar side effects
with (
    patch("secrets_helper.get_secret", return_value=None),
    patch("requests.post"),  # mock do _send_telegram_alert
):
    import kucoin_api


# ========================= Fixtures =========================

@pytest.fixture
def mock_response_ok() -> MagicMock:
    """Simula resposta HTTP com code='200000'."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"code": "200000", "data": {}}
    return resp


@pytest.fixture
def mock_price_response() -> MagicMock:
    """Resposta com preço BTC simulado (campos bestBid/bestAsk do level1)."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "code": "200000",
        "data": {"bestBid": "87000.00", "bestAsk": "87100.00"},
    }
    return resp


@pytest.fixture
def mock_orderbook_response() -> MagicMock:
    """Resposta com orderbook simulado."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "code": "200000",
        "data": {
            "bids": [["87000", "0.5"], ["86900", "1.0"], ["86800", "2.0"]],
            "asks": [["87100", "0.3"], ["87200", "0.6"], ["87300", "1.5"]],
        },
    }
    return resp


@pytest.fixture
def mock_trades_response() -> MagicMock:
    """Resposta com trades simulados."""
    resp = MagicMock()
    resp.status_code = 200
    now = int(time.time() * 1000)
    resp.json.return_value = {
        "code": "200000",
        "data": [
            {"size": "0.1", "side": "buy", "time": now},
            {"size": "0.2", "side": "sell", "time": now - 1000},
            {"size": "0.15", "side": "buy", "time": now - 2000},
        ],
    }
    return resp


# ========================= _build_headers =========================

class TestBuildHeaders:
    """Testes para a função _build_headers (HMAC-SHA256)."""

    def test_retorna_dict_com_campos_obrigatorios(self) -> None:
        with patch("kucoin_api.time") as mock_time:
            mock_time.time.return_value = 1700000000.0
            headers = kucoin_api._build_headers("GET", "/api/v1/market/orderbook/level2_20")

        assert "KC-API-KEY" in headers
        assert "KC-API-SIGN" in headers
        assert "KC-API-TIMESTAMP" in headers
        assert "KC-API-PASSPHRASE" in headers
        assert "KC-API-KEY-VERSION" in headers
        assert "Content-Type" in headers

    def test_timestamp_no_header(self) -> None:
        fixed_ts_ms = "1700000000000"
        with patch("kucoin_api._server_time", return_value=int(fixed_ts_ms)):
            headers = kucoin_api._build_headers("GET", "/api/v1/endpoint")

        assert headers["KC-API-TIMESTAMP"] == fixed_ts_ms

    def test_sign_e_string_base64(self) -> None:
        with patch("kucoin_api.time") as mock_time:
            mock_time.time.return_value = 1700000000.0
            headers = kucoin_api._build_headers("POST", "/api/v1/orders", '{"side":"buy"}')

        import base64
        # A assinatura deve ser decodificável como base64
        try:
            base64.b64decode(headers["KC-API-SIGN"])
        except Exception:
            pytest.fail("KC-API-SIGN não é base64 válido")


# ========================= _has_keys =========================

class TestHasKeys:
    """Testes para _has_keys()."""

    def test_retorna_true_com_credenciais(self) -> None:
        with (
            patch.object(kucoin_api, "API_KEY", "key123"),
            patch.object(kucoin_api, "API_SECRET", "secret456"),
            patch.object(kucoin_api, "API_PASSPHRASE", "x"),
        ):
            assert kucoin_api._has_keys() is True

    def test_retorna_false_sem_credenciais(self) -> None:
        with (
            patch.object(kucoin_api, "API_KEY", ""),
            patch.object(kucoin_api, "API_SECRET", ""),
            patch.object(kucoin_api, "API_PASSPHRASE", ""),
        ):
            assert kucoin_api._has_keys() is False


# ========================= get_price =========================

class TestGetPrice:
    """Testes para get_price()."""

    def test_retorna_float(self, mock_price_response: MagicMock) -> None:
        with patch("kucoin_api.requests.get", return_value=mock_price_response):
            price = kucoin_api.get_price("BTC-USDT")

        assert isinstance(price, float)
        # média de 87000 e 87100
        assert price == pytest.approx(87050.0)

    def test_retorna_none_em_erro_http(self) -> None:
        resp = MagicMock()
        resp.raise_for_status.side_effect = Exception("HTTP 503")
        with patch("kucoin_api.requests.get", side_effect=Exception("HTTP 503")):
            price = kucoin_api.get_price("BTC-USDT")

        assert price is None

    def test_retorna_none_se_code_invalido(self) -> None:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"code": "400001", "msg": "erro"}
        with patch("kucoin_api.requests.get", return_value=resp):
            price = kucoin_api.get_price("BTC-USDT")

        assert price is None


# ========================= get_orderbook =========================

class TestGetOrderbook:
    """Testes para get_orderbook()."""

    def test_retorna_bids_e_asks(self, mock_orderbook_response: MagicMock) -> None:
        with patch("kucoin_api.requests.get", return_value=mock_orderbook_response):
            ob = kucoin_api.get_orderbook("BTC-USDT", depth=20)

        assert "bids" in ob
        assert "asks" in ob
        assert len(ob["bids"]) > 0

    def test_retorna_dict_vazio_em_erro(self) -> None:
        with patch("kucoin_api.requests.get", side_effect=Exception("timeout")):
            ob = kucoin_api.get_orderbook("BTC-USDT")

        assert isinstance(ob, dict)


# ========================= analyze_orderbook =========================

class TestAnalyzeOrderbook:
    """Testes para analyze_orderbook()."""

    def test_retorna_imbalance_entre_menos1_e_1(self, mock_orderbook_response: MagicMock) -> None:
        with patch("kucoin_api.requests.get", return_value=mock_orderbook_response):
            result = kucoin_api.analyze_orderbook("BTC-USDT")

        assert "imbalance" in result
        assert -1.0 <= result["imbalance"] <= 1.0

    def test_imbalance_positivo_quando_mais_bids(self, mock_orderbook_response: MagicMock) -> None:
        """Bids com volume maior que asks → imbalance positivo."""
        # bids total: 0.5+1.0+2.0=3.5 @ preços altos
        # asks total: 0.3+0.6+1.5=2.4 @ preços baixos
        # imbalance deve ser positivo (mais pressão compradora)
        with patch("kucoin_api.requests.get", return_value=mock_orderbook_response):
            result = kucoin_api.analyze_orderbook("BTC-USDT")

        assert result["imbalance"] >= 0.0

    def test_retorna_estrutura_completa(self, mock_orderbook_response: MagicMock) -> None:
        with patch("kucoin_api.requests.get", return_value=mock_orderbook_response):
            result = kucoin_api.analyze_orderbook("BTC-USDT")

        for key in ("imbalance", "bid_volume", "ask_volume", "spread"):
            assert key in result, f"Chave ausente: {key}"


# ========================= analyze_trade_flow =========================

class TestAnalyzeTradeFlow:
    """Testes para analyze_trade_flow()."""

    def test_flow_bias_entre_menos1_e_1(self, mock_trades_response: MagicMock) -> None:
        with patch("kucoin_api.requests.get", return_value=mock_trades_response):
            result = kucoin_api.analyze_trade_flow("BTC-USDT")

        assert "flow_bias" in result
        assert -1.0 <= result["flow_bias"] <= 1.0

    def test_retorna_estrutura_completa(self, mock_trades_response: MagicMock) -> None:
        with patch("kucoin_api.requests.get", return_value=mock_trades_response):
            result = kucoin_api.analyze_trade_flow("BTC-USDT")

        for key in ("buy_volume", "sell_volume", "flow_bias", "total_volume"):
            assert key in result, f"Chave ausente: {key}"

    def test_retorna_neutro_sem_trades(self) -> None:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"code": "200000", "data": []}
        with patch("kucoin_api.requests.get", return_value=resp):
            result = kucoin_api.analyze_trade_flow("BTC-USDT")

        assert result["flow_bias"] == 0.0


# ========================= rate_limit / retry =========================

class TestRateLimitAndRetry:
    """Testes para decoradores de rate limiting e retry."""

    def test_rate_limit_nao_falha(self) -> None:
        """rate_limit() não deve lançar exceção."""
        kucoin_api._last_request_time = 0.0
        kucoin_api.rate_limit()  # não deve falhar

    def test_retry_sucesso_na_primeira_tentativa(self) -> None:
        chamadas = []

        @kucoin_api.retry_on_failure(max_retries=3, delay=0.0)
        def funcao_ok() -> str:
            chamadas.append(1)
            return "ok"

        resultado = funcao_ok()
        assert resultado == "ok"
        assert len(chamadas) == 1

    def test_retry_tenta_novamente_em_falha(self) -> None:
        chamadas = []

        @kucoin_api.retry_on_failure(max_retries=3, delay=0.0)
        def funcao_falha() -> None:
            chamadas.append(1)
            if len(chamadas) < 3:
                raise ValueError("erro temporário")
            return "recuperado"

        resultado = funcao_falha()
        assert resultado == "recuperado"
        assert len(chamadas) == 3

    def test_retry_relanca_excecao_apos_max(self) -> None:
        """retry_on_failure deve relançar a última exceção após esgotar tentativas."""
        @kucoin_api.retry_on_failure(max_retries=2, delay=0.0)
        def funcao_sempre_falha() -> None:
            raise RuntimeError("falha permanente")

        with pytest.raises(RuntimeError, match="falha permanente"):
            funcao_sempre_falha()
