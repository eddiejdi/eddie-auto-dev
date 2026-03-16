from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient
import requests


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


def test_conube_pending_documents_endpoint(monkeypatch):
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

        def pending_documents(self):
            return {
                "status": "ok",
                "has_pending_documents": True,
                "pending_status": {"pending": True},
                "documents_count": 1,
                "documents": [{"id": "doc-1", "name": "Contrato social"}],
            }

    monkeypatch.setattr(module, "ConubePortalAgent", FakeAgent)

    response = client.get("/conube/company/pending-documents?headless=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["has_pending_documents"] is True
    assert payload["documents_count"] == 1
    assert payload["documents"][0]["name"] == "Contrato social"


def test_pending_documents_handles_status_400(monkeypatch):
    module = _load_module(monkeypatch)

    agent = module.ConubePortalAgent("user@test", "secret", headless=True)
    monkeypatch.setattr(agent, "login", lambda: None)

    status_response = requests.Response()
    status_response.status_code = 400
    status_response.url = "https://app.conube.test/api/client/my-company/documentation/status"
    status_response._content = b'{"error":"bad request"}'

    def fake_get(path, *, api_version="client", timeout=25):
        if path == "my-company/documentation/status":
            raise requests.HTTPError(response=status_response)
        if path == "/my-company/documentation/list":
            return [{"id": "doc-1", "name": "Contrato social"}]
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(agent, "_authenticated_api_get", fake_get)

    payload = agent.pending_documents()

    assert payload["status"] == "ok"
    assert payload["has_pending_documents"] is False
    assert payload["pending_status"] == {}
    assert payload["pending_status_error"]["status_code"] == 400
    assert payload["documents_count"] == 1
    assert payload["documents"][0]["name"] == "Contrato social"


def test_conube_contracted_service_detail_endpoint(monkeypatch):
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

        def contracted_service_detail(self, service_id):
            return {
                "status": "ok",
                "company_id": "company-1",
                "service_id": service_id,
                "service": [{"_id": service_id, "status": "AGUARDANDO ENVIO DO DOCUMENTO"}],
            }

    monkeypatch.setattr(module, "ConubePortalAgent", FakeAgent)

    response = client.post(
        "/conube/company/contracted-service-detail",
        json={"headless": True, "service_id": "svc-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service_id"] == "svc-1"
    assert payload["service"][0]["status"] == "AGUARDANDO ENVIO DO DOCUMENTO"


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


def test_conube_financial_periods_endpoint(monkeypatch):
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

        def financial_periods_audit(self, months_back):
            calls["months_back"] = months_back
            return {
                "status": "ok",
                "open_periods_count": 1,
                "closed_periods_count": 3,
                "periods": [
                    {
                        "period": "2026-03",
                        "status": "Aberto",
                        "logs_count": 0,
                    },
                    {
                        "period": "2026-02",
                        "status": "Fechado",
                        "logs_count": 1,
                    },
                ],
            }

    monkeypatch.setattr(module, "ConubePortalAgent", FakeAgent)

    response = client.post("/conube/company/financial-periods", json={"headless": True, "months_back": 6})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["open_periods_count"] == 1
    assert payload["closed_periods_count"] == 3
    assert calls["months_back"] == 6


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
                "open_periods_count": 1,
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
                "responsible_counts": {"contador": 10, "cliente": 2},
                "client_actionable_items_count": 2,
                "accountant_owned_items_count": 10,
                "dashboard_loaded": False,
                "dashboard_error": "timeout",
            }

    monkeypatch.setattr(module, "ConubePortalAgent", FakeAgent)

    response = client.get("/conube/dashboard/operational-summary?headless=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["open_periods_count"] == 1
    assert payload["overdue_items_count"] == 8
    assert payload["relevant_items_count"] == 3
    assert payload["client_actionable_items_count"] == 2
    assert payload["accountant_owned_items_count"] == 10
    assert payload["certificate"]["expired"] is True


def test_conube_daily_summary_report_endpoint(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    monkeypatch.setattr(module, "load_conube_credentials", lambda: ("user@test", "secret"))
    monkeypatch.setitem(module._CONUBE_DAILY_REPORT_CACHE, "payload", None)
    monkeypatch.setitem(module._CONUBE_DAILY_REPORT_CACHE, "key", None)
    monkeypatch.setitem(module._CONUBE_DAILY_REPORT_CACHE, "expires_at", 0.0)

    class FakeAgent:
        def __init__(self, email, password, *, headless, timeout_seconds=25, download_dir=None):
            self.headless = headless

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def daily_report(self, *, use_ollama):
            assert use_ollama is False
            return {
                "status": "ok",
                "report_date": "2026-03-16",
                "generated_at": "2026-03-16T12:00:00+00:00",
                "summary": {
                    "open_periods_count": 0,
                    "client_actionable_items_count": 0,
                    "accountant_owned_items_count": 20,
                    "certificate": {"present": True, "expired": True, "latest_expiration": "2024-01-16T12:36:48.000Z"},
                },
                "grouped_pending_items": [{"subject": "Transmissão DESTDA - Estado SP", "count": 17}],
                "pending_items": [{"subject": "Transmissão DESTDA - Estado SP", "competence": "2019-01"}],
                "pending_documents": {"has_pending_documents": False, "documents_count": 0},
                "recommended_actions": [{"owner": "contador", "priority": "alta", "title": "Cobrar regularizacao"}],
                "narrative": "Relatorio fallback",
                "narrative_source": "fallback",
                "ollama_model": None,
            }

    monkeypatch.setattr(module, "ConubePortalAgent", FakeAgent)

    response = client.get("/conube/reports/daily-summary?headless=true&refresh=true&use_ollama=false")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["summary"]["accountant_owned_items_count"] == 20
    assert payload["grouped_pending_items"][0]["count"] == 17
    assert payload["narrative_source"] == "fallback"


def test_conube_remediate_client_pending_endpoint(monkeypatch):
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

        def remediate_client_pending_tasks(self):
            return {
                "status": "ok",
                "processed": 2,
                "results": [
                    {
                        "task_id": "1",
                        "subject": "Informe de Rendimentos - Sócios",
                        "action": "conclude",
                        "status": "Concluída",
                        "result": "completed",
                    },
                    {
                        "task_id": "2",
                        "subject": "TFE - Pagamento da Taxa Municipal",
                        "action": "request_recalculation",
                        "status": "Em análise",
                        "result": "updated",
                    },
                ],
                "remaining_client_tasks": [],
            }

    monkeypatch.setattr(module, "ConubePortalAgent", FakeAgent)

    response = client.post("/conube/tasks/remediate-client-pending", json={"headless": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["processed"] == 2
    assert payload["results"][0]["action"] == "conclude"
    assert payload["results"][1]["action"] == "request_recalculation"
    assert payload["remaining_client_tasks"] == []


def test_conube_run_remediation_endpoint(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    monkeypatch.setattr(module, "load_conube_credentials", lambda: ("user@test", "secret"))
    monkeypatch.setattr(module, "_send_telegram_message", lambda _: True)

    class FakeAgent:
        def __init__(self, email, password, *, headless, timeout_seconds=25, download_dir=None):
            self.headless = headless

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def run_remediation(self, *, close_periods_limit, run_client_tasks):
            assert close_periods_limit == 8
            assert run_client_tasks is True
            return {
                "status": "ok",
                "actions": [{"action": "close-open-financial-periods", "status": "ok", "processed": 1}],
                "before": {"open_periods_count": 1, "client_actionable_items_count": 2, "pending_items_count": 20},
                "after": {"open_periods_count": 0, "client_actionable_items_count": 0, "pending_items_count": 18},
            }

    monkeypatch.setattr(module, "ConubePortalAgent", FakeAgent)

    response = client.post(
        "/conube/actions/run-remediation",
        json={
            "headless": True,
            "close_periods_limit": 8,
            "run_client_tasks": True,
            "notify_telegram": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["telegram_notification_sent"] is True
    assert payload["after"]["open_periods_count"] == 0


def test_conube_run_remediation_requires_action_token(monkeypatch):
    monkeypatch.setenv("CONUBE_ACTION_TOKEN", "abc123")
    module = _load_module(monkeypatch)
    client = _build_client(module)

    response = client.get("/conube/actions/run-remediation")
    assert response.status_code == 401


def test_operational_summary_uses_resolved_period_status(monkeypatch):
    module = _load_module(monkeypatch)

    agent = module.ConubePortalAgent("user@test", "secret", headless=True)
    include_dashboard_flags = []

    monkeypatch.setattr(
        agent,
        "dashboard_pending_items",
        lambda *, include_dashboard=True: (
            include_dashboard_flags.append(include_dashboard),
            {
            "dashboard_loaded": True,
            "dashboard_error": None,
            "normalized_pending_items": [
                {
                    "source": "tarefas",
                    "subject": "DEFIS - Entrega Anual",
                    "status": "Pendente",
                    "due_date": "2026-03-31T02:59:59.000Z",
                    "year": 2026,
                    "month": 3,
                    "responsible": "contador",
                }
            ],
            "api_checks": {
                "transactions_last_periods": [
                    {"_id": "p1", "status": "Aberto", "dataFimPeriodo": "2026-03-31T23:59:59.999Z"}
                ],
                "certificados": [],
            },
            },
        )[1],
    )
    monkeypatch.setattr(
        agent,
        "get_period_status",
        lambda period_end: {
            "_id": "p1",
            "Status": "Fechado",
            "Ano": 2026,
            "Mes": 3,
        },
    )

    summary = agent.operational_summary()

    assert summary["open_periods_count"] == 0
    assert summary["open_periods"] == []
    assert summary["relevant_items_count"] == 0
    assert include_dashboard_flags == [False]
