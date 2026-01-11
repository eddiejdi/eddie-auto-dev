#!/usr/bin/env python3
"""
Script de teste para verificar a integração
"""
import asyncio
import httpx

BOT_TOKEN = "1105143633:AAEC1kmqDD_MDSpRFgEVHctwAfvfjVSp8B4"
ADMIN_CHAT_ID = 948686300

async def test():
    async with httpx.AsyncClient() as client:
        # Enviar comando /status para testar
        print("Enviando comando /models para testar integração...")
        
        response = await client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": ADMIN_CHAT_ID,
                "text": "/models"
            }
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")

if __name__ == "__main__":
    asyncio.run(test())
