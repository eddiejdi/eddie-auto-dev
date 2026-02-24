"""
Configuração do Eddie Tray Agent.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# ─── Diretórios ───────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "eddie_tray_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ─── Persistência (PostgreSQL homelab — sem fallback) ───
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/postgres",
)

# ─── API Eddie (specialized_agents) ──────────────────────
EDDIE_API_URL = os.getenv("EDDIE_API_URL", "http://localhost:8503")

# ─── Grupo Escritório ────────────────────────────────────
# Nomes dos dispositivos no grupo "escritório".
# O aquário tem tratamento especial (delay de 10s no desligamento).
OFFICE_GROUP = os.getenv("OFFICE_DEVICES", "escritorio").lower()

AQUARIUM_DEVICE_NAME = os.getenv("AQUARIUM_DEVICE", "aquario")
AQUARIUM_OFF_DELAY_SECONDS = int(os.getenv("AQUARIUM_OFF_DELAY", "10"))

# ─── Clima / Ventilador ─────────────────────────────────
# OpenWeatherMap (free tier): https://openweathermap.org/api
WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
WEATHER_CITY = os.getenv("WEATHER_CITY", "Curitiba")
WEATHER_COUNTRY = os.getenv("WEATHER_COUNTRY", "BR")
WEATHER_POLL_INTERVAL = int(os.getenv("WEATHER_POLL_INTERVAL", "300"))  # 5 min

FAN_DEVICE_NAME = os.getenv("FAN_DEVICE", "ventilador")

# ─── Voz  ────────────────────────────────────────────────
WAKE_WORD = os.getenv("WAKE_WORD", "ok home")
VOICE_LANGUAGE = os.getenv("VOICE_LANGUAGE", "pt-BR")
VOICE_ENERGY_THRESHOLD = int(os.getenv("VOICE_ENERGY", "300"))
# Índice do dispositivo de entrada (microfone).
# None = usa o default do PipeWire (recomendado — processa ruído).
# 0 = HDA Intel PCH (ALSA direto, sem filtragem — só se PipeWire falhar).
# Defina MIC_DEVICE_INDEX= (vazio) para usar PipeWire default.
_mic_env = os.getenv("MIC_DEVICE_INDEX", "")
MIC_DEVICE_INDEX: Optional[int] = int(_mic_env) if _mic_env else None

# ─── Communication Bus ───────────────────────────────────
AGENT_NAME = "eddie_tray"

# ─── Tray icon ────────────────────────────────────────────
TRAY_TOOLTIP = "Eddie Tray Agent"

# ─── LLM para comandos desconhecidos ─────────────────────
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:1.5b")
