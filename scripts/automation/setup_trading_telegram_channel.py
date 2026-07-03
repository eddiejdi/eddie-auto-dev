#!/usr/bin/env python3
"""Descobre chat/thread do Telegram e grava destino fixo de trading no Secrets Agent.

Fluxo recomendado:
1. Criar manualmente o grupo/canal no Telegram e adicionar o bot.
2. Enviar uma mensagem no grupo (ou no tópico) para gerar update.
3. Rodar este script com --discover para listar chat_id/thread_id.
4. Rodar com --set-chat-id e opcionalmente --set-thread-id para persistir no Secrets Agent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any

from tools.secrets_loader import get_telegram_token

SECRETS_AGENT_URL = os.environ.get("SECRETS_AGENT_URL", "http://192.168.15.2:8088").rstrip("/")
SECRETS_AGENT_API_KEY = os.environ.get("SECRETS_AGENT_API_KEY", "")


def _telegram_api(method: str, token: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    base = f"https://api.telegram.org/bot{token}/{method}"
    if params:
        qs = urllib.parse.urlencode(params)
        url = f"{base}?{qs}"
    else:
        url = base
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _set_secret(name: str, value: str, field: str) -> None:
    if not SECRETS_AGENT_API_KEY:
        raise RuntimeError(
            "SECRETS_AGENT_API_KEY ausente. Exporte a chave para gravar no Secrets Agent."
        )
    payload = json.dumps({"name": name, "value": value, "field": field}).encode("utf-8")
    req = urllib.request.Request(
        f"{SECRETS_AGENT_URL}/secrets",
        data=payload,
        headers={"x-api-key": SECRETS_AGENT_API_KEY, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


def _extract_chat_candidates(updates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in updates:
        msg = item.get("message") or item.get("edited_message")
        if not msg:
            continue
        chat = msg.get("chat", {})
        if not chat:
            continue
        out.append(
            {
                "update_id": item.get("update_id"),
                "chat_id": chat.get("id"),
                "chat_type": chat.get("type"),
                "title": chat.get("title") or chat.get("username") or chat.get("first_name") or "",
                "message_thread_id": msg.get("message_thread_id"),
                "text": (msg.get("text") or msg.get("caption") or "")[:120],
            }
        )
    return out


def discover(limit: int) -> int:
    token = (os.environ.get("TELEGRAM_BOT_TOKEN", "") or "").strip()
    if not token:
        token = get_telegram_token()
    data = _telegram_api("getUpdates", token, {"limit": limit})
    if not data.get("ok"):
        print("Erro ao consultar Telegram getUpdates:", data)
        return 1

    updates = data.get("result", [])
    candidates = _extract_chat_candidates(updates)

    if not candidates:
        print("Nenhum update disponível.")
        print("Envie uma mensagem no grupo/canal de trading e rode novamente.")
        return 2

    print("Candidatos encontrados (chat_id/thread_id):")
    for c in candidates:
        print(json.dumps(c, ensure_ascii=False))
    return 0


def set_trading_channel(chat_id: str, thread_id: str | None) -> int:
    _set_secret("shared/trading_telegram_chat_id", chat_id, "chat_id")
    print(f"Secret atualizado: shared/trading_telegram_chat_id.chat_id={chat_id}")

    if thread_id:
        _set_secret("shared/trading_telegram_thread_id", thread_id, "thread_id")
        print(f"Secret atualizado: shared/trading_telegram_thread_id.thread_id={thread_id}")

    print("Destino fixo de trading configurado no Secrets Agent.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup de canal fixo de trading no Telegram")
    parser.add_argument("--discover", action="store_true", help="Descobre chat_id/thread_id via getUpdates")
    parser.add_argument("--limit", type=int, default=30, help="Limite de updates para discovery")
    parser.add_argument("--set-chat-id", help="Define chat_id de trading no Secrets Agent")
    parser.add_argument("--set-thread-id", help="Define thread_id de trading no Secrets Agent")
    args = parser.parse_args()

    if args.discover:
        return discover(args.limit)

    if args.set_chat_id:
        return set_trading_channel(args.set_chat_id, args.set_thread_id)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
