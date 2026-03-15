"""Portal de gerenciamento para contratos de storage."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import platform
import re
import secrets
import shutil
import string
import subprocess
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import requests
from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile
from googleapiclient.discovery import build
from pydantic import BaseModel

from specialized_agents.gmail_credentials import load_gmail_credentials
from tools.secrets_agent_client import get_secrets_agent_client

logger = logging.getLogger(__name__)

router = APIRouter()

AUTHENTIK_URL = os.getenv("AUTHENTIK_URL", "https://auth.rpa4all.com").rstrip("/")
AUTHENTIK_TOKEN = os.getenv("AUTHENTIK_TOKEN", "ak-homelab-authentik-api-2026")
STORAGE_ACCESS_LOGIN_URL = os.getenv("STORAGE_ACCESS_LOGIN_URL", "https://auth.rpa4all.com/")
STORAGE_ACCESS_FROM_EMAIL = os.getenv("STORAGE_ACCESS_FROM_EMAIL", "edenilson.teixeira@rpa4all.com")
STORAGE_ACCESS_FROM_NAME = os.getenv("STORAGE_ACCESS_FROM_NAME", "RPA4ALL Storage")
STORAGE_ACCESS_GMAIL_SECRET_NAME = os.getenv("STORAGE_ACCESS_GMAIL_SECRET_NAME", "google/gmail_token_rpa4all")
STORAGE_ACCESS_GMAIL_FALLBACK_SECRET = os.getenv("STORAGE_ACCESS_GMAIL_FALLBACK_SECRET", "google/gmail_token")
STORAGE_ACCESS_GROUPS = [
    item.strip() for item in os.getenv("STORAGE_ACCESS_GROUPS", "users").split(",") if item.strip()
]
STORAGE_PORTAL_URL = os.getenv("STORAGE_PORTAL_URL", "https://www.rpa4all.com/storage-portal.html")
STORAGE_PORTAL_API_BASE = os.getenv("STORAGE_PORTAL_API_BASE", "https://api.rpa4all.com/agents-api").rstrip("/")
STORAGE_NEXTCLOUD_URL = os.getenv("STORAGE_NEXTCLOUD_URL", "https://nextcloud.rpa4all.com").rstrip("/")
STORAGE_WORKSPACE_ROOT = Path(
    os.getenv("STORAGE_WORKSPACE_ROOT", "/mnt/raid1/nextcloud-external/RPA4ALL/Portal_Storage")
)
STORAGE_PAYMENT_RETURN_URL = os.getenv("STORAGE_PAYMENT_RETURN_URL", STORAGE_PORTAL_URL)
STORAGE_PAYMENT_WEBHOOK_URL = os.getenv("STORAGE_PAYMENT_WEBHOOK_URL", "").strip()
STORAGE_MERCADOPAGO_TOKEN_SECRET = os.getenv("STORAGE_MERCADOPAGO_TOKEN_SECRET", "mercadopago-access-token")
STORAGE_MERCADOPAGO_PUBLIC_KEY_SECRET = os.getenv(
    "STORAGE_MERCADOPAGO_PUBLIC_KEY_SECRET", "mercadopago-public-key"
)
STORAGE_PORTAL_INVENTORY_TTL_SECONDS = int(os.getenv("STORAGE_PORTAL_INVENTORY_TTL_SECONDS", "60"))

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PATH_SANITIZE_PATTERN = re.compile(r"[^a-zA-Z0-9._-]+")
USERNAME_SANITIZE_PATTERN = re.compile(r"[^a-z0-9]+")
_TABLES_READY = False
_INVENTORY_CACHE: dict[str, Any] = {"expires": 0.0, "payload": None}

PROFILE_CAPABILITIES = {
    "manager": {
        "manage_users": True,
        "manage_profiles": True,
        "generate_tokens": True,
        "manage_payments": True,
        "upload_files": True,
        "view_inventory": True,
    },
    "operations": {
        "manage_users": False,
        "manage_profiles": False,
        "generate_tokens": False,
        "manage_payments": False,
        "upload_files": True,
        "view_inventory": True,
    },
    "api": {
        "manage_users": False,
        "manage_profiles": False,
        "generate_tokens": False,
        "manage_payments": False,
        "upload_files": True,
        "view_inventory": False,
    },
    "readonly": {
        "manage_users": False,
        "manage_profiles": False,
        "generate_tokens": False,
        "manage_payments": False,
        "upload_files": False,
        "view_inventory": True,
    },
}

PROFILE_LABELS = {
    "manager": "Gestor",
    "operations": "Operações",
    "api": "Integração API",
    "readonly": "Somente leitura",
}

PROFILE_GROUP_MAP = {
    "manager": STORAGE_ACCESS_GROUPS + ["Nextcloud Users"],
    "operations": STORAGE_ACCESS_GROUPS + ["Nextcloud Users"],
    "api": STORAGE_ACCESS_GROUPS,
    "readonly": STORAGE_ACCESS_GROUPS,
}

_CREATE_STORAGE_PORTAL_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS storage_contracts (
    id VARCHAR(64) PRIMARY KEY,
    contract_code VARCHAR(64) UNIQUE NOT NULL,
    company VARCHAR(255) NOT NULL,
    legal_name VARCHAR(255),
    project VARCHAR(255) NOT NULL,
    mode VARCHAR(32) NOT NULL DEFAULT 'sizing',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    owner_username VARCHAR(128),
    owner_authentik_id INTEGER,
    primary_email VARCHAR(255) NOT NULL,
    primary_contact VARCHAR(255) NOT NULL,
    primary_role VARCHAR(255),
    primary_phone VARCHAR(64),
    temperature VARCHAR(32),
    volume_tb DOUBLE PRECISION NOT NULL DEFAULT 0,
    ingress_tb DOUBLE PRECISION NOT NULL DEFAULT 0,
    retention VARCHAR(32),
    retrieval VARCHAR(32),
    sla VARCHAR(32),
    compliance VARCHAR(64),
    redundancy VARCHAR(32),
    billing VARCHAR(32),
    term_months INTEGER NOT NULL DEFAULT 12,
    monthly_service DOUBLE PRECISION NOT NULL DEFAULT 0,
    setup_fee DOUBLE PRECISION NOT NULL DEFAULT 0,
    contract_value DOUBLE PRECISION NOT NULL DEFAULT 0,
    notice_days INTEGER NOT NULL DEFAULT 0,
    breach_penalty DOUBLE PRECISION NOT NULL DEFAULT 0,
    start_date DATE,
    city VARCHAR(128),
    state VARCHAR(16),
    notes TEXT,
    workspace_path TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS storage_contract_users (
    id SERIAL PRIMARY KEY,
    contract_id VARCHAR(64) NOT NULL REFERENCES storage_contracts(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    username VARCHAR(128) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    profile VARCHAR(32) NOT NULL DEFAULT 'readonly',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    is_manager BOOLEAN NOT NULL DEFAULT FALSE,
    portal_token_hash VARCHAR(128) NOT NULL,
    authentik_id INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(contract_id, email),
    UNIQUE(contract_id, username)
);

CREATE TABLE IF NOT EXISTS storage_api_tokens (
    id SERIAL PRIMARY KEY,
    contract_id VARCHAR(64) NOT NULL REFERENCES storage_contracts(id) ON DELETE CASCADE,
    label VARCHAR(128) NOT NULL,
    token_hash VARCHAR(128) NOT NULL UNIQUE,
    token_preview VARCHAR(24) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_by_email VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS storage_payment_links (
    id SERIAL PRIMARY KEY,
    contract_id VARCHAR(64) NOT NULL REFERENCES storage_contracts(id) ON DELETE CASCADE,
    amount_brl DOUBLE PRECISION NOT NULL,
    description TEXT NOT NULL,
    payer_email VARCHAR(255),
    preference_id VARCHAR(128),
    init_point TEXT,
    sandbox_init_point TEXT,
    external_reference VARCHAR(128),
    status VARCHAR(32) NOT NULL DEFAULT 'created',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS storage_ingest_events (
    id SERIAL PRIMARY KEY,
    contract_id VARCHAR(64) NOT NULL REFERENCES storage_contracts(id) ON DELETE CASCADE,
    token_id INTEGER REFERENCES storage_api_tokens(id) ON DELETE SET NULL,
    user_id INTEGER REFERENCES storage_contract_users(id) ON DELETE SET NULL,
    protocol VARCHAR(32) NOT NULL,
    relative_path TEXT NOT NULL,
    bytes BIGINT NOT NULL DEFAULT 0,
    checksum VARCHAR(255),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


class PortalTokenCreateRequest(BaseModel):
    portal_token: str
    label: str = "API token"


class PortalSubUserRequest(BaseModel):
    portal_token: str
    email: str
    full_name: str
    profile: str = "readonly"
    send_email: bool = True


class PortalProfileUpdateRequest(BaseModel):
    portal_token: str
    profile: str | None = None
    status: str | None = None


class PortalPaymentLinkRequest(BaseModel):
    portal_token: str
    amount_brl: float
    description: str
    payer_email: str | None = None


class PortalFolderCreateRequest(BaseModel):
    portal_token: str
    folder_path: str


class StorageIngestRequest(BaseModel):
    relative_path: str
    bytes: int = 0
    checksum: str = ""
    protocol: str = "api"
    metadata: dict[str, Any] = {}


def _hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _slugify(value: str) -> str:
    normalized = USERNAME_SANITIZE_PATTERN.sub("-", value.lower()).strip("-")
    return normalized[:48] or "storage-client"


def _safe_name(value: str) -> str:
    cleaned = PATH_SANITIZE_PATTERN.sub("-", value.strip()).strip("-._")
    return cleaned or "workspace"


def _generate_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "@#_-!"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(char.islower() for char in password)
            and any(char.isupper() for char in password)
            and any(char.isdigit() for char in password)
        ):
            return password


def _contract_code() -> str:
    return f"STR-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"


def _portal_token() -> str:
    return f"stp_{secrets.token_urlsafe(24)}"


def _api_token() -> str:
    return f"stg_live_{secrets.token_urlsafe(28)}"


def _workspace_path(contract_code: str) -> Path:
    return STORAGE_WORKSPACE_ROOT / contract_code


def _workspace_relative_dir(contract_code: str) -> str:
    return f"Portal_Storage/{contract_code}"


def _portal_url(token: str) -> str:
    separator = "&" if "?" in STORAGE_PORTAL_URL else "?"
    return f"{STORAGE_PORTAL_URL}{separator}portal={token}"


def _validate_profile(profile: str) -> str:
    normalized = (profile or "").strip().lower()
    if normalized not in PROFILE_CAPABILITIES:
        raise HTTPException(status_code=400, detail="Perfil inválido.")
    return normalized


def _validate_status(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized not in {"active", "disabled"}:
        raise HTTPException(status_code=400, detail="Status inválido.")
    return normalized


def _authentik_request(method: str, endpoint: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.request(
        method,
        f"{AUTHENTIK_URL}/api/v3{endpoint}",
        json=data,
        headers={
            "Authorization": f"Bearer {AUTHENTIK_TOKEN}",
            "Content-Type": "application/json",
        },
        timeout=20,
        verify=False,
    )
    response.raise_for_status()
    return response.json() if response.text else {}


def _resolve_group_ids(group_names: list[str]) -> list[int]:
    group_ids: list[int] = []
    for group_name in group_names:
        try:
            result = _authentik_request("GET", f"/core/groups/?search={group_name}")
        except Exception as exc:
            logger.warning("Falha ao buscar grupo %s no Authentik: %s", group_name, exc)
            continue
        for group in result.get("results", []):
            if group.get("name") == group_name:
                group_ids.append(group["pk"])
                break
    return group_ids


def _create_authentik_user(email: str, full_name: str, profile: str) -> tuple[dict[str, Any], str]:
    username = "-".join(
        part for part in (_slugify(full_name)[:16], _slugify(email.split("@", 1)[0])[:16], secrets.token_hex(2))
        if part
    )[:64]
    password = _generate_password()
    created = _authentik_request(
        "POST",
        "/core/users/",
        {
            "username": username,
            "email": email.strip(),
            "name": full_name.strip(),
            "is_active": True,
            "password": password,
        },
    )
    user_pk = created.get("pk")
    group_ids = _resolve_group_ids(PROFILE_GROUP_MAP.get(profile, STORAGE_ACCESS_GROUPS))
    if user_pk and group_ids:
        _authentik_request("PATCH", f"/core/users/{user_pk}/", {"groups": group_ids})
    return created, password


def _update_authentik_user(authentik_id: int, profile: str | None = None, status: str | None = None) -> None:
    payload: dict[str, Any] = {}
    if profile:
        payload["groups"] = _resolve_group_ids(PROFILE_GROUP_MAP.get(profile, STORAGE_ACCESS_GROUPS))
    if status:
        payload["is_active"] = status == "active"
    if payload:
        _authentik_request("PATCH", f"/core/users/{authentik_id}/", payload)


def _delete_authentik_user(authentik_id: int) -> None:
    try:
        _authentik_request("DELETE", f"/core/users/{authentik_id}/")
    except Exception as exc:
        logger.warning("Falha ao remover usuário %s no Authentik: %s", authentik_id, exc)


def _get_gmail_credentials():
    return load_gmail_credentials(
        [
            STORAGE_ACCESS_GMAIL_SECRET_NAME,
            STORAGE_ACCESS_GMAIL_FALLBACK_SECRET,
        ]
    )


def _send_email_message(message: EmailMessage) -> str:
    creds = _get_gmail_credentials()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    result = service.users().messages().send(userId="me", body={"raw": encoded_message}).execute()
    return result.get("id", "")


def _build_user_email_message(
    recipient_email: str,
    full_name: str,
    username: str,
    temporary_password: str,
    contract_code: str,
    portal_url: str,
    profile: str,
    workspace_relative_dir: str,
) -> EmailMessage:
    subject = f"RPA4ALL | Acesso ao portal de storage {contract_code}"
    profile_label = PROFILE_LABELS.get(profile, profile.title())
    text_body = "\n".join(
        [
            f"Olá {full_name},",
            "",
            "Seu acesso ao portal de storage da RPA4ALL foi liberado.",
            f"Contrato guarda-chuva: {contract_code}",
            f"Perfil: {profile_label}",
            "",
            f"Login Authentik: {username}",
            f"Senha temporária: {temporary_password}",
            f"Portal de login: {STORAGE_ACCESS_LOGIN_URL}",
            f"Portal de gestão: {portal_url}",
            f"Nextcloud: {STORAGE_NEXTCLOUD_URL}",
            f"Workspace: {workspace_relative_dir}",
            "",
            "Altere a senha no primeiro acesso.",
            "",
            "RPA4ALL",
        ]
    )

    html_body = """\
