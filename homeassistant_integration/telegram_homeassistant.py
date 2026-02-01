#!/usr/bin/env python3
"""
Integração Home Assistant para Telegram Bot
Permite controlar dispositivos inteligentes via comandos do Telegram
"""

import os
import sys
from typing import Optional, Tuple, List, Dict

# Adicionar path para importar homeassistant_api
sys.path.insert(0, os.path.dirname(__file__))

try:
    from homeassistant_api import HomeAssistantAPI, HAConfig

    HA_AVAILABLE = True
except ImportError:
    HA_AVAILABLE = False


# Comandos disponíveis
HOMEASSISTANT_COMMANDS = {
    "/casa": "Status da casa inteligente",
    "/luzes": "Lista todas as luzes",
    "/ligar": "Liga um dispositivo (ex: /ligar luz_sala)",
    "/desligar": "Desliga um dispositivo (ex: /desligar luz_sala)",
    "/alternar": "Alterna estado do dispositivo",
    "/clima": "Status do ar-condicionado",
    "/temperatura": "Define temperatura (ex: /temperatura 22)",
    "/cena": "Ativa uma cena (ex: /cena filme)",
    "/dispositivos": "Lista todos os dispositivos",
}


def get_homeassistant_help() -> str:
    """Retorna ajuda dos comandos do Home Assistant"""
    lines = ["🏠 *Comandos Casa Inteligente:*\n"]
    for cmd, desc in HOMEASSISTANT_COMMANDS.items():
        lines.append(f"`{cmd}` - {desc}")
    return "\n".join(lines)


def _find_entity(
    ha: HomeAssistantAPI, search: str, domain: str = None
) -> Optional[Dict]:
    """
    Encontra uma entidade pelo nome ou ID

    Args:
        ha: Cliente Home Assistant
        search: Termo de busca (nome ou ID)
        domain: Domínio para filtrar (light, switch, etc.)
    """
    search_lower = search.lower().replace(" ", "_").replace("-", "_")

    # Buscar em todos os dispositivos ou por domínio
    if domain:
        devices = ha.get_devices_by_domain(domain)
    else:
        devices = ha.get_states()

    # Busca exata por entity_id
    for d in devices:
        entity_id = d.get("entity_id", "")
        if search_lower in entity_id.lower():
            return d

    # Busca por nome amigável
    for d in devices:
        name = ha.get_friendly_name(d).lower()
        if search_lower in name.replace(" ", "_"):
            return d

    # Busca parcial
    for d in devices:
        entity_id = d.get("entity_id", "")
        name = ha.get_friendly_name(d).lower()
        if any(part in name or part in entity_id for part in search_lower.split("_")):
            return d

    return None


def _format_device_list(devices: List[Dict], ha: HomeAssistantAPI) -> str:
    """Formata lista de dispositivos para exibição"""
    if not devices:
        return "Nenhum dispositivo encontrado"

    lines = []
    for d in devices:
        entity_id = d.get("entity_id", "")
        name = ha.get_friendly_name(d)
        state = d.get("state", "?")

        # Emoji baseado no estado
        if state in ["on", "home", "playing"]:
            emoji = "🟢"
        elif state in ["off", "not_home", "idle", "paused"]:
            emoji = "⚫"
        elif state == "unavailable":
            emoji = "🔴"
        else:
            emoji = "🔵"

        # Extrair ID curto
        short_id = entity_id.split(".")[-1] if "." in entity_id else entity_id

        lines.append(f"{emoji} *{name}*\n   `{short_id}` → {state}")

    return "\n".join(lines)


