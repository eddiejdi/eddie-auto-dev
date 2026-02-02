#!/usr/bin/env python3
"""Script para enviar notificação da tarefa via Telegram"""

import requests
import sys

from tools.secrets_loader import get_telegram_token, get_telegram_chat_id

TELEGRAM_TOKEN = get_telegram_token()
TELEGRAM_CHAT_ID = "948686300"

message = (
    sys.argv[1]
    if len(sys.argv) > 1
    else """📋 <b>LINKS PARA ACOMPANHAMENTO - DOC-2025-01-16-001</b>

🎯 <b>Documentação Completa do Sistema Eddie Auto-Dev</b>

✅ <b>Tarefa iniciada e em processamento no servidor local!</b>

📄 <b>Documentos para Acompanhamento (CLIQUE PARA ABRIR):</b>

📝 <b>Confluence/Documentação:</b>
https://github.com/eddiejdi/eddie-auto-dev/blob/main/docs/SYSTEM_DOCUMENTATION.md

📊 <b>Draw.io/Arquitetura:</b>
https://github.com/eddiejdi/eddie-auto-dev/blob/main/diagrams/arquitetura_eddie_auto_dev.drawio

📊 <b>Organograma:</b>
https://github.com/eddiejdi/eddie-auto-dev/blob/main/diagrams/organograma_eddie_auto_dev.drawio

📋 <b>Estrutura do Time:</b>
https://github.com/eddiejdi/eddie-auto-dev/blob/main/TEAM_STRUCTURE.md

🔄 <b>Processamento em andamento pelo servidor Ollama local (economia de tokens)</b>

👥 <b>Equipe:</b> ConfluenceAgent + BPMAgent + RequirementsAnalyst

<i>Documentos serão atualizados automaticamente durante o processo.</i>"""
)

url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
payload = {
    "chat_id": get_telegram_chat_id() or "",
    "text": message,
    "parse_mode": "HTML",
    "disable_web_page_preview": False,
}

response = requests.post(url, data=payload)
result = response.json()

if result.get("ok"):
    print("✅ Notificação enviada com sucesso para Telegram!")
    print(f"   Message ID: {result['result']['message_id']}")
else:
    print(f"❌ Erro ao enviar: {result.get('description', 'Unknown error')}")
