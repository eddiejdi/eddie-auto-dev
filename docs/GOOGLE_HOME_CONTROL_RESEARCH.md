# Controle Programático de Google Home / Nest — Pesquisa Completa

> Data: 2026-02-12  
> Objetivo: Controlar dispositivos Google Home/Nest via Python local

---

## TL;DR — Recomendação Prática

| Cenário | Melhor Abordagem | Precisa de Cloud? | Complexidade |
|---|---|---|---|
| **Ventilador em tomada Tuya** | `tinytuya` (controle LAN direto) | Não* | Baixa |
| **Ventilador em tomada TP-Link/Kasa** | `python-kasa` (controle LAN direto) | Não | Baixa |
| **Controlar Google Home speaker** | `pychromecast` (Cast protocol) | Não | Baixa |
| **Controle de Nest Thermostat/Camera** | Google SDM API (cloud REST) | Sim | Alta |
| **Comandos de voz programáticos** | Google Assistant SDK (gRPC) | Sim | Alta |
| **Automação genérica** | Home Assistant | Opcional | Média |

> \* TinyTuya precisa de cloud apenas uma vez para obter as `Local_Key`s. Depois disso funciona 100% local.

**A abordagem mais prática para ligar/desligar um ventilador conectado a uma smart plug é controlar a plug diretamente via LAN, sem passar pelo Google Home.**

---

## 1. Google Home Local API (LAN)

### Status: Limitada / Não-oficial

Os dispositivos Google Home/Nest **não expõem uma API REST/gRPC local oficial** para controle de dispositivos de terceiros. O que existe:

#### Portas conhecidas (descobertas via engenharia reversa):

| Porta | Protocolo | Uso |
|---|---|---|
| **8008** | HTTP | API local limitada (info do dispositivo, reboot) |
| **8009** | TLS/Protobuf | **Cast V2 Protocol** — usado pelo `pychromecast` |
| **8443** | HTTPS | Setup/eureka_info endpoint |
| **5353** | mDNS/Zeroconf | Descoberta de dispositivos Cast na rede |

#### O que funciona localmente (porta 8008/8443):
```bash
# Obter info do dispositivo (funciona sem autenticação)
curl http://<IP_GOOGLE_HOME>:8008/setup/eureka_info

# Reiniciar o dispositivo
curl -X POST http://<IP_GOOGLE_HOME>:8008/setup/reboot -H "Content-Type: application/json" -d '{"params":"now"}'

# Ver dispositivos conectados
curl http://<IP_GOOGLE_HOME>:8008/setup/configured_networks
```

#### O que NÃO funciona localmente:
- Enviar comandos a dispositivos de terceiros (plugs, luzes, etc.)
- Executar rotinas
- Enviar comandos de voz
- Controlar dispositivos adicionados ao Google Home

#### `glocaltokens` — Tokens locais
- **Repo**: `github.com/leikoiber/glocaltokens`
- **O que faz**: Obtém tokens de autenticação local (homegraph tokens) para seus dispositivos Google Home
- **Uso**: Autenticação para endpoints locais avançados
- **Limitação**: Mesmo com tokens, os endpoints locais são muito limitados para controle de dispositivos de terceiros
- **Instalação**: `pip install glocaltokens`

```python
from glocaltokens.client import GLocalAuthenticationTokens

# Requer credenciais Google (master token)
client = GLocalAuthenticationTokens(
    username="seu@gmail.com",
    password="sua_senha"  # ou master_token
)

# Obter tokens de todos os dispositivos
homegraph = client.get_homegraph()
devices = client.get_google_devices(force_homegraph=True)

for device in devices:
    print(f"{device.device_name}: {device.local_auth_token}")
```

---

## 2. Google Smart Device Management (SDM) API — Cloud

### Status: Oficial, mas limitada a dispositivos NEST

**Dispositivos suportados**: Apenas dispositivos Google Nest nativos:
- Nest Thermostat (todos os modelos)
- Nest Camera (todas)
- Nest Doorbell (todas)
- Nest Hub Max

**NÃO suporta**: Plugs de terceiros, luzes, ventiladores, ou qualquer dispositivo adicionado via "Works with Google"

