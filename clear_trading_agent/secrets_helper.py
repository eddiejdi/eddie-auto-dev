#!/usr/bin/env python3
"""Resolução de secrets para o Clear Trading Agent.

Cadeia de resolução:
    env var -> Vault local (Bitwarden via tools.vault.secret_store)
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_cache: dict[str, str] = {}


def get_secret(name: str, field: str = "password", *, use_cache: bool = True) -> Optional[str]:
    """Resolve um secret a partir dos backends configurados."""
    cache_key = f"{name}:{field}"
    if use_cache and cache_key in _cache:
        return _cache[cache_key]

    value = _try_env_var(name, field)
    if value is None:
        value = _try_vault_import(name, field)

    if value:
        _cache[cache_key] = value
        logger.debug("Secret '%s/%s' resolved", name, field)
    else:
        logger.warning("⚠️ Secret '%s/%s' não encontrado em nenhuma fonte", name, field)

    return value


def get_database_url() -> str:
    """Retorna a DSN do PostgreSQL para o Clear Trading Agent."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    for secret_name in ("eddie/database_url", "shared/database_url", "crypto/database_url"):
        url = get_secret(secret_name, "url")
        if url:
            return url

    raise RuntimeError(
        "❌ DATABASE_URL não configurado. "
        "Configure via env var DATABASE_URL ou no vault (shared/database_url)."
    )


def get_mt5_bridge_credentials() -> tuple[str, str]:
    """Resolve credenciais do MT5 Bridge API.

    Returns:
        (bridge_url, api_key)
    """
    bridge_url = os.getenv("MT5_BRIDGE_URL", "http://192.168.15.100:8510")
    api_key = get_secret("clear/mt5_bridge_api_key", "password") or os.getenv("MT5_BRIDGE_API_KEY", "")
    return bridge_url, api_key


def get_clear_broker_credentials() -> tuple[str, str]:
    """Resolve credenciais da conta Clear para integração com a corretora.

    Returns:
        (username, password)
    """
    username = (
        get_secret("clear/broker_login", "username")
        or get_secret("clear/broker_login", "email")
        or os.getenv("CLEAR_BROKER_LOGIN_USERNAME", "")
    )
    password = get_secret("clear/broker_login", "password") or os.getenv("CLEAR_BROKER_LOGIN", "")
    return username, password


def get_clear_integration_status() -> dict[str, object]:
    """Retorna status sanitizado da integração da Clear (sem expor secrets)."""
    bridge_url, bridge_api_key = get_mt5_bridge_credentials()
    broker_username, broker_password = get_clear_broker_credentials()
    return {
        "bridge_url": bridge_url,
        "bridge_api_key_configured": bool(bridge_api_key),
        "broker_username_configured": bool(broker_username),
        "broker_password_configured": bool(broker_password),
    }


def _try_vault_import(name: str, field: str) -> Optional[str]:
    """Tenta acesso direto ao vault local."""
    _configure_vault_runtime_env()
    try:
        from tools.vault.secret_store import get_field
        return get_field(name, field)
    except ImportError:
        logger.debug("tools.vault.secret_store não disponível no path")
    except Exception as exc:
        logger.debug("Vault get_field(%r, %r) falhou: %s", name, field, exc)
    return None


def _configure_vault_runtime_env() -> None:
    """Configura defaults para auto-unlock do Bitwarden e fallback GPG.

    Não sobrescreve variáveis já definidas pelo ambiente do processo.
    """
    project_root = _PROJECT_ROOT

    # Fallback local para decrypt de tools/simple_vault/secrets/*.gpg
    simple_passphrase = project_root / "tools" / "simple_vault" / "passphrase"
    if "SIMPLE_VAULT_PASSPHRASE_FILE" not in os.environ and simple_passphrase.exists():
        os.environ["SIMPLE_VAULT_PASSPHRASE_FILE"] = str(simple_passphrase)

    # Em homelab, o arquivo de senha BW normalmente fica nesse caminho.
    homelab_bw_password = Path("/var/lib/eddie/secrets_agent/.bw_master_password")
    if "BW_PASSWORD_FILE" not in os.environ and homelab_bw_password.exists():
        os.environ["BW_PASSWORD_FILE"] = str(homelab_bw_password)

    # Compatibilidade com fallback padrão usado pelo secret_store.
    if "SECRETS_AGENT_DATA" not in os.environ:
        homelab_data = Path("/var/lib/eddie/secrets_agent")
        if homelab_data.exists():
            os.environ["SECRETS_AGENT_DATA"] = str(homelab_data)


def _try_env_var(name: str, field: str) -> Optional[str]:
    """Tenta ler de uma variável de ambiente normalizada."""
    env_name = name.replace("/", "_").upper()
    if field and field not in ("password",):
        env_name = f"{env_name}_{field.upper()}"
    return os.environ.get(env_name)
