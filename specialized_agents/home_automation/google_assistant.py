"""
Webhook para Google Assistant / Gemini
Recebe comandos de voz e controla dispositivos tinytuya locais

Fluxo:
  1. "OK Google: Ligar ventilador"
  2. Google Assistant chama webhook: POST /home/assistant/command
  3. Parseamos comando em PT-BR
  4. Executamos ação via tinytuya (controle local)
  5. Retorna resposta de voz (pode ser synthetic speech)

Integração local:
- Usa tinytuya para controle LAN (sem dependência de Cloud API)
- Busca devices em cache local (agent_data/home_automation/device_map.json)
- Fallback para scan se device não está no cache
"""
import json
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime

"""
Modo Gemini-only: este webhook recebe e parseia comandos vindos do Gemini/Google
Assistant, mas não executa comandos localmente — a execução fica a cargo do
dispositivo do usuário (telefone/Google Home) que possui os dispositivos
vinculados. Mantemos parsing, logging e respostas para TTS.
"""

logger = logging.getLogger(__name__)

# ============================================================================
# Mapeamento semântico: alias -> device_id real
# ============================================================================

DEVICE_ALIASES = {
    "ventilador": {
        "keywords": ["ventilador", "fan", "venti"],
        "device_id": "ventilador_escritorio",
        "display_name": "ventilador",
        "actions": ["on", "off"],
    },
    "luz-escritorio": {
        "keywords": ["luz", "light", "escritório", "escritorio", "mesa"],
        "device_id": "luz_escritorio",
        "display_name": "luz do escritório",
        "actions": ["on", "off", "brightness"],
    },
    "tomada-cozinha": {
        "keywords": ["tomada", "cozinha", "kitchen", "outlet", "plug"],
        "device_id": "tomada_cozinha",
        "display_name": "tomada da cozinha",
        "actions": ["on", "off"],
    },
}

# ============================================================================
# Parser de comandos em português
# ============================================================================

COMMAND_PATTERNS = {
    "ligar": ["ligar", "liga", "acender", "acenda", "turn on", "on"],
    "desligar": ["desligar", "desligue", "desliga", "apagar", "apague", "turn off", "off"],
    "aumentar": ["aumentar", "aumente", "mais", "increase", "up"],
    "diminuir": ["diminuir", "diminua", "menos", "decrease", "down"],
    "status": ["status", "como esta", "tá ligado", "verificar"],
}


# ============================================================================
# Pydantic Models
# ============================================================================


class AssistantCommand(BaseModel):
    """Comando vindo do Google Assistant / Gemini"""
    text: str
    user_id: Optional[str] = None
    request_id: Optional[str] = None


class CommandResponse(BaseModel):
    """Resposta para o Google Assistant (TTS)"""
    success: bool
    message: str  # Texto para o Google Assistant ler em voz alta
    action: str
    device: str
    status: Optional[Dict[str, Any]] = None


# ============================================================================
# Parsing e Execução
# ============================================================================


