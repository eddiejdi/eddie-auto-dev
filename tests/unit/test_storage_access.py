from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_module(monkeypatch):
    monkeypatch.setenv("AUTHENTIK_URL", "https://auth.example.test")
    monkeypatch.setenv("AUTHENTIK_TOKEN", "test-token")
    monkeypatch.setenv("STORAGE_ACCESS_LOGIN_URL", "https://auth.example.test/")
    monkeypatch.setenv("STORAGE_ACCESS_FROM_EMAIL", "edenilson.teixeira@rpa4all.com")

    import specialized_agents.storage_access as storage_access

    storage_access = importlib.reload(storage_access)
    storage_access._RATE_LIMIT_BUCKETS.clear()
    return storage_access


def _build_client(module):
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app, raise_server_exceptions=False)


def _payload():
    return {
        "mode": "sizing",
        "company": "Acme Storage",
        "legal_name": "Acme Storage LTDA",
        "contact": "Maria Silva",
        "role": "Infra",
        "email": "maria.silva@acme.test",
        "phone": "+55 11 99999-0000",
        "project": "Sizing de storage gerenciado",
        "temperature": "warm",
        "volume": 24,
        "ingress": 4,
        "retention": "12",
        "retrieval": "monthly",
        "sla": "24h",
        "compliance": "immutable30",
        "redundancy": "dual",
        "billing": "monthly",
        "term": 12,
        "start_date": "2026-04-01",
        "city": "Sao Paulo",
        "state": "SP",
        "notes": "Operacao piloto",
        "monthly_service": 4200,
        "setup_fee": 1500,
        "contract_value": 51900,
        "notice_days": 30,
        "breach_penalty": 8400,
    }


def test_request_access_dry_run(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    response = client.post("/storage/request-access?dry_run=true", json=_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "dry_run"
    assert data["recipient_email"] == "maria.silva@acme.test"
    assert data["login_url"] == "https://auth.example.test/"


def test_request_access_rejects_duplicate_email(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    monkeypatch.setattr(module, "_enforce_rate_limit", lambda client_ip: None)
    monkeypatch.setattr(module, "_find_existing_user", lambda payload: {"pk": 11, "username": "acme-maria"})

    response = client.post("/storage/request-access", json=_payload())

    assert response.status_code == 409
    assert "Já existe um acesso provisionado" in response.json()["detail"]


def test_request_access_provisions_and_sends_email(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)
    calls = {}

    monkeypatch.setattr(module, "_enforce_rate_limit", lambda client_ip: None)
    monkeypatch.setattr(module, "_find_existing_user", lambda payload: None)

    def fake_create(payload, username, temporary_password):
        calls["create"] = {
            "username": username,
            "password": temporary_password,
            "email": payload.email,
        }
        return {"pk": 42, "username": username}

    def fake_send(payload, username, temporary_password, contract_bundle=None):
        calls["send"] = {
            "username": username,
            "password": temporary_password,
            "email": payload.email,
            "contract_bundle": contract_bundle,
        }
        return "msg-123"

    monkeypatch.setattr(module, "_create_authentik_user", fake_create)
    monkeypatch.setattr(
        module,
        "create_contract_bundle",
        lambda payload, username, authentik_id: {
            "contract_id": "ctr_123",
            "contract_code": "STR-20260315-TEST",
            "workspace_relative_dir": "Portal_Storage/STR-20260315-TEST",
            "portal_url": "https://www.rpa4all.com/storage-portal.html?portal=stp_test",
            "documents": {
                "html_relative_path": "Portal_Storage/STR-20260315-TEST/CONTRATO-STR-20260315-TEST.html",
            },
        },
    )
    monkeypatch.setattr(module, "_send_access_email", fake_send)
    monkeypatch.setattr(module, "_audit_request", lambda **kwargs: calls.setdefault("audit", kwargs))

    response = client.post("/storage/request-access", json=_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["recipient_email"] == "maria.silva@acme.test"
    assert data["contract_code"] == "STR-20260315-TEST"
    assert data["portal_url"] == "https://www.rpa4all.com/storage-portal.html?portal=stp_test"
    assert data["documents"]["html_relative_path"].endswith("CONTRATO-STR-20260315-TEST.html")
    assert calls["create"]["username"] == calls["send"]["username"]
    assert calls["create"]["password"] == calls["send"]["password"]
    assert calls["send"]["contract_bundle"]["contract_id"] == "ctr_123"
    assert calls["audit"]["status"] == "sent"
    assert calls["audit"]["authentik_id"] == 42
