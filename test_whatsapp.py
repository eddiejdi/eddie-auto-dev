#!/usr/bin/env python3
"""
Script de teste para enviar mensagem via WhatsApp
"""

import httpx
import time
import sys

WAHA_URL = os.environ.get("WAHA_URL", "http://localhost:3000")
try:
    from tools.vault.secret_store import get_field

    API_KEY = get_field("eddie/waha_api_key", "password")
except Exception:
    API_KEY = ""

SESSION = os.environ.get("WAHA_SESSION", "default")

headers = {"Content-Type": "application/json", "X-Api-Key": API_KEY}


def get_status():
    """Obtém status da sessão"""
    r = httpx.get(f"{WAHA_URL}/api/sessions/{SESSION}", headers=headers, timeout=30)
    return r.json()


def send_message(number: str, text: str):
    """Envia mensagem"""
    # Formatar número
    number = number.replace("+", "").replace("-", "").replace(" ", "")
    if not number.startswith("55"):
        number = "55" + number

    chat_id = f"{number}@s.whatsapp.net"

    payload = {"chatId": chat_id, "text": text, "session": SESSION}

    r = httpx.post(
        f"{WAHA_URL}/api/sendText", json=payload, headers=headers, timeout=30
    )
    return r.json()


def main():
    print("=" * 50)
    print("🚀 Teste de Envio de Mensagem WhatsApp")
    print("=" * 50)

    # Verificar status
    print("\n📊 Verificando status da conexão...")
    status = get_status()
    session_status = status.get("status", "unknown")

    print(f"Status: {session_status}")

    if session_status == "SCAN_QR_CODE":
        print("\n⚠️ WhatsApp NÃO está conectado!")
        print("📱 Escaneie o QR Code primeiro:")
        print(f"   http://localhost:3000/api/{SESSION}/auth/qr")
        print("\nAguardando conexão...")

        # Aguardar conexão (máximo 2 minutos)
        for i in range(24):
            time.sleep(5)
            status = get_status()
            session_status = status.get("status", "unknown")
            print(f"  Status: {session_status}")

            if session_status == "WORKING":
                print("\n✅ Conectado!")
                break
        else:
            print("\n❌ Timeout! Escaneie o QR Code e execute novamente.")
            sys.exit(1)

    if session_status != "WORKING":
        print(f"\n❌ Status inesperado: {session_status}")
        sys.exit(1)

    # Informações da conexão
    me = status.get("me", {})
    if me:
        print(f"\n📱 Conectado como: {me.get('id', 'N/A')}")
        print(f"   Nome: {me.get('pushname', 'N/A')}")

    # Enviar mensagem de teste
    numero = "5511981193899"
    mensagem = (
        """🤖 *Eddie WhatsApp Bot - Teste*

Olá! Esta é uma mensagem de teste automática.

✅ Bot funcionando corretamente!
📅 Data: """
        + time.strftime("%d/%m/%Y %H:%M:%S")
        + """

_Mensagem enviada via WAHA API_"""
    )

    print(f"\n📤 Enviando mensagem para {numero}...")
    result = send_message(numero, mensagem)

    print(f"\n📨 Resultado: {result}")

    if "id" in result:
        print("\n✅ Mensagem enviada com sucesso!")
    else:
        print(f"\n❌ Erro ao enviar: {result.get('message', result)}")


if __name__ == "__main__":
    main()
