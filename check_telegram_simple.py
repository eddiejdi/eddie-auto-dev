#!/usr/bin/env python3
"""Verificar atualizações do Telegram usando requests puro"""

import requests

try:
    from tools.secrets_loader import get_telegram_token

    TELEGRAM_TOKEN = get_telegram_token()
except Exception:
    # As a last resort keep old behaviour but prefer vault-only access
    try:
        from tools.vault.secret_store import get_field

        TELEGRAM_TOKEN = get_field("eddie/telegram_bot_token", "password")
    except Exception:
        TELEGRAM_TOKEN = ""

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}" if TELEGRAM_TOKEN else None


def check_updates():
    print("=== ATUALIZAÇÕES DO TELEGRAM ===\n")

    response = requests.get(f"{BASE_URL}/getUpdates", params={"limit": 20})
    data = response.json()

    if not data.get("ok"):
        print(f"Erro: {data}")
        return

    updates = data.get("result", [])

    if not updates:
        print("Nenhuma atualização pendente.")
        return

    for u in updates:
        print(f"Update ID: {u['update_id']}")

        # Callback query (clique em botão)
        if "callback_query" in u:
            cb = u["callback_query"]
            print("  🔘 CALLBACK QUERY (CLIQUE NO BOTÃO):")
            print(f"     Data: {cb.get('data')}")
            user = cb.get("from", {})
            print(f"     User: {user.get('first_name')} ({user.get('id')})")
            msg = cb.get("message", {})
            print(f"     Message ID: {msg.get('message_id', 'N/A')}")

        # Mensagem de texto
        if "message" in u:
            msg = u["message"]
            if msg.get("text"):
                print("  💬 MESSAGE:")
                print(f"     Text: {msg['text'][:200]}")
                user = msg.get("from", {})
                print(f"     From: {user.get('first_name', 'N/A')}")

        print("")


if __name__ == "__main__":
    check_updates()
