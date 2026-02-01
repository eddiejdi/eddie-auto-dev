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
        return os.environ.get(name.replace("/", "_").upper(), "")


def get_telegram_token() -> str:
    """
    Return the Telegram bot token from the secret store.

    Tokens are required to be stored in the repo cofre. This function will
    attempt to fetch the secret via `get_field` and will raise if the
    secret is not present. Do NOT rely on environment variables for tokens.
    """
    # Try common item names in the vault to be resilient to migration naming.
    candidates = [
        "eddie/telegram_bot_token",
        "telegram_bot_token",
        "telegram/bot_token",
    ]
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
    c = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("ADMIN_CHAT_ID") or ""
    if c:
        return c
    # Try several vault item names that may exist depending on migration
    candidates = ["eddie/telegram_chat_id", "telegram_chat_id", "telegram/chat_id"]
    for item in candidates:
        try:
            return get_field(item) or ""
        except Exception:
            continue
    return ""


def get_tunnel_token() -> str:
    """
    Return the tunnel provider token from env or secrets.

    This replaces the older Fly.io-specific token accessor. The function
    looks for `TUNNEL_API_TOKEN` in the environment and falls back to the
    secrets vault key `eddie/tunnel_api_token`.
    """
    t = os.getenv("TUNNEL_API_TOKEN") or ""
    if t:
        return t
    try:
        return get_field("eddie/tunnel_api_token") or ""
    except Exception:
        return ""


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "")


def get_openwebui_api_key() -> str:
    """
    Return the Open WebUI API key.

    Lookup order:
      1. Environment variables: OPENWEBUI_API_KEY or OPENWEBUI_TOKEN
      2. Vault item 'openwebui/api_key' via get_field()
      3. Local file '~/.openwebui_token' (useful on homelab runner)
      4. simple_vault fallback handled by get_field

    Returns empty string if not found or appears corrupted.
    """
    # 1) Env var fallback
    for env_name in ("OPENWEBUI_API_KEY", "OPENWEBUI_TOKEN"):
        v = os.environ.get(env_name)
        if v and len(v) >= 16:
            return v.strip()

    # 2) Vault / simple_vault
    try:
        k = get_field("openwebui/api_key")
    except Exception:
        k = ""

    # 3) Local homelab token file as fallback
    if not k:
        try:
            p = os.path.expanduser("~/.openwebui_token")
            if os.path.isfile(p):
                with open(p, "r") as f:
                    k = f.read().strip()
        except Exception:
            k = k or ""

    # Detect obvious corruption patterns and treat as missing key
    if not k:
        return ""
    low = k.lower()
    if "oci runtime exec failed" in low or "exec failed" in low or "sqlite3" in low:
        return ""
    if len(k) < 16:
        return ""
    return k
