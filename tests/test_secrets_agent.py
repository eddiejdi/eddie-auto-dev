"""Testes unitários do Secrets Agent (modo Bitwarden-only)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Configurar env antes de importar o módulo
_tmpdir = tempfile.mkdtemp()
os.environ["SECRETS_AGENT_DATA"] = _tmpdir
os.environ["SECRETS_AGENT_API_KEY"] = "test-api-key"
os.environ.setdefault("BW_PASSWORD_FILE", str(Path(_tmpdir) / ".bw_pw"))

# Patch BW para não tentar unlock real durante import
with patch("tools.secrets_agent.secrets_agent.BitwardenSessionManager._load_cached_session"), \
     patch("tools.secrets_agent.secrets_agent.BitwardenSessionManager.ensure_session", return_value=False):
    from tools.secrets_agent.secrets_agent import (
        AUDIT_EVENTS,
        app,
        bw_manager,
    )

API_KEY = "test-api-key"
HEADERS = {"X-API-KEY": API_KEY}

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _clean_audit():
    AUDIT_EVENTS.clear()
    yield
    AUDIT_EVENTS.clear()


class TestStoreSecret:
    """Testes de POST /secrets."""

    @patch(
        "tools.secrets_agent.secrets_agent.bw_upsert_secret",
        return_value=(True, "test/secret#token", None),
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
        assert data["bw_sync"]["enabled"] is True
        assert data["bw_sync"]["ok"] is True
        assert data["bw_sync"]["item_name"] == "test/secret#token"

    @patch(
        "tools.secrets_agent.secrets_agent.bw_upsert_secret",
        return_value=(False, "test/secret#token", "save_error"),
    )
    def test_store_secret_bw_error(self, _mock_upsert) -> None:
        resp = client.post(
            "/secrets",
            json={"name": "test/secret", "field": "token", "value": "abc123"},
            headers=HEADERS,
        )
        assert resp.status_code == 503

    def test_store_secret_no_auth(self) -> None:
        resp = client.post("/secrets", json={"name": "x", "field": "p", "value": "v"})
        assert resp.status_code == 401


class TestGetLocalSecret:
    """Testes de GET /secrets/local/{name:path}."""

    @patch("tools.secrets_agent.secrets_agent.bw_get_secret_value", return_value="local_tok")
    def test_local_with_slash(self, _mock_get) -> None:
        resp = client.get("/secrets/local/cf/rpa4all?field=token", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["value"] == "local_tok"
        assert data["source"] == "bitwarden"

    @patch("tools.secrets_agent.secrets_agent.bw_get_secret_value", return_value=None)
    def test_local_not_found(self, _mock_get) -> None:
        resp = client.get("/secrets/local/nope?field=x", headers=HEADERS)
        assert resp.status_code == 404


class TestGetSecret:
    """Testes de GET /secrets/{item_id:path}."""

    @patch("tools.secrets_agent.secrets_agent.bw_get_secret_value", return_value="local_val")
    def test_local_prefix(self, _mock_get) -> None:
        resp = client.get("/secrets/local:myapp:token", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["value"] == "local_val"

    @patch("tools.secrets_agent.secrets_agent.bw_get_item_password", return_value=None)
    @patch("tools.secrets_agent.secrets_agent.bw_get_secret_fields", return_value={"cf_token": "tok1", "tunnel_id": "tid1"})
    @patch("tools.secrets_agent.secrets_agent.bw_get_secret_value", return_value=None)
    def test_get_all_fields_fallback(self, _mock_val, _mock_fields, _mock_pwd) -> None:
        resp = client.get("/secrets/cloudflare/rpa4all", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["fields"]["cf_token"] == "tok1"
        assert data["fields"]["tunnel_id"] == "tid1"

    @patch("tools.secrets_agent.secrets_agent.bw_get_item_password", return_value="id_secret")
    @patch("tools.secrets_agent.secrets_agent.bw_get_secret_fields", return_value={})
    @patch("tools.secrets_agent.secrets_agent.bw_get_secret_value", return_value=None)
    def test_get_by_item_id(self, _mock_val, _mock_fields, _mock_pwd) -> None:
        resp = client.get("/secrets/8c0f357d-e88c-4fb0-bf2a-4af76a0f4451", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["value"] == "id_secret"

    @patch("tools.secrets_agent.secrets_agent.bw_get_item_password", return_value=None)
    @patch("tools.secrets_agent.secrets_agent.bw_get_secret_fields", return_value={})
    @patch("tools.secrets_agent.secrets_agent.bw_get_secret_value", return_value=None)
    def test_get_not_found(self, _mock_val, _mock_fields, _mock_pwd) -> None:
        resp = client.get("/secrets/nonexistent/secret", headers=HEADERS)
        assert resp.status_code == 404

    def test_get_no_auth(self) -> None:
        resp = client.get("/secrets/cloudflare/rpa4all")
        assert resp.status_code == 401


class TestDeleteLocalCompat:
    """Testes de DELETE /secrets/local/{name}."""

    @patch("tools.secrets_agent.secrets_agent.bw_delete_secret", return_value=(True, None))
    def test_delete_ok(self, _mock_del) -> None:
        resp = client.delete("/secrets/local/myapp?field=token", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @patch("tools.secrets_agent.secrets_agent.bw_delete_secret", return_value=(False, "not_found"))
    def test_delete_not_found(self, _mock_del) -> None:
        resp = client.delete("/secrets/local/myapp?field=token", headers=HEADERS)
        assert resp.status_code == 404


class TestBitwardenFallback:
    """Testes para comportamento de sessão do Bitwarden."""

    @patch("tools.secrets_agent.secrets_agent.subprocess.run")
    def test_run_command_short_circuits_when_session_unavailable(self, mock_run) -> None:
        with patch.object(bw_manager, "ensure_session", return_value=False):
            result = bw_manager.run_command(["list", "items", "--raw"])

        assert result.returncode == 1
        assert "Bitwarden unavailable" in (result.stderr or "")
        mock_run.assert_not_called()

    def test_list_secrets_uses_bw_items(self) -> None:
        with patch("tools.secrets_agent.secrets_agent.bw_list_items", return_value=[{"id": "1", "name": "storj/account"}]), \
             patch.object(bw_manager, "get_status", return_value="unlocked"):
            resp = client.get("/secrets", headers=HEADERS)

        assert resp.status_code == 200
        data = resp.json()
        assert data["bw_status"] == "unlocked"
        assert data["count"] == 1
        assert data["items"][0]["title"] == "storj/account"


class TestAudit:
    """Testes de auditoria em memória."""

    @patch(
        "tools.secrets_agent.secrets_agent.bw_upsert_secret",
        return_value=(True, "audit/test", None),
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
