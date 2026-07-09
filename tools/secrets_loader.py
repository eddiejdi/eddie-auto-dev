#!/usr/bin/env python3
"""Central secret helpers — Secrets Agent é a fonte primária de credenciais.

Telegram aceita fallback de variáveis de ambiente para serviços locais
(/etc/default/eddie-common) quando o Secrets Agent não responde.
"""
import logging
import os

logger = logging.getLogger(__name__)

def _get_client():
    """Retorna client autenticado do Secrets Agent."""
    from tools.secrets_agent_client import get_secrets_agent_client
    return get_secrets_agent_client()


def get_field(name: str, field: str = "password") -> str:
    """Busca um secret pelo nome e campo no Secrets Agent."""
    client = _get_client()
    try:
        val = client.get_local_secret(name, field=field)
        if val:
            return val
        # Tenta campo password como padrão se o field original falhou
        if field != "password":
            val = client.get_local_secret(name, field="password")
            if val:
                return val
        raise RuntimeError(f"Secret {name} field {field} not found in Secrets Agent")
    finally:
        client.close()


def get_telegram_token() -> str:
    """Retorna o token do Telegram Bot via Secrets Agent."""
    client = _get_client()
    try:
        # Tenta os fields possíveis
        for field in ("password", "token"):
            val = client.get_local_secret("shared/telegram_bot_token", field=field)
            if val:
                return val
    finally:
        client.close()
    env_token = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_TOKEN") or "").strip()
    if env_token:
        return env_token
    raise RuntimeError("Telegram token not found in Secrets Agent (shared/telegram_bot_token)")


def get_telegram_chat_id() -> str:
    """Retorna o chat_id do Telegram via Secrets Agent."""
    client = _get_client()
    try:
        for field in ("chat_id", "password"):
            val = client.get_local_secret("shared/telegram_chat_id", field=field)
            if val:
                return val
        env_chat = (os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TG_CHAT_ID") or "").strip()
        if env_chat:
            return env_chat
        logger.warning("Telegram chat_id not found in Secrets Agent")
        return ""
    finally:
        client.close()


def get_agenda_telegram_chat_id() -> str:
    """Chat_id dedicado à agenda diária (opcional)."""
    env_chat = (os.getenv("AGENDA_TELEGRAM_CHAT_ID") or "").strip()
    if env_chat:
        return env_chat
    client = _get_client()
    try:
        for secret_name, field in (
            ("shared/agenda_telegram_chat_id", "chat_id"),
            ("shared/agenda_telegram_chat_id", "password"),
        ):
            val = client.get_local_secret(secret_name, field=field)
            if val:
                return val
    finally:
        client.close()
    return get_telegram_chat_id()


def get_trading_telegram_chat_id() -> str:
    """Retorna o chat_id dedicado ao canal de trading via Secrets Agent."""
    client = _get_client()
    try:
        for secret_name, field in (
            ("shared/trading_telegram_chat_id", "chat_id"),
            ("authentik/shared/trading_telegram_chat_id", "chat_id"),
            ("shared/trading_telegram_chat_id", "password"),
            ("authentik/shared/trading_telegram_chat_id", "password"),
        ):
            val = client.get_local_secret(secret_name, field=field)
            if val:
                return val
        return ""
    finally:
        client.close()


def get_trading_telegram_thread_id() -> str:
    """Retorna o thread_id dedicado ao canal de trading via Secrets Agent."""
    client = _get_client()
    try:
        for secret_name, field in (
            ("shared/trading_telegram_thread_id", "thread_id"),
            ("authentik/shared/trading_telegram_thread_id", "thread_id"),
            ("shared/trading_telegram_thread_id", "password"),
            ("authentik/shared/trading_telegram_thread_id", "password"),
        ):
            val = client.get_local_secret(secret_name, field=field)
            if val:
                return val
        return ""
    finally:
        client.close()


def get_fly_token() -> str:
    """Retorna o Fly API token via Secrets Agent."""
    client = _get_client()
    try:
        val = client.get_secret("shared/fly_api_token")
        return val or ""
    finally:
        client.close()


def get_database_url() -> str:
    """Retorna DATABASE_URL via Secrets Agent."""
    client = _get_client()
    try:
        for field in ("url", "password"):
            val = client.get_local_secret("shared/database_url", field=field)
            if val:
                return val
        logger.warning("DATABASE_URL not found in Secrets Agent")
        return ""
    finally:
        client.close()


def get_openwebui_api_key() -> str:
    """Retorna a API key do Open WebUI via Secrets Agent."""
    client = _get_client()
    try:
        val = client.get_secret("openwebui/api_key")
        if val:
            return val
        raise RuntimeError("OpenWebUI API key not found in Secrets Agent")
    finally:
        client.close()
