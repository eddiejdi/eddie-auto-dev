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


def get_target(panel_id: int) -> dict[str, Any]:
    """Retorna o target principal de um painel."""
    panel = get_panel(panel_id)
    targets = panel.get("targets") or []
    if not targets:
        raise AssertionError(f"Painel {panel_id} sem targets")
    return targets[0]


def get_panel_datasource_type(panel_id: int) -> str:
    """Retorna o tipo de datasource configurado no painel."""
    panel = get_panel(panel_id)
    datasource = panel.get("datasource") or {}
    ds_type = datasource.get("type")
    if not ds_type:
        raise AssertionError(f"Painel {panel_id} sem datasource.type")
    return ds_type


def test_recent_decisions_respects_profile_and_time_range() -> None:
    """Painel 71 deve filtrar por profile e pela janela temporal do dashboard."""
    raw_sql = get_raw_sql(71)
    assert "COALESCE(profile, 'default') AS profile" in raw_sql
    assert "('$profile' = '.*' OR profile ~* '^$profile$')" in raw_sql
    assert 'to_timestamp("timestamp") BETWEEN $__timeFrom() AND $__timeTo()' in raw_sql


def test_recent_trades_show_only_api_confirmed_orders_with_exchange_time() -> None:
    """Painel 72 deve exibir trades confirmados pela API com horário real do fill e respeitar profile."""
    raw_sql = get_raw_sql(72)
    assert "WITH RECURSIVE api_trades AS" in raw_sql
    assert "order_id IS NOT NULL" in raw_sql
    assert "COALESCE(metadata->>'source', '') IN ('kucoin_sync', 'kucoin_restore')" in raw_sql
    assert "metadata->'fills'->0->>'createdAt'" in raw_sql
    assert "exchange_time BETWEEN $__timeFrom() AND $__timeTo()" in raw_sql
    assert "('$profile' = '.*' OR profile ~* '^$profile$')" in raw_sql
    assert "COALESCE(profile, 'default') AS profile" in raw_sql
    assert "ROUND(calc_pnl::numeric, 4) AS pnl" in raw_sql
    assert "ROUND(calc_pnl_pct::numeric, 2) AS pnl_pct" in raw_sql
    assert raw_sql.index("side,") < raw_sql.index("ROUND(calc_pnl::numeric, 4) AS pnl")
    assert "profile,\n  side," in raw_sql
    assert "ROUND(calc_pnl::numeric, 4) AS pnl,\n  ROUND(calc_pnl_pct::numeric, 2) AS pnl_pct,\n  price," in raw_sql


def test_trades_per_hour_uses_postgres_api_confirmed_orders() -> None:
    """Painel 42 deve usar PostgreSQL com os mesmos trades confirmados pela API e respeitar profile."""
    panel = get_panel(42)
    target = get_target(42)
    raw_sql = target["rawSql"]
    assert panel["datasource"]["type"] == "grafana-postgresql-datasource"
    assert panel["datasource"]["uid"] == "btc-trading-pg"
    assert "FROM btc.trades" in raw_sql
    assert "symbol = '$coin'" in raw_sql
    assert "order_id IS NOT NULL" in raw_sql
    assert "COALESCE(metadata->>'source', '') IN ('kucoin_sync', 'kucoin_restore')" in raw_sql
    assert "('$profile' = '.*' OR profile ~* '^$profile$')" in raw_sql
    assert "$__timeGroupAlias(exchange_time, '1h')" in raw_sql
    assert "exchange_time BETWEEN $__timeFrom() AND $__timeTo()" in raw_sql


def test_pending_positions_panel_exists_and_uses_open_buys_after_last_sell() -> None:
    """Painel 99 deve listar posições pendentes por perfil com target e plano mais recente."""
    panel = get_panel(99)
    raw_sql = get_raw_sql(99)
    assert panel["title"] == "📍 Posições Pendentes e Indicadores"
    assert panel["type"] == "table"
    assert panel["datasource"]["type"] == "grafana-postgresql-datasource"
    assert "position_summary AS" in raw_sql
    assert "open_trades AS" in raw_sql
    assert "latest_target AS" in raw_sql
    assert "latest_plan AS" in raw_sql
    assert "('$profile' = '.*' OR t.profile ~* '^$profile$')" in raw_sql
    assert "AND (ls.last_sell_ts IS NULL OR t.timestamp > ls.last_sell_ts)" in raw_sql
    assert "'🛒 Abrir menu' AS \"Ação\"" in raw_sql


