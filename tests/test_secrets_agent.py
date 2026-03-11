"""Testes unitários do Secrets Agent — rotas com suporte a path slashes."""
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Configurar env antes de importar o módulo
_tmpdir = tempfile.mkdtemp()
os.environ["SECRETS_AGENT_DATA"] = _tmpdir
os.environ["SECRETS_AGENT_API_KEY"] = "test-api-key"
os.environ.setdefault("BW_PASSWORD_FILE", str(Path(_tmpdir) / ".bw_pw"))

from fastapi.testclient import TestClient

# Patch BW para não tentar unlock real durante import
with patch("tools.secrets_agent.secrets_agent.BitwardenSessionManager._load_cached_session"), \
     patch("tools.secrets_agent.secrets_agent.BitwardenSessionManager.ensure_session", return_value=False):
    from tools.secrets_agent.secrets_agent import app, DB_PATH, init_db

API_KEY = "test-api-key"
HEADERS = {"X-API-KEY": API_KEY}

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _clean_db():
    """Limpa tabela secrets_store antes de cada teste."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM secrets_store")
    conn.commit()
    conn.close()
    yield


class TestStoreSecret:
    """Testes de POST /secrets."""

    def test_store_secret_ok(self) -> None:
        """Armazena um secret com sucesso."""
        resp = client.post("/secrets", json={
            "name": "test/secret", "field": "token", "value": "abc123"
        }, headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stored"
        assert data["name"] == "test/secret"

    def test_store_secret_no_auth(self) -> None:
        """Rejeita sem API key."""
        resp = client.post("/secrets", json={
            "name": "x", "field": "p", "value": "v"
        })
        assert resp.status_code == 401


class TestGetSecretWithSlash:
    """Testes de GET /secrets/{item_id:path} com nomes contendo /."""

    def _store(self, name: str, field: str, value: str) -> None:
        """Helper para inserir direto no DB."""
        conn = sqlite3.connect(DB_PATH)
        now = 1
        conn.execute(
            "INSERT OR REPLACE INTO secrets_store (name, field, value, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, field, value, now, now),
        )
        conn.commit()
        conn.close()

    def test_get_single_field(self) -> None:
        """Retorna campo específico de secret com slash."""
        self._store("cloudflare/rpa4all", "cf_token", "tok123")
        resp = client.get(
            "/secrets/cloudflare/rpa4all?field=cf_token",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "cloudflare/rpa4all"
        assert data["value"] == "tok123"

    def test_get_all_fields_fallback(self) -> None:
        """Retorna todos os campos quando field default não existe."""
        self._store("cloudflare/rpa4all", "cf_token", "tok1")
        self._store("cloudflare/rpa4all", "tunnel_id", "tid1")
        resp = client.get(
            "/secrets/cloudflare/rpa4all",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "cloudflare/rpa4all"
        assert "fields" in data
        assert data["fields"]["cf_token"] == "tok1"
        assert data["fields"]["tunnel_id"] == "tid1"

    def test_get_simple_name(self) -> None:
        """Funciona com nomes sem slash."""
        self._store("simple_name", "password", "pw123")
        resp = client.get(
            "/secrets/simple_name",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "pw123"

    def test_get_deep_path(self) -> None:
        """Suporta nomes com múltiplos segmentos de path."""
        self._store("org/team/service", "api_key", "deep_val")
        resp = client.get(
            "/secrets/org/team/service?field=api_key",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "deep_val"

    def test_get_no_auth(self) -> None:
        """Rejeita sem API key."""
        resp = client.get("/secrets/cloudflare/rpa4all")
        assert resp.status_code == 401

    @patch("tools.secrets_agent.secrets_agent.bw_get_item_password", return_value=None)
    def test_get_not_found(self, mock_bw) -> None:
        """Retorna 404 quando secret não existe."""
        resp = client.get(
            "/secrets/nonexistent/secret",
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_local_prefix(self) -> None:
        """Suporta formato local:name:field."""
        self._store("myapp", "token", "local_val")
        resp = client.get(
            "/secrets/local:myapp:token",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "local_val"


class TestGetLocalSecret:
    """Testes de GET /secrets/local/{name:path}."""

    def _store(self, name: str, field: str, value: str) -> None:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT OR REPLACE INTO secrets_store (name, field, value, created_at, updated_at) "
            "VALUES (?, ?, ?, 1, 1)",
            (name, field, value),
        )
        conn.commit()
        conn.close()

    def test_local_with_slash(self) -> None:
        """Funciona com nomes contendo slash."""
        self._store("cf/rpa4all", "token", "local_tok")
        resp = client.get(
            "/secrets/local/cf/rpa4all?field=token",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "local_tok"

    def test_local_not_found(self) -> None:
        """Retorna 404 quando local secret não existe."""
        resp = client.get(
            "/secrets/local/nope?field=x",
            headers=HEADERS,
        )
        assert resp.status_code == 404
