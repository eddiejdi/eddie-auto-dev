#!/usr/bin/env python3
"""
Integração do WhatsApp Bot com Home Assistant para controle de dispositivos.

Permite enviar comandos via WhatsApp como:
  "ligar ventilador do escritório"
  "desligar luz da sala"
  "status da casa"
  "dispositivos"

Usa o modelo eddie-whatsapp para NLP avançado quando o parser simples falha.
"""

import logging
import os
import re
from typing import Optional

logger = logging.getLogger("HomeAssistant")

# Lazy import do adaptador
_ha_instance = None

HA_URL = os.getenv("HOME_ASSISTANT_URL", "http://192.168.15.2:8123")
HA_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN", "")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")

# Keywords que indicam intenção de automação residencial
HOME_KEYWORDS = [
    # Ações
    "ligar", "ligue", "liga",
    "desligar", "desligue", "desliga",
    "acender", "acenda", "acende",
    "apagar", "apague", "apaga",
    "ativar", "ative", "ativa",
    "desativar", "desative", "desativa",
    "alternar", "toggle",
    # Dispositivos
    "ventilador", "luz", "lâmpada", "lampada",
    "tomada", "plug", "interruptor",
    "ar condicionado", "ar-condicionado", "climatizador",
    "esteira", "aquário", "aquario",
    "tv", "televisão", "televisao", "chromecast",
    "sensor", "movimento",
    # Locais
    "escritório", "escritorio", "sala", "quarto", "cozinha", "banheiro",
]

# Keywords para status/listagem (não são ações de controle)
STATUS_KEYWORDS = [
    "status da casa", "status casa", "como está a casa", "como esta a casa",
    "dispositivos", "listar dispositivos", "quais dispositivos",
    "o que tem ligado", "o que esta ligado", "o que está ligado",
    "sensores", "status sensores",
]

# Regex para detectar um comando de controle de dispositivo
_ACTION_PATTERN = re.compile(
    r'\b(ligar?|ligue|desligar?|desligue|acend[ae]r?|apag[au]e?r?|'
    r'ativ[ae]r?|desativ[ae]r?|toggle|alternar)\b',
    re.IGNORECASE
)


def _get_ha():
    """Singleton lazy do HomeAssistantAdapter."""
    global _ha_instance
    if _ha_instance is None:
        # Import direto para evitar cadeia de imports do pacote specialized_agents
        import importlib.util
        import sys
        from pathlib import Path

        # Tentar import direto do módulo
        ha_module = None
        possible_paths = [
            Path(__file__).parent / "specialized_agents" / "home_automation" / "ha_adapter.py",
            Path("/home/homelab/eddie-auto-dev/specialized_agents/home_automation/ha_adapter.py"),
            Path("/home/homelab/myClaude/specialized_agents/home_automation/ha_adapter.py"),
        ]
        for p in possible_paths:
            if p.exists():
                spec = importlib.util.spec_from_file_location("ha_adapter", str(p))
                ha_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(ha_module)
                break

        if ha_module is None:
            # Fallback: tentar import normal
            from specialized_agents.home_automation.ha_adapter import HomeAssistantAdapter as _HA
            _ha_instance = _HA(HA_URL, HA_TOKEN)
        else:
            _ha_instance = ha_module.HomeAssistantAdapter(HA_URL, HA_TOKEN)

    return _ha_instance


def detect_home_intent(text: str) -> bool:
    """Detecta se a mensagem é uma intenção de automação residencial."""
    text_lower = text.lower()

    # Status / listagem
    for kw in STATUS_KEYWORDS:
        if kw in text_lower:
            return True

    # Comando explícito (/casa, /home)
    if text_lower.startswith(("/casa", "/home ")):
        return True

    # Ação + dispositivo/local
    if _ACTION_PATTERN.search(text_lower):
        # Precisa ter pelo menos uma keyword de dispositivo/local
        device_keywords = [
            "ventilador", "luz", "lâmpada", "lampada", "tomada", "plug",
            "interruptor", "ar condicionado", "ar-condicionado", "esteira",
            "aquário", "aquario", "tv", "televisão", "televisao", "chromecast",
            "sensor", "escritório", "escritorio", "sala", "quarto", "cozinha",
            "banheiro", "backlight", "switch", "fan", "light",
        ]
        if any(kw in text_lower for kw in device_keywords):
            return True

    return False


