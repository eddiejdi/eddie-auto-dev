#!/usr/bin/env python3
"""Central secret helpers for repo scripts.

Provides small helpers to fetch commonly used secrets (Telegram token/chat id,
Fly token, DATABASE_URL) using environment variables first, then falling back to
`tools.vault.secret_store.get_field()` or simple_vault files.
"""
import os

try:
    from tools.vault.secret_store import get_field
except Exception:
    def get_field(name: str, field: str = "password"):
        return os.environ.get(name.replace('/', '_').upper(), '')


def get_telegram_token() -> str:
    """
    Return the Telegram bot token from the secret store.

    Tokens are required to be stored in the repo cofre. This function will
    attempt to fetch the secret via `get_field` and will raise if the
    secret is not present. Do NOT rely on environment variables for tokens.
    """
    # Try common item names in the vault to be resilient to migration naming.
    candidates = ["eddie/telegram_bot_token", "telegram_bot_token", "telegram/bot_token"]
    last_err = None
    for item in candidates:
        try:
            return get_field(item)
        except Exception as e:
            last_err = e
            continue
    # If not found, raise the last error to enforce vault requirement upstream
    if last_err:
        raise last_err


def get_telegram_chat_id() -> str:
    c = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("ADMIN_CHAT_ID") or ''
    if c:
        return c
    # Try several vault item names that may exist depending on migration
    candidates = ["eddie/telegram_chat_id", "telegram_chat_id", "telegram/chat_id"]
    for item in candidates:
        try:
            return get_field(item) or ''
        except Exception:
            continue
    return ''


def get_fly_token() -> str:
    t = os.getenv("FLY_API_TOKEN") or ''
    if t:
        return t
    try:
        return get_field("eddie/fly_api_token") or ''
    except Exception:
        return ''


def get_database_url() -> str:
    return os.getenv('DATABASE_URL','')


def get_openwebui_api_key() -> str:
    """
    Return the Open WebUI API key from the secret store.

    This value is considered a token and must be stored in the cofre under
    the name `openwebui/api_key`.
    """
    try:
        return get_field("openwebui/api_key")
    except Exception:
        raise
