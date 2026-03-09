#!/usr/bin/env python3
"""Testes unitários para scripts/candle_collector.py.

Cobre: ensure_table, fetch_candles, main, parsing de argumentos
e tratamento de erros. Todas as dependências externas (DB, HTTP) são mockadas.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

# Garantir que scripts/ está no sys.path
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from candle_collector import (
    DATABASE_URL,
    KTYPES,
    KUCOIN_BASE,
    SCHEMA,
    SYMBOLS,
    ensure_table,
    fetch_candles,
    main,
)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def mock_conn():
    """Conexão PostgreSQL mockada com cursor context manager."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


@pytest.fixture
def sample_kucoin_response() -> dict:
    """Resposta típica da KuCoin API para candles."""
    now = int(datetime.now(timezone.utc).timestamp())
    return {
        "code": "200000",
        "data": [
            [str(now - 60), "67900.5", "67950.0", "67980.0", "67850.0", "1.234", "83842.67"],
            [str(now - 120), "67850.0", "67900.5", "67910.0", "67800.0", "0.567", "38499.45"],
            [str(now - 180), "67800.0", "67850.0", "67870.0", "67750.0", "0.890", "60382.50"],
        ],
    }


@pytest.fixture
def error_kucoin_response() -> dict:
    """Resposta de erro da KuCoin API."""
    return {
        "code": "400001",
        "msg": "Bad Request",
        "data": [],
    }


# ── Testes ensure_table ──────────────────────────────────────


class TestEnsureTable:
    """Testes para criação/validação da tabela btc.candles."""

    def test_creates_table_with_correct_schema(self, mock_conn: tuple) -> None:
        """Deve criar tabela btc.candles com colunas corretas."""
        conn, cursor = mock_conn
        ensure_table(conn)

        cursor.execute.assert_called_once()
        sql = cursor.execute.call_args[0][0]
        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert f"{SCHEMA}.candles" in sql
        assert "timestamp BIGINT" in sql
        assert "symbol TEXT" in sql
        assert "ktype TEXT" in sql
        assert "UNIQUE(timestamp, symbol, ktype)" in sql

    def test_table_has_ohlcv_columns(self, mock_conn: tuple) -> None:
        """Deve incluir colunas OHLCV."""
        conn, cursor = mock_conn
        ensure_table(conn)

        sql = cursor.execute.call_args[0][0]
        for col in ("open", "high", "low", "close", "volume"):
            assert col in sql, f"Coluna {col} ausente no CREATE TABLE"


# ── Testes fetch_candles ─────────────────────────────────────


