#!/usr/bin/env python3
"""
Sistema de Lições Aprendidas e Aprovação de Entregas
Envia relatório pelo Telegram com botões de Aprovação/Reprovação
"""

import os
import json
import asyncio
from datetime import datetime
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

# Configuração
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "1105143633:AAEC1kmqDD_MDSpRFgEVHctwAfvfjVSp8B4")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "948686300")  # ID do chat do Eddie

async def send_approval_request(
    delivery_name: str,
    lessons_learned: list,
    tests_passed: int,
    tests_total: int,
    components: list,
    delivery_id: str = None
):
    """
    Envia relatório de entrega com botões de Aprovação/Reprovação.
    """
    bot = Bot(token=TELEGRAM_TOKEN)
    
    if not delivery_id:
        delivery_id = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Formata lições aprendidas
    lessons_text = "\n".join([f"  • {lesson}" for lesson in lessons_learned])
    
    # Formata componentes
    components_text = "\n".join([f"  ✅ {comp}" for comp in components])
    
    # Monta mensagem
    message = f"""🚀 ENTREGA CONCLUÍDA

📦 Projeto: {delivery_name}
🕐 Data: {datetime.now().strftime("%d/%m/%Y %H:%M")}
🆔 ID: {delivery_id}

📊 RESULTADOS DOS TESTES

✅ Testes Passados: {tests_passed}/{tests_total}
📈 Taxa de Sucesso: {(tests_passed/tests_total*100):.1f}%

🔧 COMPONENTES ENTREGUES

{components_text}

📚 LIÇÕES APRENDIDAS

{lessons_text}

⚡ AÇÃO NECESSÁRIA

Revise a entrega e selecione uma opção:

✅ APROVAR = +10 XP 🏆 + Acesso a modelo premium por 24h
⚠️ PARCIAL = -5 pontos + Feedback obrigatório
❌ REPROVAR = -10 pontos + Tarefa retorna à fila

🎁 BÔNUS APROVAÇÃO:
  • +10 pontos de experiência (XP)
  • Modelo LLM premium liberado por 24h
  • Prioridade +1 na próxima tarefa
  • Badge "Entrega Perfeita" 🏅

Após PARCIAL ou REPROVAR, envie mensagem com o motivo.
"""

    # Cria botões inline
    keyboard = [
        [
            InlineKeyboardButton("✅ APROVAR (+10 XP 🏆)", callback_data=f"approve_{delivery_id}"),
        ],
        [
            InlineKeyboardButton("⚠️ APROVAR PARCIAL (-5 pontos)", callback_data=f"partial_{delivery_id}"),
        ],
        [
            InlineKeyboardButton("❌ REPROVAR (-10 pontos)", callback_data=f"reject_{delivery_id}"),
        ],
        [
            InlineKeyboardButton("📋 Ver Detalhes", callback_data=f"details_{delivery_id}"),
            InlineKeyboardButton("🔄 Solicitar Correção", callback_data=f"fix_{delivery_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Envia mensagem
    try:
        sent_message = await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            reply_markup=reply_markup
        )
        
        print(f"✅ Mensagem enviada com sucesso! Message ID: {sent_message.message_id}")
        
        # Salva registro da entrega
        delivery_record = {
            "delivery_id": delivery_id,
            "name": delivery_name,
            "timestamp": datetime.now().isoformat(),
            "tests_passed": tests_passed,
            "tests_total": tests_total,
            "components": components,
            "lessons_learned": lessons_learned,
            "message_id": sent_message.message_id,
            "status": "pending_approval"
        }
        
        # Salva em arquivo
        records_file = "/tmp/delivery_records.json"
        records = []
        if os.path.exists(records_file):
            with open(records_file, "r") as f:
                records = json.load(f)
        records.append(delivery_record)
        with open(records_file, "w") as f:
            json.dump(records, f, indent=2)
        
        return {
            "success": True,
            "message_id": sent_message.message_id,
            "delivery_id": delivery_id
        }
        
    except Exception as e:
        print(f"❌ Erro ao enviar mensagem: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def send_agent_chat_delivery():
    """Envia relatório específico da entrega do Agent Chat."""
    
    delivery_name = "Agent Chat - Painel de Chat com Agentes"
    
    lessons_learned = [
        "Campo 'description' na API de geração de código, não 'prompt'",
        "Dependências (aiohttp, beautifulsoup4) precisam ser instaladas no venv do servidor",
        "Scripts de teste devem ser copiados antes de serem executados no servidor",
        "Docker network pode ter problemas após restart - usar 'docker network prune'",
        "Testes RPA com scraping são alternativa viável quando Selenium não está disponível",
        "Sempre fazer git pull no servidor antes de reiniciar serviços",
        "Verificar se serviço Streamlit iniciou com pgrep antes de declarar sucesso",
        "Timeout de 120s necessário para operações com LLM (geração de código)"
    ]
    
    components = [
        "Agent Chat (porta 8505) - Interface de chat estilo Copilot",
        "Agent Monitor (porta 8504) - Visualização de comunicação entre agentes",
        "Auto-scaler - Escalonamento automático baseado em CPU",
        "Instructor Agent - Treinamento automático diário",
        "API Endpoints - /instructor/*, /autoscaler/*",
        "Testes RPA automatizados - test_rpa_scraping.py",
        "Script de verificação do sistema - verify_system.sh"
    ]
    
    result = await send_approval_request(
        delivery_name=delivery_name,
        lessons_learned=lessons_learned,
        tests_passed=9,
        tests_total=10,
        components=components
    )
    
    return result


if __name__ == "__main__":
    print("=" * 50)
    print("   SISTEMA DE APROVAÇÃO DE ENTREGAS")
    print("=" * 50)
    
    result = asyncio.run(send_agent_chat_delivery())
    
    if result["success"]:
        print(f"\n✅ Solicitação de aprovação enviada!")
        print(f"   Delivery ID: {result['delivery_id']}")
        print(f"   Message ID: {result['message_id']}")
    else:
        print(f"\n❌ Falha ao enviar: {result.get('error')}")
