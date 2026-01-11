#!/usr/bin/env python3
"""Teste rápido do Ollama"""
import httpx
import json

OLLAMA_HOST = "http://192.168.15.2:11434"
MODEL = "eddie-coder"

async def test():
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{OLLAMA_HOST}/api/chat", json={
            "model": MODEL,
            "messages": [{"role": "user", "content": "ola, diga apenas oi"}],
            "stream": False
        })
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text[:500]}")

import asyncio
asyncio.run(test())
