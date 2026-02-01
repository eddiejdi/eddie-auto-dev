#!/usr/bin/env python3
"""
Servidor de API para envio de mensagens WhatsApp via WAHA
Este servidor permite que modelos de IA enviem mensagens reais
"""

from flask import Flask, request, jsonify
import requests
import logging

app = Flask(__name__)

# Configuração
WAHA_URL = "http://localhost:3001"
SESSION = "default"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def format_phone(phone: str) -> str:
    """Formata número de telefone para formato WhatsApp"""
    # Remove caracteres não numéricos
    phone = "".join(filter(str.isdigit, phone))

    # Adiciona código do país se não tiver
    if len(phone) == 11:  # Número brasileiro sem código do país
        phone = f"55{phone}"
    elif len(phone) == 10:  # Número sem DDD 9
        phone = f"5511{phone}"

    return f"{phone}@s.whatsapp.net"


@app.route("/send", methods=["POST"])
def send_message():
    """Envia uma mensagem WhatsApp"""
    try:
        data = request.json
        phone = data.get("phone", data.get("to", data.get("numero")))
        message = data.get("message", data.get("text", data.get("mensagem")))

        if not phone or not message:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": 'Parâmetros "phone" e "message" são obrigatórios',
                    }
                ),
                400,
            )

        # Formata número
        chat_id = format_phone(phone)

        # Envia via WAHA
        response = requests.post(
            f"{WAHA_URL}/api/sendText",
            json={"session": SESSION, "chatId": chat_id, "text": message},
        )

        if response.status_code == 201:
            result = response.json()
            logger.info(f"Mensagem enviada para {phone}: {message[:50]}...")
            return jsonify(
                {
                    "success": True,
                    "message": "Mensagem enviada com sucesso",
                    "to": phone,
                    "id": result.get("id"),
                }
            )
        else:
            logger.error(f"Erro WAHA: {response.text}")
            return (
                jsonify({"success": False, "error": response.text}),
                response.status_code,
            )

    except Exception as e:
        logger.error(f"Erro: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/status", methods=["GET"])
def status():
    """Verifica status da conexão WhatsApp"""
    try:
        response = requests.get(f"{WAHA_URL}/api/sessions/{SESSION}")
        if response.status_code == 200:
            data = response.json()
            return jsonify(
                {
                    "connected": data.get("status") == "WORKING",
                    "status": data.get("status"),
                    "session": SESSION,
                }
            )
        return jsonify({"connected": False, "status": "ERROR"})
    except Exception as e:
        return jsonify({"connected": False, "error": str(e)})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print("🚀 API de WhatsApp iniciada na porta 5050")
    print("📱 Use POST /send com {phone, message} para enviar")
    app.run(host="0.0.0.0", port=5050)
