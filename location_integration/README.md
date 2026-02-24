# Eddie Location Server
# Integração de localização do celular com servidor IA

## 🎯 Funcionalidades

- ✅ **A** - Saber quando chega/sai de casa (geofencing)
- ✅ **B** - Automações via Google Home
- ✅ **C** - Perguntar "onde estou?" via Telegram
- ✅ **D** - Histórico completo de localizações

## 📱 Setup Rápido

### 1. Instalar o Servidor
```bash
cd ~/myClaude/location_integration
chmod +x install.sh
./install.sh
### 2. Configurar OwnTracks no Android

1. **Baixe** OwnTracks na Play Store
2. Abra o app → **Menu (☰)** → **Preferences**
3. **Connection**:
   - Mode: `Private HTTP`
   - Host: `http://SEU-IP:8585/owntracks`
   - Identification: `eddie` (seu nome)
   
4. **Reporting**:
   - Mode: `Significant changes` (economia de bateria)
   - ou `Move mode` (tempo real)

### 3. Configurar seus Lugares

Edite `config.json` com suas coordenadas:

```json
{
  "geofences": {
    "casa": {
      "name": "Casa",
      "latitude": -23.5505,    // Sua latitude
      "longitude": -46.6333,   // Sua longitude
      "radius_meters": 100
    }
  }
}
**Dica**: Para pegar suas coordenadas:
1. Abra Google Maps no celular
2. Toque e segure no local
3. As coordenadas aparecem na parte superior

## 🤖 Comandos Telegram

| Comando | Descrição |
|---------|-----------|
| `/onde` | Mostra localização atual |
| `/historico` | Últimas 24h de localizações |
| `/eventos` | Entradas/saídas de lugares |
| `/geofences` | Lista lugares configurados |
| `/bateria` | Nível de bateria do celular |

## 🔧 API Endpoints

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/owntracks` | POST | Webhook do OwnTracks |
| `/location` | POST | Enviar localização simples |
| `/location/current` | GET | Localização atual |
| `/location/history` | GET | Histórico |
| `/events` | GET | Eventos de geofencing |
| `/geofences` | GET | Listar geofences |
| `/status` | GET | Status do servidor |

## 🏠 Automações

Quando você **chegar em casa**:
- Notificação no Telegram
- Pode ligar luzes (SmartLife)
- Pode desligar alarme
- Qualquer automação custom

Quando você **sair de casa**:
- Notificação no Telegram
- Pode desligar luzes
- Pode ligar alarme

### Configurar Automações

Edite `config.json`:
```json
{
  "devices_automation": {
    "chegou_casa": [
      {"device_id": "SEU_DEVICE_ID", "action": "on"}
    ],
    "saiu_casa": [
      {"device_id": "SEU_DEVICE_ID", "action": "off", "delay": 300}
    ]
  }
}
## 🔍 Testar

```bash
# Ver status
curl http://localhost:8585/status

# Simular localização
curl -X POST http://localhost:8585/location \
  -H "Content-Type: application/json" \
  -d '{"lat": -23.5505, "lon": -46.6333}'

# Ver localização atual
curl http://localhost:8585/location/current
## 📊 Banco de Dados

Dados salvos em SQLite: `data/locations.db`

- **locations**: Todas as localizações recebidas
- **events**: Entradas/saídas de geofences
- **current_state**: Estado atual dos geofences

## 🐛 Troubleshooting

```bash
# Ver logs
sudo journalctl -u eddie-location -f

# Reiniciar
sudo systemctl restart eddie-location

# Testar manualmente
cd ~/myClaude/location_integration
source venv/bin/activate
python location_server.py
## 🔐 Segurança

Para acesso externo, recomendo:
1. Use um túnel (Cloudflare, ngrok)
2. Ou VPN para sua rede
3. Adicione autenticação básica

---

**Desenvolvido para integração com Eddie Assistant** 🤖
