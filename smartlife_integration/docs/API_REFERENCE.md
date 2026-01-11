# 🌐 SmartLife API Reference

Documentação completa da API REST do SmartLife Integration.

**Base URL**: `http://localhost:8100/api`

## 📱 Devices

### Listar Dispositivos

```http
GET /api/devices
GET /api/devices?room=sala
GET /api/devices?type=light
GET /api/devices?online=true
```

**Resposta:**
```json
[
    {
        "id": "bf1234567890abcd",
        "name": "Lâmpada Sala",
        "type": "light",
        "room": "Sala",
        "is_online": true,
        "state": {
            "switch": true,
            "brightness": 80,
            "color_temp": 4000
        }
    }
]
```

### Obter Dispositivo

```http
GET /api/devices/{device_id}
```

### Controlar Dispositivo

```http
POST /api/devices/{device_id}/control
Content-Type: application/json

{
    "command": "dim",
    "value": 50
}
```

**Comandos disponíveis:**
| Comando | Valor | Descrição |
|---------|-------|-----------|
| `on` | - | Liga o dispositivo |
| `off` | - | Desliga o dispositivo |
| `toggle` | - | Alterna o estado |
| `dim` | 0-100 | Define brilho |
| `color` | hex/#RRGGBB | Define cor RGB |
| `temp` | int | Define temperatura (AC) |

### Atalhos de Controle

```http
POST /api/devices/{device_id}/on
POST /api/devices/{device_id}/off
POST /api/devices/{device_id}/toggle
POST /api/devices/{device_id}/brightness/{level}
POST /api/devices/{device_id}/color?color=#FF0000
```

### Controlar por Cômodo

```http
POST /api/devices/room/{room}/on
POST /api/devices/room/{room}/off
```

---

## 🎬 Scenes

### Listar Cenas

```http
GET /api/scenes
```

### Criar Cena

```http
POST /api/scenes
Content-Type: application/json

{
    "name": "Cinema",
    "description": "Modo para assistir filmes",
    "icon": "🎬",
    "actions": [
        {"device_id": "luz_sala", "command": "dim", "value": 10},
        {"device_id": "led_tv", "command": "on"},
        {"device_id": "led_tv", "command": "color", "value": "#0000FF"}
    ]
}
```

### Executar Cena

```http
POST /api/scenes/{scene_id}/execute
POST /api/scenes/execute/name/{scene_name}
```

### Templates de Cenas

```http
GET /api/scenes/templates/presets
```

---

## ⚙️ Automations

### Listar Automações

```http
GET /api/automations
```

### Criar Automação

```http
POST /api/automations
Content-Type: application/json

{
    "name": "Boa Noite",
    "description": "Desliga luzes às 23h",
    "trigger": {
        "type": "cron",
        "cron": "0 23 * * *"
    },
    "conditions": [
        {"type": "weekday", "days": [0, 1, 2, 3, 4, 5, 6]}
    ],
    "actions": [
        {"device_id": "all_lights", "command": "off"}
    ]
}
```

**Tipos de Trigger:**
| Tipo | Parâmetros | Descrição |
|------|------------|-----------|
| `time` | `time: "HH:MM"` | Horário específico |
| `cron` | `cron: "* * * * *"` | Expressão cron |
| `sunrise` | `offset: int` | Nascer do sol |
| `sunset` | `offset: int` | Pôr do sol |
| `device_state` | `device_id, state` | Estado de dispositivo |
| `sensor` | `device_id, comparison, value` | Valor de sensor |

### Ativar/Desativar

```http
POST /api/automations/{id}/enable
POST /api/automations/{id}/disable
```

### Executar Manualmente

```http
POST /api/automations/{id}/execute
```

---

## 👥 Users

### Listar Usuários

```http
GET /api/users
```

### Criar Usuário

```http
POST /api/users
Content-Type: application/json

{
    "name": "João",
    "role": "user",
    "telegram_id": 123456789
}
```

**Roles disponíveis:**
- `admin`: Acesso total
- `user`: Controla dispositivos permitidos
- `guest`: Apenas visualização

### Definir Permissões

```http
POST /api/users/{user_id}/permissions
Content-Type: application/json

{
    "device_id": "luz_sala",
    "can_view": true,
    "can_control": true,
    "can_configure": false
}
```

### Buscar por Telegram/WhatsApp

```http
GET /api/users/telegram/{telegram_id}
GET /api/users/whatsapp/{whatsapp_id}
```

---

## 🏥 Health & Status

### Health Check

```http
GET /health
```

**Resposta:**
```json
{
    "status": "healthy",
    "service": true,
    "devices_loaded": true,
    "automations_enabled": true
}
```

### Status Completo

```http
GET /api/status
```

**Resposta:**
```json
{
    "status": "running",
    "devices": {
        "total": 15,
        "online": 12,
        "offline": 3
    },
    "automations": {
        "total": 5,
        "active": 3
    },
    "connections": {
        "local": true,
        "cloud": true,
        "mqtt": true
    }
}
```

---

## 🔐 Autenticação (Futuro)

A API suportará autenticação via JWT:

```http
Authorization: Bearer {token}
```

---

## 📝 Exemplos com cURL

```bash
# Listar dispositivos
curl http://localhost:8100/api/devices

# Ligar dispositivo
curl -X POST http://localhost:8100/api/devices/luz_sala/on

# Executar cena
curl -X POST http://localhost:8100/api/scenes/execute/name/cinema

# Criar automação
curl -X POST http://localhost:8100/api/automations \
  -H "Content-Type: application/json" \
  -d '{"name":"Teste","trigger":{"type":"cron","cron":"0 8 * * *"},"actions":[{"device_id":"luz","command":"on"}]}'
```

---

## 📚 Swagger UI

Documentação interativa disponível em:
- **Swagger UI**: `http://localhost:8100/docs`
- **ReDoc**: `http://localhost:8100/redoc`
