#!/usr/bin/env python3
"""Enviar resultado final dos testes"""
import requests

TELEGRAM_TOKEN = "1105143633:AAEC1kmqDD_MDSpRFgEVHctwAfvfjVSp8B4"
CHAT_ID = "948686300"
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def send_result():
    text = """🎉 INSTALAÇÃO E TESTES COMPLETOS!

✅ Playwright + Chromium Headless instalado com sucesso

📊 TESTES DO NAVEGADOR HEADLESS:

✅ Dashboard (8502): OK - title='Streamlit'
✅ API Docs (8503): OK - title='Specialized Agents API'
✅ Monitor (8504): OK - title='Streamlit'
✅ Agent Chat (8505): OK - title='Streamlit'

📈 Resultado: 4/4 testes passaram

📸 Screenshots salvos em /tmp/screenshot_*.png

🔧 Sobre os botões de aprovação:
→ Seu webhook está ativo em network-bots.adaptgroup.pro
→ Os cliques foram enviados para lá
→ Verifique os logs do servidor webhook para ver suas respostas

Posso criar um sistema de aprovação local se preferir!"""
    
    response = requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text
        }
    )
    
    result = response.json()
    if result.get("ok"):
        print(f"✅ Resultado enviado! ID: {result['result']['message_id']}")
    else:
        print(f"❌ Erro: {result}")

if __name__ == "__main__":
    send_result()
