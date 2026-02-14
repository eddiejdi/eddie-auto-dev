# Home Automation Agent — Google Assistant Integration

> Agente especializado em automação residencial via Google Home / Assistant APIs.

## Visão Geral

O **GoogleAssistantAgent** controla dispositivos smart home integrados ao ecossistema Google Home.
Suporta comandos por linguagem natural (PT-BR), cenas, rotinas agendadas e sincronização com a
API Smart Device Management (SDM) do Google.

## Arquitetura

```
Usuário (Telegram / API / CLI)
       │
       ▼
GoogleAssistantAgent
       │
       ├── DeviceManager (persistência JSON, CRUD, cenas, rotinas)
       ├── LLM local (Ollama) — interpretação de comandos naturais
       ├── Google SDM API — sync e controle remoto de dispositivos
       └── Communication Bus — eventos publicados para outros agents
```

## Dispositivos Suportados

| Tipo | Enum | Exemplos |
|------|------|----------|
| Luz | `light` | Lâmpadas inteligentes, fitas LED |
| Tomada | `plug` | Tomadas smart (TP-Link, Tuya) |
| Interruptor | `switch` | Interruptores Wi-Fi |
| Termostato | `thermostat` | Nest Thermostat |
| Ar-condicionado | `air_conditioner` | AC smart via IR |
| Fechadura | `lock` | Smart locks (August, Yale) |
| Câmera | `camera` | Nest Cam, câmeras IP |
| Campainha | `doorbell` | Nest Doorbell |
| Speaker | `speaker` | Google Nest speakers |
| TV | `tv` | Chromecast, smart TVs |
| Ventilador | `fan` | Ventiladores smart |
| Cortina | `curtain` | Persianas motorizadas |
| Aspirador | `vacuum` | Robôs aspiradores |
| Portão | `garage_door` | Portões automáticos |
| Sensor | `sensor` | Sensores de temperatura, umidade, movimento |

## Configuração

### Variáveis de Ambiente

| Variável | Descrição | Obrigatória |
|----------|-----------|-------------|
| `GOOGLE_HOME_TOKEN` | Token OAuth2 da API Smart Device Management | Para sync com Google |
| `GOOGLE_SDM_PROJECT_ID` | Project ID no Google Cloud (SDM) | Para sync com Google |
| `OLLAMA_HOST` | URL do Ollama para interpretação de comandos | Não (default: `http://192.168.15.2:11434`) |

### Obter Token Google SDM