def parse_command(text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parse comando de texto natural em português.
    
    Retorna: (ação, device_alias, parametro)
    Ex: "ligar ventilador" -> ("ligar", "ventilador", None)
    """
    text_lower = text.lower().strip()
    
    # Identificar ação
    action = None
    for action_key, patterns in COMMAND_PATTERNS.items():
        for pattern in patterns:
            if pattern in text_lower:
                action = action_key
                break
        if action:
            break
    
    if not action:
        return None, None, None
    
    # Identificar device pelo alias
    device_alias = None
    for alias, config in DEVICE_ALIASES.items():
        for keyword in config["keywords"]:
            if keyword in text_lower:
                device_alias = alias
                break
        if device_alias:
            break
    
    # Extrair parâmetro (para ações como brightness)
    param = None
    if action in ["aumentar", "diminuir"]:
        for token in text_lower.split():
            if token.isdigit() or "%" in token:
                param = token
                break
    
    return action, device_alias, param


def execute_action(
    device_alias: str,
    action: str,
    param: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Modo Gemini-only: não executa comandos localmente.

    Retorna um resultado simbólico confirmando o parsing e informando que a
    execução ocorrerá via o dispositivo do usuário (telefone / Google Home),
    que deve ter os aparelhos vinculados.
    """
    if device_alias not in DEVICE_ALIASES:
        return {"success": False, "error": f"Device '{device_alias}' desconhecido"}

    device_config = DEVICE_ALIASES[device_alias]
    return {
        "success": True,
        "note": "gemini_only",
        "result": {"device_id": device_config["device_id"], "action": action, "param": param},
    }


# ============================================================================
# Router FastAPI
# ============================================================================

router = APIRouter(prefix="/home/assistant", tags=["google-assistant"])


@router.post("/command")
async def command(cmd: AssistantCommand) -> CommandResponse:
    """
    Webhook para Google Assistant / Gemini.
    
    Recebe comando de voz, parseia, e executa ação no device local.
    
    Exemplo:
      POST /home/assistant/command
      {
        "text": "ligar ventilador"
      }
    
    Resposta:
      {
        "success": true,
        "message": "Ventilador ligado",
        "action": "ligar",
        "device": "ventilador"
      }
    """
    
    logger.info(f"[AssistantCommand] {cmd.text} (user={cmd.user_id})")
    
    # Parsear comando
    action, device_alias, param = parse_command(cmd.text)
    
    if not action or not device_alias:
        return CommandResponse(
            success=False,
            message="Desculpe, não entendi. Tente: ligar ventilador, desligar luz, etc.",
            action="parse_error",
            device="unknown",
        )
    
    # Executar ação
    result = execute_action(device_alias, action, param)
    
    if result["success"]:
        # Montar mensagem em PT-BR para TTS
        device_config = DEVICE_ALIASES[device_alias]
        device_name = device_config["display_name"]
        
        action_desc = {
            "ligar": "ligado",
            "desligar": "desligado",
            "aumentar": "aumentei o brilho de",
            "diminuir": "diminuí o brilho de",
            "status": "está tudo bem com o",
        }.get(action, action)
        
        message = f"{device_name} {action_desc}!"
        
        return CommandResponse(
            success=True,
            message=message,
            action=action,
            device=device_alias,
            status=result.get("result"),
        )
    else:
        error_msg = result.get("error", "erro desconhecido")
        return CommandResponse(
            success=False,
            message=f"Não consegui controlar o {DEVICE_ALIASES[device_alias]['display_name']}: {error_msg}",
            action=action or "unknown",
            device=device_alias or "unknown",
        )


@router.get("/devices")
async def list_devices():
    """Listar dispositivos registrados"""
    # Em modo Gemini-only não mantemos controle local. Retornamos aliases
    # conhecidos para fins de debug/integração.
    return {
        "devices": [],
        "count": 0,
        "aliases": list(DEVICE_ALIASES.keys()),
        "mode": "gemini-only",
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/devices/scan")
async def scan_network():
    """Fazer scan da rede para descobrir devices Tuya"""
    logger.info("[Scan] Iniciando descoberta...")
    return {
        "success": False,
        "error": "Scan de rede desabilitado em modo gemini-only",
        "mode": "gemini-only",
    }


@router.post("/devices/register")
async def register_device(
    device_id: str,
    ip: str,
    local_key: str,
    name: str,
    version: float = 3.4,
):
    """
    Registrar device manualmente.
    
    Args:
        device_id: ID único do device (ex: "ventilador_escritorio")
        ip: IP do device na rede (ex: "192.168.15.4")
        local_key: Local key do device (obtido via Smart Life ou scan)
        name: Nome legível (ex: "Ventilador Escritório")
        version: Protocol version (3.4 ou 3.5)
    """
    return {
        "success": False,
        "error": "Registro de dispositivos desabilitado em modo gemini-only",
        "mode": "gemini-only",
    }


@router.get("/health")
async def health():
    """Health check do webhook"""
    return {
        "status": "ok",
        "mode": "gemini-only",
        "devices_registered": 0,
        "aliases_available": len(DEVICE_ALIASES),
    }
