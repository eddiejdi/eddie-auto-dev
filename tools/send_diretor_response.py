#!/usr/bin/env python3
"""Check /tmp/diretor_response.json and notify via Telegram if configured."""
import os
import sys
import json
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_SAVE = '/tmp/portal_diretor_notification.txt'
RESP_FILE = '/tmp/diretor_response.json'

def load_response():
    if not os.path.exists(RESP_FILE):
        print('NO_RESPONSE')
        return None
    with open(RESP_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

async def send_telegram(text: str):
    try:
        try:
            from specialized_agents.telegram_client import TelegramNotifier
        except Exception:
            import importlib.util, pathlib
            path = pathlib.Path(__file__).resolve().parents[1] / 'specialized_agents' / 'telegram_client.py'
            spec = importlib.util.spec_from_file_location('telegram_client_local', str(path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            TelegramNotifier = getattr(mod, 'TelegramNotifier')
    except Exception as e:
        print('IMPORT_ERROR', e)
        return {'ok': False, 'reason': 'import_error', 'detail': str(e)}

    notifier = TelegramNotifier()
    # TelegramNotifier uses async client internally
    if not notifier.client.is_configured():
        return {'ok': False, 'reason': 'not_configured'}

    return await notifier.notify_success('Portal DIRETOR Response', text)

def main():
    resp = load_response()
    portal_url = os.environ.get('PORTAL_URL', 'http://localhost:5000/portal')
    if not resp:
        print('No diretor response found at', RESP_FILE)
        return 2

    text = f"Portal: {portal_url}\n\nDiretor response:\n{json.dumps(resp, ensure_ascii=False, indent=2)}"

    # try to send
    try:
        r = asyncio.run(send_telegram(text))
    except Exception as e:
        r = {'ok': False, 'reason': 'exception', 'detail': str(e)}

    # Save a local copy
    with open(OUT_SAVE, 'w', encoding='utf-8') as f:
        f.write(text + '\n\nRESULT:\n' + json.dumps(r, ensure_ascii=False, indent=2))

    print('RESULT', r)
    if r.get('ok') or r.get('success'):
        print('Sent')
        return 0
    else:
        print('Not sent:', r)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
