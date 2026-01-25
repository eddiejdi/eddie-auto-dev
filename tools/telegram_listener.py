#!/usr/bin/env python3
"""
Listener Telegram: lê mensagens recebidas, responde perguntas e aciona agentes via bus.
"""

import os
import sys
import asyncio
import time
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from specialized_agents.agent_communication_bus import get_communication_bus, MessageType
from specialized_agents.telegram_client import TelegramClient, TelegramNotifier

LAST_UPDATE_FILE = '/tmp/telegram_last_update_id.txt'
LAST_RESPONSE_ID_FILE = '/tmp/telegram_last_response_id.txt'

async def main():
    client = TelegramClient.from_env()
    notifier = TelegramNotifier(client)
    bus = get_communication_bus()
    last_update_id = None
    last_response_id = None
    if os.path.exists(LAST_UPDATE_FILE):
        with open(LAST_UPDATE_FILE) as f:
            try:
                last_update_id = int(f.read().strip())
            except Exception:
                last_update_id = None
    if os.path.exists(LAST_RESPONSE_ID_FILE):
        with open(LAST_RESPONSE_ID_FILE) as f:
            try:
                last_response_id = f.read().strip()
            except Exception:
                last_response_id = None
    print('[telegram_listener] Iniciando listener...')
    while True:
        # 1. Recebe mensagens do Telegram
        updates = await client.get_updates(offset=(last_update_id+1) if last_update_id else None, limit=10)
        if updates.get('success') and updates.get('data'):
            for upd in updates['data']:
                last_update_id = upd['update_id']
                msg = upd.get('message')
                if not msg:
                    continue
                text = msg.get('text','').strip()
                user = msg['from'].get('username') or msg['from'].get('first_name')
                chat_id = msg['chat']['id']
                print(f'[telegram_listener] Mensagem recebida de {user}: {text}')
                # Aciona agente se for comando ou pergunta
                if text.startswith('/') or text.endswith('?'):
                    # Publica no bus para o agente diretor
                    bus.publish(MessageType.REQUEST, 'telegram', 'DIRETOR', text, {'from_user':user,'chat_id':chat_id})
                    await notifier.notify_info('Pergunta recebida', f'Encaminhada ao DIRETOR: {text}')
                else:
                    await notifier.notify_info('Recebido', f'Mensagem: {text}')
            with open(LAST_UPDATE_FILE,'w') as f:
                f.write(str(last_update_id))

        # 2. Busca respostas do DIRETOR no bus e envia ao Telegram
        responses = bus.get_messages(limit=20, message_types=[MessageType.RESPONSE], source='DIRETOR')
        for resp in responses:
            # Só responde se for novo e tiver chat_id
            resp_id = resp.id
            chat_id = resp.metadata.get('chat_id')
            if not chat_id:
                continue
            if last_response_id and resp_id <= last_response_id:
                continue
            # Envia resposta ao Telegram
            content = resp.content
            await client.send_message(f"Resposta do DIRETOR:\n{content}", chat_id=chat_id)
            print(f'[telegram_listener] Resposta enviada ao Telegram para chat_id={chat_id}')
            last_response_id = resp_id
            with open(LAST_RESPONSE_ID_FILE,'w') as f:
                f.write(str(last_response_id))

        await asyncio.sleep(5)

if __name__ == '__main__':
    asyncio.run(main())