1. Crie um projeto no [Google Cloud Console](https://console.cloud.google.com/)
2. Habilite a **Smart Device Management API**
3. Configure OAuth 2.0 credentials
4. Vincule sua conta Google Home no [Device Access Console](https://console.nest.google.com/device-access)
5. Obtenha o token e configure `GOOGLE_HOME_TOKEN`

> O agente funciona **sem** o Google token — nesse caso, os dispositivos são gerenciados localmente via API REST.

## Endpoints da API

Base: `http://localhost:8503/home`

### Status e Health

```bash
# Status geral
GET /home/status

# Healthcheck
GET /home/health
```

### Comando por Linguagem Natural

```bash
# Comando em PT-BR
POST /home/command
{
  "command": "Apagar as luzes da sala"
}

# Outros exemplos
POST /home/command
{"command": "Ligar ar condicionado do quarto a 22 graus"}

POST /home/command
{"command": "Aumentar brilho da luz do escritório para 80%"}

POST /home/command
{"command": "Trancar a porta da frente"}
```

### Dispositivos

```bash
# Listar todos
GET /home/devices

# Filtrar por cômodo
GET /home/devices?room=Sala

# Filtrar por tipo
GET /home/devices?device_type=light

# Detalhes de um dispositivo
GET /home/devices/{device_id}

# Registrar novo dispositivo
POST /home/devices
{
  "id": "luz_sala",
  "name": "Luz da Sala",
  "device_type": "light",
  "room": "Sala"
}

# Remover dispositivo
DELETE /home/devices/{device_id}

# Ação direta em dispositivo
POST /home/devices/{device_id}/action
{
  "device_id": "luz_sala",
  "action": "set_brightness",
  "params": {"brightness": 75}
}
```

### Cômodos

```bash
# Listar cômodos
GET /home/rooms

# Status de um cômodo
GET /home/rooms/Sala
```

### Cenas

```bash
# Listar cenas
GET /home/scenes

# Criar cena
POST /home/scenes
{
  "name": "Boa Noite",
  "actions": [
    {"device_id": "luz_sala", "command": "set_state", "params": {"state": "off"}},
    {"device_id": "luz_quarto", "command": "set_state", "params": {"state": "off"}},
    {"device_id": "ac_quarto", "command": "set_state", "params": {"state": "on"}}
  ]
}

# Ativar cena
POST /home/scenes/{scene_id}/activate
```

### Rotinas

```bash
# Listar rotinas
GET /home/routines

# Criar rotina (ex.: acordar às 7h)
POST /home/routines
{
  "name": "Acordar",
  "trigger": "0 7 * * *",
  "actions": [
    {"device_id": "luz_quarto", "command": "set_state", "params": {"state": "on", "brightness": 30}},
    {"device_id": "speaker_quarto", "command": "set_state", "params": {"state": "on"}}
  ]
}

# Habilitar/desabilitar rotina
PUT /home/routines/{routine_id}/toggle?enabled=false
```

### Sincronização e Histórico

```bash
# Sincronizar com Google Home
POST /home/sync

# Histórico de comandos
GET /home/history?limit=50
```

## Uso Programático

```python
from specialized_agents.home_automation import get_google_assistant_agent

agent = get_google_assistant_agent()

# Status
status = agent.get_status()

# Comando natural
result = await agent.process_command("Ligar luzes da sala")

# Registrar dispositivo
from specialized_agents.home_automation.device_manager import Device, DeviceType
dev = Device(id="luz_sala", name="Luz da Sala", device_type=DeviceType.LIGHT, room="Sala")
agent.device_manager.register_device(dev)

# Criar cena
scene = await agent.create_scene("Cinema", [
    {"device_id": "luz_sala", "command": "set_state", "params": {"state": "off"}},
    {"device_id": "tv_sala", "command": "set_state", "params": {"state": "on"}},
])

# Ativar cena
await agent.activate_scene(scene.id)

# Criar rotina
routine = await agent.create_routine(
    name="Saindo de casa",
    trigger="manual",
    actions=[
        {"device_id": "luz_sala", "command": "set_state", "params": {"state": "off"}},
        {"device_id": "porta", "command": "set_state", "params": {"state": "on"}},
    ]
)
```

## Testes

```bash
cd eddie-auto-dev
.venv/bin/python3 -m pytest tests/test_home_automation.py -v
```

## Integração com Communication Bus

O agente publica eventos no bus para que outros agentes possam reagir:

- `sync_complete` — dispositivos sincronizados
- `command_executed` — comando processado
- `scene_created` / `scene_activated` — cenas
- `routine_created` — rotinas
- `sync_error` — erro na sincronização

## Estrutura de Arquivos

```
specialized_agents/home_automation/
├── __init__.py          # Exports públicos
├── agent.py             # GoogleAssistantAgent (lógica principal)
├── device_manager.py    # DeviceManager (CRUD, persistência, cenas, rotinas)
└── routes.py            # Endpoints FastAPI (/home/*)

tests/
└── test_home_automation.py  # 20 testes unitários
```

## Segurança

- Ações destrutivas (destrancar portas, desativar alarmes) requerem confirmação conforme `AGENT_RULES.home_specific.confirm_destructive_actions`
- Eventos de segurança (câmeras, fechaduras) são logados separadamente
- Token Google armazenado via variável de ambiente (nunca commitado)
- Recomenda-se armazenar `GOOGLE_HOME_TOKEN` no vault (`tools/simple_vault/`)