<html>
  <body style="font-family: Inter, Arial, sans-serif; color: #0f172a;">
    <p>Olá <strong>{full_name}</strong>,</p>
    <p>Seu acesso ao portal de storage da RPA4ALL foi liberado.</p>
    <div style="padding: 16px; border-radius: 12px; background: #e2f3ff; margin: 16px 0;">
      <p style="margin: 0 0 8px;"><strong>Contrato:</strong> {contract_code}</p>
      <p style="margin: 0 0 8px;"><strong>Perfil:</strong> {profile_label}</p>
      <p style="margin: 0 0 8px;"><strong>Login:</strong> {username}</p>
      <p style="margin: 0 0 8px;"><strong>Senha temporária:</strong> {temporary_password}</p>
      <p style="margin: 0 0 8px;"><strong>Portal de login:</strong> <a href="{login_url}">{login_url}</a></p>
      <p style="margin: 0;"><strong>Portal de gestão:</strong> <a href="{portal_url}">{portal_url}</a></p>
    </div>
    <ul>
      <li>Nextcloud: <a href="{nextcloud_url}">{nextcloud_url}</a></li>
      <li>Workspace: {workspace_relative_dir}</li>
    </ul>
    <p>Altere a senha no primeiro acesso.</p>
    <p>RPA4ALL</p>
  </body>