### Setup Completo:

#### Passo 1: Registro no Device Access (US$5 taxa única)
```
https://console.nest.google.com/device-access
```
- Aceitar Termos de Serviço
- Pagar taxa de US$5 (não reembolsável)
- Usar conta Google pessoal (não Workspace)

#### Passo 2: Configurar Google Cloud Platform
1. Criar projeto no Google Cloud Console
2. Ativar a API **Smart Device Management**
3. Criar credenciais OAuth 2.0 (tipo: Web Server)
4. Configurar redirect URI: `https://www.google.com`
5. Anotar `client_id` e `client_secret`

#### Passo 3: Criar projeto no Device Access Console
1. Criar novo projeto
2. Inserir OAuth 2.0 Client ID
3. Habilitar/desabilitar eventos (Pub/Sub)
4. Anotar o `project-id` (UUID)

#### Passo 4: Autorizar conta (OAuth2 flow)

```bash
# 1. Abrir no browser para obter authorization code:
# https://nestservices.google.com/partnerconnections/{project-id}/auth?
#   redirect_uri=https://www.google.com&
#   access_type=offline&prompt=consent&
#   client_id={oauth2-client-id}&
#   response_type=code&
#   scope=https://www.googleapis.com/auth/sdm.service

# 2. Trocar code por tokens:
curl -L -X POST \
  "https://www.googleapis.com/oauth2/v4/token?\
client_id={CLIENT_ID}&\
client_secret={CLIENT_SECRET}&\
code={AUTH_CODE}&\
grant_type=authorization_code&\
redirect_uri=https://www.google.com"

# 3. Listar dispositivos:
curl -X GET \
  "https://smartdevicemanagement.googleapis.com/v1/enterprises/{project-id}/devices" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {access-token}"

# 4. Enviar comando (ex: mudar modo do termostato):
curl -X POST \
  "https://smartdevicemanagement.googleapis.com/v1/enterprises/{project-id}/devices/{device-id}:executeCommand" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {access-token}" \
  --data-raw '{
    "command": "sdm.devices.commands.ThermostatMode.SetMode",
    "params": { "mode": "HEAT" }
  }'
```

#### Python SDK para SDM:
```python
import requests

class NestSDMClient:
    BASE_URL = "https://smartdevicemanagement.googleapis.com/v1"
    
    def __init__(self, project_id, access_token):
        self.project_id = project_id
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
    
    def list_devices(self):
        url = f"{self.BASE_URL}/enterprises/{self.project_id}/devices"
        return requests.get(url, headers=self.headers).json()
    
    def execute_command(self, device_id, command, params):
        url = f"{self.BASE_URL}/enterprises/{self.project_id}/devices/{device_id}:executeCommand"
        data = {"command": command, "params": params}
        return requests.post(url, headers=self.headers, json=data).json()
    
    def refresh_token(self, client_id, client_secret, refresh_token):
        url = "https://www.googleapis.com/oauth2/v4/token"
        params = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        resp = requests.post(url, params=params).json()
        self.headers["Authorization"] = f"Bearer {resp['access_token']}"
        return resp

# Uso
client = NestSDMClient("project-uuid", "access-token")
devices = client.list_devices()
```

### OAuth2 Scopes necessários:
- `https://www.googleapis.com/auth/sdm.service` — scope principal do SDM

---

## 3. Bibliotecas Python de Terceiros

### 3.1 `pychromecast` — Cast Protocol (LOCAL, porta 8009)

**O que controla**: Google Home speakers, Chromecast, Nest Hub (mídia)  
**Protocolo**: Cast V2 via TLS na porta 8009  
**Cloud necessário**: Não  
**Instalação**: `pip install pychromecast`

```python
import pychromecast
import time

# Descobrir dispositivos Cast na rede
chromecasts, browser = pychromecast.get_listed_chromecasts(
    friendly_names=["Sala de Estar"]
)

if chromecasts:
    cast = chromecasts[0]
    cast.wait()  # Aguardar conexão
    
    print(f"Device: {cast.cast_info}")
    print(f"Status: {cast.status}")
    
    # Controlar volume
    cast.set_volume(0.5)
    
    # Tocar mídia
    cast.media_controller.play_media(
        "https://example.com/audio.mp3", 
        "audio/mp3"
    )
    
    # Controles de mídia
    time.sleep(5)
    cast.media_controller.pause()
    time.sleep(2)
    cast.media_controller.play()
    
    # Parar
    cast.media_controller.stop()
    
    browser.stop_discovery()
```

