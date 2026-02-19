#!/usr/bin/env python3
"""Central secret helpers — Secrets Agent é a única fonte de verdade.

Todo acesso a credenciais/tokens/senhas passa exclusivamente pelo Secrets Agent
(porta 8088). Nenhum fallback para BW CLI, env vars ou arquivos locais.
"""
import logging

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
            val = client.get_local_secret("eddie/telegram_bot_token", field=field)
            if val:
                return val
        raise RuntimeError("Telegram token not found in Secrets Agent (eddie/telegram_bot_token)")
    finally:
        client.close()


def get_telegram_chat_id() -> str:
    """Retorna o chat_id do Telegram via Secrets Agent."""
    client = _get_client()
    try:
        for field in ("chat_id", "password"):
            val = client.get_local_secret("eddie/telegram_chat_id", field=field)
            if val:
                return val
        logger.warning("Telegram chat_id not found in Secrets Agent")
        return ""
    finally:
        client.close()


def get_fly_token() -> str:
    """Retorna o Fly API token via Secrets Agent."""
    client = _get_client()
    try:
        val = client.get_secret("eddie/fly_api_token")
        return val or ""
    finally:
        client.close()


def get_database_url() -> str:
    """Retorna DATABASE_URL via Secrets Agent."""
    client = _get_client()
    try:
        for field in ("url", "password"):
            val = client.get_local_secret("eddie/database_url", field=field)
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
