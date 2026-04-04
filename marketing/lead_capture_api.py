#!/usr/bin/env python3
"""API de captura de leads — Marketing RPA4ALL.

Endpoints:
    POST /marketing/leads       — Captura novo lead do formulário
    GET  /marketing/leads       — Lista leads (autenticado)
    GET  /marketing/leads/stats — Estatísticas de leads
    GET  /marketing/health      — Health check

Integrações automáticas:
    - PostgreSQL (marketing.leads)
    - Telegram (notificação de novo lead)
    - WhatsApp (mensagem de boas-vindas)
    - Email drip (agenda sequência de nutrição)
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("marketing.lead_capture")

# ─── Config ──────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@192.168.15.2:5433/shared",
)
TELEGRAM_ENABLED = os.getenv("MARKETING_TELEGRAM_NOTIFY", "true").lower() == "true"
WHATSAPP_ENABLED = os.getenv("MARKETING_WHATSAPP_NOTIFY", "true").lower() == "true"
EMAIL_DRIP_ENABLED = os.getenv("MARKETING_EMAIL_DRIP", "true").lower() == "true"

router = APIRouter(prefix="/marketing", tags=["marketing"])


# ─── Models ──────────────────────────────────────────────────────────
class LeadCreate(BaseModel):
    """Dados do formulário de captura."""

    nome: str = Field(..., min_length=2, max_length=200)
    email: str = Field(..., max_length=254)
    empresa: str = Field(..., min_length=2, max_length=200)
    cargo: Optional[str] = Field(None, max_length=200)
    telefone: Optional[str] = Field(None, max_length=30)
    origem: str = Field("landing_diagnostico", max_length=100)
    utm_source: Optional[str] = Field(None, max_length=100)
    utm_medium: Optional[str] = Field(None, max_length=100)
    utm_campaign: Optional[str] = Field(None, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Valida formato do email."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Email inválido")
        return v.lower().strip()

    @field_validator("telefone")
    @classmethod
    def validate_telefone(cls, v: Optional[str]) -> Optional[str]:
        """Remove caracteres não numéricos do telefone."""
        if v is None:
            return v
        cleaned = re.sub(r"[^\d+]", "", v)
        if len(cleaned) < 10:
            raise ValueError("Telefone deve ter pelo menos 10 dígitos")
        return cleaned


class LeadResponse(BaseModel):
    """Resposta após captura."""

    success: bool
    lead_id: int
    message: str


class LeadStats(BaseModel):
    """Estatísticas de leads."""

    total: int
    hoje: int
    semana: int
    por_origem: dict
    por_utm_source: dict


# ─── Database ────────────────────────────────────────────────────────
def _get_conn():
    """Obtém conexão PostgreSQL."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def _ensure_schema():
    """Cria schema e tabela se não existirem."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS marketing")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS marketing.leads (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(200) NOT NULL,
                    email VARCHAR(254) NOT NULL,
                    empresa VARCHAR(200) NOT NULL,
                    cargo VARCHAR(200),
                    telefone VARCHAR(30),
                    origem VARCHAR(100) DEFAULT 'landing_diagnostico',
                    utm_source VARCHAR(100),
                    utm_medium VARCHAR(100),
                    utm_campaign VARCHAR(100),
                    status VARCHAR(50) DEFAULT 'novo',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    drip_step INT DEFAULT 0,
                    drip_next_at TIMESTAMPTZ,
                    notas TEXT
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_leads_email
                ON marketing.leads (email)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_leads_status
                ON marketing.leads (status)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS marketing.daily_metrics (
                    id SERIAL PRIMARY KEY,
                    data DATE NOT NULL UNIQUE,
                    leads_total INT DEFAULT 0,
                    leads_novos INT DEFAULT 0,
                    cpl_meta NUMERIC(10,2),
                    cpl_google NUMERIC(10,2),
                    cpl_linkedin NUMERIC(10,2),
                    custo_total NUMERIC(10,2),
                    diagnosticos_agendados INT DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
    finally:
        conn.close()


def _insert_lead(lead: LeadCreate) -> int:
    """Insere lead no banco e retorna ID."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO marketing.leads
                    (nome, email, empresa, cargo, telefone, origem,
                     utm_source, utm_medium, utm_campaign, drip_next_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW() + INTERVAL '2 days')
                RETURNING id
                """,
                (
                    lead.nome,
                    lead.email,
                    lead.empresa,
                    lead.cargo,
                    lead.telefone,
                    lead.origem,
                    lead.utm_source,
                    lead.utm_medium,
                    lead.utm_campaign,
                ),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def _check_duplicate(email: str) -> bool:
    """Verifica se email já está cadastrado."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM marketing.leads WHERE email = %s",
                (email,),
            )
            return cur.fetchone()[0] > 0
    finally:
        conn.close()


