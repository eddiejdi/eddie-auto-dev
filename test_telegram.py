#!/usr/bin/env python3
"""Teste do notificador Telegram"""

import asyncio
import os
import sys

# Configurar ambiente
from tools.secrets_loader import get_telegram_token

os.environ["TELEGRAM_BOT_TOKEN"] = get_telegram_token()
os.environ["TELEGRAM_CHAT_ID"] = "948686300"

sys.path.insert(0, "/home/homelab/myClaude")
from specialized_agents.telegram_client import TelegramNotifier


async def test():
    notifier = TelegramNotifier()

    # Notificação de sucesso
    result = await notifier.notify_success(
        "Sistema Configurado",
        "Telegram integrado ao Eddie Coder!\n\n"
        "Você receberá:\n"
        "• 🚀 Notificações de deploy\n"
        "• 🤖 Status dos agentes\n"
        "• ⚠️ Alertas do sistema",
    )
    print(f"Resultado: {result}")


asyncio.run(test())
