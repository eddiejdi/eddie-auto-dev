"""
Testes unitários para o módulo specialized_agents.user_management.

Testa as funções de CRUD de usuários com mocks para API Authentik e DB.
"""

import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock psycopg2 ANTES de importar o módulo (evita dependência real)
_mock_psycopg2 = MagicMock()
_mock_psycopg2.extensions = MagicMock()
_mock_psycopg2.extensions.connection = type("connection", (), {})
sys.modules.setdefault("psycopg2", _mock_psycopg2)
sys.modules.setdefault("psycopg2.extensions", _mock_psycopg2.extensions)

# Importar o módulo diretamente (sem __init__.py pesado)
_um_path = Path(__file__).resolve().parent.parent / "specialized_agents" / "user_management.py"
_spec = importlib.util.spec_from_file_location("user_management", _um_path)
um = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(um)

# Registrar no sys.modules para que @patch funcione
sys.modules["user_management"] = um

UserConfig = um.UserConfig
UserStatus = um.UserStatus


# ── Fixtures ───────────────────────────────────────────────────────────────
@pytest.fixture
def user_config() -> UserConfig:
    """Configuração padrão de teste."""
    return UserConfig(
        username="testuser",
        email="test@rpa4all.com",
        full_name="Test User",
        password="Senh@Segur4!",
        groups=["users"],
        quota_mb=5000,
        storage_quota_mb=100000,
    )


@pytest.fixture
def mock_authentik_response() -> dict:
    """Resposta padrão da API Authentik para criação de user."""
    return {
        "pk": 42,
        "username": "testuser",
        "email": "test@rpa4all.com",
        "name": "Test User",
        "is_active": True,
        "groups": [],
        "date_joined": "2026-03-08T12:00:00Z",
    }


@pytest.fixture
def mock_user_list() -> list[dict]:
    """Lista de usuários mockada."""
    return [
        {
            "pk": 1,
            "username": "akadmin",
            "email": "admin@rpa4all.com",
            "name": "Admin",
            "is_active": True,
            "groups_obj": [{"name": "admin"}],
            "date_joined": "2026-01-01T00:00:00Z",
            "last_login": "2026-03-08T10:00:00Z",
        },
        {
            "pk": 2,
            "username": "edenilson",
            "email": "edenilson@rpa4all.com",
            "name": "Edenilson",
            "is_active": True,
            "groups_obj": [{"name": "users"}, {"name": "admin"}],
            "date_joined": "2026-01-15T00:00:00Z",
            "last_login": "2026-03-08T12:00:00Z",
        },
    ]


def _make_mock_conn(cursor_mock: MagicMock) -> MagicMock:
    """Cria mock de conexão PostgreSQL com cursor como context manager."""
    conn = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=cursor_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = ctx
    return conn


# ── Testes de UserStatus ──────────────────────────────────────────────────
class TestUserStatus:
    """Testes do enum UserStatus."""

    def test_valores_enum(self) -> None:
        """Verifica todos os valores do enum."""
        assert UserStatus.PENDING.value == "pending"
        assert UserStatus.AUTHENTIK_CREATED.value == "authentik_created"
        assert UserStatus.EMAIL_CREATED.value == "email_created"
        assert UserStatus.ENV_SETUP.value == "env_setup"
        assert UserStatus.COMPLETE.value == "complete"
        assert UserStatus.FAILED.value == "failed"

    def test_enum_count(self) -> None:
        """Verifica quantidade de status."""
        assert len(UserStatus) == 6


# ── Testes de UserConfig ──────────────────────────────────────────────────
class TestUserConfig:
    """Testes do dataclass UserConfig."""

    def test_criacao_basica(self, user_config: UserConfig) -> None:
        """Cria config com valores padrão."""
        assert user_config.username == "testuser"
        assert user_config.email == "test@rpa4all.com"
        assert user_config.groups == ["users"]
        assert user_config.quota_mb == 5000

    def test_valores_default(self) -> None:
        """Verifica defaults do dataclass."""
        config = UserConfig(
            username="u",
            email="u@r.com",
            full_name="U",
            password="p",
        )
        assert config.groups == ["users"]
        assert config.create_ssh_key is True
        assert config.create_folders is True
        assert config.send_welcome_email is True
        assert config.storage_quota_mb == 100000


