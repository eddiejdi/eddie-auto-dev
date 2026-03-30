#!/usr/bin/env python3
"""
API de provisionamento do portal de storage da RPA4ALL.

Fluxo principal:
1. Recebe a solicitação comercial do storage.
2. Gera código do contrato, token do portal e minuta armazenada em disco.
3. Provisiona o usuário do contrato no Authentik.
4. Gera o email corporativo RPA4ALL do contrato.
5. Envia o onboarding em HTML para o email corporativo e para o email particular.

Os endpoints expostos aqui seguem exatamente o contrato esperado pelo front
publicado em https://www.rpa4all.com/storage-request.html e
https://www.rpa4all.com/storage-portal.html.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import platform
import re
import secrets
import shutil
import smtplib
import sqlite3
import string
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str, fallback: str = "cliente") -> str:
    normalized = value.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = normalized.strip("-")
    return normalized or fallback


def digits_only(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


def ensure_relative_path(relative_path: str) -> str:
    cleaned = (relative_path or ".").strip() or "."
    candidate = Path(cleaned)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise HTTPException(status_code=400, detail="Caminho inválido.")
    return str(candidate)


def render_currency(value: float | int) -> str:
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def safe_json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def build_token(prefix: str) -> tuple[str, str, str]:
    raw = secrets.token_urlsafe(24)
    token = f"{prefix}_{raw}"
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    preview = token[:12] + "..." + token[-4:]
    return token, token_hash, preview


def build_activation_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def build_contract_code(company: str, project: str) -> str:
    company_part = slugify(company, "contrato").replace("-", "")[:5].upper()
    project_part = slugify(project, "storage").replace("-", "")[:4].upper()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = secrets.token_hex(2).upper()
    return f"STG-{stamp}-{company_part}{project_part}-{suffix}"


def build_username(contract_code: str, company: str) -> str:
    company_part = slugify(company, "cliente").replace("-", "")[:18]
    code_part = contract_code.lower().replace("-", "")
    return f"ctr_{company_part}_{code_part[:10]}"


def dedupe_emails(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        email = (value or "").strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        result.append(email)
    return result


@dataclass
class Settings:
    root_dir: Path
    data_dir: Path
    workspace_root: Path
    database_path: Path
    authentik_url: str
    authentik_token: str
    authentik_verify_tls: bool
    authentik_groups: list[str]
    mail_domain: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from_email: str
    smtp_from_name: str
    smtp_starttls: bool
    nextcloud_url: str
    nextcloud_base_path: str
    authentik_public_url: str
    public_site_url: str
    portal_public_url: str
    api_public_base: str
    ingest_path: str
    manage_payments: bool
    mailbox_create_command: str


def load_settings() -> Settings:
    root_dir = Path(__file__).resolve().parent
    data_dir = Path(os.getenv("STORAGE_PORTAL_DATA_DIR", root_dir / "data" / "storage_portal"))
    workspace_root = Path(os.getenv("STORAGE_PORTAL_WORKSPACE_ROOT", data_dir / "contracts"))
    database_path = Path(os.getenv("STORAGE_PORTAL_DB_PATH", data_dir / "storage_portal.db"))
    groups = [item.strip() for item in os.getenv("STORAGE_PORTAL_AUTHENTIK_GROUPS", "users").split(",") if item.strip()]
    return Settings(
        root_dir=root_dir,
        data_dir=data_dir,
        workspace_root=workspace_root,
        database_path=database_path,
        authentik_url=os.getenv("AUTHENTIK_URL", "https://auth.rpa4all.com"),
        authentik_token=os.getenv("AUTHENTIK_TOKEN", ""),
        authentik_verify_tls=os.getenv("AUTHENTIK_VERIFY_TLS", "false").lower() in {"1", "true", "yes"},
        authentik_groups=groups or ["users"],
        mail_domain=os.getenv("MAIL_DOMAIN", "rpa4all.com"),
        smtp_host=os.getenv("SMTP_HOST", "mail.rpa4all.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME", os.getenv("SMTP_FROM_EMAIL", "it@rpa4all.com")),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from_email=os.getenv("SMTP_FROM_EMAIL", "it@rpa4all.com"),
        smtp_from_name=os.getenv("SMTP_FROM_NAME", "RPA4ALL Onboarding"),
        smtp_starttls=os.getenv("SMTP_STARTTLS", "true").lower() in {"1", "true", "yes"},
        nextcloud_url=os.getenv("NEXTCLOUD_URL", "https://nextcloud.rpa4all.com"),
        nextcloud_base_path=os.getenv("NEXTCLOUD_BASE_PATH", "/Storage Contracts"),
        authentik_public_url=os.getenv("AUTHENTIK_PUBLIC_URL", "https://auth.rpa4all.com"),
        public_site_url=os.getenv("PUBLIC_SITE_URL", "https://www.rpa4all.com"),
        portal_public_url=os.getenv("PORTAL_PUBLIC_URL", "https://www.rpa4all.com/storage-portal.html"),
        api_public_base=os.getenv("API_PUBLIC_BASE", "https://api.rpa4all.com/agents-api"),
        ingest_path=os.getenv("STORAGE_INGEST_PATH", "/storage/ingest"),
        manage_payments=os.getenv("STORAGE_PORTAL_MANAGE_PAYMENTS", "false").lower() in {"1", "true", "yes"},
        mailbox_create_command=os.getenv("RPA4ALL_MAILBOX_CREATE_COMMAND", "").strip(),
    )


class StorageRequestPayload(BaseModel):
    mode: str = "sizing"
    company: str
    legal_name: str
    company_document: str
    contact: str
    role: str
    email: str
    personal_email: str | None = None
    phone: str
    representative_document: str
    project: str
    address: str
    address_number: str
    address_complement: str | None = ""
    district: str
    postal_code: str
    temperature: str
    volume: float
    ingress: float
    retention: str
    retrieval: str
    sla: str
    compliance: str
    redundancy: str
    billing: str
    term: int = Field(default=12, ge=1)
    start_date: str | None = None
    city: str
    state: str
    notes: str | None = ""
    monthly_service: float
    setup_fee: float = 0
    contract_value: float
    notice_days: int = 30
    breach_penalty: float
    signed_contract_html: str | None = None
    signed_contract_text: str | None = None
    signed_contract_base64: str | None = None
    signed_contract_filename: str | None = None


class PortalTokenCreatePayload(BaseModel):
    portal_token: str
    label: str = "Integração principal"


class PortalSubuserCreatePayload(BaseModel):
    portal_token: str
    full_name: str
    email: str
    profile: str = "operations"


class PortalUserUpdatePayload(BaseModel):
    portal_token: str
    profile: str | None = None
    status: str | None = None


class PortalPaymentPayload(BaseModel):
    portal_token: str
    amount_brl: float
    description: str


class PortalFolderCreatePayload(BaseModel):
    portal_token: str
    folder_path: str


class FinalizeContractPayload(BaseModel):
    contract_code: str | None = None
    portal_token: str | None = None
    signed_contract_html: str | None = None
    signed_contract_text: str | None = None
    signed_contract_base64: str | None = None
    signed_contract_filename: str | None = None


class StorageRepository:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS contracts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_code TEXT UNIQUE NOT NULL,
                    portal_token_hash TEXT UNIQUE NOT NULL,
                    portal_token_preview TEXT NOT NULL,
                    company TEXT NOT NULL,
                    legal_name TEXT NOT NULL,
                    company_document TEXT NOT NULL,
                    contact TEXT NOT NULL,
                    role TEXT NOT NULL,
                    email TEXT NOT NULL,
                    personal_email TEXT,
                    corporate_email TEXT NOT NULL,
                    activation_code TEXT NOT NULL,
                    authentik_username TEXT NOT NULL,
                    authentik_user_id INTEGER,
                    status TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    project TEXT NOT NULL,
                    workspace_path TEXT NOT NULL,
                    workspace_relative_dir TEXT NOT NULL,
                    billing TEXT NOT NULL,
                    term_months INTEGER NOT NULL,
                    monthly_service REAL NOT NULL,
                    contract_value REAL NOT NULL,
                    start_date TEXT,
                    request_payload_json TEXT NOT NULL,
                    documents_json TEXT NOT NULL,
                    onboarding_sent_at TEXT,
                    mailbox_status TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS portal_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_id INTEGER NOT NULL,
                    portal_token_hash TEXT UNIQUE NOT NULL,
                    portal_token_preview TEXT NOT NULL,
                    username TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    corporate_email TEXT,
                    profile TEXT NOT NULL,
                    status TEXT NOT NULL,
                    activation_code TEXT NOT NULL,
                    authentik_user_id INTEGER,
                    is_primary INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(contract_id) REFERENCES contracts(id)
                );

                CREATE TABLE IF NOT EXISTS api_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_id INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    token_hash TEXT NOT NULL,
                    preview TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(contract_id) REFERENCES contracts(id)
                );

                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contract_id INTEGER NOT NULL,
                    amount_brl REAL NOT NULL,
                    description TEXT NOT NULL,
                    external_reference TEXT NOT NULL,
                    init_point TEXT,
                    sandbox_init_point TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(contract_id) REFERENCES contracts(id)
                );
                """
            )

    def create_contract(self, payload: dict[str, Any], documents: dict[str, Any], primary_user: dict[str, Any]) -> dict[str, Any]:
        now = utcnow_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO contracts (
                    contract_code, portal_token_hash, portal_token_preview, company, legal_name,
                    company_document, contact, role, email, personal_email, corporate_email,
                    activation_code, authentik_username, authentik_user_id, status, mode, project,
                    workspace_path, workspace_relative_dir, billing, term_months, monthly_service,
                    contract_value, start_date, request_payload_json, documents_json,
                    onboarding_sent_at, mailbox_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["contract_code"],
                    primary_user["portal_token_hash"],
                    primary_user["portal_token_preview"],
                    payload["company"],
                    payload["legal_name"],
                    payload["company_document"],
                    payload["contact"],
                    payload["role"],
                    payload["email"],
                    payload.get("personal_email"),
                    payload["corporate_email"],
                    primary_user["activation_code"],
                    primary_user["username"],
                    primary_user.get("authentik_user_id"),
                    payload["status"],
                    payload["mode"],
                    payload["project"],
                    payload["workspace_path"],
                    payload["workspace_relative_dir"],
                    payload["billing"],
                    payload["term"],
                    payload["monthly_service"],
                    payload["contract_value"],
                    payload.get("start_date"),
                    safe_json_dumps(payload["request_payload"]),
                    safe_json_dumps(documents),
                    payload.get("onboarding_sent_at"),
                    payload.get("mailbox_status", "generated"),
                    now,
                    now,
                ),
            )
            contract_id = cursor.lastrowid
            conn.execute(
                """
                INSERT INTO portal_users (
                    contract_id, portal_token_hash, portal_token_preview, username, full_name,
                    email, corporate_email, profile, status, activation_code, authentik_user_id,
                    is_primary, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    contract_id,
                    primary_user["portal_token_hash"],
                    primary_user["portal_token_preview"],
                    primary_user["username"],
                    primary_user["full_name"],
                    primary_user["email"],
                    primary_user.get("corporate_email"),
                    primary_user["profile"],
                    primary_user["status"],
                    primary_user["activation_code"],
                    primary_user.get("authentik_user_id"),
                    1,
                    now,
                    now,
                ),
            )
            conn.commit()
        return self.get_contract_by_code(payload["contract_code"])

    def get_contract_by_code(self, contract_code: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM contracts WHERE contract_code = ?", (contract_code,)).fetchone()
        return dict(row) if row else None

    def get_contract_by_portal_token(self, portal_token: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        token_hash = hashlib.sha256(portal_token.encode("utf-8")).hexdigest()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT c.*, u.id AS portal_user_id, u.username AS portal_username,
                       u.full_name AS portal_full_name, u.email AS portal_email,
                       u.corporate_email AS portal_corporate_email, u.profile AS portal_profile,
                       u.status AS portal_status, u.activation_code AS portal_activation_code,
                       u.authentik_user_id AS portal_authentik_user_id, u.is_primary AS portal_is_primary
                FROM portal_users u
                JOIN contracts c ON c.id = u.contract_id
                WHERE u.portal_token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
        if not row:
            return None
        row_dict = dict(row)
        contract = {key: row_dict[key] for key in row_dict.keys() if not key.startswith("portal_")}
        current_user = {
            "id": row_dict["portal_user_id"],
            "username": row_dict["portal_username"],
            "full_name": row_dict["portal_full_name"],
            "email": row_dict["portal_email"],
            "corporate_email": row_dict["portal_corporate_email"],
            "profile": row_dict["portal_profile"],
            "status": row_dict["portal_status"],
            "activation_code": row_dict["portal_activation_code"],
            "authentik_user_id": row_dict["portal_authentik_user_id"],
            "is_primary": bool(row_dict["portal_is_primary"]),
        }
        return contract, current_user

    def list_users(self, contract_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, username, full_name, email, corporate_email, profile, status,
                       activation_code, authentik_user_id, is_primary, created_at
                FROM portal_users
                WHERE contract_id = ?
                ORDER BY is_primary DESC, created_at ASC
                """,
                (contract_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_subuser(self, contract_id: int, user: dict[str, Any]) -> dict[str, Any]:
        now = utcnow_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO portal_users (
                    contract_id, portal_token_hash, portal_token_preview, username, full_name,
                    email, corporate_email, profile, status, activation_code, authentik_user_id,
                    is_primary, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    contract_id,
                    user["portal_token_hash"],
                    user["portal_token_preview"],
                    user["username"],
                    user["full_name"],
                    user["email"],
                    user.get("corporate_email"),
                    user["profile"],
                    user["status"],
                    user["activation_code"],
                    user.get("authentik_user_id"),
                    now,
                    now,
                ),
            )
            user_id = cursor.lastrowid
            conn.commit()
        created = self.get_user(user_id)
        if not created:
            raise HTTPException(status_code=500, detail="Falha ao persistir subusuário.")
        return created

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM portal_users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def update_user(self, user_id: int, profile: str | None = None, status: str | None = None) -> None:
        assignments: list[str] = []
        values: list[Any] = []
        if profile:
            assignments.append("profile = ?")
            values.append(profile)
        if status:
            assignments.append("status = ?")
            values.append(status)
        assignments.append("updated_at = ?")
        values.append(utcnow_iso())
        values.append(user_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE portal_users SET {', '.join(assignments)} WHERE id = ?", values)
            conn.commit()

    def create_api_token(self, contract_id: int, label: str, token_hash: str, preview: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO api_tokens (contract_id, label, token_hash, preview, status, created_at)
                VALUES (?, ?, ?, ?, 'active', ?)
                """,
                (contract_id, label, token_hash, preview, utcnow_iso()),
            )
            conn.commit()

    def list_api_tokens(self, contract_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, label, preview, status, created_at
                FROM api_tokens
                WHERE contract_id = ?
                ORDER BY created_at DESC
                """,
                (contract_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_payments(self, contract_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT amount_brl, description, external_reference, init_point, sandbox_init_point, created_at
                FROM payments
                WHERE contract_id = ?
                ORDER BY created_at DESC
                """,
                (contract_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_payment(self, contract_id: int, amount_brl: float, description: str) -> dict[str, Any]:
        external_reference = f"mp-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(2)}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO payments (contract_id, amount_brl, description, external_reference, init_point, sandbox_init_point, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    contract_id,
                    amount_brl,
                    description,
                    external_reference,
                    None,
                    None,
                    utcnow_iso(),
                ),
            )
            conn.commit()
        payments = self.list_payments(contract_id)
        return payments[0] if payments else {}

    def update_contract_documents(self, contract_id: int, documents: dict[str, Any], onboarding_sent_at: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE contracts
                SET documents_json = ?, onboarding_sent_at = COALESCE(?, onboarding_sent_at), updated_at = ?
                WHERE id = ?
                """,
                (safe_json_dumps(documents), onboarding_sent_at, utcnow_iso(), contract_id),
            )
            conn.commit()


class AuthentikClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def request(self, method: str, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.settings.authentik_token:
            return {"skipped": True}
        response = requests.request(
            method,
            f"{self.settings.authentik_url.rstrip('/')}/api/v3{endpoint}",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.settings.authentik_token}",
                "Content-Type": "application/json",
            },
            timeout=20,
            verify=self.settings.authentik_verify_tls,
        )
        response.raise_for_status()
        return response.json() if response.text else {}

    def create_or_update_user(self, username: str, email: str, full_name: str, activation_code: str) -> dict[str, Any]:
        if not self.settings.authentik_token:
            return {"skipped": True, "username": username}

        existing = self.request("GET", f"/core/users/?search={username}")
        results = existing.get("results", [])
        target = next((item for item in results if item.get("username") == username), None)
        payload = {
            "username": username,
            "email": email,
            "name": full_name,
            "is_active": True,
            "password": activation_code,
        }
        if target:
            self.request("PATCH", f"/core/users/{target['pk']}/", payload)
            user_id = target["pk"]
        else:
            created = self.request("POST", "/core/users/", payload)
            user_id = created.get("pk")

        if user_id and self.settings.authentik_groups:
            user_detail = self.request("GET", f"/core/users/{user_id}/")
            current_groups = list(user_detail.get("groups", []))
            for group_name in self.settings.authentik_groups:
                group_search = self.request("GET", f"/core/groups/?search={group_name}")
                for group in group_search.get("results", []):
                    group_id = group.get("pk")
                    if group_id and group_id not in current_groups:
                        current_groups.append(group_id)
            self.request("PATCH", f"/core/users/{user_id}/", {"groups": current_groups})

        return {"authentik_user_id": user_id, "username": username}


class MailboxProvisioner:
    def __init__(self, settings: Settings):
        self.settings = settings

    def create_mailbox(self, email_address: str, full_name: str, activation_code: str) -> dict[str, Any]:
        command = self.settings.mailbox_create_command
        if not command:
            return {"status": "generated", "email": email_address}
        rendered = (
            command.replace("{email}", email_address)
            .replace("{full_name}", full_name)
            .replace("{activation_code}", activation_code)
        )
        exit_code = os.system(rendered)
        if exit_code != 0:
            raise RuntimeError(f"Falha ao criar mailbox corporativo para {email_address}.")
        return {"status": "created", "email": email_address}


class OnboardingMailer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def render_text(self, context: dict[str, Any]) -> str:
        return (
            f"Bem-vindo(a) à RPA4ALL.\n\n"
            f"Contrato: {context['contract_code']}\n"
            f"Empresa: {context['company']}\n"
            f"Projeto: {context['project']}\n"
            f"Email corporativo: {context['corporate_email']}\n"
            f"Usuário Authentik: {context['authentik_username']}\n"
            f"Código de acesso: {context['activation_code']}\n\n"
            f"Acesse {context['authentik_url']} e ative a conta usando o código acima.\n"
            f"Portal do contrato: {context['portal_url']}\n"
            f"Nextcloud: {context['nextcloud_url']}\n"
        )

    def render_html(self, context: dict[str, Any]) -> str:
        hero_image = context["public_site_url"] + "/assets/storage-images/storage-operations.png"
        protection_image = context["public_site_url"] + "/assets/storage-images/storage-protection.png"
        archive_image = context["public_site_url"] + "/assets/storage-images/storage-archive.png"
        return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Onboarding do contrato {html.escape(context["contract_code"])}</title>
</head>
<body style="margin:0;padding:0;background:#eef3f7;font-family:Segoe UI,Arial,sans-serif;color:#193041;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#eef3f7;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="720" cellspacing="0" cellpadding="0" style="max-width:720px;background:#ffffff;border-radius:24px;overflow:hidden;box-shadow:0 18px 50px rgba(15,34,56,0.12);">
          <tr>
            <td style="background:linear-gradient(135deg,#0f172a,#0f766e);padding:32px 36px;color:#ffffff;">
              <div style="font-size:12px;letter-spacing:0.18em;text-transform:uppercase;opacity:0.76;">RPA4ALL Storage Onboarding</div>
              <h1 style="margin:12px 0 10px;font-size:32px;line-height:1.2;">Contrato pronto para ativação</h1>
              <p style="margin:0;font-size:16px;line-height:1.6;color:rgba(255,255,255,0.86);">
                O contrato <strong>{html.escape(context["contract_code"])}</strong> já está provisionado com portal,
                workspace, acesso centralizado no Authentik e email corporativo RPA4ALL.
              </p>
            </td>
          </tr>
          <tr>
            <td>
              <img src="{html.escape(hero_image)}" alt="Infraestrutura de storage RPA4ALL" width="720" style="display:block;width:100%;max-width:720px;height:auto;border:0;">
            </td>
          </tr>
          <tr>
            <td style="padding:32px 36px 12px;">
              <p style="margin:0 0 18px;font-size:16px;line-height:1.7;">
                Olá, <strong>{html.escape(context["contact"])}</strong>. Este é o email de onboarding do contrato
                <strong>{html.escape(context["project"])}</strong> para <strong>{html.escape(context["company"])}</strong>.
              </p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 24px;">
                <tr>
                  <td style="padding:14px;background:#f7fbff;border:1px solid #dbe8f2;border-radius:16px;">
                    <div style="font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:#52708a;">Código do contrato</div>
                    <div style="font-size:22px;font-weight:700;color:#0f172a;">{html.escape(context["contract_code"])}</div>
                  </td>
                  <td width="12"></td>
                  <td style="padding:14px;background:#f7fbff;border:1px solid #dbe8f2;border-radius:16px;">
                    <div style="font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:#52708a;">Código de acesso</div>
                    <div style="font-size:22px;font-weight:700;color:#0f172a;">{html.escape(context["activation_code"])}</div>
                  </td>
                </tr>
              </table>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 20px;">
                <tr>
                  <td style="padding:18px;background:#0f172a;border-radius:20px;color:#ffffff;">
                    <div style="font-size:12px;letter-spacing:0.12em;text-transform:uppercase;color:#67e8f9;">Acessos provisionados</div>
                    <p style="margin:12px 0 6px;">Email corporativo: <strong>{html.escape(context["corporate_email"])}</strong></p>
                    <p style="margin:0 0 6px;">Usuário Authentik: <strong>{html.escape(context["authentik_username"])}</strong></p>
                    <p style="margin:0;">Portal do contrato: <strong>{html.escape(context["portal_url"])}</strong></p>
                  </td>
                </tr>
              </table>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 24px;">
                <tr>
                  <td style="padding:0 0 20px;">
                    <a href="{html.escape(context["authentik_url"])}" style="display:inline-block;background:#0f766e;color:#ffffff;text-decoration:none;padding:14px 24px;border-radius:999px;font-weight:700;">Ativar conta no Authentik</a>
                  </td>
                </tr>
              </table>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 24px;">
                <tr>
                  <td width="33.33%" valign="top" style="padding-right:10px;">
                    <img src="{html.escape(protection_image)}" alt="Proteção e retenção do storage" width="206" style="display:block;width:100%;height:auto;border-radius:16px;">
                    <p style="margin:12px 0 4px;font-weight:700;">Contrato e guarda digital</p>
                    <p style="margin:0;font-size:14px;line-height:1.6;color:#567086;">O contrato assinado fica armazenado no workspace do contrato e disponível para consulta operacional.</p>
                  </td>
                  <td width="33.33%" valign="top" style="padding:0 5px;">
                    <img src="{html.escape(archive_image)}" alt="Camadas de retenção e arquivo" width="206" style="display:block;width:100%;height:auto;border-radius:16px;">
                    <p style="margin:12px 0 4px;font-weight:700;">Workspace e documentos</p>
                    <p style="margin:0;font-size:14px;line-height:1.6;color:#567086;">A pasta do contrato já foi criada para uploads, trilhas de auditoria e material de onboarding.</p>
                  </td>
                  <td width="33.33%" valign="top" style="padding-left:10px;">
                    <div style="border-radius:16px;background:#f4faf8;border:1px solid #d8eee8;padding:16px;height:100%;box-sizing:border-box;">
                      <p style="margin:0 0 10px;font-weight:700;">Próximos passos</p>
                      <ol style="margin:0;padding-left:18px;color:#567086;font-size:14px;line-height:1.6;">
                        <li>Abra o Authentik</li>
                        <li>Use o código de acesso</li>
                        <li>Valide o email corporativo</li>
                        <li>Entre no portal do contrato</li>
                      </ol>
                    </div>
                  </td>
                </tr>
              </table>
              <div style="padding:18px 20px;background:#f8fafc;border:1px solid #dce7f0;border-radius:18px;">
                <p style="margin:0 0 8px;font-size:12px;letter-spacing:0.12em;text-transform:uppercase;color:#52708a;">Links úteis</p>
                <p style="margin:0 0 6px;font-size:14px;">Portal do contrato: <a href="{html.escape(context["portal_url"])}">{html.escape(context["portal_url"])}</a></p>
                <p style="margin:0 0 6px;font-size:14px;">Authentik: <a href="{html.escape(context["authentik_url"])}">{html.escape(context["authentik_url"])}</a></p>
                <p style="margin:0;font-size:14px;">Nextcloud: <a href="{html.escape(context["nextcloud_url"])}">{html.escape(context["nextcloud_url"])}</a></p>
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 36px 30px;background:#0f172a;color:rgba(255,255,255,0.72);font-size:13px;line-height:1.6;">
              Este email foi gerado automaticamente pelo provisionamento de contratos de storage da RPA4ALL.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    def send(self, recipients: list[str], context: dict[str, Any]) -> None:
        if not recipients:
            raise RuntimeError("Nenhum destinatário informado para o onboarding.")

        if not self.settings.smtp_password:
            raise RuntimeError("SMTP_PASSWORD não configurado para envio do onboarding.")

        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=20) as smtp:
            if self.settings.smtp_starttls:
                smtp.starttls()
            smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            for recipient in recipients:
                message = MIMEMultipart("alternative")
                message["Subject"] = f"RPA4ALL | Ativação do contrato {context['contract_code']}"
                message["From"] = f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>"
                message["To"] = recipient
                message.attach(MIMEText(self.render_text(context), "plain", "utf-8"))
                message.attach(MIMEText(self.render_html(context), "html", "utf-8"))
                smtp.send_message(message)


class StoragePortalService:
    PROFILE_LABELS = {
        "manager": "Gestor",
        "operations": "Operações",
        "api": "Integração API",
        "readonly": "Somente leitura",
    }

    def __init__(
        self,
        settings: Settings,
        repository: StorageRepository,
        authentik_client: AuthentikClient,
        mailbox_provisioner: MailboxProvisioner,
        onboarding_mailer: OnboardingMailer,
    ):
        self.settings = settings
        self.repository = repository
        self.authentik_client = authentik_client
        self.mailbox_provisioner = mailbox_provisioner
        self.onboarding_mailer = onboarding_mailer
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings.workspace_root.mkdir(parents=True, exist_ok=True)

    def _workspace_for_contract(self, contract_code: str) -> tuple[Path, str]:
        relative_dir = f"contracts/{contract_code.lower()}"
        workspace = self.settings.workspace_root / contract_code.lower()
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "documents").mkdir(exist_ok=True)
        (workspace / "uploads").mkdir(exist_ok=True)
        return workspace, relative_dir

    def _corporate_email_for_contract(self, contract_code: str, company: str) -> str:
        local = slugify(company, "cliente").replace("-", ".")[:18]
        code = contract_code.lower().replace("-", "")
        return f"{local}.{code[:10]}@{self.settings.mail_domain}"

    def _save_contract_documents(self, workspace: Path, contract_code: str, payload: StorageRequestPayload) -> dict[str, Any]:
        html_path = workspace / "documents" / f"{contract_code.lower()}-minuta.html"
        text_path = workspace / "documents" / f"{contract_code.lower()}-minuta.txt"
        signed_path = None

        contract_html = self._render_contract_html(contract_code, payload)
        contract_text = self._render_contract_text(contract_code, payload)

        html_path.write_text(contract_html, encoding="utf-8")
        text_path.write_text(contract_text, encoding="utf-8")

        if payload.signed_contract_base64 or payload.signed_contract_html or payload.signed_contract_text:
            signed_filename = payload.signed_contract_filename or f"{contract_code.lower()}-contrato-assinado.html"
            signed_path = workspace / "documents" / slugify(Path(signed_filename).stem, "contrato-assinado")
            suffix = Path(signed_filename).suffix.lower() or ".html"
            signed_path = signed_path.with_suffix(suffix)
            if payload.signed_contract_base64:
                signed_path.write_bytes(base64.b64decode(payload.signed_contract_base64))
            elif payload.signed_contract_html:
                signed_path.write_text(payload.signed_contract_html, encoding="utf-8")
            else:
                signed_path.write_text(payload.signed_contract_text or "", encoding="utf-8")

        return {
            "reference": contract_code,
            "html_relative_path": str(html_path.relative_to(self.settings.root_dir)),
            "text_relative_path": str(text_path.relative_to(self.settings.root_dir)),
            "signed_relative_path": str(signed_path.relative_to(self.settings.root_dir)) if signed_path else None,
        }

    def _render_contract_text(self, contract_code: str, payload: StorageRequestPayload) -> str:
        return (
            f"Contrato {contract_code}\n"
            f"Empresa: {payload.company}\n"
            f"Razão social: {payload.legal_name}\n"
            f"Projeto: {payload.project}\n"
            f"Contato: {payload.contact} / {payload.email}\n"
            f"Volume: {payload.volume} TB | Ingresso: {payload.ingress} TB/mês\n"
            f"Temperatura: {payload.temperature} | Retenção: {payload.retention}\n"
            f"Billing: {payload.billing} | Vigência: {payload.term} meses\n"
            f"Mensal equivalente: {render_currency(payload.monthly_service)}\n"
            f"Valor contratual: {render_currency(payload.contract_value)}\n"
        )

    def _render_contract_html(self, contract_code: str, payload: StorageRequestPayload) -> str:
        return f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>{html.escape(contract_code)}</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;background:#f5f8fb;color:#173042;padding:32px;">
  <div style="max-width:900px;margin:0 auto;background:#fff;border-radius:20px;padding:32px;border:1px solid #d8e3ec;">
    <h1 style="margin-top:0;">Instrumento particular de storage gerenciado</h1>
    <p><strong>Referência:</strong> {html.escape(contract_code)}</p>
    <p><strong>Contratante:</strong> {html.escape(payload.company)} ({html.escape(payload.legal_name)})</p>
    <p><strong>Representante:</strong> {html.escape(payload.contact)} | {html.escape(payload.role)} | {html.escape(payload.email)}</p>
    <p><strong>Projeto:</strong> {html.escape(payload.project)}</p>
    <p><strong>Endereço:</strong> {html.escape(payload.address)}, {html.escape(payload.address_number)} - {html.escape(payload.district)} - {html.escape(payload.city)}/{html.escape(payload.state)}</p>
    <hr>
    <p><strong>Camada:</strong> {html.escape(payload.temperature)}</p>
    <p><strong>Volume protegido:</strong> {payload.volume:.2f} TB</p>
    <p><strong>Novos dados por mês:</strong> {payload.ingress:.2f} TB</p>
    <p><strong>Retenção:</strong> {html.escape(payload.retention)}</p>
    <p><strong>SLA:</strong> {html.escape(payload.sla)}</p>
    <p><strong>Modelo de cobrança:</strong> {html.escape(payload.billing)}</p>
    <p><strong>Mensal equivalente:</strong> {render_currency(payload.monthly_service)}</p>
    <p><strong>Valor contratual:</strong> {render_currency(payload.contract_value)}</p>
    <p><strong>Observações:</strong> {html.escape(payload.notes or "Sem observações adicionais.")}</p>
  </div>
</body>
</html>"""

    def _user_permissions(self, profile: str) -> dict[str, bool]:
        return {
            "manage_profiles": profile == "manager",
            "generate_tokens": profile in {"manager", "api"},
            "manage_payments": profile == "manager" and self.settings.manage_payments,
        }

    def _profile_label(self, profile: str) -> str:
        return self.PROFILE_LABELS.get(profile, profile)

    def _inventory(self) -> dict[str, Any]:
        total, used, free = shutil.disk_usage(self.settings.workspace_root)
        memory_available_gb = 0
        meminfo = Path("/proc/meminfo")
        if meminfo.exists():
            lines = meminfo.read_text(encoding="utf-8", errors="ignore").splitlines()
            mapping = {}
            for line in lines:
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                mapping[key.strip()] = value.strip()
            if "MemAvailable" in mapping:
                memory_available_gb = round(int(mapping["MemAvailable"].split()[0]) / 1024 / 1024, 1)
        return {
            "host": platform.node(),
            "cpu": {"model": platform.processor() or "CPU", "cores": os.cpu_count() or 0},
            "memory": {"available_gb": memory_available_gb},
            "disks": [
                {
                    "mountpoint": str(self.settings.workspace_root),
                    "used_gb": round(used / 1024 / 1024 / 1024, 1),
                    "total_gb": round(total / 1024 / 1024 / 1024, 1),
                    "free_gb": round(free / 1024 / 1024 / 1024, 1),
                }
            ],
            "services": [
                {"name": "Authentik", "status": self.settings.authentik_public_url},
                {"name": "Nextcloud", "status": self.settings.nextcloud_url},
                {"name": "Storage Workspace", "status": str(self.settings.workspace_root)},
            ],
        }

    def _nextcloud_workspace_url(self, contract_code: str) -> str:
        return self.settings.nextcloud_url.rstrip("/") + self.settings.nextcloud_base_path + "/" + contract_code.lower()

    def _build_connections(self, contract: dict[str, Any], current_user: dict[str, Any]) -> dict[str, Any]:
        workspace = Path(contract["workspace_path"])
        workspace_relative = contract["workspace_relative_dir"]
        return {
            "authentik_url": self.settings.authentik_public_url,
            "nextcloud_url": self.settings.nextcloud_url,
            "nextcloud_dir": self.settings.nextcloud_base_path.rstrip("/") + "/" + contract["contract_code"].lower(),
            "nextcloud_hint": "Pasta provisionada para contrato e onboarding",
            "nextcloud_workspace_url": self._nextcloud_workspace_url(contract["contract_code"]),
            "workspace_host_path": str(workspace),
            "api_base": self.settings.api_public_base,
            "ingest_endpoint": self.settings.api_public_base.rstrip("/") + self.settings.ingest_path,
            "curl_example": (
                "curl -X POST "
                + self.settings.api_public_base.rstrip("/")
                + self.settings.ingest_path
                + " \\\n  -H 'Authorization: Bearer <api-token>' \\\n"
                + f"  -F 'contract_code={contract['contract_code']}' \\\n"
                + "  -F 'file=@./arquivo.bin'"
            ),
        }

    def _mail_context(self, contract: dict[str, Any], current_user: dict[str, Any]) -> dict[str, Any]:
        portal_url = self.settings.portal_public_url + "?portal=" + current_user["portal_token"]
        return {
            "contract_code": contract["contract_code"],
            "company": contract["company"],
            "project": contract["project"],
            "contact": current_user["full_name"],
            "corporate_email": contract["corporate_email"],
            "authentik_username": contract["authentik_username"],
            "activation_code": current_user["activation_code"],
            "authentik_url": self.settings.authentik_public_url,
            "portal_url": portal_url,
            "nextcloud_url": self._nextcloud_workspace_url(contract["contract_code"]),
            "public_site_url": self.settings.public_site_url.rstrip("/"),
        }

    def _send_contract_onboarding(self, contract: dict[str, Any], current_user: dict[str, Any], extra_recipients: list[str] | None = None) -> None:
        recipients = dedupe_emails(
            [
                contract["corporate_email"],
                contract.get("personal_email") or contract["email"],
                *(extra_recipients or []),
            ]
        )
        self.onboarding_mailer.send(recipients, self._mail_context(contract, current_user))

    def request_access(self, payload: StorageRequestPayload) -> dict[str, Any]:
        contract_code = build_contract_code(payload.company, payload.project)
        workspace, workspace_relative_dir = self._workspace_for_contract(contract_code)
        corporate_email = self._corporate_email_for_contract(contract_code, payload.company)
        manager_username = build_username(contract_code, payload.company)
        activation_code = build_activation_code()
        portal_token, portal_token_hash, portal_token_preview = build_token("stp")

        documents = self._save_contract_documents(workspace, contract_code, payload)
        mailbox_result = self.mailbox_provisioner.create_mailbox(corporate_email, payload.contact, activation_code)
        authentik_result = self.authentik_client.create_or_update_user(
            username=manager_username,
            email=corporate_email,
            full_name=payload.contact,
            activation_code=activation_code,
        )

        primary_user = {
            "portal_token": portal_token,
            "portal_token_hash": portal_token_hash,
            "portal_token_preview": portal_token_preview,
            "username": manager_username,
            "full_name": payload.contact,
            "email": payload.personal_email or payload.email,
            "corporate_email": corporate_email,
            "profile": "manager",
            "status": "active",
            "activation_code": activation_code,
            "authentik_user_id": authentik_result.get("authentik_user_id"),
        }

        contract_record = {
            "contract_code": contract_code,
            "company": payload.company,
            "legal_name": payload.legal_name,
            "company_document": payload.company_document,
            "contact": payload.contact,
            "role": payload.role,
            "email": payload.email,
            "personal_email": payload.personal_email or payload.email,
            "corporate_email": corporate_email,
            "status": "active",
            "mode": payload.mode,
            "project": payload.project,
            "workspace_path": str(workspace),
            "workspace_relative_dir": workspace_relative_dir,
            "billing": payload.billing,
            "term": payload.term,
            "monthly_service": payload.monthly_service,
            "contract_value": payload.contract_value,
            "start_date": payload.start_date,
            "request_payload": payload.model_dump(),
            "mailbox_status": mailbox_result.get("status", "generated"),
            "authentik_username": manager_username,
            "onboarding_sent_at": None,
        }

        contract = self.repository.create_contract(contract_record, documents, primary_user)
        if not contract:
            raise HTTPException(status_code=500, detail="Falha ao persistir o contrato.")

        contract["corporate_email"] = corporate_email
        contract["authentik_username"] = manager_username
        current_user = {
            "id": 0,
            "portal_token": portal_token,
            "full_name": payload.contact,
            "activation_code": activation_code,
        }
        self._send_contract_onboarding(contract, current_user)
        onboarding_sent_at = utcnow_iso()
        documents["portal_token_preview"] = portal_token_preview
        self.repository.update_contract_documents(contract["id"], documents, onboarding_sent_at=onboarding_sent_at)
        contract = self.repository.get_contract_by_code(contract_code) or contract

        return {
            "success": True,
            "message": "Acesso provisionado, usuário criado no Authentik e onboarding enviado",
            "portal_token": portal_token,
            "portal_url": self.settings.portal_public_url + "?portal=" + portal_token,
            "contract_code": contract_code,
            "documents": documents,
            "corporate_email": corporate_email,
            "activation_code": activation_code,
        }

    def bootstrap_portal(self, portal_token: str) -> dict[str, Any]:
        result = self.repository.get_contract_by_portal_token(portal_token)
        if not result:
            raise HTTPException(status_code=404, detail="Portal token inválido ou expirado.")
        contract, current_user = result
        documents = json.loads(contract["documents_json"])
        api_tokens = self.repository.list_api_tokens(contract["id"])
        users = self._decorate_users(self.repository.list_users(contract["id"]))
        files = self.list_files(contract, ".")
        return {
            "contract": {
                "contract_code": contract["contract_code"],
                "company": contract["company"],
                "project": contract["project"],
                "monthly_service": contract["monthly_service"],
                "term_months": contract["term_months"],
                "status": contract["status"],
                "workspace_relative_dir": contract["workspace_relative_dir"],
                "workspace_path": contract["workspace_path"],
            },
            "current_user": {
                "id": current_user["id"],
                "username": current_user["username"],
                "full_name": current_user["full_name"],
                "email": current_user["email"],
                "profile": current_user["profile"],
                "profile_label": self._profile_label(current_user["profile"]),
                "status": current_user["status"],
            },
            "permissions": self._user_permissions(current_user["profile"]),
            "connections": self._build_connections(contract, current_user),
            "documents": documents,
            "api_tokens": api_tokens,
            "users": users,
            "payments": self.repository.list_payments(contract["id"]),
            "files": files,
            "inventory": self._inventory(),
        }

    def _decorate_users(self, users: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "id": user["id"],
                "username": user["username"],
                "full_name": user["full_name"],
                "email": user["email"],
                "corporate_email": user.get("corporate_email"),
                "profile": user["profile"],
                "profile_label": self._profile_label(user["profile"]),
                "status": user["status"],
                "created_at": user["created_at"],
            }
            for user in users
        ]

    def create_api_token(self, portal_token: str, label: str) -> dict[str, Any]:
        result = self.repository.get_contract_by_portal_token(portal_token)
        if not result:
            raise HTTPException(status_code=404, detail="Portal token inválido.")
        contract, current_user = result
        permissions = self._user_permissions(current_user["profile"])
        if not permissions["generate_tokens"]:
            raise HTTPException(status_code=403, detail="Seu perfil não pode gerar tokens.")

        token, token_hash, preview = build_token("sta")
        self.repository.create_api_token(contract["id"], label.strip() or "Integração principal", token_hash, preview)
        return {
            "token": {"token": token, "preview": preview},
            "api_tokens": self.repository.list_api_tokens(contract["id"]),
            "connections": self._build_connections(contract, current_user),
        }

    def create_subuser(self, portal_token: str, full_name: str, email: str, profile: str) -> dict[str, Any]:
        result = self.repository.get_contract_by_portal_token(portal_token)
        if not result:
            raise HTTPException(status_code=404, detail="Portal token inválido.")
        contract, current_user = result
        permissions = self._user_permissions(current_user["profile"])
        if not permissions["manage_profiles"]:
            raise HTTPException(status_code=403, detail="Seu perfil não pode criar subusuários.")

        normalized_profile = profile if profile in self.PROFILE_LABELS else "operations"
        activation_code = build_activation_code()
        sub_portal_token, token_hash, token_preview = build_token("stp")
        username = build_username(contract["contract_code"], full_name)
        corporate_email = f"{slugify(full_name, 'usuario').replace('-', '.')}.{contract['contract_code'].lower().replace('-', '')[:8]}@{self.settings.mail_domain}"

        authentik_result = self.authentik_client.create_or_update_user(
            username=username,
            email=corporate_email,
            full_name=full_name,
            activation_code=activation_code,
        )

        self.repository.create_subuser(
            contract["id"],
            {
                "portal_token_hash": token_hash,
                "portal_token_preview": token_preview,
                "username": username,
                "full_name": full_name,
                "email": email,
                "corporate_email": corporate_email,
                "profile": normalized_profile,
                "status": "active",
                "activation_code": activation_code,
                "authentik_user_id": authentik_result.get("authentik_user_id"),
            },
        )

        mail_context = {
            "contract_code": contract["contract_code"],
            "company": contract["company"],
            "project": contract["project"],
            "contact": full_name,
            "corporate_email": corporate_email,
            "authentik_username": username,
            "activation_code": activation_code,
            "authentik_url": self.settings.authentik_public_url,
            "portal_url": self.settings.portal_public_url + "?portal=" + sub_portal_token,
            "nextcloud_url": self._nextcloud_workspace_url(contract["contract_code"]),
            "public_site_url": self.settings.public_site_url.rstrip("/"),
        }
        self.onboarding_mailer.send(dedupe_emails([corporate_email, email]), mail_context)
        return {"users": self._decorate_users(self.repository.list_users(contract["id"]))}

    def update_user(self, portal_token: str, user_id: int, profile: str | None, status: str | None) -> dict[str, Any]:
        result = self.repository.get_contract_by_portal_token(portal_token)
        if not result:
            raise HTTPException(status_code=404, detail="Portal token inválido.")
        contract, current_user = result
        permissions = self._user_permissions(current_user["profile"])
        if not permissions["manage_profiles"]:
            raise HTTPException(status_code=403, detail="Seu perfil não pode atualizar subusuários.")
        if profile and profile not in self.PROFILE_LABELS:
            raise HTTPException(status_code=400, detail="Perfil inválido.")
        if status and status not in {"active", "disabled"}:
            raise HTTPException(status_code=400, detail="Status inválido.")
        self.repository.update_user(user_id, profile=profile, status=status)
        return {"users": self._decorate_users(self.repository.list_users(contract["id"]))}

    def _resolve_workspace_path(self, contract: dict[str, Any], relative_path: str) -> Path:
        clean_path = ensure_relative_path(relative_path)
        workspace = Path(contract["workspace_path"]).resolve()
        target = (workspace / clean_path).resolve()
        if not str(target).startswith(str(workspace)):
            raise HTTPException(status_code=400, detail="Caminho fora do workspace do contrato.")
        return target

    def list_files(self, contract: dict[str, Any], relative_path: str) -> dict[str, Any]:
        target = self._resolve_workspace_path(contract, relative_path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="Diretório não encontrado.")
        if not target.is_dir():
            raise HTTPException(status_code=400, detail="O caminho informado não é um diretório.")
        entries = []
        total_bytes = 0
        for child in sorted(target.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
            stat = child.stat()
            size = stat.st_size if child.is_file() else 0
            total_bytes += size
            entries.append(
                {
                    "name": child.name,
                    "path": str(child.relative_to(contract["workspace_path"])),
                    "kind": "folder" if child.is_dir() else "file",
                    "size": size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                }
            )
        visible_path = "." if target == Path(contract["workspace_path"]) else str(target.relative_to(contract["workspace_path"]))
        return {"path": visible_path, "entries": entries, "total_bytes": total_bytes}

    def create_folder(self, portal_token: str, folder_path: str) -> dict[str, Any]:
        result = self.repository.get_contract_by_portal_token(portal_token)
        if not result:
            raise HTTPException(status_code=404, detail="Portal token inválido.")
        contract, current_user = result
        if current_user["profile"] == "readonly":
            raise HTTPException(status_code=403, detail="Seu perfil não pode criar pastas.")
        target = self._resolve_workspace_path(contract, folder_path)
        target.mkdir(parents=True, exist_ok=True)
        parent = "." if target.parent == Path(contract["workspace_path"]) else str(target.parent.relative_to(contract["workspace_path"]))
        return {"files": self.list_files(contract, parent)}

    async def upload_file(self, portal_token: str, relative_dir: str, upload: UploadFile) -> dict[str, Any]:
        result = self.repository.get_contract_by_portal_token(portal_token)
        if not result:
            raise HTTPException(status_code=404, detail="Portal token inválido.")
        contract, current_user = result
        if current_user["profile"] == "readonly":
            raise HTTPException(status_code=403, detail="Seu perfil não pode enviar arquivos.")
        directory = self._resolve_workspace_path(contract, relative_dir or ".")
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / Path(upload.filename or "upload.bin").name
        content = await upload.read()
        target.write_bytes(content)
        visible_path = "." if directory == Path(contract["workspace_path"]) else str(directory.relative_to(contract["workspace_path"]))
        return {"files": self.list_files(contract, visible_path)}

    def create_payment(self, portal_token: str, amount_brl: float, description: str) -> dict[str, Any]:
        result = self.repository.get_contract_by_portal_token(portal_token)
        if not result:
            raise HTTPException(status_code=404, detail="Portal token inválido.")
        contract, current_user = result
        permissions = self._user_permissions(current_user["profile"])
        if not permissions["manage_payments"]:
            raise HTTPException(status_code=403, detail="Integração de pagamentos não está habilitada para este perfil.")
        self.repository.create_payment(contract["id"], amount_brl, description)
        return {"payments": self.repository.list_payments(contract["id"])}

    def finalize_contract(self, payload: FinalizeContractPayload) -> dict[str, Any]:
        contract = None
        current_user = None
        if payload.portal_token:
            result = self.repository.get_contract_by_portal_token(payload.portal_token)
            if result:
                contract, current_user = result
        elif payload.contract_code:
            contract = self.repository.get_contract_by_code(payload.contract_code)
            if contract:
                users = self.repository.list_users(contract["id"])
                current_user = users[0] if users else None
        if not contract or not current_user:
            raise HTTPException(status_code=404, detail="Contrato não encontrado para finalização.")

        workspace = Path(contract["workspace_path"])
        documents = json.loads(contract["documents_json"])
        signed_filename = payload.signed_contract_filename or f"{contract['contract_code'].lower()}-assinado.html"
        target = workspace / "documents" / Path(signed_filename).name

        if payload.signed_contract_base64:
            target.write_bytes(base64.b64decode(payload.signed_contract_base64))
        elif payload.signed_contract_html:
            target.write_text(payload.signed_contract_html, encoding="utf-8")
        elif payload.signed_contract_text:
            target.write_text(payload.signed_contract_text, encoding="utf-8")
        else:
            raise HTTPException(status_code=400, detail="Nenhum contrato assinado foi enviado para armazenamento.")

        documents["signed_relative_path"] = str(target.relative_to(self.settings.root_dir))
        self.repository.update_contract_documents(contract["id"], documents)
        return {
            "success": True,
            "message": "Contrato assinado armazenado digitalmente com sucesso",
            "documents": documents,
        }


_service_instance: StoragePortalService | None = None


def get_service() -> StoragePortalService:
    global _service_instance
    if _service_instance is None:
        settings = load_settings()
        _service_instance = StoragePortalService(
            settings=settings,
            repository=StorageRepository(settings.database_path),
            authentik_client=AuthentikClient(settings),
            mailbox_provisioner=MailboxProvisioner(settings),
            onboarding_mailer=OnboardingMailer(settings),
        )
    return _service_instance


app = FastAPI(title="RPA4ALL Storage Portal API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://rpa4all.com",
        "https://www.rpa4all.com",
        "http://localhost",
        "http://127.0.0.1",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/storage/request-access")
def storage_request_access(payload: StorageRequestPayload) -> JSONResponse:
    if digits_only(payload.company_document) and len(digits_only(payload.company_document)) != 14:
        raise HTTPException(status_code=400, detail="CNPJ inválido.")
    if digits_only(payload.representative_document) and len(digits_only(payload.representative_document)) != 11:
        raise HTTPException(status_code=400, detail="CPF do representante inválido.")
    result = get_service().request_access(payload)
    return JSONResponse(result)


@app.get("/storage/portal/bootstrap")
def storage_portal_bootstrap(portal_token: str) -> JSONResponse:
    return JSONResponse(get_service().bootstrap_portal(portal_token))


@app.post("/storage/portal/tokens")
def storage_portal_tokens(payload: PortalTokenCreatePayload) -> JSONResponse:
    return JSONResponse(get_service().create_api_token(payload.portal_token, payload.label))


@app.post("/storage/portal/subusers")
def storage_portal_subusers(payload: PortalSubuserCreatePayload) -> JSONResponse:
    return JSONResponse(get_service().create_subuser(payload.portal_token, payload.full_name, payload.email, payload.profile))


@app.patch("/storage/portal/users/{user_id}")
def storage_portal_update_user(user_id: int, payload: PortalUserUpdatePayload) -> JSONResponse:
    return JSONResponse(get_service().update_user(payload.portal_token, user_id, payload.profile, payload.status))


@app.get("/storage/portal/files")
def storage_portal_files(portal_token: str, path: str = ".") -> JSONResponse:
    result = get_service().repository.get_contract_by_portal_token(portal_token)
    if not result:
        raise HTTPException(status_code=404, detail="Portal token inválido.")
    contract, _ = result
    return JSONResponse(get_service().list_files(contract, path))


@app.post("/storage/portal/files/folder")
def storage_portal_create_folder(payload: PortalFolderCreatePayload) -> JSONResponse:
    return JSONResponse(get_service().create_folder(payload.portal_token, payload.folder_path))


@app.post("/storage/portal/files/upload")
async def storage_portal_upload_file(
    portal_token: str = Form(...),
    relative_dir: str = Form("."),
    upload: UploadFile = File(...),
) -> JSONResponse:
    return JSONResponse(await get_service().upload_file(portal_token, relative_dir, upload))


@app.post("/storage/portal/payments")
def storage_portal_payments(payload: PortalPaymentPayload) -> JSONResponse:
    return JSONResponse(get_service().create_payment(payload.portal_token, payload.amount_brl, payload.description))


@app.post("/storage/contracts/finalize")
def storage_contracts_finalize(payload: FinalizeContractPayload) -> JSONResponse:
    return JSONResponse(get_service().finalize_contract(payload))


@app.get("/health")
def health() -> dict[str, Any]:
    settings = load_settings()
    return {
        "status": "healthy",
        "service": "rpa4all-storage-portal-api",
        "workspace_root": str(settings.workspace_root),
        "database_path": str(settings.database_path),
    }
