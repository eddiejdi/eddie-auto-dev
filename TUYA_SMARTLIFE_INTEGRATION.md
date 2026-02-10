# Guia Completo de Integração Tuya/SmartLife com Python

## Resumo Técnico para Automação Residencial

---

## 1. Bibliotecas Python Disponíveis

### 1.1 TinyTuya (⭐ RECOMENDADA)
**Repositório:** https://github.com/jasonacox/tinytuya
**PyPI:** https://pypi.org/project/tinytuya/
**Versão atual:** 1.17.4
**Downloads:** ~1.5k stars, 54 contribuidores

```bash
pip install tinytuya
**Características:**
- ✅ Controle **LOCAL** (LAN) e **Cloud** (API Tuya)
- ✅ Suporta Protocolos 3.1, 3.2, 3.3, 3.4 e 3.5
- ✅ Wizard integrado para obter Local Keys
- ✅ Scanner de rede para descobrir dispositivos
- ✅ Classes especializadas (OutletDevice, BulbDevice, CoverDevice)
- ✅ Módulos contribuídos pela comunidade (Thermostat, IR Controller, etc.)
- ✅ Documentação excelente
- ✅ Ativamente mantida

**Uso básico:**
import tinytuya

# Controle Local (LAN) - Sem dependência de cloud
d = tinytuya.Device('DEVICE_ID', 'IP_ADDRESS', 'LOCAL_KEY', version=3.3)
status = d.status()
d.turn_on()
d.turn_off()

# Controle via Cloud
c = tinytuya.Cloud(apiRegion="us", apiKey="xxx", apiSecret="xxx", apiDeviceID="xxx")
devices = c.getdevices()
c.sendcommand(device_id, commands)
### 1.2 tuya-iot-python-sdk (SDK Oficial da Tuya)
**Repositório:** https://github.com/tuya/tuya-iot-python-sdk
**PyPI:** `pip install tuya-iot-py-sdk`
**Versão:** 0.6.6 (última atualização: 2021)

```bash
pip install tuya-iot-py-sdk
**Características:**
- ✅ SDK oficial da Tuya
- ✅ Suporte a MQTT (Message Queue) para eventos em tempo real
- ✅ Gerenciamento de dispositivos, assets e homes
- ⚠️ Apenas API Cloud (sem controle local)
- ⚠️ Última atualização em 2021 (menos ativo)

**Uso básico:**
from tuya_iot import TuyaOpenAPI, TuyaOpenMQ, TuyaDeviceManager

# Conectar à API
openapi = TuyaOpenAPI("https://openapi.tuyaus.com", ACCESS_ID, ACCESS_SECRET)
openapi.connect()

# Configurar MQTT para eventos em tempo real
openmq = TuyaOpenMQ(openapi)
openmq.start()
openmq.add_message_listener(on_message)

# Gerenciar dispositivos
device_manager = TuyaDeviceManager(openapi, openmq)
### 1.3 Outras bibliotecas

| Biblioteca | Descrição | Status |
|------------|-----------|--------|
| `tuyaface` | Python Async Tuya API | Alternativa async |
| `localtuya` | Plugin Home Assistant | Para HA apenas |
| `tuyapi` (Node.js) | Biblioteca Node.js | Alternativa Node |

---

## 2. Criação de Conta de Desenvolvedor na Tuya IoT Platform

### Passo a Passo Completo

