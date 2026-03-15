"""Provisionamento de acesso para solicitações comerciais de storage."""

from __future__ import annotations

import base64
import logging
import os
import re
import secrets
import string
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any

import requests
from fastapi import APIRouter, HTTPException, Request
from googleapiclient.discovery import build
from pydantic import BaseModel

from specialized_agents.gmail_credentials import load_gmail_credentials
from specialized_agents.storage_portal import (
    create_contract_bundle,
    rollback_contract_bundle,
    router as storage_portal_router,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/storage", tags=["storage"])
router.include_router(storage_portal_router)

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
STORAGE_ACCESS_RATE_WINDOW_SECONDS = int(os.getenv("STORAGE_ACCESS_RATE_WINDOW_SECONDS", "3600"))
STORAGE_ACCESS_RATE_MAX_REQUESTS = int(os.getenv("STORAGE_ACCESS_RATE_MAX_REQUESTS", "5"))

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_SANITIZE_PATTERN = re.compile(r"[^a-z0-9]+")
_RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}
_AUDIT_TABLE_READY = False

_CREATE_AUDIT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS storage_access_requests (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(64) UNIQUE NOT NULL,
    requester_email VARCHAR(255) NOT NULL,
    requester_company VARCHAR(255) NOT NULL,
    username VARCHAR(128),
    mode VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    authentik_id INTEGER,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    message_id VARCHAR(255),
    error_message TEXT,
    client_ip VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


class StorageAccessRequest(BaseModel):
    mode: str = "sizing"
    company: str
    legal_name: str = ""
    contact: str
    role: str = ""
    email: str
    phone: str = ""
    project: str
    temperature: str = "warm"
    volume: float = 0
    ingress: float = 0
    retention: str = "12"
    retrieval: str = "rare"
    sla: str = "24h"
    compliance: str = "standard"
    redundancy: str = "single"
    billing: str = "monthly"
    term: int = 12
    start_date: str | None = None
    city: str = ""
    state: str = ""
    notes: str = ""
    monthly_service: float = 0
    setup_fee: float = 0
    contract_value: float = 0
    notice_days: int = 0
    breach_penalty: float = 0


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded_for or (request.client.host if request.client else "unknown")


def _enforce_rate_limit(client_ip: str) -> None:
    now = time.time()
    window_start = now - STORAGE_ACCESS_RATE_WINDOW_SECONDS
    recent = [stamp for stamp in _RATE_LIMIT_BUCKETS.get(client_ip, []) if stamp >= window_start]
    if len(recent) >= STORAGE_ACCESS_RATE_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail="Limite temporário de solicitações atingido. Tente novamente mais tarde.",
        )
    recent.append(now)
    _RATE_LIMIT_BUCKETS[client_ip] = recent


def _validate_payload(payload: StorageAccessRequest) -> None:
    errors = []

    if payload.mode not in {"sizing", "space"}:
        errors.append("Modo inválido.")
    if not payload.company.strip():
        errors.append("Empresa solicitante é obrigatória.")
    if not payload.contact.strip():
        errors.append("Responsável é obrigatório.")
    if not payload.project.strip():
        errors.append("Projeto é obrigatório.")
    if not EMAIL_PATTERN.match(payload.email.strip()):
        errors.append("Email inválido.")
    if payload.term < 1:
        errors.append("Vigência inválida.")
    if payload.volume < 0 or payload.ingress < 0:
        errors.append("Volume e novos dados por mês não podem ser negativos.")

    if errors:
        raise HTTPException(status_code=400, detail=" ".join(errors))


def _slugify(value: str) -> str:
    normalized = USERNAME_SANITIZE_PATTERN.sub("-", value.lower()).strip("-")
    return normalized[:48] or "storage-client"


def _build_username(payload: StorageAccessRequest) -> str:
    company_part = _slugify(payload.company)[:18]
    local_part = _slugify(payload.email.split("@", 1)[0])[:18]
    seed = secrets.token_hex(3)
    username = "-".join(part for part in (company_part, local_part, seed) if part)
    return username[:64]


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


def _find_existing_user(payload: StorageAccessRequest) -> dict[str, Any] | None:
    lookup = _authentik_request("GET", f"/core/users/?search={payload.email}")
    for user in lookup.get("results", []):
        if (user.get("email") or "").strip().lower() == payload.email.strip().lower():
            return user
    return None


def _resolve_group_ids() -> list[int]:
    group_ids: list[int] = []
    for group_name in STORAGE_ACCESS_GROUPS:
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


