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
    t = os.getenv("TELEGRAM_BOT_TOKEN") or ''
    if t:
        return t
    try:
        return get_field("eddie/telegram_bot_token") or ''
    except Exception:
        return ''


def get_telegram_chat_id() -> str:
    c = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("ADMIN_CHAT_ID") or ''
    if c:
        return c
    try:
        return get_field("eddie/telegram_chat_id") or ''
    except Exception:
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