async def process_home_command(text: str, chat_id: str = "") -> Optional[str]:
    """
    Processa uma mensagem de automação residencial e retorna resposta formatada.
    Retorna None se não for um comando válido.
    """
    if not HA_TOKEN:
        return (
            "⚠️ *Home Assistant não configurado*\n\n"
            "Defina as variáveis de ambiente:\n"
            "• `HOME_ASSISTANT_URL`\n"
            "• `HOME_ASSISTANT_TOKEN`"
        )

    ha = _get_ha()
    text_lower = text.lower().strip()

    # Remover prefixo de comando
    for prefix in ["/casa ", "/home "]:
        if text_lower.startswith(prefix):
            text = text[len(prefix):].strip()
            text_lower = text.lower()
            break

    try:
        # === STATUS / LISTAGEM ===
        if _is_status_request(text_lower):
            return await _handle_status(ha)

        if _is_list_request(text_lower):
            return await _handle_list_devices(ha)

        # === CONTROLE DE DISPOSITIVO ===
        if _ACTION_PATTERN.search(text_lower):
            return await _handle_device_control(ha, text)

        # === USAR LLM PARA PARSEAR COMANDO COMPLEXO ===
        return await _handle_with_llm(ha, text)

    except Exception as e:
        logger.error(f"Erro ao processar comando HA: {e}", exc_info=True)
        return f"❌ *Erro ao controlar dispositivo*\n\n{e}"


def _is_status_request(text: str) -> bool:
    """Verifica se é pedido de status geral."""
    patterns = [
        "status", "como está", "como esta", "o que tem ligado",
        "o que esta ligado", "o que está ligado", "resumo",
    ]
    return any(p in text for p in patterns) and not _ACTION_PATTERN.search(text)


def _is_list_request(text: str) -> bool:
    """Verifica se é pedido de listagem."""
    patterns = ["dispositivos", "listar", "quais", "sensores"]
    return any(p in text for p in patterns) and not _ACTION_PATTERN.search(text)


async def _handle_status(ha) -> str:
    """Retorna status geral dos dispositivos."""
    try:
        devices = await ha.get_devices()
    except Exception as e:
        return f"❌ *Não foi possível conectar ao Home Assistant*\n\n{e}"

    on_devices = [d for d in devices if d["state"] == "on"]
    off_devices = [d for d in devices if d["state"] == "off"]
    unavailable = [d for d in devices if d["state"] in ("unavailable", "unknown")]

    lines = ["🏠 *Status da Casa*\n"]

    if on_devices:
        lines.append(f"🟢 *Ligados ({len(on_devices)}):*")
        for d in on_devices[:15]:
            emoji = _device_emoji(d["domain"])
            lines.append(f"  {emoji} {d['name']}")
        if len(on_devices) > 15:
            lines.append(f"  ... e mais {len(on_devices) - 15}")

    if off_devices:
        lines.append(f"\n🔴 *Desligados ({len(off_devices)}):*")
        for d in off_devices[:10]:
            emoji = _device_emoji(d["domain"])
            lines.append(f"  {emoji} {d['name']}")
        if len(off_devices) > 10:
            lines.append(f"  ... e mais {len(off_devices) - 10}")

    if unavailable:
        lines.append(f"\n⚪ *Indisponíveis ({len(unavailable)}):*")
        for d in unavailable[:5]:
            lines.append(f"  ❓ {d['name']}")

    lines.append(f"\n📊 Total: {len(devices)} dispositivos")
    return "\n".join(lines)


async def _handle_list_devices(ha) -> str:
    """Lista dispositivos agrupados por domínio."""
    devices = await ha.get_devices()

    by_domain = {}
    for d in devices:
        domain = d["domain"]
        by_domain.setdefault(domain, []).append(d)

    lines = ["📋 *Dispositivos no Home Assistant*\n"]
    domain_names = {
        "fan": "🌀 Ventiladores",
        "light": "💡 Luzes",
        "switch": "🔌 Interruptores/Plugs",
        "binary_sensor": "📡 Sensores",
        "sensor": "🌡️ Sensores",
        "media_player": "📺 Mídia",
        "climate": "❄️ Climatização",
        "camera": "📷 Câmeras",
        "cover": "🪟 Persianas",
        "lock": "🔒 Fechaduras",
    }

    for domain, devs in sorted(by_domain.items()):
        title = domain_names.get(domain, f"🔧 {domain.title()}")
        lines.append(f"*{title}:*")
        for d in devs:
            state_icon = "🟢" if d["state"] == "on" else ("🔴" if d["state"] == "off" else "⚪")
            lines.append(f"  {state_icon} {d['name']} ({d['state']})")
        lines.append("")

    return "\n".join(lines)


