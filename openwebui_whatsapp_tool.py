"""
title: Enviar WhatsApp
author: Eddie
version: 1.0.0
description: Envia mensagens via WhatsApp usando WAHA API
"""

import requests
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        WAHA_URL: str = Field(
            default="http://host.docker.internal:3001", description="URL da API WAHA"
        )
        SESSION: str = Field(default="default", description="Nome da sessão WAHA")

    def __init__(self):
        self.valves = self.Valves()

    def send_whatsapp(self, phone: str, message: str, __user__: dict = {}) -> str:
        """
        Envia uma mensagem de WhatsApp para um número de telefone.
        Use esta ferramenta quando o usuário pedir para enviar uma mensagem via WhatsApp.

        :param phone: Número de telefone (apenas números, ex: 5511999999999)
        :param message: Texto da mensagem a ser enviada
        :return: Confirmação do envio ou erro
        """
        try:
            # Formatar número
            phone_clean = "".join(filter(str.isdigit, phone))

            # Adicionar código do país se necessário
            if len(phone_clean) == 11:
                phone_clean = f"55{phone_clean}"
            elif len(phone_clean) == 10:
                phone_clean = f"5511{phone_clean}"

            chat_id = f"{phone_clean}@s.whatsapp.net"

            # Enviar via WAHA
            response = requests.post(
                f"{self.valves.WAHA_URL}/api/sendText",
                json={
                    "session": self.valves.SESSION,
                    "chatId": chat_id,
                    "text": message,
                },
                timeout=30,
            )

            if response.status_code == 201:
                result = response.json()
                return f"✅ Mensagem enviada com sucesso para {phone}! ID: {result.get('id', 'N/A')}"
            else:
                return f"❌ Erro ao enviar: {response.text}"

        except requests.exceptions.ConnectionError:
            return "❌ Erro: Não foi possível conectar ao serviço WhatsApp. Verifique se o WAHA está rodando."
        except Exception as e:
            return f"❌ Erro ao enviar mensagem: {str(e)}"

    def check_whatsapp_status(self, __user__: dict = {}) -> str:
        """
        Verifica o status da conexão do WhatsApp.
        Use para verificar se o WhatsApp está conectado antes de enviar mensagens.

        :return: Status da conexão WhatsApp
        """
        try:
            response = requests.get(
                f"{self.valves.WAHA_URL}/api/sessions/{self.valves.SESSION}", timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "UNKNOWN")
                me = data.get("me", {})

                if status == "WORKING":
                    name = me.get("pushName", "Desconhecido")
                    number = me.get("id", "").replace("@c.us", "")
                    return (
                        f"✅ WhatsApp conectado!\n📱 Número: {number}\n👤 Nome: {name}"
                    )
                else:
                    return f"⚠️ WhatsApp status: {status}. Pode ser necessário escanear o QR Code."
            else:
                return f"❌ Erro ao verificar status: {response.text}"

        except Exception as e:
            return f"❌ Erro ao verificar status: {str(e)}"
