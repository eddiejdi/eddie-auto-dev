#!/usr/bin/env python3
"""Enviar atualização sobre status dos botões"""

import requests

from tools.secrets_loader import get_telegram_token

TELEGRAM_TOKEN = get_telegram_token()
CHAT_ID = "948686300"
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def send_message():
    text = """📊 STATUS DA VERIFICAÇÃO

🔍 Verificação dos cliques nos botões:

✅ Webhook ATIVO detectado:
   → network-bots.adaptgroup.pro

ℹ️ Seus cliques nos botões foram enviados para o servidor do webhook, não ficaram no buffer local do Telegram.

📋 Para processar os callbacks dos botões, seria necessário:
1. Verificar os logs do servidor webhook, OU
2. Criar um handler local que substitua o webhook

🌐 Navegador Headless:
→ Playwright + Chromium sendo instalado em background
→ Aguarde ~2 min para conclusão

🤖 Você gostaria de:
A) Ver os logs do servidor webhook?
B) Criar um novo sistema de aprovação local?
C) Testar o navegador headless quando pronto?

Responda com A, B ou C"""

    response = requests.post(
        f"{BASE_URL}/sendMessage", json={"chat_id": CHAT_ID, "text": text}
    )

    result = response.json()
    if result.get("ok"):
        print(f"✅ Mensagem enviada! ID: {result['result']['message_id']}")
    else:
        print(f"❌ Erro: {result}")


if __name__ == "__main__":
    send_message()
