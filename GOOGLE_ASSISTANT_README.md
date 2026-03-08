# Google Assistant + Gemini Integration Guide

**Data:** 2026-02-09  
**Status:** ✅ Webhook implementado e testável  
**Changelog:** [mudança de abordagem] Pivoting de Cloud API para Local LAN control

---

## 📋 Visão Geral

Sistema de home automation que integra **Google Assistant** (voz) com **Gemini** (IA) para controlar dispositivos **Tuya** na rede local.

**Fluxo:**
```
Você: "OK Google, ligar ventilador"
  ↓
Google Assistant → Gemini webhook
  ↓
Shared Home Automation Agent
  ↓
tinytuya (controle local LAN)
  ↓
Ventilador liga! 💨
```

---

## 🚀 Setup Rápido

### 1. Descobrir Devices na Rede

```bash
cd /home/edenilson/shared-auto-dev

# criar device_map.json com IPs conhecidos
python3 specialized_agents/home_automation/simple_setup.py

# Resultado:
# ✅ 5 devices criados em agent_data/home_automation/device_map.json
```

### 2. Obter Local Keys

As local_keys são necessárias para controle local (sem Cloud API).

**Opção A: Via tinytuya.wizard() (recomendado)**
```bash
python3 specialized_agents/home_automation/extract_local_keys.py
# Escolher opção 1 (wizard)
# Fornecer credenciais Tuya Smart Life
# Wizard extrai automaticamente
```

**Opção B: Manual (se souber)**
```python
import json
m = json.load(open('agent_data/home_automation/device_map.json'))
m['ventilador_escritorio']['local_key'] = 'sua_chave_16_hex_aqui'
json.dump(m, open('agent_data/home_automation/device_map.json', 'w'), indent=2)
```

**Opção C: Via Smart Life App (complexo)**
- Fazer root/jailbreak do Android
- Extrair `/data/data/com.tuya.smartlife/databases/`
- Procurar `localKey` em banco de dados SQLite

### 3. Testar Localmente

```bash
# Teste via webhook HTTP
curl -X POST http://localhost:8503/home/assistant/command \
  -H "Content-Type: application/json" \
  -d '{"text": "ligar ventilador"}'

# Espera resposta:
# {
#   "success": true,
#   "message": "ventilador ligado!",
#   "action": "ligar",
#   "device": "ventilador"
# }
```

---

## 🔧 Configuração Google Assistant

### Opção 1: IFTTT + Webhook

**Passo a passo:**

1. Criar conta em ifttt.com
2. Criar applet:
   - **If This:** Google Home → "turn on [phrase]"
     - Digite: "ligar ventilador"
   - **Then That:** Webhooks → Make a request
     - **URL:** `http://<seu-ip>:8503/home/assistant/command`
     - **Method:** POST  
     - **Content Type:** application/json
     - **Body:**
     ```json
     {"text": "ligar ventilador"}
     ```

3. Ativar applet e testar:
   - Diga: "OK Google, trigger my ifttt applet"

### Opção 2: Google Home Routine (Local)

1. Abrir Google Home App
2. Criar nova Rotina
3. Adicionar acionador: "Voice command"
   - Diga: "... ligar ventilador"
4. Adicionar ação: "Send HTTP request"
   - URL: (requer extensão ou IP público)

**Nota:** Routines locais precisam de IP público ou túnel.

### Opção 3: Ngrok Tunnel (para teste remoto)

```bash
# Terminal 1: API
cd /home/edenilson/shared-auto-dev
source .venv/bin/activate
python3 -m uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503

# Terminal 2: Tunnel
ngrok http 8503
# URL pública: https://xxxx-xx-xxx-xxx.ngrok.io

# Usar em IFTTT:
# URL: https://xxxx-xx-xxx-xxx.ngrok.io/home/assistant/command
```

---

## 📱 Comandos Suportados

**Formato:** "[ação] [device]"

### Ações

- **ligar/liga/acender:** Ligar device
- **desligar/desligue/apagar:** Desligar device
- **aumentar/mais:** Aumentar brightness (0-100%)
- **diminuir/menos:** Diminuir brightness
- **status:** Ver status do device

### Devices

- **ventilador** (keywords: ventilador, fan, venti)
- **luz-escritorio** (keywords: luz, light, escritório, mesa)
- **tomada-cozinha** (keywords: tomada, cozinha, kitchen)
- **ar-condicionado** (keywords: ar, ac, condicionado)
- **tomada-sala** (keywords: tomada, sala, living)

### Exemplos Válidos

- "ligar ventilador" ✅
- "desligar luz do escritório" ✅
- "aumentar a luz em 80 por cento" ✅
- "diminuir o brightness da tomada da cozinha" ✅

---

## 🔌 Device Configuration

### agent_data/home_automation/device_map.json

```json
{
  "ventilador_escritorio": {
    "device_id": "ventilador_escritorio",
    "ip": "192.168.15.4",
    "local_key": "abcdef1234567890",  ← CRÍTICO: sem isso, falha
    "name": "Ventilador Escritório",
    "version": 3.4
  },
  ...
}
```

