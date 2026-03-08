#!/usr/bin/env python3
"""Helper centralizado para obtenção de secrets no BTC Trading Agent.

Ordem de resolução:
    1. Secrets Agent HTTP API (192.168.15.2:8088) — fonte primária
    2. tools.vault.secret_store.get_field() — Bitwarden/GPG/env (import direto)
    3. Variável de ambiente — último recurso

Nomes canônicos (Secrets Agent local):
    - shared/database_url   (field: url)   → DSN PostgreSQL
    - kucoin/homelab       (field: api_key, api_secret, passphrase)
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Garantir que o root do projeto está no sys.path para import de tools.vault
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Cache de valores já resolvidos (evita múltiplas chamadas ao vault)
_cache: dict[str, str] = {}

# Singleton do SecretsAgentClient (lazy init)
_sa_client: Optional[object] = None


def get_secret(name: str, field: str = "password", *, use_cache: bool = True) -> Optional[str]:
    """Obtém um secret pelo nome e campo.

    Args:
        name: Nome do item no vault (ex: 'crypto/database_url').
        field: Campo específico (ex: 'url', 'api_key', 'password').
        use_cache: Se True, retorna valor cacheado quando disponível.

    Returns:
        Valor do secret ou None se não encontrado.
    """
    cache_key = f"{name}:{field}"
    if use_cache and cache_key in _cache:
        return _cache[cache_key]

    value = _try_secrets_agent_http(name, field)
    if value is None:
        value = _try_vault_import(name, field)
    if value is None:
        value = _try_env_var(name, field)

    if value:
        _cache[cache_key] = value
        logger.debug(f"🔑 Secret '{name}/{field}' resolvido com sucesso")
    else:
        logger.warning(f"⚠️ Secret '{name}/{field}' não encontrado em nenhuma fonte")

    return value


def get_database_url() -> str:
    """Obtém DATABASE_URL do Secrets Agent ou fallback para env var.

    Retorna DSN PostgreSQL pronto para uso com psycopg2.
    """
    # 1. Secrets Agent (nome canônico)
    url = get_secret("crypto/database_url", "url")
    if url:
        return url

    # 2. Env var direta
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    # 3. Fallback hardcoded removido — lançar erro explícito
    raise RuntimeError(
        "❌ DATABASE_URL não configurado. "
        "Configure via Secrets Agent (shared/database_url) ou env var DATABASE_URL."
    )


def get_kucoin_credentials() -> tuple[str, str, str]:
    """Obtém credenciais KuCoin do Secrets Agent.

    Returns:
        Tupla (api_key, api_secret, passphrase).
    """
    api_key = get_secret("kucoin/homelab", "api_key") or ""
    api_secret = get_secret("kucoin/homelab", "api_secret") or ""
    passphrase = get_secret("kucoin/homelab", "passphrase") or ""

    # Fallback para env vars
    api_key = api_key or os.getenv("KUCOIN_API_KEY", "") or os.getenv("API_KEY", "")
    api_secret = api_secret or os.getenv("KUCOIN_API_SECRET", "") or os.getenv("API_SECRET", "")
    passphrase = passphrase or os.getenv("KUCOIN_API_PASSPHRASE", "") or os.getenv("API_PASSPHRASE", "")

    return api_key, api_secret, passphrase


# ====================== MÉTODOS DE RESOLUÇÃO (PRIVADOS) ======================

def _try_vault_import(name: str, field: str) -> Optional[str]:
    """Tenta obter secret via tools.vault.secret_store (import direto)."""
    try:
        from tools.vault.secret_store import get_field
        return get_field(name, field)
    except ImportError:
        logger.debug("tools.vault.secret_store não disponível no path")
    except Exception as e:
        logger.debug(f"Vault get_field('{name}', '{field}') falhou: {e}")
    return None


def _get_sa_client() -> Optional[object]:
    """Retorna singleton do SecretsAgentClient (lazy init)."""
    global _sa_client
    if _sa_client is not None:
        return _sa_client
    try:
        from tools.secrets_agent_client import SecretsAgentClient
        base_url = os.getenv("SECRETS_AGENT_URL", "http://192.168.15.2:8088")
        api_key = os.getenv("SECRETS_AGENT_API_KEY", "")
        _sa_client = SecretsAgentClient(base_url=base_url, api_key=api_key)
        return _sa_client
    except ImportError:
        logger.debug("tools.secrets_agent_client não disponível no path")
    except Exception as e:
        logger.debug(f"Erro ao criar SecretsAgentClient: {e}")
    return None


def _try_secrets_agent_http(name: str, field: str) -> Optional[str]:
    """Tenta obter secret via Secrets Agent HTTP API (192.168.15.2:8088)."""
    # 1. Tentar via SecretsAgentClient (tools/secrets_agent_client.py)
    client = _get_sa_client()
    if client is not None:
        try:
            val = client.get_local_secret(name, field=field)
            if val:
                return val
        except Exception as e:
            logger.debug(f"SecretsAgentClient.get_local_secret('{name}', '{field}') falhou: {e}")

    # 2. Fallback: requests direto
    api_key = os.getenv("SECRETS_AGENT_API_KEY", "")
    base_url = os.getenv("SECRETS_AGENT_URL", "http://192.168.15.2:8088")
    if not api_key:
        return None
    try:
        import requests as _req
        from urllib.parse import quote
        encoded_name = quote(name, safe="")
        r = _req.get(
            f"{base_url}/secrets/local/{encoded_name}",
            params={"field": field},
            headers={"X-API-KEY": api_key},
            timeout=5,
        )
        if r.status_code == 200:
            return r.json().get("value")
    except Exception:
        pass
    return None


def _try_env_var(name: str, field: str) -> Optional[str]:
    """Tenta obter via variável de ambiente (nome normalizado)."""
    env_name = name.replace("/", "_").upper()
    if field and field not in ("password",):
        env_name = f"{env_name}_{field.upper()}"
    return os.environ.get(env_name)
