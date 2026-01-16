#!/usr/bin/env python3
"""Script para enviar notificação da tarefa via Telegram"""

import requests
import os

TELEGRAM_TOKEN = "1105143633:AAEC1kmqDD_MDSpRFgEVHctwAfvfjVSp8B4"
TELEGRAM_CHAT_ID = "948686300"

message = """📋 <b>NOVA TAREFA: DOC-2025-01-16-001</b>

🎯 <b>Documentação Completa do Sistema Eddie Auto-Dev</b>

👥 <b>Equipe Responsável:</b>
• ConfluenceAgent (Coordenador)
• BPMAgent
• RequirementsAnalyst

📄 <b>Documentos para Acompanhamento:</b>

📝 <b>Confluence/Docs:</b>
https://github.com/eddiejdi/eddie-auto-dev/blob/main/docs/SYSTEM_DOCUMENTATION.md

📊 <b>Draw.io/Arquitetura:</b>
https://github.com/eddiejdi/eddie-auto-dev/blob/main/diagrams/arquitetura_eddie_auto_dev.drawio

🔄 <b>Workflow:</b>
1️⃣ Entrevistas com 17 Agents
2️⃣ Documentação no Confluence
3️⃣ Diagramas BPMN
4️⃣ Sincronização com Nuvem

⏱️ <b>Status:</b> INICIANDO...

<i>Atualizações serão enviadas durante o processo.</i>"""

url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
payload = {
    "chat_id": TELEGRAM_CHAT_ID,
    "text": message,
    "parse_mode": "HTML",
    "disable_web_page_preview": False
}

response = requests.post(url, data=payload)
result = response.json()

if result.get("ok"):
    print("✅ Notificação enviada com sucesso para Telegram!")
    print(f"   Message ID: {result['result']['message_id']}")
else:
    print(f"❌ Erro ao enviar: {result.get('description', 'Unknown error')}")