</html>
""".format(
        full_name=full_name,
        contract_code=contract_code,
        profile_label=profile_label,
        username=username,
        temporary_password=temporary_password,
        login_url=STORAGE_ACCESS_LOGIN_URL,
        portal_url=portal_url,
        nextcloud_url=STORAGE_NEXTCLOUD_URL,
        workspace_relative_dir=workspace_relative_dir,
    )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{STORAGE_ACCESS_FROM_NAME} <{STORAGE_ACCESS_FROM_EMAIL}>"
    message["To"] = recipient_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    return message


def _get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL não configurada para o portal de storage.")
    return database_url


def _ensure_tables() -> None:
    global _TABLES_READY
    if _TABLES_READY:
        return

    database_url = _get_database_url()
    try:
        import psycopg2

        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(_CREATE_STORAGE_PORTAL_TABLES_SQL)
        _TABLES_READY = True
    except Exception as exc:
        raise RuntimeError(f"Falha ao preparar tabelas do portal de storage: {exc}") from exc


def _db_fetchone(sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    _ensure_tables()
    import psycopg2
    from psycopg2.extras import RealDictCursor

    with psycopg2.connect(_get_database_url()) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
    return dict(row) if row else None


def _db_fetchall(sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    _ensure_tables()
    import psycopg2
    from psycopg2.extras import RealDictCursor

    with psycopg2.connect(_get_database_url()) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def _db_execute(sql: str, params: tuple[Any, ...]) -> None:
    _ensure_tables()
    import psycopg2

    with psycopg2.connect(_get_database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)


def _safe_workspace(contract_code: str) -> Path:
    base = _workspace_path(contract_code).resolve()
    root = STORAGE_WORKSPACE_ROOT.resolve()
    if root not in base.parents and base != root:
        raise RuntimeError("Workspace fora da raiz configurada.")
    return base


def _sanitize_relative_path(relative_path: str) -> Path:
    candidate = Path(relative_path.strip() or ".")
    if candidate.is_absolute():
        raise HTTPException(status_code=400, detail="Caminho absoluto não é permitido.")

    resolved_parts: list[str] = []
    for part in candidate.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            raise HTTPException(status_code=400, detail="Caminho inválido.")
        safe = _safe_name(part)
        resolved_parts.append(safe)

    return Path(*resolved_parts) if resolved_parts else Path(".")


def _ensure_workspace(contract_code: str) -> Path:
    workspace = _safe_workspace(contract_code)
    workspace.mkdir(parents=True, exist_ok=True)
    readme = workspace / "README-RPA4ALL.txt"
    if not readme.exists():
        readme.write_text(
            "\n".join(
                [
                    "Workspace provisionado pela RPA4ALL.",
                    f"Contrato: {contract_code}",
                    "Esta pasta pode ser acessada pelo portal, API de ingest e Nextcloud.",
                ]
            )
        )
    return workspace


def create_contract_bundle(
    payload: dict[str, Any],
    owner_username: str,
    owner_authentik_id: int | None,
) -> dict[str, Any]:
    contract_id = f"ctr_{secrets.token_hex(12)}"
    contract_code = _contract_code()
    manager_token = _portal_token()
    workspace = _ensure_workspace(contract_code)

    _db_execute(
        """
        INSERT INTO storage_contracts (
            id, contract_code, company, legal_name, project, mode, status,
            owner_username, owner_authentik_id, primary_email, primary_contact, primary_role, primary_phone,
            temperature, volume_tb, ingress_tb, retention, retrieval, sla, compliance, redundancy, billing,
            term_months, monthly_service, setup_fee, contract_value, notice_days, breach_penalty,
            start_date, city, state, notes, workspace_path
        ) VALUES (%s, %s, %s, %s, %s, %s, 'active', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            contract_id,
            contract_code,
            (payload.get("company") or "").strip(),
            (payload.get("legal_name") or "").strip(),
            (payload.get("project") or "").strip(),
            (payload.get("mode") or "sizing").strip(),
            owner_username,
            owner_authentik_id,
            (payload.get("email") or "").strip().lower(),
            (payload.get("contact") or "").strip(),
            (payload.get("role") or "").strip(),
            (payload.get("phone") or "").strip(),
            (payload.get("temperature") or "warm").strip(),
            float(payload.get("volume") or 0),
            float(payload.get("ingress") or 0),
            (payload.get("retention") or "12").strip(),
            (payload.get("retrieval") or "rare").strip(),
            (payload.get("sla") or "24h").strip(),
            (payload.get("compliance") or "standard").strip(),
            (payload.get("redundancy") or "single").strip(),
            (payload.get("billing") or "monthly").strip(),
            int(payload.get("term") or 12),
            float(payload.get("monthly_service") or 0),
            float(payload.get("setup_fee") or 0),
            float(payload.get("contract_value") or 0),
            int(payload.get("notice_days") or 0),
            float(payload.get("breach_penalty") or 0),
            payload.get("start_date"),
            (payload.get("city") or "").strip(),
            (payload.get("state") or "").strip().upper(),
            (payload.get("notes") or "").strip(),
            str(workspace),
        ),
    )

    _db_execute(
        """
        INSERT INTO storage_contract_users (
            contract_id, email, username, full_name, profile, status, is_manager, portal_token_hash, authentik_id
        ) VALUES (%s, %s, %s, %s, 'manager', 'active', TRUE, %s, %s)
        """,
        (
            contract_id,
            (payload.get("email") or "").strip().lower(),
            owner_username,
            (payload.get("contact") or "").strip() or (payload.get("company") or "").strip(),
            _hash_secret(manager_token),
            owner_authentik_id,
        ),
    )

    return {
        "contract_id": contract_id,
        "contract_code": contract_code,
        "workspace_path": str(workspace),
        "workspace_relative_dir": _workspace_relative_dir(contract_code),
        "portal_token": manager_token,
        "portal_url": _portal_url(manager_token),
    }


