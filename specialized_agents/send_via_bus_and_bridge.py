#!/usr/bin/env python3
"""
Lightweight in-process bridge + publisher.

This script subscribes to the in-process AgentCommunicationBus and sends any
messages targeted to "telegram" using the Telegram HTTP API (curl). It then
publishes a message read from `/tmp/openwebui_admin_password.txt` so the same
process receives and delivers it. On successful delivery the password file is
renamed to `.sent`.

This avoids importing the full `TelegramClient` (which requires `httpx`) and
ensures the bus message is processed by a local subscriber.
"""
import os
import json
import time
import threading
import subprocess
from specialized_agents.agent_communication_bus import get_communication_bus, MessageType


def read_token_and_chat():
    token = None
    chat = None
    if os.path.exists('/etc/eddie/telegram.env'):
        with open('/etc/eddie/telegram.env', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('TELEGRAM_BOT_TOKEN='):
                    token = line.split('=',1)[1].strip().strip('"').strip("'")
                if line.startswith('TELEGRAM_CHAT_ID='):
                    chat = line.split('=',1)[1].strip().strip('"').strip("'")
    return token, chat


def send_via_curl(token: str, chat_id: str, text: str):
    api = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        p = subprocess.Popen([
            'curl', '-s', '-X', 'POST', api,
            '--data-urlencode', f'text={text}',
            '-d', f'chat_id={chat_id}',
            '-d', 'parse_mode=HTML'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate(timeout=15)
        out = out.decode('utf-8', errors='ignore')
        return out
    except Exception as e:
        return json.dumps({'ok': False, 'error': str(e)})


def handle_message(message):
    try:
        if getattr(message, 'target', '') != 'telegram':
            return
        # parse content
        try:
            payload = json.loads(message.content)
        except Exception:
            payload = {'action': 'sendMessage', 'text': message.content}

        action = payload.get('action', 'sendMessage')
        chat_id = payload.get('chat_id')
        if not chat_id:
            # try env default
            _, default_chat = read_token_and_chat()
            chat_id = chat_id or default_chat

        if action == 'sendMessage':
            text = payload.get('text') or payload.get('message') or ''
            token, _ = read_token_and_chat()
            if not token or not chat_id:
                print('bridge: missing token or chat_id; skipping')
                return
            print('bridge: sending message to chat', chat_id)
            resp = send_via_curl(token, chat_id, text)
            print('bridge: telegram response:', resp)
            try:
                r = json.loads(resp)
                if r.get('ok'):
                    # If payload contained a local password file reference, move it
                    # We expect the publisher to have written the file at /tmp/openwebui_admin_password.txt
                    src = '/tmp/openwebui_admin_password.txt'
                    dst = src + '.sent'
                    if os.path.exists(src):
                        try:
                            os.rename(src, dst)
                            print('bridge: moved password file to', dst)
                        except Exception as e:
                            print('bridge: failed to move file:', e)
            except Exception:
                pass

    except Exception as e:
        print('bridge: unhandled error', e)


def main():
    bus = get_communication_bus()
    # subscribe
    bus.subscribe(handle_message)
    print('bridge: subscribed to bus, publishing message now')

    # Read password file
    pwd_file = '/tmp/openwebui_admin_password.txt'
    if not os.path.exists(pwd_file):
        print('publisher: password file not found:', pwd_file)
        return
    with open(pwd_file, 'r', encoding='utf-8') as f:
        pwd = f.read().strip()

    text = f"Admin password for edenilson.adm@gmail.com:\n{pwd}\n\nRotate after use."
    payload = {'action': 'sendMessage', 'chat_id': '11981193899', 'text': text}
    # publish
    msg = bus.publish(MessageType.REQUEST, source='send_via_bus_and_bridge', target='telegram', content=json.dumps(payload), metadata={'via_bus': True})
    print('publisher: published message id', getattr(msg, 'id', None))

    # wait a bit for delivery
    for i in range(10):
        time.sleep(1)


if __name__ == '__main__':
    main()
