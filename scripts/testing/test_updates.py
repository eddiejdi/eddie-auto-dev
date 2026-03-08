#!/usr/bin/env python3
"""Script para testar updates do Telegram"""
import asyncio
import httpx
import json

from tools.secrets_loader import get_telegram_token

BOT_TOKEN = get_telegram_token()
TELEGRAM_API = f'https://api.telegram.org/bot{BOT_TOKEN}'

async def check_updates():
    async with httpx.AsyncClient(timeout=30) as client:
        # Verificar updates pendentes
        r = await client.get(f'{TELEGRAM_API}/getUpdates')
        print('Updates:', json.dumps(r.json(), indent=2, ensure_ascii=False))
        
asyncio.run(check_updates())
