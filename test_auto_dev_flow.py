#!/usr/bin/env python3
"""
Script para testar o fluxo completo de auto-aprendizado.
Simula uma conversa com o bot.
"""
import asyncio
import httpx
import json
import time
from datetime import datetime

from tools.secrets_loader import get_telegram_token

BOT_TOKEN = get_telegram_token()
TELEGRAM_API = f'https://api.telegram.org/bot{BOT_TOKEN}'
CHAT_ID = 948686300

async def send_message(text: str):
    """Envia mensagem via API"""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f'{TELEGRAM_API}/sendMessage', json={
            'chat_id': CHAT_ID,
            'text': text
        })
        return r.json()

async def get_updates(offset=None):
    """Busca updates"""
    async with httpx.AsyncClient(timeout=30) as client:
        params = {'timeout': 0}
        if offset:
            params['offset'] = offset
        r = await client.get(f'{TELEGRAM_API}/getUpdates', params=params)
        return r.json()

async def test_auto_dev():
    """Testa o fluxo de auto-desenvolvimento"""
    print("=" * 60)
    print("🧪 TESTE DE AUTO-APRENDIZADO")
    print("=" * 60)
    
    # 1. Importar e iniciar o bot
    print("\n[1] Iniciando bot...")
    from telegram_bot import TelegramBot, AutoDeveloper, INABILITY_PATTERNS
    import re
    
    bot = TelegramBot()
    await bot.clear_old_updates()
    
    # 2. Testar detecção de incapacidade
    print("\n[2] Testando detecção de incapacidade...")
    test_responses = [
        "Não tenho acesso a informações em tempo real",
        "Desculpe, não consigo fazer isso",
        "Infelizmente não tenho essa capacidade",
        "Posso te ajudar com isso! Aqui está o código...",
        "Claro, vou explicar como funciona",
    ]
    
    for resp in test_responses:
        detected = bot.auto_dev.detect_inability(resp)
        status = "🔴 INCAPAZ" if detected else "🟢 CAPAZ"
        print(f"  {status}: {resp[:50]}...")
    
    # 3. Simular uma mensagem de usuário
    print("\n[3] Testando processamento de mensagem...")
    
    # Criar mensagem simulada
    test_message = {
        "message_id": 9999,
        "from": {"id": CHAT_ID, "first_name": "Teste"},
        "chat": {"id": CHAT_ID},
        "date": int(time.time()),
        "text": "qual é a cotação do dólar hoje?"
    }
    
    print(f"  Mensagem de teste: {test_message['text']}")
    
    # 4. Testar ask_ollama
    print("\n[4] Testando resposta do Ollama...")
    response = await bot.ask_ollama(test_message['text'], CHAT_ID)
    print(f"  Resposta: {response[:200]}...")
    
    # 5. Verificar se detecta incapacidade
    print("\n[5] Verificando detecção na resposta...")
    is_unable = bot.auto_dev.detect_inability(response)
    print(f"  Incapacidade detectada: {is_unable}")
    
    if is_unable:
        print("\n[6] Iniciando auto-desenvolvimento...")
        print("  (Isso pode demorar alguns segundos...)")
        
        success, dev_response = await bot.auto_dev.auto_develop(
            test_message['text'], 
            response
        )
        
        print(f"  Sucesso: {success}")
        print(f"  Resposta: {dev_response[:500] if dev_response else 'N/A'}...")
    else:
        print("\n[6] Não necessário auto-desenvolvimento")
        print("  O Ollama conseguiu responder normalmente")
    
    # Cleanup
    await bot.api.close()
    await bot.stop()
    
    print("\n" + "=" * 60)
    print("✅ TESTE CONCLUÍDO")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_auto_dev())