**Dispositivos reconhecidos pelo pychromecast**:
- Google Home, Google Home Mini, Google Nest Mini
- Nest Audio, Nest Hub, Nest Hub Max
- Chromecast (todas as gerações)
- Chromecast Audio
- Nest WiFi Point

**Limitação**: Controla apenas funcionalidades de mídia/áudio, NÃO controla dispositivos smart home de terceiros.

### 3.2 `tinytuya` — Controle LOCAL de dispositivos Tuya (RECOMENDADO para plugs Tuya)

**O que controla**: Smart plugs, interruptores, bulbs, cortinas, etc. baseados em Tuya  
**Protocolo**: TCP/UDP Tuya Protocol (portas 6666, 6667, 6668, 7000)  
**Cloud necessário**: Apenas uma vez para obter Local Keys  
**Instalação**: `pip install tinytuya`

#### Setup Inicial (uma vez):
```bash
# 1. Instalar
pip install tinytuya

# 2. Scan da rede para encontrar dispositivos Tuya
python -m tinytuya scan

# 3. Wizard — obtém Local Keys do Tuya Cloud
#    Necessita: Tuya IoT Account (iot.tuya.com)
#    API Key, API Secret, Region, Device ID
python -m tinytuya wizard
```

#### Preparação Tuya IoT Platform:
1. Criar conta em https://iot.tuya.com
2. Cloud → Create Cloud Project (selecionar região correta)
3. Service API → Subscrever: **IoT Core** e **Authorization**
4. Devices → Link Tuya App Account → Scan QR com Smart Life app
5. Executar `python -m tinytuya wizard` com API Key e Secret

#### Controle LOCAL do dispositivo:
```python
import tinytuya

# Conectar ao dispositivo (100% local, sem cloud)
plug = tinytuya.OutletDevice(
    dev_id='DEVICE_ID_HERE',
    address='192.168.15.XX',       # IP do dispositivo ou 'Auto'
    local_key='LOCAL_KEY_HERE',
    version=3.3                     # ou 3.4, 3.5
)

# Status
data = plug.status()
print(f"Status: {data}")
print(f"Ligado: {data['dps']['1']}")

# Ligar
plug.turn_on()

# Desligar
plug.turn_off()

# Toggle
current = plug.status()['dps']['1']
plug.set_status(not current)

# Monitor contínuo
plug_persistent = tinytuya.OutletDevice(
    'DEVICE_ID', '192.168.15.XX', 'LOCAL_KEY', 
    version=3.3, persist=True
)
plug_persistent.status(nowait=True)
while True:
    data = plug_persistent.receive()
    if data:
        print(f"Status update: {data}")
    else:
        plug_persistent.heartbeat()
```

#### Via Cloud (alternativo):
```python
import tinytuya

c = tinytuya.Cloud(
    apiRegion="us",
    apiKey="xxxxxxxxxxxx",
    apiSecret="xxxxxxxxxxxxxxxx",
    apiDeviceID="xxxxxxxxxxxx"
)

# Listar dispositivos
devices = c.getdevices()

# Ligar switch
c.sendcommand("DEVICE_ID", {
    "commands": [
        {"code": "switch_1", "value": True}
    ]
})
```

### 3.3 `python-kasa` — Controle LOCAL de dispositivos TP-Link/Kasa/Tapo

**O que controla**: Smart plugs, switches, bulbs TP-Link  
**Protocolo**: TP-Link proprietário (LAN direto)  
**Cloud necessário**: Não  
**Instalação**: `pip install python-kasa`

