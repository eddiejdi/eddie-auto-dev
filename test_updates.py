#!/usr/bin/env python3
"""Script para testar updates do Telegram"""
import asyncio
import httpx
import json

BOT_TOKEN = '1105143633:AAEC1kmqDD_MDSpRFgEVHctwAfvfjVSp8B4'
TELEGRAM_API = f'https://api.telegram.org/bot{BOT_TOKEN}'

async def check_updates():
    async with httpx.AsyncClient(timeout=30) as client:
        # Verificar updates pendentes
        r = await client.get(f'{TELEGRAM_API}/getUpdates')
        print('Updates:', json.dumps(r.json(), indent=2, ensure_ascii=False))
        
asyncio.run(check_updates())
