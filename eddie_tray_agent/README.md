# Eddie Tray Agent 🖥️

Agente que reside na **system tray** (Windows/Linux) e monitora/controla dispositivos smart home integrados ao ecossistema Eddie.

## Funcionalidades

### 1. 🔒 Lock/Unlock → Controle do Escritório
- Ao **bloquear a tela**: desliga todos os dispositivos do grupo "escritório"
  - **Exceção**: o aquário desliga com delay de 10 segundos
  - Salva snapshot do estado de cada dispositivo antes de desligar
- Ao **desbloquear a tela**: restaura cada dispositivo ao estado salvo

### 2. 🌡️ Monitor de Clima + Ventilador
- Consulta OpenWeatherMap periodicamente (temperatura, umidade, condição)
- Registra estado do ventilador correlacionado com clima
- Guarda histórico completo no PostgreSQL do homelab
- Ao desbloquear, restaura o ventilador ao último estado registrado

### 3. 🎙️ Assistente de Voz — "OK HOME"
- Escuta o microfone continuamente em background
- Detecta wake word **"OK HOME"** seguida de um comando
- Executa via Home Automation API do Eddie
- Se o comando não existir, usa **LLM local (Ollama)** para tentar implementar

## Instalação

```bash
cd eddie-auto-dev

# Instalar dependências
pip install -r eddie_tray_agent/requirements.txt

# Linux: dependências de sistema para D-Bus e áudio
sudo apt install -y python3-dbus libgirepository1.0-dev portaudio19-dev
```

## Persistência

Os dados são persistidos no **PostgreSQL do homelab** (`192.168.15.2:5433`) por padrão.
Se o Postgres não estiver disponível, o agente **falha com erro** (sem fallback — orientação do treinamento).

Tabelas criadas no homelab (prefixo `tray_`):
- `tray_screen_events` — histórico lock/unlock
- `tray_climate_readings` — temperatura/umidade
- `tray_fan_states` — estado do ventilador correlacionado ao clima
- `tray_voice_commands` — comandos de voz executados
- `tray_device_snapshots` — snapshots antes de desligar

## Configuração

Variáveis de ambiente (ou `.env`):

| Variável | Default | Descrição |
|----------|---------|-----------|
| `DATABASE_URL` | `postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/postgres` | Postgres homelab |
| `EDDIE_API_URL` | `http://localhost:8503` | URL da API do Eddie |
| `OFFICE_DEVICES` | `escritorio` | Nome do grupo/sala |
| `AQUARIUM_DEVICE` | `aquario` | Nome do dispositivo aquário |
| `AQUARIUM_OFF_DELAY` | `10` | Delay (s) para desligar aquário |
| `FAN_DEVICE` | `ventilador` | Nome do dispositivo ventilador |
| `OPENWEATHER_API_KEY` | *(vazio)* | Chave da OpenWeatherMap API |
| `WEATHER_CITY` | `Curitiba` | Cidade para clima |
| `WEATHER_COUNTRY` | `BR` | País |
| `WEATHER_POLL_INTERVAL` | `300` | Intervalo de consulta (s) |
| `WAKE_WORD` | `ok home` | Palavra de ativação do mic |
| `VOICE_LANGUAGE` | `pt-BR` | Idioma do reconhecimento de voz |
| `OLLAMA_HOST` | `http://192.168.15.2:11434` | URL do Ollama |
| `LLM_MODEL` | `qwen2.5-coder:1.5b` | Modelo LLM para comandos desconhecidos |

## Uso

```bash
# Executar diretamente
python -m eddie_tray_agent

# Ou via systemd (user service)
cp eddie_tray_agent/eddie-tray-agent@.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now eddie-tray-agent@$USER
```

## Arquitetura

```
eddie_tray_agent/
├── __init__.py           ← Versão
├── __main__.py           ← Entry point
├── app.py                ← App principal (tray icon + orquestração)
├── config.py             ← Configuração via env vars
├── screen_monitor.py     ← Detecção lock/unlock (D-Bus / Win32 / polling)
├── device_controller.py  ← Controle de dispositivos via API
├── climate_monitor.py    ← OpenWeatherMap + estado do ventilador
├── voice_assistant.py    ← Mic listener + "OK HOME" + LLM fallback
├── history_db.py         ← PostgreSQL para histórico
├── requirements.txt      ← Dependências Python
└── eddie-tray-agent@.service ← Systemd user unit
```

### Fluxo Lock/Unlock

```
[Tela Bloqueada]
     │
     ├─ Salvar snapshot de cada dispositivo
     ├─ Desligar dispositivos (imediato)
     └─ Desligar aquário (após 10s delay)

[Tela Desbloqueada]
     │
     ├─ Ler snapshots salvos
     ├─ Restaurar cada dispositivo ao estado anterior
     └─ Restaurar ventilador (velocidade/modo registrado)
```

### Fluxo Voice

```
[Microfone]
     │
     ├─ Speech-to-text (Google / Vosk offline)
     ├─ Detectar "OK HOME ..."
     ├─ Extrair comando
     ├─ Executar via API /home/command
     │    ├─ ✅ Sucesso → log
     │    └─ ❌ Falha → LLM tenta implementar
     │         ├─ Gera sequência de sub-comandos
     │         └─ Executa sequencialmente
     └─ Registrar no histórico
```

## Integração com Communication Bus

O agent publica eventos no bus do Eddie:
- `tray_agent_started` / `tray_agent_stopped`
- `office_locked` / `office_unlocked`
- Todos os comandos de dispositivo passam pela API que já integra com o bus

## Exemplos de Comandos de Voz

```
"OK HOME ligue a luz"
"OK HOME desligue tudo do escritório"
"OK HOME temperatura a 22 graus"
"OK HOME aumente o ventilador"
"OK HOME ative cena noite"
"OK HOME como está o tempo?"       ← LLM interpreta
"OK HOME toque música relaxante"   ← LLM tenta mapear
```