#### 2.1 Criar Conta
1. Acesse [iot.tuya.com](https://iot.tuya.com)
2. Clique em "Sign Up" e crie uma conta
3. Quando perguntar "Account Type", selecione **"Skip this step..."**

#### 2.2 Criar Cloud Project
1. Vá em **Cloud** → **Development** → **Create Cloud Project**
2. Configure:
   - **Project Name:** Nome do seu projeto
   - **Development Method:** "Smart Home" (para uso pessoal)
   - **Data Center Region:** Escolha a região correta (veja tabela abaixo)

**Regiões disponíveis:**
| Código | Região | Endpoint |
|--------|--------|----------|
| `cn` | China | openapi.tuyacn.com |
| `us` | Western America | openapi.tuyaus.com |
| `us-e` | Eastern America | openapi-ueaz.tuyaus.com |
| `eu` | Central Europe | openapi.tuyaeu.com |
| `eu-w` | Western Europe | openapi-weaz.tuyaeu.com |
| `in` | India | openapi.tuyain.com |

> ⚠️ **IMPORTANTE:** A região deve corresponder ao Data Center onde seus dispositivos foram registrados no app Smart Life. Pode não ser a mais lógica geograficamente!

#### 2.3 Autorizar APIs
No projeto criado:
1. Vá em **Service API** → **Go to Authorize**
2. Assine (Subscribe) as APIs necessárias:
   - **IoT Core** (obrigatória)
   - **Authorization** (obrigatória)
   - **Smart Home Scene Linkage** (para automações)
   - **Data Dashboard Service** (para estatísticas)

#### 2.4 Vincular App Smart Life
1. No projeto, vá em **Devices** → **Link Tuya App Account**
2. Clique em **Add App Account**
3. Selecione "Automatic" e "Read Only Status"
4. Escaneie o QR Code com o app **Smart Life** ou **Tuya Smart**
   - No app: **Me** → ícone QR code no canto superior direito

#### 2.5 Obter Credenciais
No projeto, em **Overview**, você encontra:
- **Access ID / Client ID** → `apiKey`
- **Access Secret / Client Secret** → `apiSecret`

---

## 3. API Cloud vs API Local

### Comparação Detalhada

| Aspecto | API Local (LAN) | API Cloud |
|---------|-----------------|-----------|
| **Latência** | ~10-50ms | ~200-500ms |
| **Dependência Internet** | Não | Sim |
| **Rate Limits** | Nenhum | Sim (ver limitações) |
| **Disponibilidade** | 24/7 (local) | Depende dos servidores Tuya |
| **Requisitos** | Local Key | API Key + Secret |
| **Eventos Real-time** | Polling/Heartbeat | MQTT |
| **Segurança** | Criptografia AES | HTTPS + HMAC-SHA256 |

### 3.1 Quando usar API Local
✅ Automações que precisam de baixa latência
✅ Quando internet não é confiável
✅ Alto volume de comandos
✅ Privacidade (dados não saem da rede local)

### 3.2 Quando usar API Cloud
✅ Acesso remoto (fora de casa)
✅ Eventos em tempo real via MQTT
✅ Integração com cenas da Tuya
✅ Gerenciamento de múltiplas casas

### 3.3 Abordagem Híbrida (RECOMENDADA)
import tinytuya

class HybridTuyaController:
    def __init__(self, device_id, ip, local_key, cloud_config):
        # Dispositivo local para comandos rápidos
        self.local = tinytuya.Device(device_id, ip, local_key, version=3.3)
        
        # Cloud para eventos e backup
        self.cloud = tinytuya.Cloud(**cloud_config)
    
    def send_command(self, command, use_local=True):
        try:
            if use_local:
                return self.local.set_status(command)
        except:
            # Fallback para cloud se local falhar
            return self.cloud.sendcommand(self.device_id, command)
---

## 4. Obtenção de Credenciais

### 4.1 Credenciais Cloud
- **client_id (Access ID):** Obtido no projeto em iot.tuya.com
- **client_secret (Access Secret):** Obtido no projeto em iot.tuya.com
- **Região:** Definida na criação do projeto

### 4.2 Credenciais Locais (Device)
Usando TinyTuya Wizard:

```bash
# Executar wizard interativo
python -m tinytuya wizard
O wizard irá:
1. Solicitar API Key e Secret
2. Conectar ao Tuya Cloud
3. Baixar lista de todos os dispositivos
4. Gerar `devices.json` com:
   - `device_id` - ID único do dispositivo
   - `local_key` - Chave de criptografia local
   - `ip` - Endereço IP (se detectado)
   - `version` - Versão do protocolo

**Arquivo gerado (devices.json):**
```json
[
  {
    "name": "Smart Plug",
    "id": "bf1234567890abcdef",
    "key": "1234567890abcdef",
    "ip": "192.168.1.100",
    "version": "3.3"
  }
]
### 4.3 Scanner de Rede
```bash
# Descobrir dispositivos na rede
python -m tinytuya scan
Portas necessárias (firewall):
- UDP 6666, 6667, 7000
- TCP 6668

---

## 5. Limitações da API Gratuita (Trial)

### 5.1 IoT Core Service
- **Duração inicial:** 1 mês grátis
- **Renovação:** 1, 3 ou 6 meses (precisa preencher formulário)
- **Chamadas API:** Limitadas (não especificado oficialmente)
- **Dispositivos:** Limite de dispositivos vinculados

### 5.2 Rate Limits Conhecidos
| Tipo | Limite |
|------|--------|
| Chamadas API/minuto | ~20-30 (estimado) |
| Tokens refresh | 7200s (2 horas) |
| MQTT connections | Limitado por projeto |

### 5.3 Boas Práticas para Evitar Rate Limits
import time
from functools import wraps

def rate_limit(max_per_minute=20):
    """Decorator para limitar chamadas"""
    min_interval = 60.0 / max_per_minute
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            wait = min_interval - elapsed
            if wait > 0:
                time.sleep(wait)
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result
        return wrapper
    return decorator

@rate_limit(max_per_minute=15)
def call_tuya_api():
    pass
### 5.4 Expiração do IoT Core
⚠️ **IMPORTANTE:** Quando a assinatura do IoT Core expira:
- O wizard do TinyTuya para de funcionar
- Você precisa renovar em iot.tuya.com → Cloud Services → IoT Core

---

## 6. Eventos em Tempo Real

### 6.1 MQTT com tuya-iot-python-sdk
from tuya_iot import TuyaOpenAPI, TuyaOpenMQ, TuyaDeviceManager, TuyaDeviceListener

# Configurar API
openapi = TuyaOpenAPI("https://openapi.tuyaus.com", ACCESS_ID, ACCESS_SECRET)
openapi.connect()

# Listener de eventos
class MyDeviceListener(TuyaDeviceListener):
    def update_device(self, device):
        print(f"Device updated: {device}")
    
    def add_device(self, device):
        print(f"Device added: {device}")
    
    def remove_device(self, device_id):
        print(f"Device removed: {device_id}")

# Iniciar MQTT
openmq = TuyaOpenMQ(openapi)
openmq.start()

# Gerenciador de dispositivos com listener
device_manager = TuyaDeviceManager(openapi, openmq)
device_manager.add_device_listener(MyDeviceListener())
device_manager.update_device_list_in_smart_home()
### 6.2 Monitoramento Local com TinyTuya
import tinytuya

# Conexão persistente
d = tinytuya.OutletDevice('DEVICE_ID', 'IP', 'KEY', version=3.3, persist=True)

# Loop de monitoramento
d.status(nowait=True)  # Solicita status

while True:
    data = d.receive()  # Aguarda dados
    if data:
        print(f"Estado alterado: {data}")
    else:
        d.heartbeat()  # Mantém conexão viva
### 6.3 Webhooks (Message Service)
A Tuya oferece **Message Service** para webhooks:

1. Ative em iot.tuya.com → **Message Service**
2. Configure URL de callback
3. Tipos de eventos:
   - Device status change
   - Device online/offline
   - Device binding/unbinding

**Formato do webhook:**
```json
{
  "devId": "device_id",
  "productKey": "product_key",
  "dataId": "data_id",
  "status": [
    {"code": "switch_1", "value": true}
  ],
  "t": 1609459200000
}
---

## 7. Arquitetura Recomendada para Integração Robusta

### 7.1 Diagrama de Arquitetura
┌─────────────────────────────────────────────────────────────┐
│                    Bot Telegram/WhatsApp                     │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Controlador Central                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ API REST    │  │ Cache Redis │  │ Queue (Celery/RQ)   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────┬───────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ TinyTuya      │    │ Tuya Cloud    │    │ Message       │
│ (Local LAN)   │    │ API           │    │ Service MQTT  │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                    ┌───────────────┐
                    │ Dispositivos  │
                    │ Smart Life    │
                    └───────────────┘
### 7.2 Código Base Recomendado
import tinytuya
import json
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TuyaDevice:
    id: str
    name: str
    ip: Optional[str]
    key: str
    version: float
    category: str

class TuyaSmartHomeController:
    """Controlador robusto para dispositivos Tuya/SmartLife"""
    
    def __init__(self, config_path: str = "tuya_config.json"):
        self.config = self._load_config(config_path)
        self.devices: Dict[str, TuyaDevice] = {}
        self.local_connections: Dict[str, tinytuya.Device] = {}
        self.cloud: Optional[tinytuya.Cloud] = None
        
        self._init_cloud()
        self._load_devices()
    
    def _load_config(self, path: str) -> dict:
        with open(path) as f:
            return json.load(f)
    
    def _init_cloud(self):
        """Inicializa conexão com Tuya Cloud"""
        self.cloud = tinytuya.Cloud(
            apiRegion=self.config["region"],
            apiKey=self.config["api_key"],
            apiSecret=self.config["api_secret"],
            apiDeviceID=self.config.get("device_id", "")
        )
    
    def _load_devices(self):
        """Carrega dispositivos do arquivo devices.json"""
        devices_file = Path("devices.json")
        if devices_file.exists():
            with open(devices_file) as f:
                for d in json.load(f):
                    self.devices[d["id"]] = TuyaDevice(
                        id=d["id"],
                        name=d.get("name", "Unknown"),
                        ip=d.get("ip"),
                        key=d.get("key", ""),
                        version=float(d.get("version", 3.3)),
                        category=d.get("category", "switch")
                    )
    
    def get_local_device(self, device_id: str) -> Optional[tinytuya.Device]:
        """Obtém conexão local com dispositivo"""
        if device_id not in self.local_connections:
            device = self.devices.get(device_id)
            if device and device.ip and device.key:
                self.local_connections[device_id] = tinytuya.Device(
                    dev_id=device.id,
                    address=device.ip,
                    local_key=device.key,
                    version=device.version
                )
        return self.local_connections.get(device_id)
    
    def turn_on(self, device_id: str, switch: int = 1) -> dict:
        """Liga um dispositivo"""
        return self._execute_command(device_id, "on", switch)
    
    def turn_off(self, device_id: str, switch: int = 1) -> dict:
        """Desliga um dispositivo"""
        return self._execute_command(device_id, "off", switch)
    
    def get_status(self, device_id: str) -> dict:
        """Obtém status do dispositivo"""
        device = self.get_local_device(device_id)
        if device:
            try:
                return device.status()
            except Exception as e:
                logger.warning(f"Local status failed: {e}, trying cloud...")
        
        # Fallback para cloud
        return self.cloud.getstatus(device_id)
    
    def _execute_command(self, device_id: str, command: str, switch: int = 1) -> dict:
        """Executa comando com fallback local -> cloud"""
        device = self.get_local_device(device_id)
        
        if device:
            try:
                if command == "on":
                    return device.turn_on(switch=switch)
                elif command == "off":
                    return device.turn_off(switch=switch)
            except Exception as e:
                logger.warning(f"Local command failed: {e}, trying cloud...")
        
        # Fallback para cloud
        commands = {
            "commands": [
                {"code": f"switch_{switch}", "value": command == "on"}
            ]
        }
        return self.cloud.sendcommand(device_id, commands)
    
    def set_brightness(self, device_id: str, brightness: int) -> dict:
        """Define brilho de lâmpada (0-1000)"""
        device = self.get_local_device(device_id)
        if device and isinstance(device, tinytuya.BulbDevice):
            return device.set_brightness(brightness)
        
        commands = {"commands": [{"code": "bright_value", "value": brightness}]}
        return self.cloud.sendcommand(device_id, commands)
    
    def list_devices(self) -> List[dict]:
        """Lista todos os dispositivos"""
        return [
            {
                "id": d.id,
                "name": d.name,
                "category": d.category,
                "online": self._check_online(d.id)
            }
            for d in self.devices.values()
        ]
    
    def _check_online(self, device_id: str) -> bool:
        """Verifica se dispositivo está online"""
        try:
            status = self.get_status(device_id)
            return "Error" not in status
        except:
            return False


# Exemplo de uso
if __name__ == "__main__":
    controller = TuyaSmartHomeController("tuya_config.json")
    
    # Listar dispositivos
    print("Dispositivos disponíveis:")
    for device in controller.list_devices():
        print(f"  - {device['name']} ({device['id']}): {'Online' if device['online'] else 'Offline'}")
    
    # Controlar dispositivo
    # controller.turn_on("device_id_here")
### 7.3 Arquivo de Configuração (tuya_config.json)
```json
{
    "api_key": "YOUR_ACCESS_ID",
    "api_secret": "YOUR_ACCESS_SECRET",
    "region": "us",
    "device_id": "any_device_id_for_auth"
}
---

## 8. Integração com Bots de Mensagem

### 8.1 Exemplo com Telegram Bot
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

controller = TuyaSmartHomeController("tuya_config.json")

async def devices_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista dispositivos disponíveis"""
    devices = controller.list_devices()
    message = "🏠 *Dispositivos Smart Home:*\n\n"
    for d in devices:
        status = "🟢" if d["online"] else "🔴"
        message += f"{status} {d['name']}\n"
    await update.message.reply_text(message, parse_mode="Markdown")

async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Liga dispositivo: /on <device_name>"""
    if context.args:
        device_name = " ".join(context.args)
        # Encontrar device por nome
        device_id = find_device_by_name(device_name)
        if device_id:
            result = controller.turn_on(device_id)
            await update.message.reply_text(f"✅ {device_name} ligado!")
        else:
            await update.message.reply_text(f"❌ Dispositivo não encontrado")
    else:
        await update.message.reply_text("Uso: /on <nome_dispositivo>")

async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Desliga dispositivo: /off <device_name>"""
    if context.args:
        device_name = " ".join(context.args)
        device_id = find_device_by_name(device_name)
        if device_id:
            result = controller.turn_off(device_id)
            await update.message.reply_text(f"✅ {device_name} desligado!")
        else:
            await update.message.reply_text(f"❌ Dispositivo não encontrado")

def find_device_by_name(name: str) -> Optional[str]:
    """Encontra device ID pelo nome"""
    for device in controller.devices.values():
        if name.lower() in device.name.lower():
            return device.id
    return None

# Configurar bot
app = Application.builder().token("YOUR_BOT_TOKEN").build()
app.add_handler(CommandHandler("devices", devices_command))
app.add_handler(CommandHandler("on", on_command))
app.add_handler(CommandHandler("off", off_command))
app.run_polling()
---

## 9. Troubleshooting

### Problemas Comuns

| Problema | Causa | Solução |
|----------|-------|---------|
| "Unable to connect" | IP errado ou dispositivo offline | Rodar `python -m tinytuya scan` |
| "Decrypt error" | Local Key alterada | Re-executar wizard |
| "Rate limit exceeded" | Muitas chamadas cloud | Usar controle local |
| "Token expired" | IoT Core expirado | Renovar em iot.tuya.com |
| Sem dispositivos no QR scan | Data Center errado | Mudar região do projeto |
| App SmartLife não escaneia QR | Bloqueador de temas | Desativar Dark Reader |

### Debug Mode
import tinytuya
tinytuya.set_debug(True, color=True)  # Ativa logs detalhados
---

## 10. Referências e Recursos

### Documentação Oficial
- [Tuya IoT Platform](https://iot.tuya.com)
- [Tuya Developer Docs](https://developer.tuya.com/en/docs/cloud/)
- [TinyTuya GitHub](https://github.com/jasonacox/tinytuya)

### Projetos Relacionados
- [tuya-local](https://github.com/make-all/tuya-local) - Home Assistant
- [tinytuya2mqtt](https://github.com/mafrosis/tinytuya2mqtt) - Bridge MQTT
- [LocalTuya](https://github.com/rospogrigio/localtuya) - HA Integration

---

**Última atualização:** Janeiro 2026
**Autor:** Documentação gerada para integração Smart Home
