"""
Testes unitários para prometheus_exporter.py
Foco: cálculo correto de total_trades e win_rate incluindo sell_reconciled
"""
import sys
import threading
import time
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


class TestEquityDailyChanges:
    """Cards Hoje/Ontem devem usar a mesma base completa do calendário."""

    def test_daily_changes_use_balance_snapshots_and_compute_open_close(self):
        collector = _build_collector()

        cursor = MagicMock()
        cursor.fetchone.return_value = (100.0, 110.0, 200.0, 190.0)

        conn = MagicMock()
        conn.cursor.return_value = cursor
        collector._get_conn = MagicMock(return_value=conn)

        result = collector._get_equity_daily_changes()

        sql = cursor.execute.call_args[0][0]
        assert "btc.exchange_balance_snapshots" in sql
        assert "COUNT(DISTINCT account_type) >= 3" in sql
        assert "btc.exchange_snapshots" not in sql
        assert result["equity_change_today_usdt"] == 10.0
        assert result["equity_change_today_pct"] == 10.0
        assert result["equity_change_yesterday_usdt"] == -10.0
        assert result["equity_change_yesterday_pct"] == -5.0


# ---------------------------------------------------------------------------
# Testes: TrainingDatabase compartilhada (um pool por processo, não por scrape)
# ---------------------------------------------------------------------------

@pytest.fixture
def pe_module():
    """prometheus_exporter com o singleton de TrainingDatabase zerado."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "btc_trading_agent"))
    import prometheus_exporter as pe
    saved = pe._TRAINING_DB
    pe._TRAINING_DB = None
    try:
        yield pe
    finally:
        pe._TRAINING_DB = saved


def _fake_training_db_module(cls):
    """Módulo training_db falso, para não construir pool psycopg2 de verdade."""
    mod = types.ModuleType("training_db")
    mod.TrainingDatabase = cls
    return mod


class TestSharedTrainingDatabase:
    """get_training_db() deve reaproveitar a instância entre scrapes."""

    def test_constructs_only_once_across_calls(self, pe_module):
        """Chamadas repetidas retornam a mesma instância e não abrem novo pool."""
        constructions = []

        class FakeDB:
            def __init__(self):
                constructions.append(self)

        with patch.dict(sys.modules, {"training_db": _fake_training_db_module(FakeDB)}):
            first = pe_module.get_training_db()
            second = pe_module.get_training_db()
            third = pe_module.get_training_db()

        assert first is second is third
        assert len(constructions) == 1, (
            f"TrainingDatabase deve ser construída 1x, foi {len(constructions)}x "
            "(um ThreadedConnectionPool vazando por scrape)"
        )

    def test_concurrent_scrapes_share_one_instance(self, pe_module):
        """ThreadingHTTPServer: threads simultâneas não podem criar pools extras."""
        constructions = []
        barrier = threading.Barrier(8)

        class SlowFakeDB:
            def __init__(self):
                # Amplia a janela de corrida entre os threads
                time.sleep(0.01)
                constructions.append(self)

        results = []
        results_lock = threading.Lock()

        def worker():
            barrier.wait()
            db = pe_module.get_training_db()
            with results_lock:
                results.append(db)

        with patch.dict(sys.modules, {"training_db": _fake_training_db_module(SlowFakeDB)}):
            threads = [threading.Thread(target=worker) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert len(constructions) == 1, (
            f"8 scrapes concorrentes construíram {len(constructions)} instâncias"
        )
        assert len(results) == 8
        assert all(r is results[0] for r in results)

    def test_construction_failure_is_not_cached(self, pe_module):
        """DB fora do ar: falha propaga e o próximo scrape tenta de novo."""
        attempts = []

        class FlakyDB:
            def __init__(self):
                attempts.append(1)
                if len(attempts) == 1:
                    raise RuntimeError("db down")

        with patch.dict(sys.modules, {"training_db": _fake_training_db_module(FlakyDB)}):
            with pytest.raises(RuntimeError):
                pe_module.get_training_db()
            assert pe_module._TRAINING_DB is None
            db = pe_module.get_training_db()

        assert db is not None
        assert len(attempts) == 2

    def test_metrics_snapshot_uses_shared_instance(self, pe_module):
        """A métrica de conversão deve ler pelo singleton, não construir por scrape."""
        import inspect
        source = inspect.getsource(pe_module.PrometheusHandler.send_metrics)
        assert "get_training_db().conversion_metrics_snapshot(" in source, (
            "send_metrics deve usar get_training_db()"
        )
        assert "TrainingDatabase()" not in source, (
            "send_metrics não pode construir TrainingDatabase por scrape "
            "(cada construção abre um ThreadedConnectionPool que nunca é fechado)"
        )


class TestSubDollarPricePrecision:
    """Regressão do achado real de produção (2026-08-01, DOGE-USDT shadow
    slot #3817): métricas de preço formatadas com '{v:.2f}' truncam
    qualquer ativo sub-$1 (DOGE, XRP, ADA...) em degraus de 1 centavo —
    ~14% do preço de um ativo de $0.07 — fazendo um target_sell calculado
    corretamente acima da entrada aparecer como se estivesse abaixo dela
    no dashboard/Prometheus. Preço precisa de 8 casas, como já usado em
    btc_trading_open_position_btc."""

    def test_price_scale_metrics_use_eight_decimal_precision(self, pe_module):
        import inspect
        source = inspect.getsource(pe_module)
        for metric_name in (
            "btc_trading_avg_entry_price",
            "btc_trade_window_entry_low",
            "btc_trade_window_entry_high",
            "btc_trade_window_target_sell",
        ):
            idx = source.index(f"'{metric_name}'") if f"'{metric_name}'" in source else source.index(f'"{metric_name}"')
            snippet = source[idx:idx + 200]
            assert "{v:.2f}" not in snippet.split("\n")[0], (
                f"{metric_name} não pode usar precisão de 2 casas — "
                "trunca preços sub-$1 até parecerem abaixo da entrada"
            )
            assert "{v:.8f}" in snippet, f"{metric_name} deve usar {{v:.8f}}"


class TestMarketRagFileSymbolScoping:
    """Regressão do achado real de produção (2026-08-01): regime_adjustments
    e trade_window eram lidos por um caminho scoped só por profile
    (shadow/aggressive/conservative), compartilhado por todos os símbolos
    que dividem o mesmo profile (BTC/ETH/SOL/DOGE em "shadow" liam o mesmo
    arquivo) — o exporter da DOGE-USDT shadow chegou a expor
    target_sell=63015 (preço de BTC). Mesma classe de bug do index.pkl
    legado, nunca corrigida nos arquivos irmãos até agora."""

    def test_send_metrics_reads_symbol_scoped_regime_adjustments_first(self, pe_module):
        import inspect
        source = inspect.getsource(pe_module.PrometheusHandler.send_metrics)
        assert 'f"regime_adjustments_{_sym}{_profile_suffix}.json"' in source or \
            "regime_adjustments_{_sym}" in source, (
                "send_metrics precisa preferir o arquivo scoped por symbol+profile "
                "antes do fallback só-por-profile"
            )

    def test_send_metrics_reads_symbol_scoped_trade_window_first(self, pe_module):
        import inspect
        source = inspect.getsource(pe_module.PrometheusHandler.send_metrics)
        assert "trade_window_{_sym}" in source, (
            "send_metrics precisa preferir o trade_window scoped por symbol+profile "
            "antes do fallback só-por-profile"
        )