async def _handle_device_control(ha, command: str) -> str:
    """Executa controle de dispositivo via parser NL do ha_adapter."""
    result = await ha.execute_natural_command(command)

    if result.get("success"):
        action = result["action"]
        device_name = result["device"]
        emoji = "🟢" if action == "turn_on" else ("🔴" if action == "turn_off" else "🔄")
        action_text = {
            "turn_on": "ligado",
            "turn_off": "desligado",
            "toggle": "alternado",
        }.get(action, action)

        return (
            f"{emoji} *{device_name}* {action_text} com sucesso!\n\n"
            f"🔧 Entity: `{result['entity_id']}`\n"
            f"📊 Estado anterior: {result.get('previous_state', '?')}"
        )
    else:
        error = result.get("error", "Erro desconhecido")
        return f"❌ *Falha no comando*\n\n{error}"


async def _handle_with_llm(ha, text: str) -> str:
    """
    Usa o modelo eddie-whatsapp via Ollama para interpretar comandos complexos
    e extrair ação + dispositivo.
    """
    try:
        import httpx

        devices = await ha.get_devices()
        device_list = "\n".join(
            [f"- {d['name']} ({d['entity_id']}, state={d['state']})" for d in devices[:30]]
        )

        prompt = f"""Analise este comando de automação residencial e extraia:
1. action: turn_on, turn_off, ou toggle
2. entity_id: o entity_id do dispositivo mais provável

Dispositivos disponíveis:
{device_list}

Comando do usuário: "{text}"

Responda APENAS em JSON, sem texto extra:
{{"action": "...", "entity_id": "..."}}"""

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": "eddie-whatsapp:latest",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 100},
                },
            )
            resp.raise_for_status()
            llm_text = resp.json().get("response", "").strip()

        # Extrair JSON da resposta
        import json

        # Tentar parsear diretamente
        json_match = re.search(r'\{[^}]+\}', llm_text)
        if json_match:
            parsed = json.loads(json_match.group())
            action = parsed.get("action", "")
            entity_id = parsed.get("entity_id", "")

            if action and entity_id:
                # Validar que entity_id existe
                valid_ids = {d["entity_id"] for d in devices}
                if entity_id not in valid_ids:
                    return f"❌ Dispositivo `{entity_id}` não encontrado no Home Assistant."

                domain = entity_id.split(".")[0]
                await ha.call_service(domain, action, {"entity_id": entity_id})

                device_name = next(
                    (d["name"] for d in devices if d["entity_id"] == entity_id),
                    entity_id,
                )
                emoji = "🟢" if action == "turn_on" else ("🔴" if action == "turn_off" else "🔄")
                action_text = {"turn_on": "ligado", "turn_off": "desligado", "toggle": "alternado"}.get(action, action)

                return (
                    f"{emoji} *{device_name}* {action_text} com sucesso!\n\n"
                    f"🤖 Interpretado pelo modelo eddie-whatsapp\n"
                    f"🔧 Entity: `{entity_id}`"
                )

        return f"🤔 Não entendi o comando: *{text}*\n\nTente algo como:\n• _ligar ventilador_\n• _desligar luz da sala_\n• _status da casa_"

    except Exception as e:
        logger.error(f"Erro no LLM para home command: {e}")
        return f"🤔 Não entendi o comando: *{text}*\n\nTente algo como:\n• _ligar ventilador_\n• _desligar luz da sala_\n• _status da casa_"


def _device_emoji(domain: str) -> str:
    """Retorna emoji baseado no domínio."""
    return {
        "fan": "🌀",
        "light": "💡",
        "switch": "🔌",
        "binary_sensor": "📡",
        "sensor": "🌡️",
        "media_player": "📺",
        "climate": "❄️",
        "camera": "📷",
        "cover": "🪟",
        "lock": "🔒",
    }.get(domain, "🔧")


def get_home_commands() -> str:
    """Retorna texto de ajuda para comandos de casa."""
    return """🏠 *Automação Residencial*

*Comandos disponíveis:*

🔧 *Controle:*
• _ligar ventilador_ — liga um dispositivo
• _desligar luz da sala_ — desliga um dispositivo
• _acender luz do quarto_ — liga uma luz
• _apagar todas as luzes_ — apaga as luzes

📊 *Status:*
• _status da casa_ — mostra o que está ligado/desligado
• _dispositivos_ — lista todos os dispositivos
• /casa status — status da casa
• /casa dispositivos — listar dispositivos

💡 *Exemplos:*
• "ligar ventilador do escritório"
• "desligar esteira"
• "acender luz backlight"
• "como está a casa?"
• "o que tem ligado?"
"""
