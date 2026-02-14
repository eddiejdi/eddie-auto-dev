# Resumo: Integração Gemini + Google Home para Controle de Dispositivos

**Data:** 2026-02-12
**Status:** Configuração preparada, aguardando credenciais OAuth

## O Que Foi Feito

### 1. Arquitetura Implementada ✅

- **Gemini Connector** (`specialized_agents/gemini_connector.py`)
  - Endpoint webhook: `POST /gemini/webhook`
  - Recebe comandos em PT-BR do Gemini
  - Encaminha para GoogleAssistantAgent

- **Google Assistant Agent** (atualizado para modo Gemini-only)
  - Interpreta comandos via LLM (Gemini ou Ollama)
  - Gerencia dispositivos via DeviceManager
  - Integra com Google Smart Device Management API

- **Configuração Gemini 2.0 Flash** (com preparação para 2.5 Pro)
  - Alternância automática: Gemini (cloud) ↔ Ollama (local)
  - Ativa via `GOOGLE_AI_API_KEY` ou `GEMINI_ENABLED=true`

### 2. Scripts Criados ✅

| Arquivo | Propósito |
|---------|-----------|
| `setup_google_home_oauth.py` | Configuração OAuth 2.0 automática |
| `GOOGLE_HOME_SETUP_GUIDE.md` | Guia passo-a-passo completo |
| `GEMINI_CONFIG.md` | Documentação Gemini 2.5 Pro |
| `store_secrets.py` | Armazenamento seguro (Bitwarden) |
| `extract_tuya_keys_cloud.py` | Extração local_keys (Tuya Cloud) |

### 3. Fluxo de Controle Implementado ✅

```
Usuário → "OK Google, ligar ventilador"
    ↓
Gemini (celular) reconhece comando
    ↓
POST /gemini/webhook {"text": "ligar ventilador do escritório"}
    ↓
GoogleAssistantAgent interpreta via LLM
    ↓
Identifica dispositivo + ação (parsed)
    ↓
Executa via Google SDM API
    ↓
Dispositivo físico liga
    ↓
Resposta TTS ao usuário
```

## Próximos Passos (Para Você)

### Passo 1: Configurar Google Cloud Console 🔧

Siga o guia em `GOOGLE_HOME_SETUP_GUIDE.md`:

1. **Criar projeto** no Google Cloud Console
2. **Habilitar** Smart Device Management API
3. **Criar OAuth 2.0 Client**:
   - Type: Web Application
   - Redirect URI: `http://localhost:8080`
4. **Criar Device Access Project**:
   - Taxa única: $5 USD
   - Necessário para acesso aos dispositivos
5. **Anotar**:
   - Client ID
   - Client Secret  
   - Device Access Project ID

### Passo 2: Executar Script OAuth 🔐

```bash
# Editar credenciais no script
nano setup_google_home_oauth.py

# Preencher:
OAUTH_CLIENT_ID = "seu-client-id"
OAUTH_CLIENT_SECRET = "seu-secret"
SDM_PROJECT_ID = "projects/seu-project-id"

# Executar (abrirá navegador)
source .venv/bin/activate
python3 setup_google_home_oauth.py

# Autorizar no navegador
# Script salvará tokens automaticamente
```

### Passo 3: Configurar Gemini API 🤖

```bash
# Obter API key em https://ai.google.dev/
# (Grátis: 1500 requisições/dia)

# Adicionar ao .env
echo "GOOGLE_AI_API_KEY=sua-api-key-aqui" >> .env
echo "GEMINI_ENABLED=true" >> .env

# Testar
python3 - << 'EOF'
from specialized_agents.config import LLM_CONFIG
print(f"Provider: {LLM_CONFIG.get('provider')}")
print(f"Model: {LLM_CONFIG.get('model')}")
EOF
```

### Passo 4: Armazenar Credenciais 🔒

```bash
# Instalar Bitwarden CLI (se necessário)
npm install -g @bitwarden/cli

# Logar e desbloquear
bw login
export BW_SESSION=$(bw unlock --raw)

# Executar script de armazenamento
python3 store_secrets.py

# Limpar arquivos locais
rm google_home_credentials.json
rm extract_tuya_keys_cloud.py
```

### Passo 5: Configurar Variáveis de Ambiente 🌍

Adicionar ao `.env` ou exportar:

```bash
# Gemini
export GOOGLE_AI_API_KEY="sua-api-key"
export GEMINI_ENABLED=true

# Google Home
export GOOGLE_HOME_TOKEN="access-token-do-oauth"
export GOOGLE_SDM_PROJECT_ID="projects/seu-project-id"
```

### Passo 6: Testar Integração ✅

```bash
# Iniciar API
source .venv/bin/activate
python3 -m uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503

# Em outro terminal, testar webhook
curl -X POST http://localhost:8503/gemini/webhook \
  -H "Content-Type: application/json" \
  -d '{"text":"ligar ventilador do escritório"}'

# Verificar se dispositivo liga!
```

## Comandos Suportados

- ✅ **Ligar/Desligar**: "ligar ventilador", "desligar luz da sala"
- ✅ **Ajustar**: "aumentar temperatura para 22 graus", "diminuir brilho"
- ✅ **Status**: "como está a temperatura?", "ventilador está ligado?"
- ✅ **Cenas**: "ativar cena boa noite", "modo filme"

## Troubleshooting Rápido

| Problema | Solução |
|----------|---------|
| Webhook retorna success mas dispositivo não liga | Verificar se `GOOGLE_HOME_TOKEN` está válido (expira em 1h) |
| Erro "invalid_grant" no OAuth | Código expirou (10 min); executar script novamente |
| Gemini não está sendo usado | Verificar `GOOGLE_AI_API_KEY` e `GEMINI_ENABLED=true` |
| Dispositivo não encontrado | Sincronizar: `curl http://localhost:8503/home/sync` |

## Arquitetura Final

```
┌─────────────────┐
│   Seu Celular   │
│  (Gemini App)   │
└────────┬────────┘
         │ "OK Google, ligar ventilador"
         ↓
┌─────────────────────────┐
│  Eddie Auto-Dev Server  │
│  ┌───────────────────┐  │
│  │ Gemini Connector  │←─┼─ POST /gemini/webhook
│  └─────────┬─────────┘  │
│            ↓             │
│  ┌───────────────────┐  │
│  │ GoogleAssistant   │  │
│  │      Agent        │  │
│  └─────────┬─────────┘  │
│            ↓             │
│  ┌───────────────────┐  │
│  │ Google SDM API    │──┼─→ Cloud
│  └───────────────────┘  │
└─────────────────────────┘
         ↓
┌─────────────────┐
│  Seu Ventilador │  ← Liga fisicamente!
└─────────────────┘
```

## Custos Totais

- **Google Cloud**: Grátis (uso pessoal)
- **Device Access API**: $5 USD (taxa única)
- **Gemini API**: Grátis (1500 req/dia)
- **Ollama (fallback)**: $0 (local)

**Total inicial: $5 USD**

## Contatos Rápidos

- Google AI: https://ai.google.dev/
- Device Access Console: https://console.nest.google.com/device-access/
- Documentação SDM: https://developers.google.com/nest/device-access

---

**Aviso de Segurança**: As credenciais Tuya (email/senha) fornecidas foram armazenadas temporariamente para extração de `local_keys`. Recomendo alterar a senha após concluir o setup e remover os scripts temporários.

## Quando Estiver Pronto

Depois de completar os 6 passos acima, me avise e eu farei o teste final end-to-end para validar que tudo está funcionando!
