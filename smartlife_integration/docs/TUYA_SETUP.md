# 🔧 Guia de Configuração da Tuya IoT Platform

Este guia explica como configurar a Tuya IoT Platform para usar com a integração SmartLife.

## 📋 Pré-requisitos

1. Conta na Tuya IoT Platform
2. App SmartLife instalado com dispositivos vinculados
3. Dispositivos Tuya/SmartLife na mesma rede local

## 🚀 Passo a Passo

### 1. Criar Conta na Tuya IoT Platform

1. Acesse [iot.tuya.com](https://iot.tuya.com)
2. Clique em **Sign Up** (usar mesma conta do SmartLife facilita)
3. Complete o cadastro e verifique o email

### 2. Criar Cloud Project

1. No painel, vá para **Cloud** > **Development** > **Cloud Projects**
2. Clique em **Create Cloud Project**
3. Configure:
   - **Project Name**: `HomeAssistant` ou `SmartHome`
   - **Industry**: Smart Home
   - **Development Method**: Smart Home PaaS
   - **Data Center**: Western Europe (ou mais próximo de você)
4. Clique em **Create**

### 3. Vincular App SmartLife

1. No projeto criado, vá para **Link Tuya App Account**
2. Clique em **Add App Account**
3. Escaneie o QR code com o app SmartLife/Tuya Smart:
   - No app: **Perfil** > **⚙️** > **Link to Third-party Services**
4. Autorize a conexão

### 4. Obter Credenciais

1. Na página do projeto, vá para **Overview**
2. Copie:
   - **Access ID/Client ID** → `api_key`
   - **Access Secret/Client Secret** → `api_secret`
3. Anote também um **Device ID** de qualquer dispositivo vinculado

### 5. Configurar API Permissions

1. Vá para **Cloud** > **Development** > seu projeto
2. Clique em **API** ou **Subscribe APIs**
3. Assine os seguintes serviços (Free Trial disponível):
   - **Authorization Management**
   - **Device Management**
   - **Device Control**
   - **Smart Home Device Management**

## 🔑 Obter Local Keys com TinyTuya

O TinyTuya Wizard automatiza a obtenção das chaves locais:

```bash
# Ativar ambiente virtual
cd ~/myClaude/smartlife_integration
source venv/bin/activate

# Executar wizard
python -m tinytuya wizard
```

### Durante o Wizard:

1. **Enter API Key**: Cole o Access ID
2. **Enter API Secret**: Cole o Access Secret  
3. **Enter Region**: `eu` (ou sua região: us, cn, in)
4. **Enter Device ID**: Cole qualquer Device ID

O wizard vai:
- Conectar à API Tuya
- Baixar lista de todos os dispositivos
- Obter Local Keys
- Salvar em `devices.json`

### Arquivo devices.json

```json
[
    {
        "name": "Lâmpada Sala",
        "id": "bfxxxxxxxxxxxxxxxxxx",
        "key": "xxxxxxxxxxxxxxxx",
        "ip": "192.168.1.100",
        "version": "3.3"
    }
]
```

Mova para o diretório config:

```bash
mv devices.json config/
```

## 📝 Configurar config.yaml

Edite `config/config.yaml`:

```yaml
# Tuya Cloud API
tuya:
  api_key: "SEU_ACCESS_ID"
  api_secret: "SEU_ACCESS_SECRET"
  region: "eu"  # us, eu, cn, in
  device_id: "SEU_DEVICE_ID"

# Integração Local
local:
  enabled: true
  devices_file: "config/devices.json"
  scan_interval: 60
```

## 🔍 Verificar Configuração

```bash
# Testar conexão
python -c "
import tinytuya
c = tinytuya.Cloud(
    apiRegion='eu',
    apiKey='SEU_ACCESS_ID',
    apiSecret='SEU_ACCESS_SECRET',
    apiDeviceID='SEU_DEVICE_ID'
)
devices = c.getdevices()
print(f'Encontrados {len(devices)} dispositivos')
for d in devices[:5]:
    print(f'  - {d[\"name\"]} ({d[\"id\"]})')
"
```

## ⚠️ Solução de Problemas

### Erro: "sign invalid"
- Verifique se copiou API Key e Secret corretamente
- Verifique se a região está correta

### Erro: "token invalid"
- Token pode ter expirado, execute wizard novamente

### Dispositivos não aparecem
- Verifique se vinculou a conta do app corretamente
- Verifique se os dispositivos estão online no app

### Local Key inválida
- Execute `python -m tinytuya scan` para verificar IPs
- Re-execute o wizard para atualizar keys

## 📚 Links Úteis

- [Tuya IoT Platform](https://iot.tuya.com)
- [TinyTuya Documentation](https://github.com/jasonacox/tinytuya)
- [Tuya Developer Docs](https://developer.tuya.com/en/docs/iot)