def rollback_contract_bundle(contract_id: str) -> None:
    try:
        _db_execute("DELETE FROM storage_contracts WHERE id = %s", (contract_id,))
    except Exception as exc:
        logger.warning("Falha ao reverter contrato %s: %s", contract_id, exc)


def _get_portal_session(portal_token: str) -> dict[str, Any]:
    token = (portal_token or "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Portal token é obrigatório.")

    session = _db_fetchone(
        """
        SELECT
            c.*,
            u.id AS user_id,
            u.email AS user_email,
            u.username AS user_username,
            u.full_name AS user_full_name,
            u.profile AS user_profile,
            u.status AS user_status,
            u.is_manager AS user_is_manager,
            u.authentik_id AS user_authentik_id
        FROM storage_contract_users u
        JOIN storage_contracts c ON c.id = u.contract_id
        WHERE u.portal_token_hash = %s AND u.status = 'active' AND c.status = 'active'
        """,
        (_hash_secret(token),),
    )
    if not session:
        raise HTTPException(status_code=401, detail="Portal token inválido ou expirado.")
    session["portal_token"] = token
    return session


def _require_manager_session(portal_token: str) -> dict[str, Any]:
    session = _get_portal_session(portal_token)
    if not session.get("user_is_manager"):
        raise HTTPException(status_code=403, detail="Ação disponível apenas para o gestor do contrato.")
    return session


