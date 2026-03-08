# 🏠 Shared SmartLife Integration

Integração completa entre o servidor homelab e dispositivos SmartLife/Tuya.

## ✨ Funcionalidades

- **Controle Total**: Lâmpadas, tomadas, sensores, AC, cortinas, etc.
- **Monitoramento Real-time**: Estados via MQTT e polling local
- **Automações**: Por horário, eventos, condições e geofencing
- **Multi-interface**: Telegram, WhatsApp, API REST, Grafana, PWA Mobile
- **Gestão de Usuários**: Permissões granulares por dispositivo/ação
- **Híbrido Local+Cloud**: Prioriza LAN, fallback para cloud

## 📋 Pré-requisitos

1. Conta na [Tuya IoT Platform](https://iot.tuya.com)
2. Dispositivos vinculados no app SmartLife
3. Python 3.11+
4. PostgreSQL 15+
5. Redis 7+

## 🚀 Instalação Rápida

```bash
# 1. Configurar ambiente
cd ~/myClaude/smartlife_integration
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Obter credenciais Tuya
python -m tinytuya wizard

# 3. Configurar
cp config/config.example.yaml config/config.yaml
nano config/config.yaml

# 4. Inicializar database
python -m src.database.init_db

# 5. Executar
python -m src.main
## 🔧 Configuração Tuya IoT

Veja: [TUYA_SETUP.md](docs/TUYA_SETUP.md)

## 📱 Comandos do Bot

### Controle
- `/devices` - Listar dispositivos
- `/on <nome>` - Ligar dispositivo
- `/off <nome>` - Desligar dispositivo
- `/toggle <nome>` - Alternar estado
- `/dim <nome> <0-100>` - Ajustar brilho
- `/status` - Status geral

### Cenas
- `/scenes` - Listar cenas
- `/scene <nome>` - Executar cena
- `/newscene` - Criar cena

### Admin
- `/users` - Gerenciar usuários
- `/automations` - Gerenciar automações
- `/logs` - Ver logs

## 🏗️ Arquitetura

┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Telegram   │  │  WhatsApp   │  │  Mobile PWA │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────────┼────────────────┘
                        ▼
              ┌─────────────────┐
              │ SmartLife Core  │
              │    Service      │
              └────────┬────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
    ┌─────────┐  ┌──────────┐  ┌──────────┐
    │ TinyTuya│  │Tuya Cloud│  │PostgreSQL│
    │ (Local) │  │(+MQTT)   │  │+ Redis   │
    └────┬────┘  └────┬─────┘  └──────────┘
         │            │
         └─────┬──────┘
               ▼
        ┌─────────────┐
        │  Devices    │
        └─────────────┘
## 🌐 API REST

API disponível em `http://localhost:8100`

### Endpoints principais:

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/devices` | GET | Listar dispositivos |
| `/api/devices/{id}/on` | POST | Ligar dispositivo |
| `/api/devices/{id}/off` | POST | Desligar dispositivo |
| `/api/scenes` | GET | Listar cenas |
| `/api/scenes/{id}/execute` | POST | Executar cena |
| `/api/automations` | GET/POST | Gerenciar automações |
| `/api/users` | GET/POST | Gerenciar usuários |

**Documentação completa**: [docs/API_REFERENCE.md](docs/API_REFERENCE.md)

**Swagger UI**: `http://localhost:8100/docs`

## 📊 Grafana Dashboard

Acesse: `http://localhost:3000/d/smartlife`

## 📖 Documentação

- [Configuração Tuya IoT](docs/TUYA_SETUP.md)
- [API Reference](docs/API_REFERENCE.md)

## 🧪 Testes

```bash
# Ativar ambiente
source venv/bin/activate

# Executar testes de integração
python test_integration.py
## 📄 Licença

MIT
