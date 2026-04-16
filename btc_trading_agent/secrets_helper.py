#!/usr/bin/env python3
"""Secret resolution helpers for the BTC trading agent."""
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
for _extra_root in (
    Path("/apps/crypto-trader/trading"),
    Path("/apps/crypto-trader/trading/btc_trading_agent"),
):
    try:
        _extra_exists = _extra_root.exists()
    except PermissionError:
        _extra_exists = False
    if _extra_exists and str(_extra_root) not in sys.path:
        sys.path.insert(0, str(_extra_root))

_cache: dict[str, str] = {}
_sa_client: Optional[object] = None


def _iter_kucoin_secret_names() -> tuple[str, ...]:
    """Retorna os nomes de secret aceitos para as credenciais KuCoin."""
    custom = os.getenv("KUCOIN_SECRET_NAMES", "").strip()
    if custom:
        names = tuple(part.strip() for part in custom.split(",") if part.strip())
        if names:
            return names
    return (
        "kucoin/homelab",
        "authentik/kucoin/homelab",
        "authentik/kucoin_homelab",
        "authentik/kucoin",
    )


def get_secret(name: str, field: str = "password", *, use_cache: bool = True) -> Optional[str]:
    """Resolve a secret from the configured backends."""
    cache_key = f"{name}:{field}"
    if use_cache and cache_key in _cache:
        return _cache[cache_key]

    value = _try_env_var(name, field)
    if value is None:
        value = _try_secrets_agent_http(name, field)
    if value is None:
        value = _try_vault_import(name, field)

    if value:
        _cache[cache_key] = value
        logger.debug("Secret '%s/%s' resolved", name, field)
    else:
        logger.warning("⚠️ Secret '%s/%s' não encontrado em nenhuma fonte", name, field)

    return value


def get_database_url() -> str:
    """Return the Postgres DSN for trading services."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    for secret_name in ("eddie/database_url", "shared/database_url", "crypto/database_url"):
        url = get_secret(secret_name, "url")
        if url:
            return url

    raise RuntimeError(
        "❌ DATABASE_URL não configurado. "
        "Configure via env var DATABASE_URL ou Secrets Agent (shared/database_url)."
    )


def get_kucoin_credentials() -> tuple[str, str, str]:
    """Resolve KuCoin credentials from secrets or env vars."""
    api_key, api_secret, passphrase, _source = get_kucoin_credentials_with_source()
    return api_key, api_secret, passphrase


def get_kucoin_credentials_with_source() -> tuple[str, str, str, str]:
    """Resolve KuCoin credentials and report which backend won."""
    resolved_by_secret: list[tuple[str, str, str, str]] = []
    for secret_name in _iter_kucoin_secret_names():
        api_key = get_secret(secret_name, "api_key") or ""
        api_secret = get_secret(secret_name, "api_secret") or ""
        passphrase = get_secret(secret_name, "passphrase") or ""
        resolved_by_secret.append((secret_name, api_key, api_secret, passphrase))
        if api_key and api_secret and passphrase:
            return api_key, api_secret, passphrase, f"agent-secrets:{secret_name}"

    env_api_key = os.getenv("KUCOIN_API_KEY", "") or os.getenv("API_KEY", "")
    env_api_secret = os.getenv("KUCOIN_API_SECRET", "") or os.getenv("API_SECRET", "")
    env_passphrase = os.getenv("KUCOIN_API_PASSPHRASE", "") or os.getenv("API_PASSPHRASE", "")

    partial_secret_name = ""
    partial_api_key = partial_api_secret = partial_passphrase = ""
    for secret_name, partial_api_key, partial_api_secret, partial_passphrase in resolved_by_secret:
        if partial_api_key or partial_api_secret or partial_passphrase:
            partial_secret_name = secret_name
            break

    api_key = partial_api_key
    api_secret = partial_api_secret
    passphrase = partial_passphrase

    merged_api_key = api_key or env_api_key
    merged_api_secret = api_secret or env_api_secret
    merged_passphrase = passphrase or env_passphrase

    source = "env"
    if (api_key or api_secret or passphrase) and (env_api_key or env_api_secret or env_passphrase):
        source = f"agent-secrets+env:{partial_secret_name or 'kucoin'}"
    elif api_key or api_secret or passphrase:
        source = f"agent-secrets(partial):{partial_secret_name or 'kucoin'}"

    return merged_api_key, merged_api_secret, merged_passphrase, source


def _try_vault_import(name: str, field: str) -> Optional[str]:
    """Try direct vault access when available."""
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
    """Configura defaults para auto-unlock do Bitwarden e fallback GPG."""
    project_root = _PROJECT_ROOT

    simple_passphrase = project_root / "tools" / "simple_vault" / "passphrase"
    if "SIMPLE_VAULT_PASSPHRASE_FILE" not in os.environ and simple_passphrase.exists():
        os.environ["SIMPLE_VAULT_PASSPHRASE_FILE"] = str(simple_passphrase)

    homelab_bw_password = Path("/var/lib/eddie/secrets_agent/.bw_master_password")
    if "BW_PASSWORD_FILE" not in os.environ and homelab_bw_password.exists():
        os.environ["BW_PASSWORD_FILE"] = str(homelab_bw_password)

    if "SECRETS_AGENT_DATA" not in os.environ:
        homelab_data = Path("/var/lib/eddie/secrets_agent")
        if homelab_data.exists():
            os.environ["SECRETS_AGENT_DATA"] = str(homelab_data)


def _get_sa_client() -> Optional[object]:
    """Return a lazy singleton SecretsAgentClient instance."""
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
    except Exception as exc:
        logger.debug("Erro ao criar SecretsAgentClient: %s", exc)
    return None


def _try_secrets_agent_http(name: str, field: str) -> Optional[str]:
    """Try the Secrets Agent HTTP API."""
    client = _get_sa_client()
    if client is not None:
        try:
            value = client.get_local_secret(name, field=field)
            if value:
                return value
        except Exception as exc:
            logger.debug("SecretsAgentClient.get_local_secret(%r, %r) falhou: %s", name, field, exc)

    api_key = os.getenv("SECRETS_AGENT_API_KEY", "")
    base_url = os.getenv("SECRETS_AGENT_URL", "http://192.168.15.2:8088")
    if not api_key:
        return None

    try:
        import requests as _req
        from urllib.parse import quote

        encoded_name = quote(name, safe="")
        response = _req.get(
            f"{base_url}/secrets/local/{encoded_name}",
            params={"field": field},
            headers={"X-API-KEY": api_key},
            timeout=5,
        )
        if response.status_code == 200:
            return response.json().get("value")
    except Exception:
        pass
    return None


def _try_env_var(name: str, field: str) -> Optional[str]:
    """Try a normalized environment variable name."""
    env_name = name.replace("/", "_").upper()
    if field and field not in ("password",):
        env_name = f"{env_name}_{field.upper()}"
    return os.environ.get(env_name)
