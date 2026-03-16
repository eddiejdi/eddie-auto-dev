from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_module(monkeypatch):
    monkeypatch.setenv("CONUBE_BASE_URL", "https://app.conube.test")
    monkeypatch.setenv("CONUBE_LOGIN_URL", "https://app.conube.test/login")
    monkeypatch.setenv("CONUBE_SECRET_NAME", "conube/rpa4all")

    import specialized_agents.conube_agent as conube_agent

    return importlib.reload(conube_agent)


def _build_client(module):
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app, raise_server_exceptions=False)


def test_conube_health_reports_config(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    response = client.get("/conube/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["login_url"] == "https://app.conube.test/login"
    assert payload["secret_names"] == ["conube/rpa4all"]


def test_conube_test_login_uses_agent(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    monkeypatch.setattr(module, "load_conube_credentials", lambda: ("user@test", "secret"))

    calls: dict[str, object] = {}

    class FakeAgent:
        def __init__(self, email, password, *, headless, timeout_seconds=25, download_dir=None):
            calls["init"] = {"email": email, "password": password, "headless": headless}

        def __enter__(self):
            calls["enter"] = True
            return self

        def __exit__(self, exc_type, exc, tb):
            calls["exit"] = True

        def login(self):
            calls["login"] = True

        def snapshot(self):
            calls["snapshot"] = True
            return module.ConubeSessionResult(
                success=True,
                current_url="https://app.conube.test/dashboard",
                title="Conube",
                menu_items=["Minha empresa", "Documentos"],
                visible_text="Painel principal",
                document_links=[],
                service_items=[],
            )

    monkeypatch.setattr(module, "ConubePortalAgent", FakeAgent)

    response = client.post("/conube/session/test-login", json={"headless": False})

    assert response.status_code == 200
    assert response.json()["current_url"] == "https://app.conube.test/dashboard"
    assert calls["init"] == {"email": "user@test", "password": "secret", "headless": False}
    assert calls["login"] is True
    assert calls["snapshot"] is True


def test_conube_documents_endpoint(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    monkeypatch.setattr(module, "load_conube_credentials", lambda: ("user@test", "secret"))

    class FakeAgent:
        def __init__(self, email, password, *, headless, timeout_seconds=25, download_dir=None):
            self.email = email
            self.password = password
            self.headless = headless

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def company_documents(self):
            return {
                "status": "ok",
                "documents": [
                    {"label": "Contrato Social", "href": "https://app.conube.test/doc/1"},
                    {"label": "Cartao CNPJ", "href": "https://app.conube.test/doc/2"},
                ],
            }

    monkeypatch.setattr(module, "ConubePortalAgent", FakeAgent)

    response = client.get("/conube/company/documents?headless=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert len(payload["documents"]) == 2
    assert payload["documents"][0]["label"] == "Contrato Social"


def test_conube_close_overdue_balances_endpoint(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    monkeypatch.setattr(module, "load_conube_credentials", lambda: ("user@test", "secret"))

    calls: dict[str, object] = {}

    class FakeAgent:
        def __init__(self, email, password, *, headless, timeout_seconds=25, download_dir=None):
            calls["init"] = {"email": email, "password": password, "headless": headless}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def close_overdue_balances_without_movement(self, limit):
            calls["limit"] = limit
            return {
                "status": "ok",
                "processed": 2,
                "results": [
                    {
                        "competence": "01/2026",
                        "status": "closed",
                        "message": "Encerrado como sem movimentacao.",
                    },
                    {
                        "competence": "02/2026",
                        "status": "closed",
                        "message": "Encerrado como sem movimentacao.",
                    },
                ],
            }

    monkeypatch.setattr(module, "ConubePortalAgent", FakeAgent)

    response = client.post("/conube/company/close-overdue-balances", json={"headless": True, "limit": 6})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["processed"] == 2
    assert calls["limit"] == 6


def test_conube_billing_diagnostic_endpoint(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    monkeypatch.setattr(module, "load_conube_credentials", lambda: ("user@test", "secret"))

    class FakeAgent:
        def __init__(self, email, password, *, headless, timeout_seconds=25, download_dir=None):
            self.headless = headless

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def billing_diagnostic(self):
            return {
                "status": "blocked",
                "blocked_by_certificate": True,
                "certificate_message_detected": True,
                "checks": [
                    {
                        "step": "emit_invoice",
                        "url": "https://app.conube.test/notas-fiscais/emitir-nota-fiscal",
                        "status": "blocked",
                        "blocker": "expired_certificate",
                        "summary": "Seu certificado digital (e-CNPJ) venceu!",
                    }
                ],
            }

    monkeypatch.setattr(module, "ConubePortalAgent", FakeAgent)

    response = client.get("/conube/billing/diagnostic?headless=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["blocked_by_certificate"] is True
    assert payload["checks"][0]["step"] == "emit_invoice"


def test_conube_close_open_financial_periods_endpoint(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    monkeypatch.setattr(module, "load_conube_credentials", lambda: ("user@test", "secret"))

    calls: dict[str, object] = {}

    class FakeAgent:
        def __init__(self, email, password, *, headless, timeout_seconds=25, download_dir=None):
            calls["init"] = {"email": email, "password": password, "headless": headless}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def close_open_financial_periods(self, limit):
            calls["limit"] = limit
            return {
                "status": "ok",
                "processed": 2,
                "blocked": 0,
                "results": [
                    {"period": "2025-09", "status": "closed"},
                    {"period": "2025-10", "status": "closed"},
                ],
            }

    monkeypatch.setattr(module, "ConubePortalAgent", FakeAgent)

    response = client.post("/conube/company/close-open-financial-periods", json={"headless": True, "limit": 4})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["processed"] == 2
    assert payload["blocked"] == 0
    assert calls["limit"] == 4


def test_conube_dashboard_pending_items_endpoint(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    monkeypatch.setattr(module, "load_conube_credentials", lambda: ("user@test", "secret"))

    class FakeAgent:
        def __init__(self, email, password, *, headless, timeout_seconds=25, download_dir=None):
            self.headless = headless

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def dashboard_pending_items(self):
            return {
                "status": "ok",
                "dashboard_url": "https://dynamo.conube.test/",
                "dashboard_loaded": True,
                "certificate_alert": True,
                "dashboard_periods": [
                    {
                        "label": "Fevereiro",
                        "details": "Encerramento 28/02/2026",
                        "status": "em_atraso",
                    }
                ],
                "api_checks": {"tarefas": {"docs": [{"_id": "1", "status": "pendente"}]}},
                "api_errors": {},
            }

    monkeypatch.setattr(module, "ConubePortalAgent", FakeAgent)

    response = client.get("/conube/dashboard/pending-items?headless=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["dashboard_loaded"] is True
    assert payload["certificate_alert"] is True
    assert payload["dashboard_periods"][0]["status"] == "em_atraso"


def test_conube_operational_summary_endpoint(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    monkeypatch.setattr(module, "load_conube_credentials", lambda: ("user@test", "secret"))

    class FakeAgent:
        def __init__(self, email, password, *, headless, timeout_seconds=25, download_dir=None):
            self.headless = headless

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def operational_summary(self):
            return {
                "status": "ok",
                "open_periods_count": 4,
                "open_periods": [
                    {"id": "p1", "status": "Aberto", "period_end": "2026-03-31T23:59:59.999Z"}
                ],
                "pending_items_count": 12,
                "overdue_items_count": 8,
                "relevant_items_count": 3,
                "relevant_open_period_items": [
                    {
                        "source": "tarefas",
                        "subject": "Fechamento 02/2026",
                        "status": "Pendente",
                        "due_date": "2026-02-28T02:59:59.000Z",
                    }
                ],
                "top_overdue_items": [
                    {
                        "source": "tarefas",
                        "subject": "DEFIS - Entrega Anual",
                        "status": "Pendente",
                        "due_date": "2026-03-31T02:59:59.000Z",
                    }
                ],
                "certificate": {
                    "present": True,
                    "expired": True,
                    "latest_expiration": "2024-01-16T12:36:48.000Z",
                },
                "dashboard_loaded": False,
                "dashboard_error": "timeout",
            }

    monkeypatch.setattr(module, "ConubePortalAgent", FakeAgent)

    response = client.get("/conube/dashboard/operational-summary?headless=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["open_periods_count"] == 4
    assert payload["overdue_items_count"] == 8
    assert payload["relevant_items_count"] == 3
    assert payload["certificate"]["expired"] is True
