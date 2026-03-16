from __future__ import annotations

import importlib


def test_conube_exporter_formats_metrics(monkeypatch):
    import tools.conube_exporter as conube_exporter

    module = importlib.reload(conube_exporter)

    monkeypatch.setattr(module, "load_conube_credentials", lambda: ("user@test", "secret"))

    class FakeAgent:
        def __init__(self, email, password, *, headless):
            self.email = email
            self.password = password
            self.headless = headless

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def operational_summary(self):
            return {
                "dashboard_loaded": True,
                "open_periods_count": 2,
                "pending_items_count": 5,
                "overdue_items_count": 3,
                "relevant_items_count": 1,
                "top_overdue_items": [
                    {"subject": "DEFIS - Entrega Anual", "source": "tarefas"},
                ],
                "certificate": {"present": True, "expired": True},
            }

        def financial_periods_audit(self, months_back):
            assert months_back == module.CONUBE_EXPORTER_MONTHS_BACK
            return {
                "open_periods_count": 1,
                "closed_periods_count": 4,
                "periods": [
                    {"period": "2025-03", "status": "Aberto", "logs_count": 0},
                    {"period": "2025-02", "status": "Fechado", "logs_count": 1},
                ],
            }

        def billing_diagnostic(self):
            return {"blocked_by_certificate": True}

    monkeypatch.setattr(module, "ConubePortalAgent", FakeAgent)

    collector = module.ConubeMetricsCollector(cache_seconds=0)
    payload = collector.collect()

    assert "conube_exporter_up 1" in payload
    assert "conube_open_periods_total 2" in payload
    assert "conube_certificate_expired 1" in payload
    assert 'conube_financial_period_open{period="2025-03"} 1' in payload
    assert 'conube_financial_period_logs_count{period="2025-02"} 1' in payload
    assert 'conube_pending_item_overdue{subject="DEFIS - Entrega Anual",source="tarefas"} 1' in payload