def _create_authentik_user(payload: StorageAccessRequest, username: str, temporary_password: str) -> dict[str, Any]:
    full_name = payload.contact.strip() or payload.company.strip()
    user = _authentik_request(
        "POST",
        "/core/users/",
        {
            "username": username,
            "email": payload.email.strip(),
            "name": full_name,
            "is_active": True,
            "password": temporary_password,
        },
    )
    user_pk = user.get("pk")
    group_ids = _resolve_group_ids()
    if user_pk and group_ids:
        _authentik_request("PATCH", f"/core/users/{user_pk}/", {"groups": group_ids})
    return user


def _delete_authentik_user(user_pk: int) -> None:
    try:
        _authentik_request("DELETE", f"/core/users/{user_pk}/")
    except Exception as exc:
        logger.warning("Falha ao remover usuário %s após erro de email: %s", user_pk, exc)


def _get_gmail_credentials():
    return load_gmail_credentials(
        [
            STORAGE_ACCESS_GMAIL_SECRET_NAME,
            STORAGE_ACCESS_GMAIL_FALLBACK_SECRET,
        ]
    )


def _build_email_body(
    payload: StorageAccessRequest,
    username: str,
    temporary_password: str,
    contract_bundle: dict[str, Any] | None = None,
) -> EmailMessage:
    subject = "RPA4ALL | Acesso ao sizing de storage"
    summary_lines = [
        f"Empresa: {payload.company}",
        f"Projeto: {payload.project}",
        f"Temperatura: {payload.temperature}",
        f"Volume protegido: {payload.volume:.2f} TB",
        f"Novos dados por mês: {payload.ingress:.2f} TB",
        f"Mensal equivalente: R$ {payload.monthly_service:,.2f}",
        f"Setup estimado: R$ {payload.setup_fee:,.2f}",
        f"Valor contratual: R$ {payload.contract_value:,.2f}",
    ]
    if contract_bundle:
        summary_lines.extend(
            [
                f"Contrato guarda-chuva: {contract_bundle['contract_code']}",
                f"Workspace: {contract_bundle['workspace_relative_dir']}",
            ]
        )

    portal_url = contract_bundle["portal_url"] if contract_bundle else STORAGE_ACCESS_LOGIN_URL

    text_body = "\n".join(
        [
            f"Olá {payload.contact},",
            "",
            "Recebemos a sua solicitação de sizing de storage na RPA4ALL.",
            "Geramos um acesso no portal Authentik e no painel de gerenciamento do contrato guarda-chuva.",
            "",
            f"Login: {username}",
            f"Senha temporária: {temporary_password}",
            f"Portal: {STORAGE_ACCESS_LOGIN_URL}",
            f"Painel do gestor: {portal_url}",
            "",
            "Resumo da solicitação:",
            *summary_lines,
            "",
            "Por segurança, altere a senha no primeiro acesso.",
            "",
            "RPA4ALL",
        ]
    )

    html_body = """\
<html>
  <body style="font-family: Inter, Arial, sans-serif; color: #0f172a;">
    <p>Olá <strong>{contact}</strong>,</p>
    <p>Recebemos a sua solicitação de sizing de storage na RPA4ALL.</p>
    <p>Geramos um acesso no portal Authentik e no painel de gerenciamento do contrato guarda-chuva.</p>
    <div style="padding: 16px; border-radius: 12px; background: #e2f3ff; margin: 16px 0;">
      <p style="margin: 0 0 8px;"><strong>Login:</strong> {username}</p>
      <p style="margin: 0 0 8px;"><strong>Senha temporária:</strong> {password}</p>
      <p style="margin: 0 0 8px;"><strong>Portal:</strong> <a href="{login_url}">{login_url}</a></p>
      <p style="margin: 0;"><strong>Painel do gestor:</strong> <a href="{portal_url}">{portal_url}</a></p>
    </div>
    <p><strong>Resumo da solicitação</strong></p>
    <ul>
      {summary_items}
    </ul>
    <p>Por segurança, altere a senha no primeiro acesso.</p>
    <p>RPA4ALL</p>
  </body>
</html>
""".format(
        contact=payload.contact,
        username=username,
        password=temporary_password,
        login_url=STORAGE_ACCESS_LOGIN_URL,
        portal_url=portal_url,
        summary_items="".join(f"<li>{line}</li>" for line in summary_lines),
    )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{STORAGE_ACCESS_FROM_NAME} <{STORAGE_ACCESS_FROM_EMAIL}>"
    message["To"] = payload.email.strip()
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    return message