class TestFetchCandles:
    """Testes para download e inserção de candles."""

    @patch("candle_collector.requests.get")
    @patch("candle_collector.time.sleep")
    def test_inserts_candles_on_success(
        self,
        mock_sleep: MagicMock,
        mock_get: MagicMock,
        mock_conn: tuple,
        sample_kucoin_response: dict,
    ) -> None:
        """Deve inserir candles quando API retorna sucesso."""
        conn, cursor = mock_conn
        mock_resp = MagicMock()
        mock_resp.json.return_value = sample_kucoin_response
        mock_get.return_value = mock_resp

        result = fetch_candles(conn, "BTC-USDT", "1min", hours=1)

        assert result == 3
        assert cursor.execute.call_count == 3
        mock_sleep.assert_called()  # Rate limit respeitado

    @patch("candle_collector.requests.get")
    @patch("candle_collector.time.sleep")
    def test_uses_correct_kucoin_url(
        self,
        mock_sleep: MagicMock,
        mock_get: MagicMock,
        mock_conn: tuple,
        sample_kucoin_response: dict,
    ) -> None:
        """Deve chamar API KuCoin com parâmetros corretos."""
        conn, cursor = mock_conn
        mock_resp = MagicMock()
        mock_resp.json.return_value = sample_kucoin_response
        mock_get.return_value = mock_resp

        fetch_candles(conn, "ETH-USDT", "15min", hours=1)

        url = mock_get.call_args[0][0]
        assert "symbol=ETH-USDT" in url
        assert "type=15min" in url
        assert KUCOIN_BASE in url

    @patch("candle_collector.requests.get")
    @patch("candle_collector.time.sleep")
    def test_handles_api_error_gracefully(
        self,
        mock_sleep: MagicMock,
        mock_get: MagicMock,
        mock_conn: tuple,
        error_kucoin_response: dict,
    ) -> None:
        """Deve retornar 0 quando API retorna erro."""
        conn, cursor = mock_conn
        mock_resp = MagicMock()
        mock_resp.json.return_value = error_kucoin_response
        mock_get.return_value = mock_resp

        result = fetch_candles(conn, "BTC-USDT", "1min", hours=1)

        assert result == 0

    @patch("candle_collector.requests.get")
    @patch("candle_collector.time.sleep")
    def test_handles_network_error(
        self,
        mock_sleep: MagicMock,
        mock_get: MagicMock,
        mock_conn: tuple,
    ) -> None:
        """Deve tratar exceções de rede sem crash."""
        conn, _ = mock_conn
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError("timeout")

        result = fetch_candles(conn, "BTC-USDT", "1min", hours=1)

        assert result == 0

    @patch("candle_collector.requests.get")
    @patch("candle_collector.time.sleep")
    def test_skips_malformed_candles(
        self,
        mock_sleep: MagicMock,
        mock_get: MagicMock,
        mock_conn: tuple,
    ) -> None:
        """Deve ignorar candles com menos de 7 campos."""
        conn, cursor = mock_conn
        mock_resp = MagicMock()
        now = int(datetime.now(timezone.utc).timestamp())
        mock_resp.json.return_value = {
            "code": "200000",
            "data": [
                [str(now), "100", "101"],  # Apenas 3 campos — inválido
                [str(now - 60), "100", "101", "102", "99", "1.0", "100.0"],  # Válido
            ],
        }
        mock_get.return_value = mock_resp

        result = fetch_candles(conn, "BTC-USDT", "1min", hours=1)

        assert result == 1  # Apenas 1 candle válido

    @patch("candle_collector.requests.get")
    @patch("candle_collector.time.sleep")
    def test_uses_on_conflict_do_nothing(
        self,
        mock_sleep: MagicMock,
        mock_get: MagicMock,
        mock_conn: tuple,
        sample_kucoin_response: dict,
    ) -> None:
        """Deve usar ON CONFLICT DO NOTHING para evitar duplicatas."""
        conn, cursor = mock_conn
        mock_resp = MagicMock()
        mock_resp.json.return_value = sample_kucoin_response
        mock_get.return_value = mock_resp

        fetch_candles(conn, "BTC-USDT", "1min", hours=1)

        sql = cursor.execute.call_args_list[0][0][0]
        assert "ON CONFLICT" in sql
        assert "DO NOTHING" in sql

    @patch("candle_collector.requests.get")
    @patch("candle_collector.time.sleep")
    def test_rate_limits_requests(
        self,
        mock_sleep: MagicMock,
        mock_get: MagicMock,
        mock_conn: tuple,
        sample_kucoin_response: dict,
    ) -> None:
        """Deve aplicar rate limit de 0.2s entre requests."""
        conn, cursor = mock_conn
        mock_resp = MagicMock()
        mock_resp.json.return_value = sample_kucoin_response
        mock_get.return_value = mock_resp

        fetch_candles(conn, "BTC-USDT", "1min", hours=1)

        mock_sleep.assert_called_with(0.2)

    @patch("candle_collector.requests.get")
    @patch("candle_collector.time.sleep")
    def test_correct_field_mapping(
        self,
        mock_sleep: MagicMock,
        mock_get: MagicMock,
        mock_conn: tuple,
    ) -> None:
        """Deve mapear campos da KuCoin corretamente (index 1=open, 2=close, 3=high, 4=low, 5=vol)."""
        conn, cursor = mock_conn
        now = int(datetime.now(timezone.utc).timestamp())
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "code": "200000",
            "data": [
                [str(now), "100.0", "105.0", "110.0", "95.0", "50.0", "5000.0"],
            ],
        }
        mock_get.return_value = mock_resp

        fetch_candles(conn, "BTC-USDT", "1min", hours=1)

        # Verificar parâmetros do INSERT
        params = cursor.execute.call_args[0][1]
        # (timestamp, symbol, ktype, open, high, low, close, volume)
        assert params[0] == now  # timestamp
        assert params[1] == "BTC-USDT"  # symbol
        assert params[2] == "1min"  # ktype
        assert params[3] == 100.0  # open (index 1)
        assert params[4] == 110.0  # high (index 3)
        assert params[5] == 95.0  # low (index 4)
        assert params[6] == 105.0  # close (index 2)
        assert params[7] == 50.0  # volume (index 5)

    @patch("candle_collector.requests.get")
    @patch("candle_collector.time.sleep")
    def test_windows_for_1min_candles(
        self,
        mock_sleep: MagicMock,
        mock_get: MagicMock,
        mock_conn: tuple,
    ) -> None:
        """Deve usar janela de 24h para candles de 1min."""
        conn, cursor = mock_conn
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": "200000", "data": []}
        mock_get.return_value = mock_resp

        # 48h deve gerar 2 requests para 1min (janela 24h)
        fetch_candles(conn, "BTC-USDT", "1min", hours=48)

        assert mock_get.call_count == 2

    @patch("candle_collector.requests.get")
    @patch("candle_collector.time.sleep")
    def test_windows_for_15min_candles(
        self,
        mock_sleep: MagicMock,
        mock_get: MagicMock,
        mock_conn: tuple,
    ) -> None:
        """Deve usar janela de 72h para candles de 15min."""
        conn, cursor = mock_conn
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": "200000", "data": []}
        mock_get.return_value = mock_resp

        # 144h deve gerar 2 requests para 15min (janela 72h)
        fetch_candles(conn, "BTC-USDT", "15min", hours=144)

        assert mock_get.call_count == 2

    @patch("candle_collector.requests.get")
    @patch("candle_collector.time.sleep")
    def test_empty_data_returns_zero(
        self,
        mock_sleep: MagicMock,
        mock_get: MagicMock,
        mock_conn: tuple,
    ) -> None:
        """Deve retornar 0 quando não há candles."""
        conn, cursor = mock_conn
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": "200000", "data": []}
        mock_get.return_value = mock_resp

        result = fetch_candles(conn, "BTC-USDT", "1min", hours=1)

        assert result == 0


