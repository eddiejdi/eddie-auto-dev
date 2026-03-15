from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_module(monkeypatch):
    monkeypatch.setenv("AUTHENTIK_URL", "https://auth.example.test")
    monkeypatch.setenv("AUTHENTIK_TOKEN", "test-token")
    monkeypatch.setenv("STORAGE_ACCESS_LOGIN_URL", "https://auth.example.test/")
    monkeypatch.setenv("STORAGE_PORTAL_URL", "https://www.rpa4all.com/storage-portal.html")

    import specialized_agents.storage_portal as storage_portal

    return importlib.reload(storage_portal)


def _build_client(module):
    app = FastAPI()
    app.include_router(module.router, prefix="/storage")
    return TestClient(app, raise_server_exceptions=False)


def _session():
    return {
        "id": "ctr_123",
        "contract_code": "STR-20260315-TEST",
        "company": "Acme Storage",
        "legal_name": "Acme Storage LTDA",
        "project": "Portal Storage",
        "mode": "sizing",
        "status": "active",
        "primary_email": "maria@acme.test",
        "primary_contact": "Maria Silva",
        "workspace_path": "/mnt/raid1/nextcloud-external/RPA4ALL/Portal_Storage/STR-20260315-TEST",
        "user_id": 1,
        "user_email": "maria@acme.test",
        "user_username": "acme-maria",
        "user_full_name": "Maria Silva",
        "user_profile": "manager",
        "user_is_manager": True,
        "portal_token": "stp_test",
        "volume_tb": 20.0,
        "ingress_tb": 3.0,
        "term_months": 12,
        "monthly_service": 4200.0,
        "setup_fee": 1500.0,
        "contract_value": 51900.0,
        "notice_days": 30,
        "breach_penalty": 8400.0,
    }


def test_portal_bootstrap_returns_contract_data(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    monkeypatch.setattr(module, "_get_portal_session", lambda token: _session())
    monkeypatch.setattr(
        module,
        "_build_bootstrap",
        lambda session: {"contract": {"contract_code": session["contract_code"]}, "permissions": {"manage_users": True}},
    )

    response = client.get("/storage/portal/bootstrap", params={"portal_token": "stp_test"})

    assert response.status_code == 200
    assert response.json()["contract"]["contract_code"] == "STR-20260315-TEST"


def test_portal_create_token_returns_plain_token(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    monkeypatch.setattr(module, "_require_manager_session", lambda token: _session())
    monkeypatch.setattr(
        module,
        "_create_api_token",
        lambda contract_id, label, created_by_email: {
            "id": 9,
            "label": label,
            "preview": "stg_live_xxx...",
            "token": "stg_live_secret",
            "status": "active",
        },
    )
    monkeypatch.setattr(module, "_build_connection_info", lambda session: {"ingest_endpoint": "https://api.rpa4all.com/agents-api/storage/ingest"})
    monkeypatch.setattr(module, "_list_contract_tokens", lambda contract_id: [{"id": 9, "label": "Portal", "preview": "stg_live_xxx..."}])

    response = client.post("/storage/portal/tokens", json={"portal_token": "stp_test", "label": "Portal"})

    assert response.status_code == 200
    data = response.json()
    assert data["token"]["token"] == "stg_live_secret"
    assert data["connections"]["ingest_endpoint"].endswith("/storage/ingest")


def test_storage_ingest_records_event(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    monkeypatch.setattr(
        module,
        "_resolve_api_token",
        lambda authorization: {
            "id": "ctr_123",
            "contract_code": "STR-20260315-TEST",
            "token_id": 3,
        },
    )
    monkeypatch.setattr(
        module,
        "_record_ingest_event",
        lambda contract_id, token_id, user_id, protocol, relative_path, bytes_count, checksum, metadata: {
            "id": 1,
            "relative_path": relative_path,
            "bytes": bytes_count,
            "protocol": protocol,
        },
    )

    response = client.post(
        "/storage/ingest",
        headers={"Authorization": "Bearer stg_live_secret"},
        json={"relative_path": "lote-01/backup.tar", "bytes": 2048, "protocol": "api", "metadata": {"source": "agent"}},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["ingest_event"]["relative_path"] == "lote-01/backup.tar"