# ── Testes de _authentik_api ──────────────────────────────────────────────
class TestAuthentikAPI:
    """Testes da função _authentik_api."""

    @patch("user_management.requests.request")
    def test_api_get_sucesso(self, mock_req: MagicMock) -> None:
        """GET com resposta válida."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"results": []}'
        mock_resp.json.return_value = {"results": []}
        mock_req.return_value = mock_resp

        result = um._authentik_api("GET", "/core/users/")
        assert result == {"results": []}
        mock_req.assert_called_once()

    @patch("user_management.requests.request")
    def test_api_post_sucesso(self, mock_req: MagicMock, mock_authentik_response: dict) -> None:
        """POST com criação de usuário."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.text = '{"pk": 42}'
        mock_resp.json.return_value = mock_authentik_response
        mock_req.return_value = mock_resp

        result = um._authentik_api("POST", "/core/users/", {"username": "test"})
        assert result["pk"] == 42

    @patch("user_management.requests.request")
    def test_api_erro_conexao(self, mock_req: MagicMock) -> None:
        """Erro de conexão retorna dict com 'error'."""
        mock_req.side_effect = um.requests.RequestException("Connection refused")

        result = um._authentik_api("GET", "/core/users/")
        assert "error" in result
        assert "Connection refused" in result["error"]

    @patch("user_management.requests.request")
    def test_api_http_error(self, mock_req: MagicMock) -> None:
        """Erro HTTP (ex: 409) retorna dict com 'error'."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = um.requests.HTTPError("409 Conflict")
        mock_req.return_value = mock_resp

        result = um._authentik_api("POST", "/core/users/", {"username": "dup"})
        assert "error" in result


# ── Testes de list_users ──────────────────────────────────────────────────
class TestListUsers:
    """Testes da função list_users."""

    @patch("user_management._get_conn")
    def test_list_via_db(self, mock_get_conn: MagicMock) -> None:
        """Lista usuários via DB quando disponível."""
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [
            ("user1", "u1@r.com", "User 1", "complete", 10, ["users"], 5000,
             datetime(2026, 1, 1), datetime(2026, 3, 1)),
        ]
        mock_get_conn.return_value = _make_mock_conn(mock_cur)

        users = um.list_users()
        assert len(users) == 1
        assert users[0]["username"] == "user1"
        assert users[0]["status"] == "complete"

    @patch("user_management._get_conn")
    @patch("user_management._authentik_api")
    def test_list_fallback_api(self, mock_api: MagicMock, mock_conn: MagicMock, mock_user_list: list) -> None:
        """Fallback para API quando DB falha."""
        mock_conn.side_effect = Exception("DB offline")
        mock_api.return_value = {"results": mock_user_list}

        users = um.list_users()
        assert len(users) == 2
        assert users[0]["username"] == "akadmin"

    @patch("user_management._get_conn")
    @patch("user_management._authentik_api")
    def test_list_filtra_service_accounts(self, mock_api: MagicMock, mock_conn: MagicMock) -> None:
        """Ignora contas de serviço (ak-*)."""
        mock_conn.side_effect = Exception("DB offline")
        mock_api.return_value = {
            "results": [
                {"pk": 1, "username": "ak-outpost-abc", "email": "", "name": "Outpost",
                 "is_active": True, "groups_obj": [], "date_joined": "2026-01-01T00:00:00Z",
                 "last_login": None},
                {"pk": 2, "username": "real_user", "email": "r@r.com", "name": "Real",
                 "is_active": True, "groups_obj": [], "date_joined": "2026-01-01T00:00:00Z",
                 "last_login": None},
            ]
        }

        users = um.list_users()
        assert len(users) == 1
        assert users[0]["username"] == "real_user"


# ── Testes de get_user ────────────────────────────────────────────────────
class TestGetUser:
    """Testes da função get_user."""

    @patch("user_management._get_conn")
    def test_get_via_db(self, mock_get_conn: MagicMock) -> None:
        """Busca usuário pelo DB."""
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (
            "testuser", "t@r.com", "Test", "complete", 42,
            ["users"], 5000, datetime(2026, 1, 1), datetime(2026, 3, 1),
        )
        mock_get_conn.return_value = _make_mock_conn(mock_cur)

        user = um.get_user("testuser")
        assert user is not None
        assert user["username"] == "testuser"
        assert user["authentik_id"] == 42

    @patch("user_management._get_conn")
    @patch("user_management._authentik_api")
    def test_get_fallback_api(self, mock_api: MagicMock, mock_get_conn: MagicMock) -> None:
        """Fallback para API quando DB não tem o user."""
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_get_conn.return_value = _make_mock_conn(mock_cur)

        mock_api.return_value = {
            "results": [
                {"pk": 5, "username": "target", "email": "t@r.com", "name": "Target",
                 "is_active": True, "groups_obj": [{"name": "users"}],
                 "date_joined": "2026-02-01T00:00:00Z", "last_login": None},
            ]
        }

        user = um.get_user("target")
        assert user is not None
        assert user["username"] == "target"
        assert user["authentik_id"] == 5

    @patch("user_management._get_conn")
    @patch("user_management._authentik_api")
    def test_get_nao_encontrado(self, mock_api: MagicMock, mock_get_conn: MagicMock) -> None:
        """Retorna None quando user não existe."""
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_get_conn.return_value = _make_mock_conn(mock_cur)

        mock_api.return_value = {"results": []}

        user = um.get_user("inexistente")
        assert user is None


# ── Testes de pipeline assíncrono ─────────────────────────────────────────
class TestPipeline:
    """Testes do pipeline de criação de usuário."""

    @pytest.mark.asyncio
    @patch("user_management._save_user")
    @patch("user_management._step_setup_env")
    @patch("user_management._step_create_email")
    @patch("user_management._step_create_authentik")
    async def test_pipeline_sucesso(
        self,
        mock_auth: MagicMock,
        mock_email: MagicMock,
        mock_env: MagicMock,
        mock_save: MagicMock,
        user_config: UserConfig,
    ) -> None:
        """Pipeline completo com sucesso."""
        mock_auth.return_value = {"success": True, "authentik_id": 42}
        mock_email.return_value = {"success": True, "email": "t@r.com"}
        mock_env.return_value = {"success": True}

        result = await um.pipeline(user_config)

        assert result["success"] is True
        assert result["steps"]["authentik"] == "✓"
        assert result["steps"]["email"] == "✓"
        assert result["steps"]["environment"] == "✓"

    @pytest.mark.asyncio
    @patch("user_management._save_user")
    @patch("user_management._step_create_authentik")
    async def test_pipeline_falha_authentik(
        self,
        mock_auth: MagicMock,
        mock_save: MagicMock,
        user_config: UserConfig,
    ) -> None:
        """Pipeline falha no passo Authentik."""
        mock_auth.return_value = {"success": False, "error": "User already exists"}

        result = await um.pipeline(user_config)

        assert result["success"] is False
        assert "already exists" in result["error"]
        assert result["steps"]["authentik"] == "✗"

    @pytest.mark.asyncio
    @patch("user_management._save_user")
    @patch("user_management._step_create_email")
    @patch("user_management._step_create_authentik")
    async def test_pipeline_falha_email(
        self,
        mock_auth: MagicMock,
        mock_email: MagicMock,
        mock_save: MagicMock,
        user_config: UserConfig,
    ) -> None:
        """Pipeline falha no passo email."""
        mock_auth.return_value = {"success": True, "authentik_id": 42}
        mock_email.return_value = {"success": False, "error": "Postfix down"}

        result = await um.pipeline(user_config)

        assert result["success"] is False
        assert result["steps"]["authentik"] == "✓"
        assert result["steps"]["email"] == "✗"


# ── Testes de delete_user ─────────────────────────────────────────────────
class TestDeleteUser:
    """Testes da função delete_user."""

    @pytest.mark.asyncio
    @patch("user_management._get_conn")
    @patch("user_management._authentik_api")
    async def test_delete_sucesso(self, mock_api: MagicMock, mock_get_conn: MagicMock) -> None:
        """Deleta usuário com sucesso."""
        mock_api.side_effect = [
            {"results": [{"pk": 42, "username": "testuser"}]},  # GET search
            {},  # DELETE
        ]
        mock_cur = MagicMock()
        mock_get_conn.return_value = _make_mock_conn(mock_cur)

        result = await um.delete_user("testuser")
        assert result["success"] is True

    @pytest.mark.asyncio
    @patch("user_management._get_conn")
    @patch("user_management._authentik_api")
    async def test_delete_user_nao_existe(self, mock_api: MagicMock, mock_get_conn: MagicMock) -> None:
        """Deleta usuário inexistente (sem erro)."""
        mock_api.return_value = {"results": []}
        mock_cur = MagicMock()
        mock_get_conn.return_value = _make_mock_conn(mock_cur)

        result = await um.delete_user("ghost")
        assert result["success"] is True


# ── Teste de _step_create_authentik ───────────────────────────────────────
class TestStepCreateAuthentik:
    """Testes do passo de criação no Authentik."""

    @patch("user_management._authentik_api")
    def test_criacao_sucesso(self, mock_api: MagicMock, user_config: UserConfig) -> None:
        """Cria usuário com sucesso no Authentik."""
        mock_api.side_effect = [
            {"pk": 42, "username": "testuser"},  # POST create
            {"results": [{"pk": "group-uuid-1", "name": "users"}]},  # GET group search
            {"pk": 42, "groups": []},  # GET user detail
            {},  # PATCH add group
        ]

        result = um._step_create_authentik(user_config)
        assert result["success"] is True
        assert result["authentik_id"] == 42

    @patch("user_management._authentik_api")
    def test_criacao_erro_api(self, mock_api: MagicMock, user_config: UserConfig) -> None:
        """Erro na API do Authentik."""
        mock_api.return_value = {"error": "409 Conflict"}

        result = um._step_create_authentik(user_config)
        assert result["success"] is False
        assert "409" in result["error"]
