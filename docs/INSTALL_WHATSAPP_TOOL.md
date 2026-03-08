# 📱 Instalação da Tool WhatsApp no Open WebUI

## O Problema
O modelo `shared-assistant` consegue gerar mensagens de amor/etc, mas não consegue **realmente enviar** via WhatsApp porque não tem uma **Tool/Function** configurada.

## A Solução
Instalar a Function `send_whatsapp` no Open WebUI para que o modelo possa chamar a API WAHA.

---

## Passo a Passo de Instalação

### 1. Acesse o Open WebUI
Abra no navegador: **http://192.168.15.2:3000**

### 2. Vá para Admin Panel
- Clique no seu avatar/perfil (canto superior direito)
- Selecione **"Admin Panel"** ou **"Painel de Admin"**

### 3. Acesse Functions/Tools
- No menu lateral, clique em **"Functions"** ou **"Tools"**
- Pode estar em **"Workspace"** → **"Functions"**

### 4. Adicione Nova Function
- Clique no botão **"+"** ou **"Create Function"**
- Preencha:
  - **ID**: `send_whatsapp`
  - **Name**: `Enviar WhatsApp`
  - **Description**: `Envia mensagens via WhatsApp`

### 5. Cole o Código
Cole o conteúdo do arquivo `/home/homelab/myClaude/openwebui_whatsapp_tool.py`:

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
            default="http://host.docker.internal:3001",
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
            phone_clean = ''.join(filter(str.isdigit, phone))
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
                status = data.get('status', 'UNKNOWN')
                me = data.get('me', {})

                if status == 'WORKING':
                    name = me.get('pushName', 'Desconhecido')
                    number = me.get('id', '').replace('@c.us', '')
                    return f"✅ WhatsApp conectado! Número: {number}, Nome: {name}"
                else:
                    return f"⚠️ WhatsApp status: {status}"
            else:
                return f"❌ Erro: {response.text}"

        except Exception as e:
            return f"❌ Erro: {str(e)}"
### 6. Salve e Ative
- Clique em **"Save"** ou **"Salvar"**
- Certifique-se de que está **Enabled/Ativado**

### 7. Configure os Valves (se necessário)
- Clique no ícone de engrenagem ao lado da function
- Ajuste:
  - **WAHA_URL**: `http://host.docker.internal:3001` (para Docker) ou `http://192.168.15.2:3001` (para acesso direto)
  - **SESSION**: `default`

### 8. Associe ao Modelo
- Vá para **Settings** → **Models** ou **Workspace** → **Models**
- Encontre `shared-assistant`
- Edite e em **"Tools"** ou **"Functions"**, habilite `send_whatsapp`

---

## Teste

Depois de instalado, teste no chat com `shared-assistant`:

"Envie uma mensagem de WhatsApp para 11981193899 dizendo: Teste da integração!"
Se funcionar, você verá:
✅ Mensagem enviada com sucesso para 11981193899! ID: xxx
---

## Troubleshooting

### "Não foi possível conectar ao serviço WhatsApp"
- Verifique se o WAHA está rodando: `docker ps | grep waha`
- Verifique status: `curl http://localhost:3001/api/sessions`

### "host.docker.internal não resolve"
- Altere WAHA_URL para: `http://172.17.0.1:3001` (IP do host Docker)

### Function não aparece
- Certifique-se de que salvou corretamente
- Reinicie o Open WebUI: `docker restart open-webui`