# ── Testes main() ────────────────────────────────────────────


class TestMain:
    """Testes para a função main() e parsing de argumentos."""

    @patch("candle_collector.psycopg2.connect")
    @patch("candle_collector.fetch_candles", return_value=10)
    @patch("candle_collector.ensure_table")
    def test_main_default_args(
        self,
        mock_ensure: MagicMock,
        mock_fetch: MagicMock,
        mock_connect: MagicMock,
    ) -> None:
        """Deve usar valores padrão quando sem argumentos."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        with patch("sys.argv", ["candle_collector.py"]):
            result = main()

        assert result == 0
        mock_connect.assert_called_once_with(DATABASE_URL)
        mock_ensure.assert_called_once()
        # 6 symbols × 2 ktypes = 12 chamadas
        assert mock_fetch.call_count == len(SYMBOLS) * len(KTYPES)
        mock_conn.close.assert_called_once()

    @patch("candle_collector.psycopg2.connect")
    @patch("candle_collector.fetch_candles", return_value=5)
    @patch("candle_collector.ensure_table")
    def test_main_custom_hours(
        self,
        mock_ensure: MagicMock,
        mock_fetch: MagicMock,
        mock_connect: MagicMock,
    ) -> None:
        """Deve respeitar --hours."""
        mock_connect.return_value = MagicMock()

        with patch("sys.argv", ["candle_collector.py", "--hours", "12"]):
            main()

        # Verificar que todas as chamadas usaram hours=12
        for c in mock_fetch.call_args_list:
            assert c[1].get("hours", c[0][3] if len(c[0]) > 3 else None) == 12 or \
                   c.kwargs.get("hours") == 12 or c[0][3] == 12

    @patch("candle_collector.psycopg2.connect")
    @patch("candle_collector.fetch_candles", return_value=100)
    @patch("candle_collector.ensure_table")
    def test_main_backfill_overrides_hours(
        self,
        mock_ensure: MagicMock,
        mock_fetch: MagicMock,
        mock_connect: MagicMock,
    ) -> None:
        """--backfill deve ter prioridade sobre --hours."""
        mock_connect.return_value = MagicMock()

        with patch("sys.argv", ["candle_collector.py", "--backfill", "168", "--hours", "2"]):
            main()

        # Backfill=168 deve ser usado
        for c in mock_fetch.call_args_list:
            hours_arg = c[0][3] if len(c[0]) > 3 else c.kwargs.get("hours")
            assert hours_arg == 168

    @patch("candle_collector.psycopg2.connect")
    @patch("candle_collector.fetch_candles", return_value=0)
    @patch("candle_collector.ensure_table")
    def test_main_custom_symbols(
        self,
        mock_ensure: MagicMock,
        mock_fetch: MagicMock,
        mock_connect: MagicMock,
    ) -> None:
        """Deve filtrar por --symbols."""
        mock_connect.return_value = MagicMock()

        with patch("sys.argv", ["candle_collector.py", "--symbols", "BTC-USDT", "ETH-USDT"]):
            main()

        # 2 symbols × 2 ktypes = 4 chamadas
        assert mock_fetch.call_count == 4
        symbols_called = [c[0][1] for c in mock_fetch.call_args_list]
        assert "BTC-USDT" in symbols_called
        assert "ETH-USDT" in symbols_called

    @patch("candle_collector.psycopg2.connect")
    def test_main_db_connection_failure(self, mock_connect: MagicMock) -> None:
        """Deve retornar 1 quando falha a conexão com PostgreSQL."""
        mock_connect.side_effect = Exception("Connection refused")

        with patch("sys.argv", ["candle_collector.py"]):
            result = main()

        assert result == 1

    @patch("candle_collector.psycopg2.connect")
    @patch("candle_collector.fetch_candles", return_value=0)
    @patch("candle_collector.ensure_table")
    def test_main_sets_autocommit(
        self,
        mock_ensure: MagicMock,
        mock_fetch: MagicMock,
        mock_connect: MagicMock,
    ) -> None:
        """Deve definir autocommit=True na conexão."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        with patch("sys.argv", ["candle_collector.py"]):
            main()

        assert mock_conn.autocommit is True


# ── Testes de configuração ───────────────────────────────────


class TestConfig:
    """Testes para constantes e configuração."""

    def test_default_symbols(self) -> None:
        """Deve ter 6 pares de trading padrão."""
        assert len(SYMBOLS) == 6
        assert "BTC-USDT" in SYMBOLS

    def test_default_ktypes(self) -> None:
        """Deve ter 1min e 15min como padrão."""
        assert KTYPES == ["1min", "15min"]

    def test_database_url_points_to_btc_trading(self) -> None:
        """DATABASE_URL padrão deve apontar para btc_trading, não postgres."""
        assert "btc_trading" in DATABASE_URL
        assert "5433" in DATABASE_URL

    def test_schema_is_btc(self) -> None:
        """Schema deve ser 'btc'."""
        assert SCHEMA == "btc"

    def test_kucoin_base_url(self) -> None:
        """Base URL deve ser KuCoin API."""
        assert KUCOIN_BASE == "https://api.kucoin.com"
