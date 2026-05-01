"""Testes para garantir fallback de conversao BRL no dashboard Storj."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_storj_dashboard_brl_panels_have_usdbrl_fallback() -> None:
    """Valida fallback para cotacao USD/BRL nos dois paineis finais de conversao."""
    dashboard_path = ROOT / "grafana/dashboards/storj-node-dashboard.json"
    dashboard = json.loads(dashboard_path.read_text())

    panels = {panel.get("id"): panel for panel in dashboard.get("panels", [])}

    panel_eth_brl = panels[40]
    expr_eth_brl = panel_eth_brl["targets"][0]["expr"]
    assert "vector(4.9544)" in expr_eth_brl
    assert "USDT-BRL|USD-BRL|USDBRL" in expr_eth_brl

    panel_gain_brl = panels[41]
    expr_gain_brl = panel_gain_brl["targets"][0]["expr"]
    assert "vector(4.9544)" in expr_gain_brl
    assert "storj_payout_current_month_cents" in expr_gain_brl