def _mask_tokens(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    masked: list[dict[str, Any]] = []
    for row in rows:
        masked.append(
            {
                "id": row["id"],
                "label": row["label"],
                "preview": row["token_preview"],
                "status": row["status"],
                "created_by_email": row.get("created_by_email"),
                "created_at": row.get("created_at"),
                "last_used_at": row.get("last_used_at"),
            }
        )
    return masked


def _list_contract_users(contract_id: str) -> list[dict[str, Any]]:
    rows = _db_fetchall(
        """
        SELECT id, email, username, full_name, profile, status, is_manager, created_at
        FROM storage_contract_users
        WHERE contract_id = %s
        ORDER BY is_manager DESC, created_at ASC
        """,
        (contract_id,),
    )
    for row in rows:
        row["profile_label"] = PROFILE_LABELS.get(row["profile"], row["profile"])
    return rows


def _list_contract_tokens(contract_id: str) -> list[dict[str, Any]]:
    rows = _db_fetchall(
        """
        SELECT id, label, token_preview, status, created_by_email, created_at, last_used_at
        FROM storage_api_tokens
        WHERE contract_id = %s
        ORDER BY created_at DESC
        """,
        (contract_id,),
    )
    return _mask_tokens(rows)


def _list_contract_payments(contract_id: str) -> list[dict[str, Any]]:
    return _db_fetchall(
        """
        SELECT id, amount_brl, description, payer_email, preference_id, init_point, sandbox_init_point, external_reference, status, created_at
        FROM storage_payment_links
        WHERE contract_id = %s
        ORDER BY created_at DESC
        """,
        (contract_id,),
    )


def _list_contract_ingest_events(contract_id: str) -> list[dict[str, Any]]:
    return _db_fetchall(
        """
        SELECT id, protocol, relative_path, bytes, checksum, metadata, created_at
        FROM storage_ingest_events
        WHERE contract_id = %s
        ORDER BY created_at DESC
        LIMIT 25
        """,
        (contract_id,),
    )


def _workspace_listing(contract_code: str, relative_path: str = ".") -> dict[str, Any]:
    workspace = _ensure_workspace(contract_code)
    relative = _sanitize_relative_path(relative_path)
    current = (workspace / relative).resolve()
    if workspace.resolve() not in current.parents and current != workspace.resolve():
        raise HTTPException(status_code=400, detail="Caminho fora do workspace.")
    if not current.exists():
        raise HTTPException(status_code=404, detail="Diretório não encontrado.")
    if not current.is_dir():
        raise HTTPException(status_code=400, detail="O caminho informado não é um diretório.")

    items = []
    total_bytes = 0
    total_files = 0
    for entry in sorted(current.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
        stat = entry.stat()
        is_file = entry.is_file()
        size = stat.st_size if is_file else 0
        if is_file:
            total_bytes += size
            total_files += 1
        relative_entry = entry.relative_to(workspace).as_posix()
        items.append(
            {
                "name": entry.name,
                "path": relative_entry,
                "kind": "file" if is_file else "folder",
                "size": size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
        )

    return {
        "path": "." if relative == Path(".") else relative.as_posix(),
        "entries": items,
        "total_files": total_files,
        "total_bytes": total_bytes,
        "workspace_path": str(workspace),
    }


def _service_status_snapshot() -> list[dict[str, Any]]:
    try:
        completed = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}|{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except Exception:
        return []

    services = []
    interesting = {"nextcloud", "authentik-server", "authentik-worker", "grafana", "open-webui", "storagenode"}
    for line in completed.stdout.splitlines():
        if "|" not in line:
            continue
        name, status = line.split("|", 1)
        if name in interesting:
            services.append({"name": name, "status": status})
    return services


def _read_meminfo() -> dict[str, float]:
    values: dict[str, float] = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                key, _, value = line.partition(":")
                raw = value.strip().split()[0]
                if raw.isdigit():
                    values[key] = round(int(raw) / 1024 / 1024, 2)
    except Exception:
        pass
    return values


def _inventory_snapshot() -> dict[str, Any]:
    now = time.time()
    cached = _INVENTORY_CACHE.get("payload")
    if cached and _INVENTORY_CACHE.get("expires", 0) > now:
        return cached

    disks = []
    for mountpoint in [Path("/"), STORAGE_WORKSPACE_ROOT]:
        try:
            usage = shutil.disk_usage(mountpoint)
            disks.append(
                {
                    "mountpoint": str(mountpoint),
                    "total_gb": round(usage.total / 1024 / 1024 / 1024, 1),
                    "used_gb": round(usage.used / 1024 / 1024 / 1024, 1),
                    "free_gb": round(usage.free / 1024 / 1024 / 1024, 1),
                }
            )
        except Exception:
            continue

    meminfo = _read_meminfo()
    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "platform": platform.platform(),
        "cpu": {
            "cores": os.cpu_count() or 0,
            "model": platform.processor() or platform.machine(),
        },
        "memory": {
            "total_gb": round(meminfo.get("MemTotal", 0), 2),
            "available_gb": round(meminfo.get("MemAvailable", 0), 2),
            "swap_total_gb": round(meminfo.get("SwapTotal", 0), 2),
            "swap_free_gb": round(meminfo.get("SwapFree", 0), 2),
        },
        "disks": disks,
        "services": _service_status_snapshot(),
        "reused_stack": [
            "Authentik para identidade e subusuários",
            "Nextcloud para workspace e navegação de arquivos",
            "Specialized Agents API para token, ingest e painel",
            "Mercado Pago para link de cobrança",
        ],
    }
    _INVENTORY_CACHE["payload"] = payload
    _INVENTORY_CACHE["expires"] = now + STORAGE_PORTAL_INVENTORY_TTL_SECONDS
    return payload


def _build_connection_info(session: dict[str, Any]) -> dict[str, Any]:
    contract_code = session["contract_code"]
    workspace_relative_dir = _workspace_relative_dir(contract_code)
    return {
        "api_base": STORAGE_PORTAL_API_BASE,
        "ingest_endpoint": f"{STORAGE_PORTAL_API_BASE}/storage/ingest",
        "portal_url": _portal_url(session["portal_token"]),
        "nextcloud_url": STORAGE_NEXTCLOUD_URL,
        "authentik_url": STORAGE_ACCESS_LOGIN_URL,
        "workspace_relative_dir": workspace_relative_dir,
        "workspace_host_path": session["workspace_path"],
        "nextcloud_hint": f"Abra {STORAGE_NEXTCLOUD_URL} e navegue até {workspace_relative_dir}",
        "curl_example": "\n".join(
            [
                "curl -X POST \\",
                f"  '{STORAGE_PORTAL_API_BASE}/storage/ingest' \\",
                "  -H 'Authorization: Bearer <API_TOKEN>' \\",
                "  -H 'Content-Type: application/json' \\",
                "  -d '{\"relative_path\":\"lote-01/backup.tar\",\"bytes\":1073741824,\"checksum\":\"sha256:...\",\"protocol\":\"api\",\"metadata\":{\"source\":\"agent\"}}'",
            ]
        ),
        "upload_hint": "Para arquivos maiores, use o portal ou sincronize a pasta pelo cliente Nextcloud.",
    }


def _build_bootstrap(session: dict[str, Any]) -> dict[str, Any]:
    permissions = PROFILE_CAPABILITIES.get(session["user_profile"], PROFILE_CAPABILITIES["readonly"])
    listing = _workspace_listing(session["contract_code"])
    return {
        "current_user": {
            "id": session["user_id"],
            "email": session["user_email"],
            "username": session["user_username"],
            "full_name": session["user_full_name"],
            "profile": session["user_profile"],
            "profile_label": PROFILE_LABELS.get(session["user_profile"], session["user_profile"]),
            "is_manager": bool(session["user_is_manager"]),
        },
        "permissions": permissions,
        "contract": {
            "id": session["id"],
            "contract_code": session["contract_code"],
            "company": session["company"],
            "legal_name": session.get("legal_name") or session["company"],
            "project": session["project"],
            "mode": session["mode"],
            "status": session["status"],
            "temperature": session.get("temperature"),
            "volume_tb": session.get("volume_tb"),
            "ingress_tb": session.get("ingress_tb"),
            "retention": session.get("retention"),
            "retrieval": session.get("retrieval"),
            "sla": session.get("sla"),
            "compliance": session.get("compliance"),
            "redundancy": session.get("redundancy"),
            "billing": session.get("billing"),
            "term_months": session.get("term_months"),
            "monthly_service": session.get("monthly_service"),
            "setup_fee": session.get("setup_fee"),
            "contract_value": session.get("contract_value"),
            "notice_days": session.get("notice_days"),
            "breach_penalty": session.get("breach_penalty"),
            "workspace_relative_dir": _workspace_relative_dir(session["contract_code"]),
            "workspace_path": session["workspace_path"],
            "created_at": session.get("created_at"),
            "start_date": session.get("start_date").isoformat() if session.get("start_date") else None,
            "city": session.get("city") or "",
            "state": session.get("state") or "",
        },
        "users": _list_contract_users(session["id"]),
        "api_tokens": _list_contract_tokens(session["id"]),
        "payments": _list_contract_payments(session["id"]),
        "ingest_events": _list_contract_ingest_events(session["id"]),
        "connections": _build_connection_info(session),
        "files": listing,
        "inventory": _inventory_snapshot(),
    }


def _create_api_token(contract_id: str, label: str, created_by_email: str) -> dict[str, Any]:
    raw_token = _api_token()
    preview = raw_token[:16] + "..."
    row = _db_fetchone(
        """
        INSERT INTO storage_api_tokens (contract_id, label, token_hash, token_preview, status, created_by_email)
        VALUES (%s, %s, %s, %s, 'active', %s)
        RETURNING id, label, token_preview, status, created_by_email, created_at, last_used_at
        """,
        (contract_id, label.strip() or "API token", _hash_secret(raw_token), preview, created_by_email),
    )
    if not row:
        raise RuntimeError("Não foi possível gerar o API token.")
    masked = _mask_tokens([row])[0]
    masked["token"] = raw_token
    return masked


def _mercadopago_access_token() -> str:
    env_token = os.getenv("BANK_MERCADOPAGO_ACCESS_TOKEN") or os.getenv("MERCADOPAGO_ACCESS_TOKEN")
    if env_token:
        return env_token

    client = get_secrets_agent_client()
    token = (
        client.get_local_secret(STORAGE_MERCADOPAGO_TOKEN_SECRET, field="token")
        or client.get_secret(STORAGE_MERCADOPAGO_TOKEN_SECRET, field="token")
    )
    client.close()
    if not token:
        raise RuntimeError("Token do Mercado Pago não encontrado.")
    return token


def _mercadopago_public_key() -> str:
    env_key = os.getenv("MERCADOPAGO_PUBLIC_KEY")
    if env_key:
        return env_key

    client = get_secrets_agent_client()
    key = (
        client.get_local_secret(STORAGE_MERCADOPAGO_PUBLIC_KEY_SECRET, field="key")
        or client.get_secret(STORAGE_MERCADOPAGO_PUBLIC_KEY_SECRET, field="key")
    )
    client.close()
    return key or ""


def _create_payment_link(session: dict[str, Any], amount_brl: float, description: str, payer_email: str | None) -> dict[str, Any]:
    token = _mercadopago_access_token()
    payload: dict[str, Any] = {
        "items": [
            {
                "id": session["contract_code"],
                "title": description,
                "description": f"Storage gerenciado RPA4ALL | {session['contract_code']}",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": round(amount_brl, 2),
            }
        ],
        "external_reference": session["contract_code"],
        "back_urls": {
            "success": STORAGE_PAYMENT_RETURN_URL,
            "failure": STORAGE_PAYMENT_RETURN_URL,
            "pending": STORAGE_PAYMENT_RETURN_URL,
        },
        "auto_return": "approved",
        "metadata": {
            "contract_id": session["id"],
            "contract_code": session["contract_code"],
            "company": session["company"],
        },
    }
    if STORAGE_PAYMENT_WEBHOOK_URL:
        payload["notification_url"] = STORAGE_PAYMENT_WEBHOOK_URL
    if payer_email:
        payload["payer"] = {"email": payer_email}

    response = requests.post(
        "https://api.mercadopago.com/checkout/preferences",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=25,
    )
    response.raise_for_status()
    data = response.json()

    row = _db_fetchone(
        """
        INSERT INTO storage_payment_links (
            contract_id, amount_brl, description, payer_email, preference_id,
            init_point, sandbox_init_point, external_reference, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'created')
        RETURNING id, amount_brl, description, payer_email, preference_id, init_point, sandbox_init_point, external_reference, status, created_at
        """,
        (
            session["id"],
            amount_brl,
            description,
            payer_email,
            data.get("id"),
            data.get("init_point"),
            data.get("sandbox_init_point"),
            session["contract_code"],
        ),
    )
    if not row:
        raise RuntimeError("Falha ao registrar cobrança do Mercado Pago.")
    row["public_key"] = _mercadopago_public_key()
    return row


def _record_ingest_event(
    contract_id: str,
    relative_path: str,
    protocol: str,
    bytes_count: int,
    checksum: str,
    metadata: dict[str, Any],
    token_id: int | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    row = _db_fetchone(
        """
        INSERT INTO storage_ingest_events (contract_id, token_id, user_id, protocol, relative_path, bytes, checksum, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, protocol, relative_path, bytes, checksum, metadata, created_at
        """,
        (contract_id, token_id, user_id, protocol, relative_path, bytes_count, checksum, json.dumps(metadata or {})),
    )
    if not row:
        raise RuntimeError("Falha ao registrar evento de ingest.")
    return row


def _resolve_api_token(authorization: str | None) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authorization Bearer é obrigatório.")
    raw_token = authorization.split(" ", 1)[1].strip()
    row = _db_fetchone(
        """
        SELECT
            t.id AS token_id,
            t.label AS token_label,
            t.status AS token_status,
            c.*
        FROM storage_api_tokens t
        JOIN storage_contracts c ON c.id = t.contract_id
        WHERE t.token_hash = %s AND t.status = 'active' AND c.status = 'active'
        """,
        (_hash_secret(raw_token),),
    )
    if not row:
        raise HTTPException(status_code=401, detail="API token inválido.")
    _db_execute(
        "UPDATE storage_api_tokens SET last_used_at = NOW() WHERE id = %s",
        (row["token_id"],),
    )
    return row


@router.get("/portal/bootstrap")
async def portal_bootstrap(portal_token: str = Query(...)) -> dict[str, Any]:
    session = _get_portal_session(portal_token)
    return _build_bootstrap(session)


@router.get("/portal/files")
async def portal_files(portal_token: str = Query(...), path: str = Query(".")) -> dict[str, Any]:
    session = _get_portal_session(portal_token)
    return _workspace_listing(session["contract_code"], path)


@router.post("/portal/files/folder")
async def portal_create_folder(payload: PortalFolderCreateRequest) -> dict[str, Any]:
    session = _get_portal_session(payload.portal_token)
    permissions = PROFILE_CAPABILITIES.get(session["user_profile"], PROFILE_CAPABILITIES["readonly"])
    if not permissions.get("upload_files"):
        raise HTTPException(status_code=403, detail="Seu perfil não pode criar pastas.")

    workspace = _ensure_workspace(session["contract_code"])
    relative = _sanitize_relative_path(payload.folder_path)
    target = (workspace / relative).resolve()
    if workspace.resolve() not in target.parents and target != workspace.resolve():
        raise HTTPException(status_code=400, detail="Caminho fora do workspace.")
    target.mkdir(parents=True, exist_ok=True)
    return {
        "status": "ok",
        "folder_path": "." if relative == Path(".") else relative.as_posix(),
        "files": _workspace_listing(session["contract_code"]),
    }


@router.post("/portal/files/upload")
async def portal_upload_file(
    portal_token: str = Form(...),
    relative_dir: str = Form("."),
    upload: UploadFile = File(...),
) -> dict[str, Any]:
    session = _get_portal_session(portal_token)
    permissions = PROFILE_CAPABILITIES.get(session["user_profile"], PROFILE_CAPABILITIES["readonly"])
    if not permissions.get("upload_files"):
        raise HTTPException(status_code=403, detail="Seu perfil não pode enviar arquivos.")

    workspace = _ensure_workspace(session["contract_code"])
    relative = _sanitize_relative_path(relative_dir)
    destination_dir = (workspace / relative).resolve()
    if workspace.resolve() not in destination_dir.parents and destination_dir != workspace.resolve():
        raise HTTPException(status_code=400, detail="Destino inválido.")
    destination_dir.mkdir(parents=True, exist_ok=True)

    filename = _safe_name(upload.filename or "arquivo.bin")
    target_file = destination_dir / filename
    content = await upload.read()
    target_file.write_bytes(content)

    relative_file = target_file.relative_to(workspace).as_posix()
    event = _record_ingest_event(
        contract_id=session["id"],
        relative_path=relative_file,
        protocol="portal-upload",
        bytes_count=len(content),
        checksum="",
        metadata={"content_type": upload.content_type or "application/octet-stream"},
        user_id=session["user_id"],
    )

    return {
        "status": "ok",
        "file": {
            "name": filename,
            "path": relative_file,
            "bytes": len(content),
        },
        "event": event,
        "files": _workspace_listing(session["contract_code"], relative.as_posix()),
    }


@router.post("/portal/tokens")
async def portal_create_token(payload: PortalTokenCreateRequest) -> dict[str, Any]:
    session = _require_manager_session(payload.portal_token)
    created = _create_api_token(session["id"], payload.label, session["user_email"])
    return {
        "status": "ok",
        "token": created,
        "connections": _build_connection_info(session),
        "api_tokens": _list_contract_tokens(session["id"]),
    }


@router.post("/portal/subusers")
async def portal_create_subuser(payload: PortalSubUserRequest) -> dict[str, Any]:
    session = _require_manager_session(payload.portal_token)
    profile = _validate_profile(payload.profile)
    email = payload.email.strip().lower()
    full_name = payload.full_name.strip()
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=400, detail="Email inválido.")
    if not full_name:
        raise HTTPException(status_code=400, detail="Nome completo é obrigatório.")

    existing = _db_fetchone(
        "SELECT id FROM storage_contract_users WHERE contract_id = %s AND email = %s",
        (session["id"], email),
    )
    if existing:
        raise HTTPException(status_code=409, detail="Já existe um subusuário com este email no contrato.")

    portal_token = _portal_token()
    created_user = None
    password = ""
    try:
        created_user, password = _create_authentik_user(email=email, full_name=full_name, profile=profile)
        row = _db_fetchone(
            """
            INSERT INTO storage_contract_users (
                contract_id, email, username, full_name, profile, status, is_manager, portal_token_hash, authentik_id
            ) VALUES (%s, %s, %s, %s, %s, 'active', FALSE, %s, %s)
            RETURNING id, email, username, full_name, profile, status, is_manager, created_at
            """,
            (
                session["id"],
                email,
                created_user["username"],
                full_name,
                profile,
                _hash_secret(portal_token),
                created_user.get("pk"),
            ),
        )
        if not row:
            raise RuntimeError("Falha ao gravar subusuário.")
        row["profile_label"] = PROFILE_LABELS.get(profile, profile)

        email_message_id = None
        if payload.send_email:
            message = _build_user_email_message(
                recipient_email=email,
                full_name=full_name,
                username=created_user["username"],
                temporary_password=password,
                contract_code=session["contract_code"],
                portal_url=_portal_url(portal_token),
                profile=profile,
                workspace_relative_dir=_workspace_relative_dir(session["contract_code"]),
            )
            email_message_id = _send_email_message(message)

        return {
            "status": "ok",
            "user": row,
            "portal_url": _portal_url(portal_token),
            "email_message_id": email_message_id,
            "users": _list_contract_users(session["id"]),
        }
    except Exception as exc:
        if created_user and created_user.get("pk"):
            _delete_authentik_user(created_user["pk"])
        if isinstance(exc, HTTPException):
            raise
        logger.exception("Falha ao criar subusuário de storage")
        raise HTTPException(status_code=500, detail="Não foi possível criar o subusuário.") from exc


@router.patch("/portal/users/{user_id}")
async def portal_update_user(user_id: int, payload: PortalProfileUpdateRequest) -> dict[str, Any]:
    session = _require_manager_session(payload.portal_token)
    target = _db_fetchone(
        """
        SELECT id, contract_id, email, username, full_name, profile, status, is_manager, authentik_id
        FROM storage_contract_users
        WHERE id = %s AND contract_id = %s
        """,
        (user_id, session["id"]),
    )
    if not target:
        raise HTTPException(status_code=404, detail="Usuário do contrato não encontrado.")
    if target["is_manager"] and payload.status == "disabled":
        raise HTTPException(status_code=400, detail="O gestor principal não pode ser desativado por este fluxo.")

    next_profile = _validate_profile(payload.profile or target["profile"]) if payload.profile else target["profile"]
    next_status = _validate_status(payload.status or target["status"]) if payload.status else target["status"]

    _db_execute(
        """
        UPDATE storage_contract_users
        SET profile = %s, status = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (next_profile, next_status, user_id),
    )
    if target.get("authentik_id"):
        _update_authentik_user(target["authentik_id"], profile=next_profile, status=next_status)

    return {
        "status": "ok",
        "users": _list_contract_users(session["id"]),
    }


@router.post("/portal/payments")
async def portal_create_payment(payload: PortalPaymentLinkRequest) -> dict[str, Any]:
    session = _require_manager_session(payload.portal_token)
    if payload.amount_brl <= 0:
        raise HTTPException(status_code=400, detail="O valor precisa ser maior que zero.")
    description = payload.description.strip()
    if not description:
        raise HTTPException(status_code=400, detail="A descrição do pagamento é obrigatória.")

    try:
        payment = _create_payment_link(
            session=session,
            amount_brl=round(payload.amount_brl, 2),
            description=description,
            payer_email=(payload.payer_email or session["primary_email"]).strip().lower(),
        )
    except Exception as exc:
        logger.exception("Falha ao criar link de pagamento no Mercado Pago")
        raise HTTPException(status_code=500, detail="Não foi possível gerar o link de pagamento agora.") from exc

    return {
        "status": "ok",
        "payment": payment,
        "payments": _list_contract_payments(session["id"]),
    }


@router.post("/ingest")
async def storage_ingest(
    payload: StorageIngestRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    session = _resolve_api_token(authorization)
    relative = _sanitize_relative_path(payload.relative_path)
    record = _record_ingest_event(
        contract_id=session["id"],
        token_id=session["token_id"],
        user_id=None,
        protocol=(payload.protocol or "api").strip()[:32],
        relative_path=relative.as_posix(),
        bytes_count=max(0, int(payload.bytes)),
        checksum=(payload.checksum or "").strip(),
        metadata=payload.metadata or {},
    )
    return {
        "status": "accepted",
        "contract_code": session["contract_code"],
        "workspace_relative_dir": _workspace_relative_dir(session["contract_code"]),
        "ingest_event": record,
        "nextcloud_url": STORAGE_NEXTCLOUD_URL,
    }