```python
import asyncio
from kasa import Discover

async def main():
    # Descobrir dispositivos na rede
    devices = await Discover.discover()
    for addr, dev in devices.items():
        await dev.update()
        print(f"{dev.alias}: {dev.model} @ {addr} - {'ON' if dev.is_on else 'OFF'}")
    
    # Controlar dispositivo específico
    plug = await Discover.discover_single("192.168.15.XX")
    
    # Ligar
    await plug.turn_on()
    await plug.update()
    
    # Desligar
    await plug.turn_off()
    await plug.update()
    
    print(f"Estado: {'ON' if plug.is_on else 'OFF'}")

asyncio.run(main())
```

**Dispositivos suportados (exemplos)**:
- **Plugs Kasa**: EP10, HS100, HS103, HS105, HS110, KP115, KP125
- **Plugs Tapo**: P100, P105, P110, P115, P125M
- **Power Strips**: HS300, KP303, P300
- **Switches**: HS200, HS220, KS220, S500D
- **Bulbs**: KL110, KL130, L510E, L530E
- **Light Strips**: KL430, L920-5, L930-5

### 3.4 Comparação de bibliotecas

| Biblioteca | Protocolo | Local? | Dispositivos | Maturidade |
|---|---|---|---|---|
| `tinytuya` | Tuya Protocol | Sim | Tuya-based (milhares de marcas) | Alta |
| `python-kasa` | TP-Link Protocol | Sim | TP-Link/Kasa/Tapo | Alta |
| `pychromecast` | Cast V2 | Sim | Google Home/Chromecast (mídia) | Alta |
| `glocaltokens` | Google Auth | Parcial | Google Home (tokens apenas) | Média |

---

## 4. Google Home Device Access Program

### Sandbox (Individual)
- **Custo**: US$5 (taxa única, não reembolsável)
- **Uso**: Pessoal / desenvolvimento
- **Limite**: Sem uso comercial
- **Dispositivos**: Apenas Google Nest nativos
- **Tokens**: Refresh tokens expiram em 7 dias se não aprovado

### Comercial
- **Custo**: Negociado com Google
- **Requisitos**: Certificação obrigatória
- **Uso**: Integração comercial
- **Processo**: Inscrição → Certificação → Produção

### Como se inscrever:
1. Acesse https://console.nest.google.com/device-access
2. Aceite os ToS
3. Pague a taxa de US$5
4. Crie um projeto no Google Cloud
5. Crie um projeto Device Access
6. Vincule sua conta Google

---

## 5. Abordagens Alternativas

### 5.1 Google Assistant SDK
- **Status**: Disponível mas uso experimental apenas (não comercial)
- **Protocolo**: gRPC
- **Pode**: Enviar comandos de voz programáticos ("Hey Google, turn on the fan")
- **Limitação**: Setup complexo, requer Actions on Google project
- **Instalação**: `pip install google-assistant-sdk[samples]`

### 5.2 Home Assistant (recomendado como hub)
- **O que faz**: Hub de automação que integra 2000+ plataformas
- **Suporta**: Google Home, Tuya, TP-Link, Z-Wave, Zigbee, etc.
- **API REST**: http://homeassistant.local:8123/api/
- **Vantagem**: Uma vez configurado, todos os dispositivos ficam acessíveis via REST
```python
import requests

HA_URL = "http://homeassistant.local:8123"
TOKEN = "seu_long_lived_access_token"

# Ligar um switch
requests.post(
    f"{HA_URL}/api/services/switch/turn_on",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={"entity_id": "switch.ventilador"}
)
```

### 5.3 Cast Protocol para Smart Displays
- Use `pychromecast` para Nest Hub
- DashCast controller para mostrar URLs
- Sem controle de dispositivos smart home via Cast

### 5.4 Home Graph API
- Apenas para desenvolvedores de ações Smart Home
- Sincroniza estado de dispositivos com Google
- Não permite enviar comandos a dispositivos de terceiros

### 5.5 Routines API
- Não existe API pública para criar/executar Routines
- Routines são gerenciadas apenas via Google Home App

---

## 6. Caso Prático: Controlar Ventilador via Smart Plug

### Cenário A: Plug Tuya (ex: Positivo, Geonav, Elgin, etc.)

