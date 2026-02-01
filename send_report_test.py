#!/usr/bin/env python3
"""Enviar mensagem de teste sobre relatórios"""

import requests

msg = {
    "chatId": "5511981193899@c.us",
    "text": """📊 *SISTEMA DE RELATÓRIOS INTEGRADO!*

Agora você pode solicitar relatórios via WhatsApp!

*Comandos disponíveis:*
• /relatorio - Ver menu
• /relatorio btc - Status Bitcoin
• /relatorio sistema - Status servidor

*Ou pergunte naturalmente:*
• "como está o btc?"
• "relatório de trading"
• "status do sistema"

Teste agora! 🚀""",
}

r = requests.post(
    "http://localhost:3000/api/sendText",
    headers={
        "Content-Type": "application/json",
        "X-Api-Key": "96263ae8a9804541849ebc5efa212e0e",
    },
    json={**msg, "session": "default"},
)
print("Status:", r.status_code)
print("Mensagem enviada!" if r.status_code == 201 else f"Erro: {r.text}")
