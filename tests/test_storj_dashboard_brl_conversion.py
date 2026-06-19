"""Testes para garantir fallback de conversao BRL no dashboard Storj."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATHS = (
    ROOT / "grafana/dashboards/storj-node-dashboard.json",
    ROOT / "grafana/dashboards/storj-node-monitor.json",
)


def _load_dashboard(path: Path) -> dict:
    return json.loads(path.read_text())


def test_storj_dashboard_brl_panels_have_usdbrl_fallback() -> None:
    """Valida fallback para cotacao USD/BRL nos dois paineis finais de conversao."""
    for dashboard_path in DASHBOARD_PATHS:
        dashboard = _load_dashboard(dashboard_path)
        panels = {panel.get("id"): panel for panel in dashboard.get("panels", [])}

        panel_eth_brl = panels[40]
        expr_eth_brl = panel_eth_brl["targets"][0]["expr"]
        assert "vector(4.9544)" in expr_eth_brl
        assert "USDT-BRL|USD-BRL|USDBRL" in expr_eth_brl

        panel_gain_brl = panels[41]
        expr_gain_brl = panel_gain_brl["targets"][0]["expr"]
        assert "vector(4.9544)" in expr_gain_brl
        assert "storj_payout_current_gross_total_cents" in expr_gain_brl

        panel_held_schedule = panels[55]
        for target in panel_held_schedule["targets"]:
            expr = target["expr"]
            assert "vector(4.9544)" in expr, (
                f"{dashboard_path.name}: painel 55 refId={target['refId']} sem fallback vector() — "
                "scalar() retorna NaN quando crypto_price USD-BRL não existe"
            )
            assert "storj_payout_current_gross_total_cents" in expr

        panel_brl_breakdown = panels[56]
        for target in panel_brl_breakdown["targets"]:
            assert "vector(4.9544)" in target["expr"]

        panel_report_brl = panels[57]
        for target in panel_report_brl["targets"]:
            assert "vector(4.9544)" in target["expr"]


def test_storj_dashboard_uses_raw_usd_metrics_without_dividing_by_100() -> None:
    """Painéis em USD devem refletir a API real do Storj sem escala adicional incorreta."""
    for dashboard_path in DASHBOARD_PATHS:
        dashboard = _load_dashboard(dashboard_path)
        panels = {panel.get("id"): panel for panel in dashboard.get("panels", [])}

        for panel_id in (5, 6, 21, 50, 51, 52, 54):
            for target in panels[panel_id]["targets"]:
                assert "/ 100" not in target["expr"], (
                    f"{dashboard_path.name}: painel {panel_id} ainda divide payout do Storj por 100, "
                    "mas o exporter já expõe esses valores diretamente em USD."
                )

        panel_21_exprs = [target["expr"] for target in panels[21]["targets"]]
        assert any("storj_payout_current_repair_audit_cents" in expr for expr in panel_21_exprs)


def test_storj_dashboard_source_and_monitor_artifacts_match() -> None:
    """Os dois artefatos locais do dashboard Storj devem permanecer sincronizados."""
    source = _load_dashboard(ROOT / "grafana/dashboards/storj-node-dashboard.json")
    monitor = _load_dashboard(ROOT / "grafana/dashboards/storj-node-monitor.json")
    assert source == monitor