**Campos obrigatórios:**
- `device_id`: Identificador único
- `ip`: IP na rede local (192.168.15.x)
- `local_key`: Chave de 16 caracteres hex (CRÍTICO)
- `version`: 3.1, 3.3, 3.4, ou 3.5

---

## 📡 API Endpoints

Todos em `/home/assistant/` (após rotas serem incluídas no main API):

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/command` | Executar comando |
| GET | `/devices` | Listar devices |
| POST | `/devices/scan` | Rescanear rede |
| POST | `/devices/register` | Registrar device |
| GET | `/health` | Health check |

### Exemplo: POST /command

```bash
curl -X POST http://localhost:8503/home/assistant/command \
  -H "Content-Type: application/json" \
  -d '{
    "text": "ligar ventilador",
    "user_id": "user@example.com",
    "request_id": "123e4567-e89b-12d3-a456-426614174000"
  }'
```

### Resposta (sucesso)

```json
{
  "success": true,
  "message": "ventilador ligado!",
  "action": "ligar",
  "device": "ventilador",
  "status": {
    "success": true,
    "command": "ligar",
    "device_id": "ventilador_escritorio",
    "device_name": "Ventilador Escritório",
    "result": {...}
  }
}
```

---

## 🐛 Troubleshooting

### Problem: "Device não encontrado"

**Causa:** device_id não existe em device_map.json

**Solução:**
```bash
# Listar devices registrados
curl http://localhost:8503/home/assistant/devices

# Se vazio, rodar setup:
python3 specialized_agents/home_automation/simple_setup.py
```

### Problem: "Error ao conectar ao device"

**Causa:** IP ou local_key incorretos

**Solução:**
1. Verificar IP da rede: `ping 192.168.15.4`
2. Verificar local_key: `python3 -c "import tinytuya; tinytuya.wizard()"`
3. Atualizar device_map.json com informações corretas

### Problem: "Local key DESCONHECIDA"

**Causa:** tinytuya não conseguiu extrair via broadcast

**Solução:**
1. Usar `tinytuya.wizard()` com credenciais Cloud
2. Extrair manualmente do Smart Life app
3. Usar ferramenta externa (ex: tuya-cli)

---

## 🏗️ Arquitetura

```
specialized_agents/home_automation/
├── __init__.py                    ← Exports
├── agent.py                       ← GoogleAssistantAgent (agent base)
├── device_manager.py              ← Device CRUD
├── routes.py                      ← FastAPI routers
├── google_assistant.py             ← ✨ NEW: Webhook Gemini
├── tinytuya_executor.py            ← ✨ NEW: Local LAN control
├── simple_setup.py                 ← ✨ NEW: Setup initial
├── extract_local_keys.py           ← ✨ NEW: Key extraction
└── setup_google_assistant.py        ← Setup interativo (demo)
```

---

## 🔐 Segurança

### Local Keys

- **Nunca** compartilhar local_keys publicamente
- **Nunca** commitar `device_map.json` com chaves reais
- **Sempre** usar `.gitignore` para arquivos sensíveis

```bash
# .gitignore
agent_data/home_automation/device_map.json
agent_data/home_automation/.cache/
tinytuya_devices.json
```

### Webhook Security

Para produção, adicionar autenticação:

```python
# Em google_assistant.py

from fastapi import Header, HTTPException

@router.post("/command")
async def command(
    cmd: AssistantCommand,
    authorization: str = Header(None)
):
    if not authorization or authorization != "Bearer YOUR_TOKEN":
        raise HTTPException(403, "Unauthorized")
    # ... resto do código
```

---

## 📊 Testing

### Unit Tests

```bash
cd /home/edenilson/shared-auto-dev
pytest tests/test_home_automation.py -v

# Expected: 20+ tests passing
```

### Integration Test

```bash
# Terminal 1: Start API
python3 -m uvicorn specialized_agents.api:app --port 8503

# Terminal 2: Test webhook
python3 -c "
import requests
resp = requests.post(
    'http://localhost:8503/home/assistant/command',
    json={'text': 'ligar ventilador'}
)
print(resp.json())
"
```

---

## 📈 Next Steps

### Phase 1: ✅ Local Control (Current)
- [x] tinytuya executor
- [x] Webhook endpoint
- [x] Device discovery
- [ ] Local key extraction (em progresso)

### Phase 2: Google Assistant Integration
- [ ] IFTTT webhook registration
- [ ] Google Routines setup
- [ ] Voice command testing

### Phase 3: Advanced Features
- [ ] Natural language via Gemini
- [ ] Multi-command scenes
- [ ] Voice feedback (TTS)
- [ ] Home automation routines (scheduled)

---

## 📚 References

- [tinytuya GitHub](https://github.com/jasonacox/tinytuya)
- [Tuya IoT Platform](https://iot.tuya.com/)
- [IFTTT Webhooks](https://ifttt.com/maker_webhooks)
- [Google Home Routines](https://support.google.com/googlenest/answer/7029585)

---

**Última atualização:** 2026-02-09 14:30 UTC  
**Autor:** Shared Auto-Dev System  
**Status:** 🚀 Pronto para testes
