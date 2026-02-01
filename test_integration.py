#!/usr/bin/env python3
"""
Script de teste para verificar a integração
"""

import asyncio
import httpx

from tools.secrets_loader import get_telegram_token

BOT_TOKEN = get_telegram_token()
ADMIN_CHAT_ID = 948686300


async def test():
    async with httpx.AsyncClient() as client:
        # Enviar comando /status para testar
        print("Enviando comando /models para testar integração...")

        response = await client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": ADMIN_CHAT_ID, "text": "/models"},
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")


if __name__ == "__main__":
    asyncio.run(test())
