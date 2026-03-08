# 🔗 Integração Shared AI - Open WebUI, Telegram e WhatsApp

## Visão Geral

Este documento descreve a integração completa entre os modelos de IA do Shared, Open WebUI, Telegram Bot e WhatsApp API.

## Arquitetura

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Open WebUI    │     │  Telegram Bot   │     │   WhatsApp API  │
│  :3000          │     │                 │     │   WAHA :3004    │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     Ollama Server       │
                    │     :11434              │
                    │  ┌──────────────────┐   │
                    │  │ shared-assistant  │   │ ← Assistente pessoal (sem censura)
                    │  │ shared-coder      │   │ ← Programação apenas
                    │  │ shared-homelab    │   │ ← DevOps/Infraestrutura
                    │  │ dolphin-llama3   │   │ ← Base sem censura
                    │  └──────────────────┘   │
                    └─────────────────────────┘
## Modelos Disponíveis

| Modelo | Base | Propósito | Censura |
|--------|------|-----------|---------|
| `shared-assistant` | dolphin-llama3:8b | Assistente pessoal completo | ❌ Nenhuma |
| `shared-coder` | qwen2.5-coder:7b | Programação e DevOps | ✅ Apenas código |
| `shared-homelab` | qwen2.5-coder:7b | Infraestrutura e homelab | ✅ Técnico |
| `github-agent` | codestral:22b | Desenvolvimento GitHub | ✅ Código |

## Componentes

### 1. Open WebUI (http://192.168.15.2:3000)
Interface web para interação com os modelos.

### 2. Ollama Server (http://192.168.15.2:11434)
Servidor de inferência dos modelos LLM.

### 3. Telegram Bot
Bot integrado para comunicação via Telegram.
- Token: Configurado em `telegram_bot.py`
- Comandos: `/models`, `/profiles`, `/profile`, `/use`

### 4. WhatsApp API - WAHA (http://192.168.15.2:3004)
API HTTP para envio de mensagens WhatsApp.

```bash
# Verificar status
curl http://192.168.15.2:3004/api/sessions

# Enviar mensagem
curl -X POST http://192.168.15.2:3004/api/sendText \
  -H "Content-Type: application/json" \
  -d '{"session":"default","chatId":"5511999999999@s.whatsapp.net","text":"Olá!"}'
## Módulo de Integração

O arquivo `openwebui_integration.py` fornece uma interface unificada:

from openwebui_integration import get_integration_client

client = get_integration_client()

# Listar modelos
models = await client.list_models()

# Chat com seleção automática de perfil
response = await client.chat("Escreva um código Python", auto_profile=True)

# Chat com perfil específico
response = await client.chat("Escreva uma mensagem de amor", profile="assistant")
## Perfis de Modelo

MODEL_PROFILES = {
    "assistant": "shared-assistant",   # Assistente pessoal
    "coder": "shared-coder",           # Programação
    "homelab": "shared-homelab",       # Infraestrutura
    "general": "shared-assistant",     # Uso geral
    "fast": "qwen2.5-coder:1.5b",     # Respostas rápidas
    "advanced": "deepseek-coder-v2:16b", # Tarefas complexas
    "github": "github-agent"          # Desenvolvimento GitHub
}
## Configuração do WhatsApp

1. Acesse http://192.168.15.2:3004/dashboard
2. Clique na sessão "default"
3. Escaneie o QR Code com WhatsApp

## Arquivos Principais

- `openwebui_integration.py` - Módulo de integração
- `telegram_bot.py` - Bot Telegram
- `whatsapp_api.py` - API de envio WhatsApp
- `whatsapp_bot.py` - Bot WhatsApp completo

## Variáveis de Ambiente

```bash
OLLAMA_HOST=http://192.168.15.2:11434
OPENWEBUI_HOST=http://192.168.15.2:3000
TELEGRAM_TOKEN=seu_token
ADMIN_CHAT_ID=seu_chat_id
---
*Última atualização: 10 de janeiro de 2026*
