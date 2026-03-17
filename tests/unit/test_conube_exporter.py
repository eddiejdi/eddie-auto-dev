from __future__ import annotations

import importlib


def test_conube_exporter_formats_metrics(monkeypatch):
    import tools.conube_exporter as conube_exporter

    module = importlib.reload(conube_exporter)

    collector = module.ConubeMetricsCollector(cache_seconds=0)
    monkeypatch.setattr(
        collector,
        "_fetch_snapshot",
        lambda: {
            "summary": {
                "dashboard_loaded": True,
                "open_periods_count": 2,
                "pending_items_count": 5,
                "overdue_items_count": 3,
                "relevant_items_count": 1,
                "top_overdue_items": [
                    {"subject": "DEFIS - Entrega Anual", "source": "tarefas"},
                ],
                "certificate": {"present": True, "expired": True},
            },
            "audit": {
                "open_periods_count": 1,
                "closed_periods_count": 4,
                "periods": [
                    {"period": "2025-03", "status": "Aberto", "logs_count": 0},
                    {"period": "2025-02", "status": "Fechado", "logs_count": 1},
                ],
            },
            "billing": {"blocked_by_certificate": True},
        },
    )
    collector._refresh_cache()
    payload = collector.collect()

    assert "conube_exporter_up 1" in payload
    assert "conube_open_periods_total 2" in payload
    assert "conube_certificate_expired 1" in payload
    assert 'conube_financial_period_open{period="2025-03"} 1' in payload
    assert 'conube_financial_period_logs_count{period="2025-02"} 1' in payload
    assert 'conube_pending_item_overdue{subject="DEFIS - Entrega Anual",source="tarefas"} 1' in payload