def _send_access_email(
    payload: StorageAccessRequest,
    username: str,
    temporary_password: str,
    contract_bundle: dict[str, Any] | None = None,
) -> str:
    message = _build_email_body(payload, username, temporary_password, contract_bundle=contract_bundle)
    creds = _get_gmail_credentials()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    result = service.users().messages().send(userId="me", body={"raw": encoded_message}).execute()
    return result.get("id", "")


def _ensure_audit_table() -> None:
    global _AUDIT_TABLE_READY
    if _AUDIT_TABLE_READY:
        return

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return

    try:
        import psycopg2

        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(_CREATE_AUDIT_TABLE_SQL)
        _AUDIT_TABLE_READY = True
    except Exception as exc:
        logger.warning("Falha ao preparar tabela de auditoria de storage access: %s", exc)


def _audit_request(
    request_id: str,
    payload: StorageAccessRequest,
    status: str,
    client_ip: str,
    username: str | None = None,
    authentik_id: int | None = None,
    message_id: str | None = None,
    error_message: str | None = None,
) -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return

    _ensure_audit_table()
    if not _AUDIT_TABLE_READY:
        return

    try:
        import psycopg2
        from psycopg2.extras import Json

        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO storage_access_requests (
                        request_id,
                        requester_email,
                        requester_company,
                        username,
                        mode,
                        status,
                        authentik_id,
                        payload,
                        message_id,
                        error_message,
                        client_ip
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (request_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        status = EXCLUDED.status,
                        authentik_id = EXCLUDED.authentik_id,
                        payload = EXCLUDED.payload,
                        message_id = EXCLUDED.message_id,
                        error_message = EXCLUDED.error_message,
                        client_ip = EXCLUDED.client_ip
                    """,
                    (
                        request_id,
                        payload.email.strip(),
                        payload.company.strip(),
                        username,
                        payload.mode,
                        status,
                        authentik_id,
                        Json(payload.model_dump(mode="json")),
                        message_id,
                        error_message,
                        client_ip,
                    ),
                )
    except Exception as exc:
        logger.warning("Falha ao gravar auditoria de solicitação de storage: %s", exc)


@router.post("/request-access")
async def request_access(
    payload: StorageAccessRequest,
    request: Request,
    dry_run: bool = False,
) -> dict[str, Any]:
    client_ip = _client_ip(request)
    _validate_payload(payload)

    username = _build_username(payload)
    request_id = f"storage-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}"

    if dry_run:
        return {
            "status": "dry_run",
            "request_id": request_id,
            "username": username,
            "recipient_email": payload.email.strip(),
            "login_url": STORAGE_ACCESS_LOGIN_URL,
            "message": "Solicitação validada em modo dry-run.",
        }

    _enforce_rate_limit(client_ip)

    existing_user = _find_existing_user(payload)
    if existing_user:
        _audit_request(
            request_id=request_id,
            payload=payload,
            status="duplicate",
            client_ip=client_ip,
            username=existing_user.get("username"),
            authentik_id=existing_user.get("pk"),
            error_message="Email já provisionado no Authentik.",
        )
        raise HTTPException(
            status_code=409,
            detail="Já existe um acesso provisionado para este email. Fale com o time RPA4ALL para reenvio.",
        )

    temporary_password = _generate_password()
    contract_bundle: dict[str, Any] | None = None

    try:
        created_user = _create_authentik_user(payload, username, temporary_password)
        user_pk = created_user.get("pk")
        contract_bundle = create_contract_bundle(payload.model_dump(mode="json"), username, user_pk)
        message_id = _send_access_email(payload, username, temporary_password, contract_bundle=contract_bundle)
    except Exception as exc:
        logger.exception("Falha ao provisionar acesso de storage")
        if contract_bundle and contract_bundle.get("contract_id"):
            rollback_contract_bundle(contract_bundle["contract_id"])
        if "user_pk" in locals() and user_pk:
            _delete_authentik_user(user_pk)
        _audit_request(
            request_id=request_id,
            payload=payload,
            status="failed",
            client_ip=client_ip,
            username=username,
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail="Não foi possível provisionar o acesso neste momento. Tente novamente em alguns minutos.",
        ) from exc

    _audit_request(
        request_id=request_id,
        payload=payload,
        status="sent",
        client_ip=client_ip,
        username=username,
        authentik_id=user_pk,
        message_id=message_id,
    )

    return {
        "status": "ok",
        "request_id": request_id,
        "username": username,
        "recipient_email": payload.email.strip(),
        "login_url": STORAGE_ACCESS_LOGIN_URL,
        "contract_code": contract_bundle["contract_code"] if contract_bundle else None,
        "portal_url": contract_bundle["portal_url"] if contract_bundle else None,
        "message": f"Acesso gerado e enviado para {payload.email.strip()}",
    }
