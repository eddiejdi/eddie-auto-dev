"""Regressoes do dashboard operacional da Conube."""

from __future__ import annotations

import json
from pathlib import Path


DASHBOARD_PATH = Path(__file__).resolve().parent.parent / "grafana" / "dashboards" / "conube-operational.json"


def load_dashboard() -> dict:
    return json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))


def get_panel(panel_id: int) -> dict:
    for panel in load_dashboard()["panels"]:
        if panel.get("id") == panel_id:
            return panel
    raise AssertionError(f"Painel {panel_id} nao encontrado")


def test_stat_panels_use_instant_vector_queries_with_prometheus() -> None:
    for panel_id, metric in (
        (1, "conube_exporter_up"),
        (2, "conube_open_periods_total"),
        (3, "conube_pending_items_total"),
        (4, "conube_overdue_items_total"),
        (5, "conube_certificate_expired"),
        (6, "conube_billing_blocked"),
        (10, "conube_client_actionable_items_total"),
        (11, "conube_accountant_owned_items_total"),
    ):
        panel = get_panel(panel_id)
        target = panel["targets"][0]
        assert panel["datasource"]["type"] == "prometheus"
        assert target["instant"] is True
        assert target["format"] == "time_series"
        assert target["expr"] == f"max({metric})"
        assert panel["options"]["reduceOptions"]["calcs"] == ["lastNotNull"]
        assert panel["options"]["reduceOptions"]["values"] is False


def test_risk_panel_uses_vector_queries_instead_of_scalars() -> None:
    panel = get_panel(7)
    exprs = [target["expr"] for target in panel["targets"]]
    assert panel["type"] == "bargauge"
    assert exprs == [
        "max(conube_open_periods_total)",
        "max(conube_pending_items_total)",
        "max(conube_overdue_items_total)",
    ]


def test_dashboard_has_action_links_for_remediation() -> None:
    dashboard = load_dashboard()
    dashboard_links = dashboard.get("links") or []
    assert any("actions/run-remediation" in (link.get("url") or "") for link in dashboard_links)

    periods_panel = get_panel(2)
    client_panel = get_panel(10)
    overdue_panel = get_panel(4)
    for panel in (periods_panel, client_panel, overdue_panel):
        links = panel.get("links") or []
        assert any("actions/run-remediation" in (link.get("url") or "") for link in links)
