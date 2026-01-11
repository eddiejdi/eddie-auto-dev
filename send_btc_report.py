#!/usr/bin/env python3
"""Testar relatório via WhatsApp"""

import requests
import time

# Gerar relatório BTC
import sys
sys.path.insert(0, '/home/eddie/myClaude')
from reports_integration import generate_report

report = generate_report("btc")

# Enviar via WhatsApp
msg = {
    'chatId': '5511981193899@c.us',
    'text': report,
    'session': 'default'
}

r = requests.post(
    'http://localhost:3000/api/sendText',
    headers={
        'Content-Type': 'application/json',
        'X-Api-Key': '96263ae8a9804541849ebc5efa212e0e'
    },
    json=msg
)
print('Status:', r.status_code)
if r.status_code == 201:
    print('✅ Relatório BTC enviado com sucesso!')
else:
    print(f'❌ Erro: {r.text[:200]}')
