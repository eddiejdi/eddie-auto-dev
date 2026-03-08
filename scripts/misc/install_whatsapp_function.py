#!/usr/bin/env python3
"""
Instala a Function de WhatsApp no Open WebUI via API
"""
import requests
import json
import getpass
import os

OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "http://localhost:3000")

WHATSAPP_TOOL_CODE = '''
"""
title: Enviar WhatsApp
author: Shared
version: 1.0.0
description: Envia mensagens via WhatsApp usando WAHA API
"""

import requests
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        WAHA_URL: str = Field(
            default="http://172.17.0.1:3001",
            description="URL da API WAHA"
        )
        SESSION: str = Field(
            default="default",
            description="Nome da sessão WAHA"
        )

    def __init__(self):
        self.valves = self.Valves()

    def send_whatsapp(
        self,
        phone: str,
        message: str,
        __user__: dict = {}
    ) -> str:
        """
        Envia uma mensagem de WhatsApp para um número de telefone.
        Use esta ferramenta quando o usuário pedir para enviar uma mensagem via WhatsApp.

        :param phone: Número de telefone (apenas números, ex: 5511999999999)
        :param message: Texto da mensagem a ser enviada
        :return: Confirmação do envio ou erro
        """
        try:
            phone_clean = "".join(filter(str.isdigit, phone))
            if len(phone_clean) == 11:
                phone_clean = f"55{phone_clean}"
            elif len(phone_clean) == 10:
                phone_clean = f"5511{phone_clean}"

            chat_id = f"{phone_clean}@s.whatsapp.net"

            response = requests.post(
                f"{self.valves.WAHA_URL}/api/sendText",
                json={
                    "session": self.valves.SESSION,
                    "chatId": chat_id,
                    "text": message
                },
                timeout=30
            )

            if response.status_code == 201:
                result = response.json()
                return f"✅ Mensagem enviada com sucesso para {phone}! ID: {result.get('id', 'N/A')}"
            else:
                return f"❌ Erro ao enviar: {response.text}"

        except requests.exceptions.ConnectionError:
            return "❌ Erro: Não foi possível conectar ao serviço WhatsApp."
        except Exception as e:
            return f"❌ Erro ao enviar mensagem: {str(e)}"

    def check_whatsapp_status(self, __user__: dict = {}) -> str:
        """
        Verifica o status da conexão do WhatsApp.
        """
        try:
            response = requests.get(
                f"{self.valves.WAHA_URL}/api/sessions/{self.valves.SESSION}",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "UNKNOWN")
                me = data.get("me", {})

                if status == "WORKING":
                    name = me.get("pushName", "Desconhecido")
                    number = me.get("id", "").replace("@c.us", "")
                    return f"✅ WhatsApp conectado! Número: {number}, Nome: {name}"
                else:
                    return f"⚠️ WhatsApp status: {status}"
            else:
                return f"❌ Erro: {response.text}"

        except Exception as e:
            return f"❌ Erro: {str(e)}"
'''


def login(email: str, password: str) -> str:
    """Faz login e retorna o token"""
    response = requests.post(
        f"{OPENWEBUI_URL}/api/v1/auths/signin",
        json={"email": email, "password": password}
    )
    if response.status_code == 200:
        return response.json().get("token")
    else:
        raise Exception(f"Erro no login: {response.text}")


def create_function(token: str):
    """Cria a function no Open WebUI"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Primeiro, verifica se já existe
    response = requests.get(
        f"{OPENWEBUI_URL}/api/v1/functions/send_whatsapp",
        headers=headers
    )
    
    if response.status_code == 200:
        print("⚠️  Function 'send_whatsapp' já existe. Atualizando...")
        # Atualiza
        response = requests.post(
            f"{OPENWEBUI_URL}/api/v1/functions/send_whatsapp/update",
            headers=headers,
            json={
                "id": "send_whatsapp",
                "name": "Enviar WhatsApp",
                "meta": {
                    "description": "Envia mensagens via WhatsApp usando WAHA API"
                },
                "content": WHATSAPP_TOOL_CODE,
                "is_active": True,
                "is_global": True
            }
        )
    else:
        # Cria nova
        response = requests.post(
            f"{OPENWEBUI_URL}/api/v1/functions/create",
            headers=headers,
            json={
                "id": "send_whatsapp",
                "name": "Enviar WhatsApp",
                "meta": {
                    "description": "Envia mensagens via WhatsApp usando WAHA API"
                },
                "content": WHATSAPP_TOOL_CODE,
                "is_active": True,
                "is_global": True
            }
        )
    
    if response.status_code in [200, 201]:
        print("✅ Function 'send_whatsapp' instalada com sucesso!")
        return True
    else:
        print(f"❌ Erro ao criar function: {response.text}")
        return False


def list_functions(token: str):
    """Lista functions existentes"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{OPENWEBUI_URL}/api/v1/functions",
        headers=headers
    )
    if response.status_code == 200:
        functions = response.json()
        print(f"\n📋 Functions instaladas ({len(functions)}):")
        for f in functions:
            status = "✅" if f.get("is_active") else "❌"
            print(f"  {status} {f.get('id')}: {f.get('name')}")
    else:
        print(f"Erro ao listar: {response.text}")


def main():
    print("=" * 50)
    print("🔧 Instalador de Function WhatsApp - Open WebUI")
    print("=" * 50)
    print(f"\nURL: {OPENWEBUI_URL}")
    
    # Credenciais
    email = input("\n📧 Email do admin: ")
    password = getpass.getpass("🔑 Senha: ")
    
    try:
        print("\n🔐 Fazendo login...")
        token = login(email, password)
        print("✅ Login OK!")
        
        # Salvar token para uso futuro
        with open(os.path.expanduser("~/.openwebui_token"), "w") as f:
            f.write(token)
        print("💾 Token salvo em ~/.openwebui_token")
        
        # Lista functions existentes
        list_functions(token)
        
        # Cria a function
        print("\n📤 Instalando function WhatsApp...")
        create_function(token)
        
        # Lista novamente
        list_functions(token)
        
        print("\n" + "=" * 50)
        print("🎉 Instalação concluída!")
        print("=" * 50)
        print("\nPróximos passos:")
        print("1. Acesse http://localhost:3000")
        print("2. Vá em Admin Panel → Functions")
        print("3. Ative 'Enviar WhatsApp' para os modelos desejados")
        print("4. Teste: 'Envie uma mensagem para 11999999999 dizendo Oi!'")
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
