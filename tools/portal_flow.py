#!/usr/bin/env python3
"""
Invoke the Diretor to review the new portal and, when a response arrives,
send a Telegram notification with the portal link (if Telegram is configured).

Usage: python3 tools/portal_flow.py
"""
import subprocess
import time
import json
import os
import asyncio
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]

def publish_to_diretor(message: str):
    cmd = ['python3', str(BASE / 'tools' / 'invoke_director.py'), message]
    print('Publishing to DIRETOR...')
    subprocess.run(cmd)

def wait_for_diretor(timeout=120):
    print('Waiting for DIRETOR response (helper will write /tmp/diretor_response.json)')
    cmd = ['python3', str(BASE / 'tools' / 'wait_for_diretor.py')]
    p = subprocess.Popen(cmd)
    start = time.time()
    outfile = '/tmp/diretor_response.json'
    while time.time() - start < timeout:
        if os.path.exists(outfile):
            with open(outfile, 'r', encoding='utf-8') as f:
                return json.load(f)
        time.sleep(1)
    try:
        p.terminate()
    except Exception:
        pass
    return None

async def try_send_telegram(title: str, message: str):
    try:
        from specialized_agents.telegram_client import TelegramNotifier
    except Exception:
        # Attempt to load by path if package import fails (when PYTHONPATH not set)
        import importlib.util, pathlib
        path = pathlib.Path(__file__).resolve().parents[1] / 'specialized_agents' / 'telegram_client.py'
        spec = importlib.util.spec_from_file_location('telegram_client_local', str(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        TelegramNotifier = getattr(mod, 'TelegramNotifier')
    notifier = TelegramNotifier()
    if not notifier.client.is_configured():
        print('Telegram not configured (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID).')
        print('Message to send:\n', message)
        return {'success': False, 'reason': 'not-configured'}
    print('Sending Telegram message...')
    return await notifier.notify_success(title, message)

def main():
    portal_url = os.environ.get('PORTAL_URL', 'http://localhost:5000/portal')
    message = f"Por favor, DIRETOR: autorize exposição do Portal unificado em {portal_url}"
    publish_to_diretor(message)

    resp = wait_for_diretor(timeout=180)
    telegram_text = f"Portal unificado disponível: {portal_url}\n\n"
    if resp:
        telegram_text += "Diretor respondeu:\n" + json.dumps(resp, ensure_ascii=False, indent=2)
    else:
        telegram_text += "Nenhuma resposta do Diretor dentro do timeout."

    # Try to send via Telegram if configured
    try:
        r = asyncio.run(try_send_telegram('Portal Unificado', telegram_text))
        print('Telegram result:', r)
    except Exception as e:
        print('Erro ao enviar Telegram:', e)

    print('Done.')

if __name__ == '__main__':
    main()
