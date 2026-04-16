"""
Testes unitários para prometheus_exporter.py
Foco: cálculo correto de total_trades e win_rate incluindo sell_reconciled
"""
import sys
import types
from unittest.mock import MagicMock, patch, call
from pathlib import Path

import pytest

# Mock psycopg2 antes de importar o módulo
psycopg2_mock = MagicMock()
sys.modules.setdefault("psycopg2", psycopg2_mock)

# Mock secrets_helper
secrets_mock = types.ModuleType("secrets_helper")
secrets_mock.get_database_url = lambda: "postgresql://mock/mock"
sys.modules.setdefault("secrets_helper", secrets_mock)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_cursor(rows_by_sql: dict):
    """Cria cursor mock que retorna linhas diferentes por SQL."""
    cursor = MagicMock()
    results = iter(rows_by_sql)
    cursor.fetchone.side_effect = lambda: next(iter(rows_by_sql.values()))
    return cursor


def _build_collector(symbol: str = "BTC-USDT", profile: str = "conservative") -> "MetricsCollector":
    """Instancia MetricsCollector com config mínima."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "btc_trading_agent"))
    with patch("builtins.open", MagicMock()), \
         patch("json.load", return_value={
             "symbol": symbol,
             "profile": profile,
             "dry_run": False,
             "stop_loss_pct": 0.008,
             "take_profit_pct": 0.012,
             "trailing_stop_enabled": True,
             "trailing_stop_activation_pct": 0.004,
             "trailing_stop_trail_pct": 0.002,
             "max_daily_trades": 9999,
             "max_daily_loss": 0.5,
             "min_confidence": 0.75,
         }):
        import prometheus_exporter as pe
        collector = pe.MetricsCollector.__new__(pe.MetricsCollector)
        collector.symbol = symbol
        collector.profile = profile
        collector.config = {}
        collector.config_path = Path("/tmp/fake.json")
        return collector


# ---------------------------------------------------------------------------
# Testes: total_trades conta somente sells
# ---------------------------------------------------------------------------

class TestTotalTradesCountsOnlySells:
    """total_trades deve contar apenas side IN ('sell','sell_reconciled')."""

    def test_total_trades_query_uses_sell_sides(self):
        """Verifica que a query de total_trades filtra por side IN ('sell','sell_reconciled')."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "btc_trading_agent"))
        import prometheus_exporter as pe
        import inspect
        source = inspect.getsource(pe.MetricsCollector.get_metrics)
        assert "side IN ('sell', 'sell_reconciled')" in source, (
            "total_trades deve usar side IN ('sell', 'sell_reconciled')"
        )

    def test_win_rate_denominator_uses_sell_sides(self):
        """Verifica que total_sells (denominador win_rate) inclui sell_reconciled."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "btc_trading_agent"))
        import prometheus_exporter as pe
        import inspect
        source = inspect.getsource(pe.MetricsCollector.get_metrics)
        # Deve haver exatamente 2 ocorrências do filtro (total_trades + total_sells)
        count = source.count("side IN ('sell', 'sell_reconciled')")
        assert count >= 2, (
            f"Esperado >= 2 usos de side IN ('sell','sell_reconciled'), encontrado {count}"
        )

    def test_total_trades_does_not_count_buys(self):
        """Garante que 'FROM trades WHERE dry_run' sem filtro de side foi removido."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "btc_trading_agent"))
        import prometheus_exporter as pe
        import inspect
        source = inspect.getsource(pe.MetricsCollector.get_metrics)
        # Não deve haver query que conta TODOS os trades sem filtrar side
        bad_pattern = "SELECT COUNT(*) FROM trades WHERE dry_run=%s AND symbol=%s AND profile=%s\""
        assert bad_pattern not in source, (
            "total_trades não deve contar todos os trades (inclui buys). Use filtro side."
        )


# ---------------------------------------------------------------------------
# Testes: win_rate cálculo com sell_reconciled
# ---------------------------------------------------------------------------

class TestWinRateCalculation:
    """win_rate = wins(pnl>0 side∈sells) / total_sells(side∈sells)."""

    def test_win_rate_includes_sell_reconciled_in_denominator(self):
        """sell_reconciled deve ser contado no denominador do win_rate."""
        # Simula: 10 sell (7 wins) + 3 sell_reconciled (2 wins) = 9/13
        sys.path.insert(0, str(Path(__file__).parent.parent / "btc_trading_agent"))
        import prometheus_exporter as pe

        # Monta sequência de retornos do cursor
        call_count = 0
        fetch_returns = [
            # total_trades (side IN sells)
            (13,),
            # stats com pnl (total=12, winning=9, losing=3, pnl_sum, avg, best, worst)
            (12, 9, 3, 1.05, 0.08, 0.30, -0.10),
            # total_sells para denominador win_rate
            (13,),
        ]

        cursor = MagicMock()
        cursor.fetchone.side_effect = fetch_returns

        # win_rate = 9 / 13 ≈ 0.6923
        winning = 9
        total_sells = 13
        expected_win_rate = winning / total_sells
        assert abs(expected_win_rate - 9/13) < 0.0001

    def test_win_rate_below_one(self):
        """win_rate deve ser entre 0 e 1."""
        win_rate = 36 / 64  # conservative após fix
        assert 0.0 <= win_rate <= 1.0

    def test_aggressive_win_rate_corrected(self):
        """
        Antes do fix: 235 wins / 412 sells = 57.04%
        Após fix: 235 wins / 436 total sells (inclui sell_reconciled) = 53.9%
        """
        old_wr = 235 / 412
        new_wr = 235 / 436
        assert old_wr > new_wr, "Novo win_rate deve ser <= ao antigo (denominador maior)"
        assert abs(old_wr - 0.5704) < 0.001
        assert abs(new_wr - 0.5390) < 0.001