async def handle_homeassistant_command(
    command: str, args: str, chat_id: int
) -> Tuple[str, bool]:
    """
    Processa comandos do Home Assistant

    Args:
        command: Comando (casa, luzes, ligar, etc.)
        args: Argumentos do comando
        chat_id: ID do chat

    Returns:
        Tuple[resposta, sucesso]
    """
    if not HA_AVAILABLE:
        return "❌ Integração Home Assistant não disponível", False

    ha = HomeAssistantAPI()
    status = ha.check_connection()

    if status["status"] != "connected":
        if status["status"] == "unauthorized":
            return (
                "⚠️ Home Assistant: Token não configurado\nUse o painel web para configurar",
                False,
            )
        return f"❌ Home Assistant offline: {status['message']}", False

    command = command.lower().strip("/")
    args = args.strip() if args else ""

    try:
        # /casa - Status geral
        if command == "casa":
            summary = ha.summarize_devices()
            config = ha.get_config()

            lines = [
                f"🏠 *{config.get('location_name', 'Casa Inteligente')}*",
                f"📊 Total: {summary['total']} dispositivos\n",
            ]

            # Contar por tipo relevante
            relevant = [
                "light",
                "switch",
                "climate",
                "cover",
                "fan",
                "sensor",
                "binary_sensor",
            ]
            for domain in relevant:
                count = summary["by_domain"].get(domain, 0)
                if count > 0:
                    emoji = {
                        "light": "💡",
                        "switch": "🔌",
                        "climate": "❄️",
                        "cover": "🪟",
                        "fan": "🌀",
                        "sensor": "📊",
                        "binary_sensor": "📡",
                    }.get(domain, "📦")
                    lines.append(f"{emoji} {domain}: {count}")

            # Listar dispositivos ligados
            lights_on = [d for d in ha.get_lights() if d.get("state") == "on"]
            if lights_on:
                lines.append(f"\n💡 *Luzes ligadas:* {len(lights_on)}")
                for l in lights_on[:5]:
                    lines.append(f"  • {ha.get_friendly_name(l)}")
                if len(lights_on) > 5:
                    lines.append(f"  ... e mais {len(lights_on) - 5}")

            return "\n".join(lines), True

        # /luzes - Lista luzes
        elif command == "luzes":
            lights = ha.get_lights()
            if not lights:
                return "💡 Nenhuma luz encontrada", True
            return (
                f"💡 *Luzes ({len(lights)}):*\n\n" + _format_device_list(lights, ha),
                True,
            )

        # /dispositivos - Lista todos
        elif command == "dispositivos":
            if args:
                # Filtrar por domínio
                devices = ha.get_devices_by_domain(args)
                title = f"📦 *{args.title()} ({len(devices)}):*"
            else:
                devices = ha.get_states()[:30]  # Limitar
                title = f"📦 *Dispositivos (mostrando 30 de {len(ha.get_states())}):*"

            if not devices:
                return "Nenhum dispositivo encontrado", True

            return f"{title}\n\n" + _format_device_list(devices, ha), True

        # /ligar - Liga dispositivo
        elif command == "ligar":
            if not args:
                return (
                    "❌ Uso: `/ligar nome_do_dispositivo`\nEx: `/ligar luz_sala`",
                    False,
                )

            device = _find_entity(ha, args)
            if not device:
                return (
                    f"❌ Dispositivo '{args}' não encontrado\nUse `/dispositivos` para ver a lista",
                    False,
                )

            entity_id = device.get("entity_id")
            ha.turn_on(entity_id)

            # Verificar novo estado
            new_state = ha.get_state(entity_id)
            name = ha.get_friendly_name(new_state)
            state = new_state.get("state", "?")

            return f"✅ *{name}* ligado\nEstado: {state}", True

        # /desligar - Desliga dispositivo
        elif command == "desligar":
            if not args:
                return "❌ Uso: `/desligar nome_do_dispositivo`", False

            device = _find_entity(ha, args)
            if not device:
                return f"❌ Dispositivo '{args}' não encontrado", False

            entity_id = device.get("entity_id")
            ha.turn_off(entity_id)

            new_state = ha.get_state(entity_id)
            name = ha.get_friendly_name(new_state)
            state = new_state.get("state", "?")

            return f"✅ *{name}* desligado\nEstado: {state}", True

        # /alternar - Toggle
        elif command == "alternar":
            if not args:
                return "❌ Uso: `/alternar nome_do_dispositivo`", False

            device = _find_entity(ha, args)
            if not device:
                return f"❌ Dispositivo '{args}' não encontrado", False

            entity_id = device.get("entity_id")
            ha.toggle(entity_id)

            new_state = ha.get_state(entity_id)
            name = ha.get_friendly_name(new_state)
            state = new_state.get("state", "?")

            emoji = "🟢" if state == "on" else "⚫"
            return f"{emoji} *{name}* alternado\nEstado: {state}", True

        # /clima - Status ar-condicionado
        elif command == "clima":
            climate_devices = ha.get_climate()
            if not climate_devices:
                return "❄️ Nenhum dispositivo de climatização encontrado", True

            lines = ["❄️ *Climatização:*\n"]
            for c in climate_devices:
                name = ha.get_friendly_name(c)
                state = c.get("state", "?")
                attrs = c.get("attributes", {})

                temp_atual = attrs.get("current_temperature", "?")
                temp_alvo = attrs.get("temperature", "?")
                mode = attrs.get("hvac_mode", state)

                emoji = "🔥" if mode == "heat" else "❄️" if mode == "cool" else "🌀"

                lines.append(f"{emoji} *{name}*")
                lines.append(f"   Estado: {state}")
                lines.append(f"   Temperatura: {temp_atual}°C → {temp_alvo}°C")
                if attrs.get("fan_mode"):
                    lines.append(f"   Ventilador: {attrs['fan_mode']}")

            return "\n".join(lines), True

        # /temperatura - Define temperatura
        elif command == "temperatura":
            if not args:
                return "❌ Uso: `/temperatura 22` ou `/temperatura ar_sala 22`", False

            parts = args.split()
            if len(parts) == 1:
                # Apenas temperatura, usar primeiro clima
                temp = float(parts[0])
                climate_devices = ha.get_climate()
                if not climate_devices:
                    return "❌ Nenhum ar-condicionado encontrado", False
                device = climate_devices[0]
            else:
                # Dispositivo + temperatura
                temp = float(parts[-1])
                device_name = " ".join(parts[:-1])
                device = _find_entity(ha, device_name, "climate")
                if not device:
                    return f"❌ Ar-condicionado '{device_name}' não encontrado", False

            entity_id = device.get("entity_id")
            ha.set_climate_temperature(entity_id, temp)

            name = ha.get_friendly_name(device)
            return f"✅ *{name}*\nTemperatura definida para {temp}°C", True

        # /cena - Ativa cena
        elif command == "cena":
            if not args:
                scenes = ha.get_devices_by_domain("scene")
                if not scenes:
                    return "🎬 Nenhuma cena configurada", True

                lines = ["🎬 *Cenas disponíveis:*\n"]
                for s in scenes:
                    name = ha.get_friendly_name(s)
                    short_id = s.get("entity_id", "").split(".")[-1]
                    lines.append(f"  • `{short_id}` - {name}")
                lines.append("\nUse: `/cena nome_da_cena`")
                return "\n".join(lines), True

            device = _find_entity(ha, args, "scene")
            if not device:
                return f"❌ Cena '{args}' não encontrada", False

            ha.activate_scene(device.get("entity_id"))
            name = ha.get_friendly_name(device)
            return f"🎬 Cena *{name}* ativada!", True

        else:
            return f"❓ Comando desconhecido: {command}", False

    except Exception as e:
        return f"❌ Erro: {str(e)}", False


