"""
🔧 Configuração Centralizada do Home Lab
Todas as configurações do sistema em um único lugar
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ================== PATHS ==================
BASE_DIR = Path("/home/homelab/myClaude")
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# ================== SERVIDOR ==================
@dataclass
class ServerConfig:
    """Configurações do servidor"""
    hostname: str = "homelab"
    ip: str = "192.168.15.2"
    user: str = "homelab"
    home: str = "/home/homelab"
    project_dir: str = "/home/homelab/myClaude"

SERVER = ServerConfig()

# ================== SERVIÇOS ==================
@dataclass
class ServiceConfig:
    """Configuração de um serviço"""
    name: str
    port: Optional[int] = None
    description: str = ""
    enabled: bool = True
    systemd_name: str = ""
    health_endpoint: str = ""

SERVICES: Dict[str, ServiceConfig] = {
    "ollama": ServiceConfig(
        name="Ollama",
        port=11434,
        description="Servidor de modelos LLM",
        systemd_name="ollama",
        health_endpoint="/api/tags"
    ),
    "openwebui": ServiceConfig(
        name="Open WebUI",
        port=3000,
        description="Interface web para chat com IA",
        systemd_name="open-webui",
        health_endpoint="/"
    ),
    "waha": ServiceConfig(
        name="WAHA WhatsApp",
        port=3001,
        description="API WhatsApp Business",
        systemd_name="waha",
        health_endpoint="/api/health"
    ),
    "telegram_bot": ServiceConfig(
        name="Telegram Bot",
        description="Bot do Telegram para comandos",
        systemd_name="eddie-telegram-bot"
    ),
    "whatsapp_bot": ServiceConfig(
        name="WhatsApp Bot",
        description="Bot do WhatsApp para comandos",
        systemd_name="eddie-whatsapp-bot"
    ),
    "calendar": ServiceConfig(
        name="Calendar Service",
        description="Lembretes do Google Calendar",
        systemd_name="eddie-calendar"
    ),
    "specialized_agents": ServiceConfig(
        name="Specialized Agents API",
        port=8503,
        description="API de agentes especializados",
        systemd_name="specialized-agents-api",
        health_endpoint="/health"
    ),
    "btc_trading": ServiceConfig(
        name="BTC Trading Engine",
        port=8511,
        description="Engine de trading Bitcoin",
        systemd_name="btc-trading-engine",
        health_endpoint="/health"
    ),
    "btc_webui": ServiceConfig(
        name="BTC WebUI API",
        port=8510,
        description="API para Open WebUI trading",
        systemd_name="btc-webui-api",
        health_endpoint="/health"
    ),
    "github_agent": ServiceConfig(
        name="GitHub Agent",
        description="Agente GitHub para automação",
        systemd_name="github-agent"
    ),
}

# ================== CREDENCIAIS ==================
@dataclass
class Credentials:
    """Credenciais do sistema (carregadas de variáveis de ambiente)"""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    github_token: str = ""
    whatsapp_number: str = ""
    admin_numbers: List[str] = field(default_factory=list)
    
    @classmethod
    def from_env(cls):
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            whatsapp_number=os.getenv("WHATSAPP_NUMBER", "5511981193899"),
            admin_numbers=os.getenv("ADMIN_NUMBERS", "5511981193899").split(",")
        )

# ================== MODELOS OLLAMA ==================
OLLAMA_MODELS = {
    "eddie-coder": {
        "description": "Modelo principal para programação",
        "base": "codestral:22b",
        "modelfile": "eddie-coder-v2.Modelfile"
    },
    "eddie-assistant": {
        "description": "Assistente geral",
        "base": "qwen2.5-coder:7b",
        "modelfile": "eddie-assistant-v2.Modelfile"
    },
    "eddie-reports": {
        "description": "Geração de relatórios",
        "base": "qwen2.5-coder:7b",
        "modelfile": "eddie-assistant-reports.Modelfile"
    },
}

# ================== INTEGRAÇÕES ==================
@dataclass
class IntegrationConfig:
    """Configuração de integrações externas"""
    name: str
    enabled: bool = True
    config_file: str = ""
    credentials_file: str = ""

INTEGRATIONS = {
    "gmail": IntegrationConfig(
        name="Gmail",
        config_file="gmail_data/config.json",
        credentials_file="gmail_data/token.json"
    ),
    "google_calendar": IntegrationConfig(
        name="Google Calendar",
        config_file="calendar_data/config.json",
        credentials_file="calendar_data/token.json"
    ),
    "github": IntegrationConfig(
        name="GitHub",
        credentials_file=".env"
    ),
    "kucoin": IntegrationConfig(
        name="KuCoin Trading",
        config_file="btc_trading_agent/config.json"
    ),
}

# ================== PORTAS ==================
PORTS = {
    "ollama": 11434,
    "openwebui": 3000,
    "waha": 3001,
    "streamlit_dashboard": 8500,
    "specialized_agents": 8503,
    "btc_webui": 8510,
    "btc_engine": 8511,
}

# ================== URLs ==================
def get_url(service: str, path: str = "") -> str:
    """Retorna URL completa de um serviço"""
    port = PORTS.get(service)
    if port:
        return f"http://{SERVER.ip}:{port}{path}"
    return ""

URLS = {
    "ollama": get_url("ollama"),
    "ollama_api": get_url("ollama", "/api"),
    "openwebui": get_url("openwebui"),
    "waha": get_url("waha"),
    "waha_dashboard": get_url("waha", "/dashboard"),
    "dashboard": get_url("streamlit_dashboard"),
}

# ================== EXPORTS ==================
__all__ = [
    "SERVER", "SERVICES", "PORTS", "URLS", 
    "OLLAMA_MODELS", "INTEGRATIONS", "Credentials",
    "BASE_DIR", "DATA_DIR", "LOGS_DIR"
]