def test_pending_positions_panel_exposes_manual_sell_link() -> None:
    """Painel 99 deve oferecer atalho de venda manual por linha."""
    panel = get_panel(99)
    overrides = panel["fieldConfig"]["overrides"]
    action_override = next(
        item for item in overrides if item["matcher"]["id"] == "byName" and item["matcher"]["options"] == "Ação"
    )
    links_prop = next(prop for prop in action_override["properties"] if prop["id"] == "links")
    link = links_prop["value"][0]
    assert link["title"] == "Abrir venda manual"
    assert link["targetBlank"] is True
    assert link["url"] == "https://www.rpa4all.com/guardrails/manual-sell?profile=${__data.fields.Profile}"


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


def test_news_panels_use_sql_with_coin_base_and_time_range() -> None:
    """Painéis 91-96 devem filtrar a moeda base derivada do par e a janela temporal."""
    for panel_id in (91, 92, 93, 94, 95, 96):
        raw_sql = get_raw_sql(panel_id)
        assert "coin = SPLIT_PART('$coin', '-', 1)" in raw_sql
        assert "BETWEEN $__timeFrom() AND $__timeTo()" in raw_sql


def test_news_summary_panels_use_table_format_for_single_row_aggregates() -> None:
    """Painéis 91-94 devem usar formato table para evitar No data em agregações únicas."""
    for panel_id in (91, 92, 93, 94):
        target = get_target(panel_id)
        assert target["format"] == "table"
        assert 'NOW() AS "time"' not in target["rawSql"]


def test_top_prometheus_stat_panels_keep_prometheus_datasource() -> None:
    """Painéis 1 e 2 devem continuar em Prometheus porque usam expr."""
    for panel_id in (1, 2):
        assert get_panel_datasource_type(panel_id) == "prometheus"


def test_cumulative_pnl_panel_uses_dashboard_time_range_instead_of_fixed_24h() -> None:
    """Painel 11 deve reconstruir total e período pela janela selecionada no Grafana."""
    panel = get_panel(11)
    targets = panel["targets"]
    assert panel["datasource"]["type"] == "grafana-postgresql-datasource"
    assert panel["datasource"]["uid"] == "btc-trading-pg"
    assert len(targets) == 2
    assert targets[0]["format"] == "time_series"
    assert targets[1]["format"] == "time_series"
    assert "AND to_timestamp(timestamp) < $__timeFrom()" in targets[0]["rawSql"]
    assert "AND to_timestamp(timestamp) BETWEEN $__timeFrom() AND $__timeTo()" in targets[0]["rawSql"]
    assert 'AS "PnL Total"' in targets[0]["rawSql"]
    assert "AND to_timestamp(timestamp) BETWEEN $__timeFrom() AND $__timeTo()" in targets[1]["rawSql"]
    assert 'AS "PnL no período"' in targets[1]["rawSql"]
    assert "cumulative_pnl_24h" not in targets[0]["rawSql"]
    assert "cumulative_pnl_24h" not in targets[1]["rawSql"]


def test_trades_period_panel_uses_dashboard_time_range_instead_of_fixed_24h_metric() -> None:
    """Painel 52 deve usar SQL filtrado pelo range do dashboard."""
    panel = get_panel(52)
    target = get_target(52)
    assert panel["title"] == "📊 Trades no Período"
    assert panel["datasource"]["type"] == "grafana-postgresql-datasource"
    assert target["format"] == "table"
    assert "FROM btc.trades" in target["rawSql"]
    assert "symbol = '$coin'" in target["rawSql"]
    assert "dry_run = false" in target["rawSql"]
    assert "('$profile' = '.*' OR profile ~* '^$profile$')" in target["rawSql"]
    assert "to_timestamp(timestamp) BETWEEN $__timeFrom() AND $__timeTo()" in target["rawSql"]
    assert "trades_24h" not in target["rawSql"]


