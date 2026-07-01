# Notebook Power Agent

Agente local para expor o notebook como dispositivo IoT, com comandos para desligar, hibernar, suspender, reiniciar e bloquear sessoes.

Ele suporta dois modos:

- `NOTEBOOK_POWER_MODE=tuya`: conecta direto no MQTT da TuyaLink, sem Home Assistant.
- `NOTEBOOK_POWER_MODE=ha-mqtt`: publica discovery MQTT para Home Assistant.

## Modo Tuya puro

A Tuya suporta dispositivo customizado via TuyaLink MQTT. O notebook precisa ser cadastrado na Tuya Developer Platform como um produto/dispositivo TuyaLink para obter:

- `ProductID`
- `DeviceID`
- `DeviceSecret`

O agente usa `DeviceID` e `DeviceSecret` para autenticar no broker MQTT da Tuya com TLS na porta `8883`.

### Modelo sugerido do produto Tuya

Crie um produto TuyaLink com estas propriedades:

| Codigo | Tipo | Uso |
|---|---|---|
| `power_command` | enum/string | Comando enviado da nuvem para o notebook: `shutdown`, `hibernate`, `suspend`, `reboot`, `lock` |
| `power_state` | string | Estado reportado pelo agente, normalmente `online` |
| `dangerous_enabled` | bool | Indica se comandos perigosos estao habilitados localmente |
| `last_action` | string | Ultima acao aceita |
| `last_error` | string | Ultimo erro |
| `hostname` | string | Hostname local |

Opcionalmente, crie acoes TuyaLink com `actionCode` igual a `shutdown`, `hibernate`, `suspend`, `reboot` e `lock`, ou uma acao generica com `inputParams.action`.

### Configuracao Tuya

Crie `/etc/default/notebook-power-agent` no notebook:

```bash
NOTEBOOK_POWER_MODE=tuya
NOTEBOOK_POWER_MQTT_HOST=m1.tuyaus.com
NOTEBOOK_POWER_MQTT_PORT=8883
TUYA_PRODUCT_ID=xxxxxxxx
TUYA_DEVICE_ID=xxxxxxxx
TUYA_DEVICE_SECRET=xxxxxxxx

NOTEBOOK_POWER_DEVICE_ID=notebook-edenilson
NOTEBOOK_POWER_DEVICE_NAME=Notebook Edenilson
NOTEBOOK_POWER_ALLOWED_ACTIONS=shutdown,hibernate,suspend,reboot,lock

# Comece em 0. Em 0, o agente conecta e reporta estado, mas bloqueia desligar/hibernar/suspender/reiniciar.
NOTEBOOK_POWER_ENABLE_DANGEROUS=0
NOTEBOOK_POWER_COMMAND_DELAY=3
```

Endpoints comuns da TuyaLink:

| Regiao | Host |
|---|---|
| Western America | `m1.tuyaus.com` |
| Eastern America | `m1-ueaz.tuyaus.com` |
| Central Europe | `m1.tuyaeu.com` |
| Western Europe | `m1-weaz.tuyaeu.com` |
| China | `m1.tuyacn.com` |
| India | `m1.tuyain.com` |
| Singapore | `m1-sg.iotbing.com` |

Valide a assinatura MQTT sem conectar:

```bash
python3 tools/notebook_power_agent.py --print-tuya-credentials
```

Teste comando sem executar:

```bash
NOTEBOOK_POWER_DRY_RUN=1 NOTEBOOK_POWER_ENABLE_DANGEROUS=1 \
  python3 tools/notebook_power_agent.py --execute hibernate
```

## Modo Home Assistant MQTT

Este modo continua disponivel se voce quiser que o notebook apareca no Home Assistant ao lado dos dispositivos Tuya ja pareados.

Para acordar a maquina depois de suspender/hibernar, o comando precisa sair de outro equipamento ligado, normalmente o Home Assistant/homelab via Wake-on-LAN. O agente local nao consegue receber comando quando o notebook esta dormindo.

## Arquivos

- `tools/notebook_power_agent.py`: agente MQTT e executor local.
- `systemd/notebook-power-agent.service`: unit systemd para rodar no notebook.

## Dependencia

```bash
python3 -m pip install paho-mqtt
```

## Configuracao

Crie `/etc/default/notebook-power-agent` no notebook:

```bash
NOTEBOOK_POWER_MODE=ha-mqtt
NOTEBOOK_POWER_MQTT_HOST=192.168.15.2
NOTEBOOK_POWER_MQTT_PORT=1883
NOTEBOOK_POWER_MQTT_USERNAME=
NOTEBOOK_POWER_MQTT_PASSWORD=
NOTEBOOK_POWER_DEVICE_ID=notebook-edenilson
NOTEBOOK_POWER_DEVICE_NAME=Notebook Edenilson
NOTEBOOK_POWER_BASE_TOPIC=eddie/notebook/notebook-edenilson
NOTEBOOK_POWER_ALLOWED_ACTIONS=shutdown,hibernate,suspend,reboot,lock

# Comece em 0. Em 0, o agente aparece no HA mas bloqueia desligar/hibernar/suspender/reiniciar.
NOTEBOOK_POWER_ENABLE_DANGEROUS=0
NOTEBOOK_POWER_COMMAND_DELAY=3
```

Valide discovery sem ligar no MQTT:

```bash
python3 tools/notebook_power_agent.py --print-discovery
```

Teste comando sem executar:

```bash
NOTEBOOK_POWER_DRY_RUN=1 NOTEBOOK_POWER_ENABLE_DANGEROUS=1 \
  python3 tools/notebook_power_agent.py --execute hibernate
```

## Instalacao systemd

No notebook, ajuste os caminhos da unit se o repo estiver em outro lugar:

```bash
sudo cp systemd/notebook-power-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now notebook-power-agent.service
sudo journalctl -u notebook-power-agent.service -f
```

Quando o dispositivo aparecer no Home Assistant e os botoes estiverem corretos, habilite os comandos perigosos:

```bash
sudo sed -i 's/^NOTEBOOK_POWER_ENABLE_DANGEROUS=.*/NOTEBOOK_POWER_ENABLE_DANGEROUS=1/' /etc/default/notebook-power-agent
sudo systemctl restart notebook-power-agent.service
```

## Wake-on-LAN

Para acordar o notebook, habilite WoL na BIOS/UEFI e na placa de rede. No Home Assistant, use a integracao `wake_on_lan` ou um `shell_command` no homelab apontando para o MAC da interface cabeada/Wi-Fi que suporta WoL.

Exemplo manual no homelab:

```bash
wakeonlan AA:BB:CC:DD:EE:FF
```

Use MAC real da interface que fica energizada durante suspensao/hibernacao.
