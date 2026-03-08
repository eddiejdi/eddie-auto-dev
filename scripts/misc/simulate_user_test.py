#!/usr/bin/env python3
"""
Script para criar um webhook temporário e testar o bot.
Isso simula uma mensagem vinda do usuário.
"""
import asyncio
import httpx
import json
import time

from tools.secrets_loader import get_telegram_token

BOT_TOKEN = get_telegram_token()
TELEGRAM_API = f'https://api.telegram.org/bot{BOT_TOKEN}'
CHAT_ID = 948686300

async def simulate_user_message():
    """
    Simula uma mensagem de usuário criando um update fake.
    Como não podemos injetar updates diretamente, vamos:
    1. Enviar mensagem para o chat
    2. Esperar o bot processar
    3. Verificar se houve resposta
    """
    print("=" * 60)
    print("🧪 SIMULAÇÃO DE MENSAGEM DE USUÁRIO")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=60) as client:
        # Passo 1: Verificar mensagens atuais
        print("\n[1] Verificando estado inicial...")
        r = await client.get(f'{TELEGRAM_API}/getUpdates', params={'offset': -1})
        initial = r.json()
        print(f"  Updates iniciais: {initial}")
        
        # Passo 2: Solicitar ao usuário que envie mensagem
        print("\n[2] Enviando instrução ao usuário...")
        instruction = (
            "🧪 *TESTE DE AUTO-APRENDIZADO*\n\n"
            "Por favor, envie uma das seguintes mensagens:\n\n"
            "1️⃣ `qual a cotação do dólar hoje?`\n"
            "2️⃣ `qual o clima em São Paulo agora?`\n"
            "3️⃣ `quanto está a bitcoin?`\n\n"
            "_Aguardando sua mensagem para testar o auto-desenvolvimento..._"
        )
        
        r = await client.post(f'{TELEGRAM_API}/sendMessage', json={
            'chat_id': CHAT_ID,
            'text': instruction,
            'parse_mode': 'Markdown'
        })
        print(f"  Instrução enviada: {r.json()['ok']}")
        
        # Passo 3: Aguardar e monitorar
        print("\n[3] Aguardando resposta do bot (30 segundos)...")
        print("    (O usuário deve enviar mensagem pelo app do Telegram)")
        
        for i in range(6):
            await asyncio.sleep(5)
            print(f"  Verificando... ({(i+1)*5}s)")
            
            # Verificar se há updates
            r = await client.get(f'{TELEGRAM_API}/getUpdates')
            data = r.json()
            
            if data.get('result'):
                print(f"\n  ✅ Updates encontrados: {len(data['result'])}")
                for update in data['result']:
                    msg = update.get('message', {})
                    text = msg.get('text', '')
                    from_user = msg.get('from', {}).get('first_name', 'Unknown')
                    print(f"    - De {from_user}: {text[:50]}...")
            else:
                print(f"    (Nenhum update pendente - bot está processando)")
        
        print("\n" + "=" * 60)
        print("✅ TESTE CONCLUÍDO")
        print("=" * 60)
        print("\nVerifique o chat do Telegram para ver se o bot respondeu")
        print("com a mensagem de Auto-Desenvolvimento!")

if __name__ == "__main__":
    asyncio.run(simulate_user_message())