# Função de conveniência para comandos de texto natural
async def process_natural_command(text: str) -> Optional[Tuple[str, bool]]:
    """
    Processa comandos em linguagem natural

    Exemplos:
    - "ligar luz da sala"
    - "desligar todas as luzes"
    - "temperatura do ar para 22"
    """
    text_lower = text.lower()

    # Padrões de comando
    patterns = [
        (r"lig(ar|ue|a)\s+(.+)", "ligar"),
        (r"deslig(ar|ue|a)\s+(.+)", "desligar"),
        (r"apag(ar|ue|a)\s+(.+)", "desligar"),
        (r"acend(er|a)\s+(.+)", "ligar"),
        (r"temperatura.*?(\d+)", "temperatura"),
        (r"ar.*?(\d+)\s*graus?", "temperatura"),
        (r"cena\s+(.+)", "cena"),
    ]

    import re

    for pattern, command in patterns:
        match = re.search(pattern, text_lower)
        if match:
            args = match.group(2) if len(match.groups()) > 1 else match.group(1)
            return await handle_homeassistant_command(command, args, 0)

    return None


if __name__ == "__main__":
    # Teste
    import asyncio

    async def test():
        print("Testando integração Home Assistant...")
        result, success = await handle_homeassistant_command("casa", "", 0)
        print(result)

    asyncio.run(test())