```python
#!/usr/bin/env python3
"""Controle local de ventilador via plug Tuya"""
import tinytuya
import sys

# Configuração (obtida via tinytuya wizard)
PLUG_CONFIG = {
    "dev_id": "SEU_DEVICE_ID",
    "address": "192.168.15.XX",       
    "local_key": "SEU_LOCAL_KEY",
    "version": 3.3
}

def get_plug():
    return tinytuya.OutletDevice(**PLUG_CONFIG)

def fan_on():
    plug = get_plug()
    plug.turn_on()
    print("Ventilador LIGADO")

def fan_off():
    plug = get_plug()
    plug.turn_off()
    print("Ventilador DESLIGADO")

def fan_status():
    plug = get_plug()
    data = plug.status()
    state = data.get('dps', {}).get('1', None)
    print(f"Ventilador: {'LIGADO' if state else 'DESLIGADO'}")
    return state

def fan_toggle():
    plug = get_plug()
    data = plug.status()
    current = data.get('dps', {}).get('1', False)
    plug.set_status(not current)
    print(f"Ventilador: {'DESLIGADO' if current else 'LIGADO'}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"on": fan_on, "off": fan_off, "status": fan_status, "toggle": fan_toggle}[cmd]()
```

### Cenário B: Plug TP-Link/Kasa

```python
#!/usr/bin/env python3
"""Controle local de ventilador via plug TP-Link"""
import asyncio
from kasa import Discover

PLUG_IP = "192.168.15.XX"

async def fan_on():
    plug = await Discover.discover_single(PLUG_IP)
    await plug.turn_on()
    await plug.update()
    print("Ventilador LIGADO")

async def fan_off():
    plug = await Discover.discover_single(PLUG_IP)
    await plug.turn_off()
    await plug.update()
    print("Ventilador DESLIGADO")

async def fan_status():
    plug = await Discover.discover_single(PLUG_IP)
    await plug.update()
    print(f"Ventilador: {'LIGADO' if plug.is_on else 'DESLIGADO'}")

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    funcs = {"on": fan_on, "off": fan_off, "status": fan_status}
    asyncio.run(funcs[cmd]())
```

### Setup Steps (Tuya — abordagem recomendada):

1. **Instalar o plug** na tomada e parear com Smart Life App
2. **Criar conta** no Tuya IoT Platform (iot.tuya.com)
3. **Criar Cloud Project** → selecionar região → anotar API Key/Secret
4. **Subscrever APIs**: IoT Core e Authorization
5. **Vincular Smart Life App** à conta Tuya IoT (scan QR code)
6. **Instalar TinyTuya**: `pip install tinytuya`
7. **Executar Wizard**: `python -m tinytuya wizard` para obter Device ID + Local Key
8. **Executar scan**: `python -m tinytuya scan` para obter IP do dispositivo
9. **Usar o script** acima com os dados obtidos

---

## 7. Conclusões

### O controle LOCAL (LAN) é possível sem cloud?

| Método | Cloud-free? | Detalhes |
|---|---|---|
| **TinyTuya** | Sim (após setup) | Precisa de cloud uma vez para Local Keys |
| **python-kasa** | Sim | Totalmente local, sem setup cloud |
| **pychromecast** | Sim | Totalmente local via mDNS |
| **Google SDM API** | Não | Sempre cloud, REST API |
| **Google Home "Hey Google"** | Não | Sempre cloud |
| **Home Assistant** | Sim | Roda localmente, bridge para tudo |

### Recomendação final por ordem de praticidade:

1. **Se a plug é Tuya-based**: Use `tinytuya` — setup inicial requer cloud, depois é 100% local
2. **Se a plug é TP-Link**: Use `python-kasa` — zero setup cloud, 100% local
3. **Se quer controlar TUDO de um lugar**: Monte um Home Assistant e use a API REST dele
4. **Se precisa controlar dispositivos Google Nest nativos**: SDM API (US$5 + setup complexo)
5. **Se quer enviar comandos de voz**: Google Assistant SDK (complexo, não-comercial)

### Requisitos de rede para controle local:
- Dispositivo Python e smart plug na **mesma VLAN/subnet**
- Firewall permitindo:
  - UDP 6666, 6667, 7000 (Tuya discovery)
  - TCP 6668 (Tuya control)
  - TCP 9999 (TP-Link control)
  - TCP 8009 (Cast V2)
  - UDP 5353 (mDNS)
