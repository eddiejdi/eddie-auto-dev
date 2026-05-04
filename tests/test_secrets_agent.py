"""Testes unitários do Secrets Agent (backend Authentik)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from fastapi.testclient import TestClient

# Configurar env antes de importar o módulo
_tmpdir = tempfile.mkdtemp()
os.environ["SECRETS_AGENT_DATA"] = _tmpdir
os.environ["SECRETS_AGENT_API_KEY"] = "test-api-key"
os.environ.setdefault("AUTHENTIK_URL", "http://authentik.test")
os.environ.setdefault("AUTHENTIK_TOKEN", "test-token")

from tools.secrets_agent.secrets_agent import (
    AUDIT_EVENTS,
    app,
    ak_manager,
)

API_KEY = "test-api-key"
HEADERS = {"X-API-KEY": API_KEY}

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _clean_audit():
    AUDIT_EVENTS.clear()
    yield
    AUDIT_EVENTS.clear()


@pytest.fixture(autouse=True)
def _clean_local_vault() -> None:
    vault_dir = Path(os.environ["SECRETS_AGENT_DATA"]) / "local_vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    for fpath in vault_dir.glob("*.json"):
        fpath.unlink(missing_ok=True)
    yield
    for fpath in vault_dir.glob("*.json"):
        fpath.unlink(missing_ok=True)


class TestStoreSecret:
    """Testes de POST /secrets."""

    @patch(
        "tools.secrets_agent.secrets_agent.AuthentikSecretManager.upsert_secret",
        return_value=(True, "secret-test-secret-token", None),
    )
    def test_store_secret_ok(self, _mock_upsert) -> None:
        resp = client.post(
            "/secrets",
            json={"name": "test/secret", "field": "token", "value": "abc123"},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stored"
        assert data["name"] == "test/secret"
        assert data["backend_sync"]["source"] == "authentik"
        assert data["backend_sync"]["ok"] is True
        assert data["backend_sync"]["item_id"] == "secret-test-secret-token"

    @patch(
        "tools.secrets_agent.secrets_agent.AuthentikSecretManager.upsert_secret",
        return_value=(False, "secret-test-secret-token", "create_error:400"),
    )
    def test_store_secret_authentik_error_succeeds_via_local_vault(self, _mock_upsert) -> None:
        """Se Authentik falha mas LocalVault funciona, deve retornar 200."""
        resp = client.post(
            "/secrets",
            json={"name": "test/secret", "field": "token", "value": "abc123"},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["backend_sync"]["ok"] is False
        assert data["local_vault"] is True

    def test_store_secret_no_auth(self) -> None:
        resp = client.post("/secrets", json={"name": "x", "field": "p", "value": "v"})
        assert resp.status_code == 401


class TestGetLocalSecret:
    """Testes de GET /secrets/local/{name:path} — somente LocalVault."""

    def test_local_with_slash(self) -> None:
        from tools.secrets_agent.secrets_agent import local_vault
        local_vault.store("cf/rpa4all", "local_tok", field="token")
        resp = client.get("/secrets/local/cf/rpa4all?field=token", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["value"] == "local_tok"
        assert data["source"] == "local_vault"

    def test_local_not_found(self) -> None:
        resp = client.get("/secrets/local/nope?field=x", headers=HEADERS)
        assert resp.status_code == 404


class TestGetSecret:
    """Testes de GET /secrets/{item_id:path}."""

    @patch(
        "tools.secrets_agent.secrets_agent.AuthentikSecretManager.get_secret",
        return_value="ak_val",
    )
    def test_local_prefix(self, _mock_get) -> None:
        resp = client.get("/secrets/local:myapp:token", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["value"] == "ak_val"

    @patch(
        "tools.secrets_agent.secrets_agent.AuthentikSecretManager.get_secret_fields",
        return_value={"cf_token": "tok1", "tunnel_id": "tid1"},
    )
    @patch(
        "tools.secrets_agent.secrets_agent.AuthentikSecretManager.get_secret",
        return_value=None,
    )
    def test_get_all_fields_fallback(self, _mock_val, _mock_fields) -> None:
        resp = client.get("/secrets/cloudflare/rpa4all", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["fields"]["cf_token"] == "tok1"
        assert data["fields"]["tunnel_id"] == "tid1"

    @patch(
        "tools.secrets_agent.secrets_agent.AuthentikSecretManager.get_secret_fields",
        return_value={},
    )
    @patch(
        "tools.secrets_agent.secrets_agent.AuthentikSecretManager.get_secret",
        return_value=None,
    )
    def test_get_falls_back_to_local_vault(self, _mock_val, _mock_fields) -> None:
        from tools.secrets_agent.secrets_agent import local_vault
        local_vault.store("myapp/secret", "vault_val")
        resp = client.get("/secrets/myapp/secret", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["value"] == "vault_val"
        assert data["source"] == "local_vault"

    @patch(
        "tools.secrets_agent.secrets_agent.AuthentikSecretManager.get_secret_fields",
        return_value={},
    )
    @patch(
        "tools.secrets_agent.secrets_agent.AuthentikSecretManager.get_secret",
        return_value=None,
    )
    def test_get_not_found(self, _mock_val, _mock_fields) -> None:
        resp = client.get("/secrets/nonexistent/secret", headers=HEADERS)
        assert resp.status_code == 404

    def test_get_no_auth(self) -> None:
        resp = client.get("/secrets/cloudflare/rpa4all")
        assert resp.status_code == 401


class TestDeleteSecret:
    """Testes de DELETE /secrets/local/{name}."""

    @patch(
        "tools.secrets_agent.secrets_agent.AuthentikSecretManager.delete_secret",
        return_value=(True, None),
    )
    def test_delete_ok(self, _mock_del) -> None:
        resp = client.delete("/secrets/local/myapp?field=token", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @patch(
        "tools.secrets_agent.secrets_agent.AuthentikSecretManager.delete_secret",
        return_value=(False, "not_found"),
    )
    def test_delete_not_found(self, _mock_del) -> None:
        resp = client.delete("/secrets/local/myapp?field=token", headers=HEADERS)
        assert resp.status_code == 404


class TestAuthentikFallback:
    """Testes de comportamento quando Authentik está indisponível."""

    @patch(
        "tools.secrets_agent.secrets_agent.AuthentikSecretManager.get_secret",
        return_value=None,
    )
    @patch(
        "tools.secrets_agent.secrets_agent.AuthentikSecretManager.get_secret_fields",
        return_value={},
    )
    def test_falls_back_to_local_vault_when_authentik_unavailable(
        self, _mock_fields, _mock_get
    ) -> None:
        from tools.secrets_agent.secrets_agent import local_vault
        local_vault.store("fallback/key", "vault_secret")
        resp = client.get("/secrets/fallback/key", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["source"] == "local_vault"

    @patch(
        "tools.secrets_agent.secrets_agent.AuthentikSecretManager.list_items",
        return_value=[{"id": "secret-storj-account", "title": "secret-holder:storj/account#password", "source": "authentik"}],
    )
    @patch.object(ak_manager, "get_info", return_value={"authentik_status": "available", "authentik_url": "http://test", "token_configured": True})
    def test_list_secrets_includes_authentik_items(self, _mock_info, _mock_list) -> None:
        resp = client.get("/secrets", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["backend_status"] == "available"
        assert data["count"] >= 1
        assert data["items"][0]["source"] == "authentik"


class TestAudit:
    """Testes de auditoria em memória."""

    @patch(
        "tools.secrets_agent.secrets_agent.AuthentikSecretManager.upsert_secret",
        return_value=(True, "secret-audit-test", None),
    )
    def test_recent_audit(self, _mock_upsert) -> None:
        resp = client.post(
            "/secrets",
            json={"name": "audit/test", "field": "password", "value": "v"},
            headers=HEADERS,
        )
        assert resp.status_code == 200

        audit = client.get("/audit/recent?limit=1").json()
        assert len(audit["rows"]) == 1
        assert audit["rows"][0][2] == "store"


class TestClientId:
    """Testes da convenção de client_id."""

    def test_password_field(self) -> None:
        assert ak_manager._client_id("kucoin/homelab", "password") == "secret-kucoin-homelab"

    def test_other_field(self) -> None:
        assert ak_manager._client_id("kucoin/homelab", "api_key") == "secret-kucoin-homelab-api-key"

    def test_underscore_in_name(self) -> None:
        cid = ak_manager._client_id("shared/home_assistant", "password")
        assert cid == "secret-shared-home-assistant"

    def test_uppercase_normalized(self) -> None:
        cid = ak_manager._client_id("KuCoin/Homelab", "ApiKey")
        assert cid == "secret-kucoin-homelab-apikey"