def _get_stats() -> dict:
    """Coleta estatísticas de leads."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as total FROM marketing.leads")
            total = cur.fetchone()["total"]

            cur.execute(
                "SELECT COUNT(*) as hoje FROM marketing.leads "
                "WHERE created_at::date = CURRENT_DATE"
            )
            hoje = cur.fetchone()["hoje"]

            cur.execute(
                "SELECT COUNT(*) as semana FROM marketing.leads "
                "WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'"
            )
            semana = cur.fetchone()["semana"]

            cur.execute(
                "SELECT COALESCE(origem, 'desconhecido') as origem, COUNT(*) as qtd "
                "FROM marketing.leads GROUP BY origem ORDER BY qtd DESC"
            )
            por_origem = {r["origem"]: r["qtd"] for r in cur.fetchall()}

            cur.execute(
                "SELECT COALESCE(utm_source, 'direto') as src, COUNT(*) as qtd "
                "FROM marketing.leads GROUP BY utm_source ORDER BY qtd DESC"
            )
            por_utm = {r["src"]: r["qtd"] for r in cur.fetchall()}

            return {
                "total": total,
                "hoje": hoje,
                "semana": semana,
                "por_origem": por_origem,
                "por_utm_source": por_utm,
            }
    finally:
        conn.close()


# ─── Notificações ────────────────────────────────────────────────────
async def _notify_telegram(lead: LeadCreate, lead_id: int) -> None:
    """Envia notificação de novo lead no Telegram."""
    if not TELEGRAM_ENABLED:
        return
    try:
        from tools.secrets_loader import get_telegram_token, get_telegram_chat_id

        from telegram import Bot

        token = get_telegram_token()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "948686300")
        bot = Bot(token=token)

        msg = (
            f"🔔 *Novo Lead Capturado!*\n\n"
            f"👤 *Nome*: {lead.nome}\n"
            f"🏢 *Empresa*: {lead.empresa}\n"
            f"💼 *Cargo*: {lead.cargo or 'Não informado'}\n"
            f"📧 *Email*: {lead.email}\n"
            f"📱 *Telefone*: {lead.telefone or 'Não informado'}\n"
            f"📍 *Origem*: {lead.origem}\n"
            f"🏷️ *UTM*: {lead.utm_source or '-'} / {lead.utm_medium or '-'} / {lead.utm_campaign or '-'}\n"
            f"🆔 *ID*: {lead_id}\n\n"
            f"⏱️ Capturado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        await bot.send_message(
            chat_id=chat_id,
            text=msg,
            parse_mode="Markdown",
        )
        logger.info("Telegram notification sent for lead %s", lead_id)
    except Exception:
        logger.exception("Falha ao notificar Telegram para lead %s", lead_id)


async def _notify_whatsapp(lead: LeadCreate, lead_id: int) -> None:
    """Envia mensagem de boas-vindas no WhatsApp."""
    if not WHATSAPP_ENABLED or not lead.telefone:
        return
    try:
        import httpx

        waha_url = os.getenv("WAHA_API_URL", "http://localhost:3001")
        phone = lead.telefone.lstrip("+")
        if not phone.startswith("55"):
            phone = f"55{phone}"

        msg = (
            f"Olá {lead.nome.split()[0]}! 👋\n\n"
            f"Obrigado pelo interesse no Diagnóstico de Automação da RPA4ALL!\n\n"
            f"Em breve um especialista entrará em contato para agendar "
            f"sua sessão gratuita de 20 minutos.\n\n"
            f"Enquanto isso, me conta: qual é o principal processo "
            f"que você gostaria de automatizar na {lead.empresa}?\n\n"
            f"— Equipe RPA4ALL 🤖"
        )

        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{waha_url}/api/sendText",
                json={
                    "chatId": f"{phone}@c.us",
                    "text": msg,
                    "session": "default",
                },
            )
        logger.info("WhatsApp welcome sent for lead %s", lead_id)
    except Exception:
        logger.exception("Falha ao enviar WhatsApp para lead %s", lead_id)


# ─── Endpoints ───────────────────────────────────────────────────────
@router.on_event("startup")
async def _startup():
    """Garante schema no startup."""
    _ensure_schema()
    logger.info("Marketing schema pronto")


@router.post("/leads", response_model=LeadResponse)
async def capture_lead(lead: LeadCreate, request: Request):
    """Captura novo lead do formulário da landing page."""
    if _check_duplicate(lead.email):
        return LeadResponse(
            success=True,
            lead_id=0,
            message="Obrigado! Já recebemos seu cadastro anteriormente.",
        )

    lead_id = _insert_lead(lead)
    logger.info(
        "Lead capturado: id=%s email=%s empresa=%s origem=%s",
        lead_id,
        lead.email,
        lead.empresa,
        lead.origem,
    )

    # Dispara notificações async (não bloqueia resposta)
    asyncio.create_task(_notify_telegram(lead, lead_id))
    asyncio.create_task(_notify_whatsapp(lead, lead_id))

    return LeadResponse(
        success=True,
        lead_id=lead_id,
        message="Obrigado! Em breve entraremos em contato para agendar seu diagnóstico gratuito.",
    )


@router.get("/leads/stats", response_model=LeadStats)
async def get_lead_stats():
    """Retorna estatísticas de leads."""
    stats = _get_stats()
    return LeadStats(**stats)


@router.get("/health")
async def marketing_health():
    """Health check do módulo marketing."""
    return {"status": "ok", "module": "marketing", "timestamp": datetime.now(timezone.utc).isoformat()}