def test_connectivity_panel_aggregates_selected_profiles_into_single_up_value() -> None:
    """Painel 57 deve consolidar as séries up em um único valor agregado."""
    panel = get_panel(57)
    target = panel["targets"][0]
    assert target["expr"] == 'min(max without(job, instance, coin, exported_coin, exported_profile) ((up{coin="$coin",profile=~"$profile"}) or (up{exported_coin="$coin",profile=~"$profile"})))'


def test_stale_self_heal_panels_are_not_present() -> None:
    """Painéis sem séries ativas não devem permanecer no dashboard."""
    dashboard = load_dashboard()
    titles = {panel.get("title") for panel in dashboard["panels"]}
    assert "🩺 Stall Detection (Last Decision Age)" not in titles
    assert "🔄 Mudanças de Estado (24h)" not in titles


def test_controls_panel_shows_read_only_guidance() -> None:
    """Painel 55 deve explicar que o dashboard público está em modo somente leitura."""
    panel = get_panel(55)
    content = panel["options"]["content"]
    assert panel["type"] == "text"
    assert "modo somente leitura" in content
    assert "REAL e DRY RUN" in content


def test_performance_report_filters_trade_ctes_by_symbol() -> None:
    """Painel 98 deve restringir stats, período e entry pela moeda selecionada."""
    raw_sql = get_raw_sql(98)
    assert raw_sql.count("WHERE symbol = '$coin'") == 5
    assert "FROM btc.trades\n  WHERE symbol = '$coin'\n  AND ('$profile' = '.*' OR profile ~* '^$profile$')" in raw_sql
    assert "period_stats AS" in raw_sql
    assert "AND to_timestamp(timestamp) BETWEEN $__timeFrom() AND $__timeTo()" in raw_sql
    assert "open_position AS" in raw_sql
    assert "price_now AS" in raw_sql


def test_performance_report_labels_period_card_from_dashboard_range() -> None:
    """Painel 98 deve expor PnL e trades do período selecionado, não 24h fixo."""
    panel = get_panel(98)
    content = panel["options"]["content"]
    raw_sql = get_raw_sql(98)
    assert "PnL no período" in content
    assert "{{{pnl_periodo}}}" in content
    assert "{{{trades_periodo}}}" in content
    assert "PnL 24h" not in content
    assert "{{{pnl_24h}}}" not in content
    assert "{{{trades_24h}}}" not in content
    assert "pnl_periodo_color" in raw_sql
    assert "pnl24_color" not in raw_sql


def test_performance_report_clamps_negative_position_and_prefers_live_snapshot_price() -> None:
    """Painel 98 não deve inferir posição short e deve priorizar snapshot live."""
    raw_sql = get_raw_sql(98)
    assert "SELECT GREATEST(COALESCE(" in raw_sql
    assert "SELECT btc_price::numeric\n      FROM btc.exchange_snapshots" in raw_sql
    assert "SELECT price::numeric\n      FROM btc.trades" in raw_sql
    assert raw_sql.index("SELECT btc_price::numeric") < raw_sql.index("SELECT price::numeric")
    assert "CASE WHEN op.net_btc > 0 THEN e.avg_entry_raw ELSE NULL::numeric(10,2) END AS avg_entry" in raw_sql


def test_latest_ai_analysis_panel_has_no_synthetic_fallback() -> None:
    """Painel 89 deve consultar somente dados reais de ai_plans."""
    raw_sql = get_raw_sql(89)
    assert "FROM btc.ai_plans" in raw_sql
    assert "ORDER BY timestamp DESC" in raw_sql
    assert "LIMIT 1" in raw_sql
    assert "WHERE NOT EXISTS" not in raw_sql
    assert "Nenhuma análise encontrada no período selecionado." not in raw_sql


def test_total_deposit_panel_uses_official_kucoin_fiat_deposit_ledger() -> None:
    """Painel 104 deve somar apenas Fiat Deposit em BRL confirmados pela API."""
    raw_sql = get_raw_sql(104)
    panel = get_panel(104)
    assert "FROM btc.exchange_account_ledgers" in raw_sql
    assert "currency = 'BRL'" in raw_sql
    assert "account_type = 'MAIN'" in raw_sql
    assert "direction = 'in'" in raw_sql
    assert "biz_type = 'Fiat Deposit'" in raw_sql
    assert panel["fieldConfig"]["defaults"]["unit"] == "currencyBRL"
