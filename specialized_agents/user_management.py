"""
Módulo de gestão de usuários com pipeline automático.

Integra Authentik API, tracking em PostgreSQL e email.
"""

import enum
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import psycopg2
import requests

from tools.authentik_management.authentik_os_login_guard import ensure_local_account

logger = logging.getLogger(__name__)

# ── Configuração ───────────────────────────────────────────────────────────
AUTHENTIK_URL = os.getenv("AUTHENTIK_URL", "http://localhost:9000")
AUTHENTIK_TOKEN = os.getenv(
    "AUTHENTIK_TOKEN", "ak-homelab-authentik-api-2026"
)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/postgres",
)
MAIL_DOMAIN = os.getenv("MAIL_DOMAIN", "rpa4all.com")
CREATE_OS_USERS = os.getenv("AUTHENTIK_OS_CREATE_LOCAL_USER", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
LOCAL_USER_SHELL = os.getenv("AUTHENTIK_OS_LOCAL_SHELL", "/bin/bash")
LOCAL_USER_GROUPS = [
    item.strip()
    for item in os.getenv("AUTHENTIK_OS_LOCAL_GROUPS", "").split(",")
    if item.strip()
]

_HEADERS = {
    "Authorization": f"Bearer {AUTHENTIK_TOKEN}",
    "Content-Type": "application/json",
}

# ── SQL para tabela de tracking ────────────────────────────────────────────
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS user_management (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(200) NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    authentik_id INTEGER,
    groups TEXT[] DEFAULT '{}',
    quota_mb INTEGER DEFAULT 5000,
    storage_quota_mb INTEGER DEFAULT 100000,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    pipeline_steps JSONB DEFAULT '{}'::jsonb,
    error_message TEXT
);
"""


# ── Enums e dataclasses ───────────────────────────────────────────────────
class UserStatus(enum.Enum):
    """Status do pipeline de criação de usuário."""

    PENDING = "pending"
    AUTHENTIK_CREATED = "authentik_created"
    EMAIL_CREATED = "email_created"
    ENV_SETUP = "env_setup"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class UserConfig:
    """Configuração para criação de usuário."""

    username: str
    email: str
    full_name: str
    password: str
    groups: list[str] = field(default_factory=lambda: ["users"])
    quota_mb: int = 5000
    storage_quota_mb: int = 100000
    create_ssh_key: bool = True
    create_folders: bool = True
    send_welcome_email: bool = True


# ── Conexão DB ─────────────────────────────────────────────────────────────
def _get_conn() -> psycopg2.extensions.connection:
    """Obtém conexão PostgreSQL com autocommit."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def _ensure_table() -> None:
    """Cria tabela de tracking se não existir."""
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
        conn.close()
    except Exception as exc:
        logger.warning(f"Não foi possível criar tabela: {exc}")


_ensure_table()


# ── Authentik API ──────────────────────────────────────────────────────────
def _authentik_api(
    method: str,
    endpoint: str,
    data: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Faz requisição à API do Authentik."""
    url = f"{AUTHENTIK_URL}/api/v3{endpoint}"
    try:
        resp = requests.request(
            method,
            url,
            json=data,
            headers=_HEADERS,
            timeout=15,
            verify=False,
        )
        resp.raise_for_status()
        return resp.json() if resp.text else {}
    except requests.RequestException as exc:
        logger.error(f"Authentik API error: {exc}")
        return {"error": str(exc)}


# ── Funções de pipeline ───────────────────────────────────────────────────
def _step_create_authentik(config: UserConfig) -> dict[str, Any]:
    """Cria usuário no Authentik."""
    payload = {
        "username": config.username,
        "email": config.email,
        "name": config.full_name,
        "is_active": True,
        "password": config.password,
    }
    result = _authentik_api("POST", "/core/users/", payload)

    if "error" in result:
        return {"success": False, "error": result["error"]}

    # Adicionar a grupos
    user_pk = result.get("pk")
    if user_pk and config.groups:
        for group_name in config.groups:
            groups_resp = _authentik_api(
                "GET", f"/core/groups/?search={group_name}"
            )
            group_results = groups_resp.get("results", [])
            if group_results:
                group_pk = group_results[0]["pk"]
                user_detail = _authentik_api("GET", f"/core/users/{user_pk}/")
                current_groups = user_detail.get("groups", [])
                if group_pk not in current_groups:
                    current_groups.append(group_pk)
                    _authentik_api(
                        "PATCH",
                        f"/core/users/{user_pk}/",
                        {"groups": current_groups},
                    )

    return {"success": True, "authentik_id": user_pk}


def _step_create_email(config: UserConfig) -> dict[str, Any]:
    """Registra email no pipeline (placeholder — Dovecot/Postfix)."""
    # TODO: Integrar com Dovecot/Postfix quando email server estiver pronto
    logger.info(f"Email step placeholder para {config.email}")
    return {"success": True, "email": config.email}


def _step_setup_env(config: UserConfig) -> dict[str, Any]:
    """Provisiona conta local do SO para usuarios gerenciados no Authentik."""
    if not CREATE_OS_USERS:
        logger.info("Criação de conta local desabilitada para %s", config.username)
        return {"success": True, "skipped": True}

    try:
        result = ensure_local_account(
            config.username,
            config.full_name,
            shell=LOCAL_USER_SHELL,
            local_groups=LOCAL_USER_GROUPS,
        )
        logger.info("Conta local preparada para %s (created=%s)", config.username, result["created"])
        return {"success": True, **result}
    except Exception as exc:
        logger.error("Falha ao preparar conta local para %s: %s", config.username, exc)
        return {"success": False, "error": str(exc)}


# ── Pipeline principal ────────────────────────────────────────────────────
async def pipeline(config: UserConfig) -> dict[str, Any]:
    """Executa o pipeline completo de criação de usuário."""
    steps: dict[str, str] = {}
    authentik_id: Optional[int] = None

    try:
        # 1. Authentik
        result = _step_create_authentik(config)
        if not result["success"]:
            steps["authentik"] = "✗"
            _save_user(config, UserStatus.FAILED, steps, error=result["error"])
            return {"success": False, "error": result["error"], "steps": steps}
        steps["authentik"] = "✓"
        authentik_id = result.get("authentik_id")
        _save_user(config, UserStatus.AUTHENTIK_CREATED, steps, authentik_id=authentik_id)

        # 2. Email
        result = _step_create_email(config)
        if not result["success"]:
            steps["email"] = "✗"
            _save_user(config, UserStatus.FAILED, steps, authentik_id=authentik_id, error=result.get("error"))
            return {"success": False, "error": result.get("error", "Email step failed"), "steps": steps}
        steps["email"] = "✓"
        _save_user(config, UserStatus.EMAIL_CREATED, steps, authentik_id=authentik_id)

        # 3. Environment
        result = _step_setup_env(config)
        if not result["success"]:
            steps["environment"] = "✗"
            _save_user(config, UserStatus.FAILED, steps, authentik_id=authentik_id, error=result.get("error"))
            return {"success": False, "error": result.get("error", "Env step failed"), "steps": steps}
        steps["environment"] = "✓"

        # 4. Completo
        _save_user(config, UserStatus.COMPLETE, steps, authentik_id=authentik_id)
        return {"success": True, "steps": steps}

    except Exception as exc:
        logger.exception("Pipeline error")
        return {"success": False, "error": str(exc), "steps": steps}


async def create_user(config: UserConfig) -> dict[str, Any]:
    """Cria usuário pelo pipeline completo."""
    return await pipeline(config)


async def delete_user(username: str) -> dict[str, Any]:
    """Remove usuário do Authentik e do tracking."""
    try:
        # Buscar no Authentik
        users_resp = _authentik_api("GET", f"/core/users/?search={username}")
        results = users_resp.get("results", [])
        target = next((u for u in results if u["username"] == username), None)

        if target:
            _authentik_api("DELETE", f"/core/users/{target['pk']}/")

        # Remover do tracking
        try:
            conn = _get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM user_management WHERE username = %s",
                    (username,),
                )
            conn.close()
        except Exception as db_err:
            logger.warning(f"DB delete warning: {db_err}")

        return {"success": True}
    except Exception as exc:
        logger.error(f"Delete user error: {exc}")
        return {"success": False, "error": str(exc)}


# ── Funções de consulta ───────────────────────────────────────────────────
def list_users() -> list[dict[str, Any]]:
    """Lista todos os usuários do tracking DB + Authentik."""
    users: list[dict[str, Any]] = []

    # Tentar buscar do DB primeiro
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username, email, full_name, status, authentik_id, "
                "groups, quota_mb, created_at, updated_at "
                "FROM user_management ORDER BY created_at DESC"
            )
            for row in cur.fetchall():
                users.append({
                    "username": row[0],
                    "email": row[1],
                    "full_name": row[2],
                    "status": row[3],
                    "authentik_id": row[4],
                    "groups": row[5] or [],
                    "quota_mb": row[6],
                    "created_at": row[7],
                    "updated_at": row[8],
                })
        conn.close()
        if users:
            return users
    except Exception as exc:
        logger.warning(f"DB list fallback: {exc}")

    # Fallback: Authentik API
    try:
        resp = _authentik_api("GET", "/core/users/?format=json")
        for u in resp.get("results", []):
            # Ignorar service accounts
            if u.get("username", "").startswith("ak-"):
                continue
            users.append({
                "username": u["username"],
                "email": u.get("email", ""),
                "full_name": u.get("name", ""),
                "status": UserStatus.COMPLETE.value,
                "authentik_id": u.get("pk"),
                "groups": [g.get("name", "") for g in u.get("groups_obj", [])],
                "quota_mb": 5000,
                "created_at": u.get("date_joined", datetime.now().isoformat()),
                "updated_at": u.get("last_login") or u.get("date_joined", datetime.now().isoformat()),
            })
    except Exception as exc:
        logger.error(f"Authentik list error: {exc}")

    return users


def get_user(username: str) -> Optional[dict[str, Any]]:
    """Busca usuário pelo username."""
    # Tentar DB
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username, email, full_name, status, authentik_id, "
                "groups, quota_mb, created_at, updated_at "
                "FROM user_management WHERE username = %s",
                (username,),
            )
            row = cur.fetchone()
            if row:
                conn.close()
                return {
                    "username": row[0],
                    "email": row[1],
                    "full_name": row[2],
                    "status": row[3],
                    "authentik_id": row[4],
                    "groups": row[5] or [],
                    "quota_mb": row[6],
                    "created_at": row[7],
                    "updated_at": row[8],
                }
        conn.close()
    except Exception as exc:
        logger.warning(f"DB get fallback: {exc}")

    # Fallback: Authentik
    try:
        resp = _authentik_api("GET", f"/core/users/?search={username}")
        for u in resp.get("results", []):
            if u["username"] == username:
                return {
                    "username": u["username"],
                    "email": u.get("email", ""),
                    "full_name": u.get("name", ""),
                    "status": UserStatus.COMPLETE.value,
                    "authentik_id": u.get("pk"),
                    "groups": [g.get("name", "") for g in u.get("groups_obj", [])],
                    "quota_mb": 5000,
                    "created_at": u.get("date_joined", datetime.now().isoformat()),
                    "updated_at": u.get("last_login") or u.get("date_joined", datetime.now().isoformat()),
                }
    except Exception as exc:
        logger.error(f"Authentik get error: {exc}")

    return None


# ── DB helper ──────────────────────────────────────────────────────────────
def _save_user(
    config: UserConfig,
    status: UserStatus,
    steps: dict[str, str],
    *,
    authentik_id: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    """Salva ou atualiza usuário no tracking DB."""
    import json

    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_management
                    (username, email, full_name, status, authentik_id,
                     groups, quota_mb, storage_quota_mb, pipeline_steps, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (username) DO UPDATE SET
                    status = EXCLUDED.status,
                    authentik_id = COALESCE(EXCLUDED.authentik_id, user_management.authentik_id),
                    pipeline_steps = EXCLUDED.pipeline_steps,
                    error_message = EXCLUDED.error_message,
                    updated_at = NOW()
                """,
                (
                    config.username,
                    config.email,
                    config.full_name,
                    status.value,
                    authentik_id,
                    config.groups,
                    config.quota_mb,
                    config.storage_quota_mb,
                    json.dumps(steps),
                    error,
                ),
            )
        conn.close()
    except Exception as exc:
        logger.warning(f"Erro ao salvar tracking: {exc}")
