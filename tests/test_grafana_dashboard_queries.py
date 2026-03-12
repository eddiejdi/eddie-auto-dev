"""Testes de regressão para queries críticas do dashboard Grafana."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DASHBOARD_PATH = Path(__file__).resolve().parent.parent / "grafana" / "btc_trading_dashboard_v3_prometheus.json"


def load_dashboard() -> dict[str, Any]:
    """Carrega o JSON do dashboard de trading."""
    return json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))


def get_panel(panel_id: int) -> dict[str, Any]:
    """Retorna um painel pelo id."""
    dashboard = load_dashboard()
    for panel in dashboard["panels"]:
        if panel.get("id") == panel_id:
            return panel
    raise AssertionError(f"Painel {panel_id} não encontrado")


def get_raw_sql(panel_id: int) -> str:
    """Retorna a query SQL principal de um painel."""
    panel = get_panel(panel_id)
    targets = panel.get("targets") or []
    if not targets:
        raise AssertionError(f"Painel {panel_id} sem targets")
    raw_sql = targets[0].get("rawSql")
    if not raw_sql:
        raise AssertionError(f"Painel {panel_id} sem rawSql")
    return raw_sql


def test_recent_decisions_respects_profile_and_time_range() -> None:
    """Painel 71 deve filtrar por profile e pela janela temporal do dashboard."""
    raw_sql = get_raw_sql(71)
    assert "COALESCE(profile, 'default') AS profile" in raw_sql
    assert "('$profile' = '.*' OR profile ~* '^$profile$')" in raw_sql
    assert 'to_timestamp("timestamp") BETWEEN $__timeFrom() AND $__timeTo()' in raw_sql


def test_recent_trades_respects_profile_and_time_range() -> None:
    """Painel 72 deve filtrar por profile e pela janela temporal do dashboard."""
    raw_sql = get_raw_sql(72)
    assert "COALESCE(profile, 'default') AS profile" in raw_sql
    assert "('$profile' = '.*' OR profile ~* '^$profile$')" in raw_sql
    assert "created_at BETWEEN $__timeFrom() AND $__timeTo()" in raw_sql


def test_ai_panels_respect_coin_profile_and_time_range() -> None:
    """Painéis 87, 88 e 89 devem usar a moeda, o profile e a janela temporal."""
    for panel_id in (87, 88, 89):
        raw_sql = get_raw_sql(panel_id)
        assert "symbol = '$coin'" in raw_sql
        assert "('$profile' = '.*' OR profile ~* '^$profile$')" in raw_sql
        assert "BETWEEN $__timeFrom() AND $__timeTo()" in raw_sql
        assert "symbol = 'BTC-USDT'" not in raw_sql


def test_news_table_respects_coin_and_time_range() -> None:
    """Painel 96 deve filtrar a moeda derivada do par e a janela temporal."""
    raw_sql = get_raw_sql(96)
    assert "coin = SPLIT_PART('$coin', '-', 1)" in raw_sql
    assert "timestamp BETWEEN $__timeFrom() AND $__timeTo()" in raw_sql


def get_prometheus_exprs(panel_id: int) -> list[str]:
    """Retorna todas as expressões Prometheus de um painel."""
    panel = get_panel(panel_id)
    return [t.get("expr", "") for t in (panel.get("targets") or [])]


def test_news_panels_filter_by_coin() -> None:
    """Painéis 91-95 devem usar label_replace para filtrar pelo coin selecionado."""
    EXPECTED_METRICS = {
        91: ["btc_news_sentiment"],
        92: ["btc_news_confidence"],
        93: ["btc_news_bullish_pct", "btc_news_bearish_pct"],
        94: ["btc_news_count"],
        95: ["btc_news_sentiment", "btc_news_latest_sentiment"],
    }
    for panel_id, metrics in EXPECTED_METRICS.items():
        exprs = get_prometheus_exprs(panel_id)
        for i, metric in enumerate(metrics):
            expr = exprs[i] if i < len(exprs) else ""
            assert f"label_replace({metric}" in expr, (
                f"Painel {panel_id}: expressão '{expr}' não usa label_replace"
            )
            assert 'coin=~"$coin"' in expr, (
                f"Painel {panel_id}: expressão '{expr}' não filtra por $coin"
            )
            # Não deve usar a métrica global (sem filtro de coin)
            assert expr.strip() != metric, (
                f"Painel {panel_id}: expressão não pode ser métrica global sem filtro"
            )


def test_performance_report_filters_trade_ctes_by_symbol() -> None:
    """Painel 98 deve restringir stats, pnl24 e entry pela moeda selecionada."""
    raw_sql = get_raw_sql(98)
    assert raw_sql.count("WHERE symbol = '$coin'") == 3
    assert "FROM btc.trades\n  WHERE symbol = '$coin'\n  AND ('$profile' = '.*' OR profile ~* '^$profile$')" in raw_sql
    assert "FROM btc.trades WHERE symbol = '$coin' AND ('$profile' = '.*' OR profile ~* '^$profile$') AND to_timestamp(timestamp) >= NOW() - interval '24 hours'" in raw_sql
