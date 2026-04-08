"""Testes para _get_initial_capital — remoção de hardcodes no prometheus_exporter."""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock dependências externas antes de importar o módulo
sys.modules.setdefault("psycopg2", MagicMock())
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5433/test")

# Adicionar o diretório do módulo ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "btc_trading_agent"))

from prometheus_exporter import MetricsCollector  # noqa: E402


@pytest.fixture
def collector():
    """Cria um MetricsCollector com DSN fake (sem conexão real)."""
    with patch("prometheus_exporter.psycopg2") as mock_pg:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_pg.connect.return_value = mock_conn
        mc = MetricsCollector(dsn="dbname=test", symbol="BTC-USDT", profile="aggressive")
        yield mc


class TestGetInitialCapital:
    """Testes para MetricsCollector._get_initial_capital."""

    def test_reads_from_config_json(self, collector: MagicMock) -> None:
        """Quando config JSON contém initial_capital, usa esse valor."""
        with patch("prometheus_exporter.load_config", return_value={"initial_capital": 250.0}):
            assert collector._get_initial_capital() == 250.0

    def test_reads_from_db_when_config_missing(self, collector: MagicMock) -> None:
        """Quando config não tem initial_capital, busca no profile_config (PG)."""
        with patch("prometheus_exporter.load_config", return_value={}):
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = (500.0,)
            mock_conn.cursor.return_value = mock_cur
            with patch.object(collector, "_get_conn", return_value=mock_conn):
                assert collector._get_initial_capital() == 500.0
                mock_cur.execute.assert_called_once()

    def test_fallback_when_both_unavailable(self, collector: MagicMock) -> None:
        """Quando config vazio e DB falha, retorna fallback 100.0."""
        with patch("prometheus_exporter.load_config", return_value={}):
            with patch.object(collector, "_get_conn", side_effect=Exception("DB down")):
                assert collector._get_initial_capital() == 100.0

    def test_config_value_zero_is_valid(self, collector: MagicMock) -> None:
        """Zero no config é um valor válido (não deve cair no fallback)."""
        with patch("prometheus_exporter.load_config", return_value={"initial_capital": 0}):
            assert collector._get_initial_capital() == 0.0

    def test_config_takes_priority_over_db(self, collector: MagicMock) -> None:
        """Config JSON tem prioridade sobre profile_config no PG."""
        with patch("prometheus_exporter.load_config", return_value={"initial_capital": 300}):
            # DB deve NÃO ser consultado
            mock_conn = MagicMock()
            with patch.object(collector, "_get_conn", return_value=mock_conn) as mock_get:
                result = collector._get_initial_capital()
                assert result == 300.0
                mock_get.assert_not_called()

    def test_db_returns_none_falls_to_fallback(self, collector: MagicMock) -> None:
        """Quando profile não existe no DB, retorna fallback."""
        with patch("prometheus_exporter.load_config", return_value={}):
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = None
            mock_conn.cursor.return_value = mock_cur
            with patch.object(collector, "_get_conn", return_value=mock_conn):
                assert collector._get_initial_capital() == 100.0
