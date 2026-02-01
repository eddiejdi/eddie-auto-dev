#!/usr/bin/env python3
"""
Integração de Localização com Telegram Bot
Adiciona comandos de localização ao bot existente
"""

import os
import httpx
from datetime import datetime

# Configurações
LOCATION_SERVER = os.getenv("LOCATION_SERVER", "http://localhost:8585")

# Comandos disponíveis
LOCATION_COMMANDS = {
    "/onde": "Mostra sua localização atual",
    "/historico": "Histórico de localizações (últimas 24h)",
    "/eventos": "Eventos de chegada/saída",
    "/geofences": "Lista lugares configurados",
    "/bateria": "Nível de bateria do celular",
}


async def get_current_location() -> dict:
    """Obtém a localização atual do servidor"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{LOCATION_SERVER}/location/current", timeout=10
            )
            return response.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}


async def get_location_history(hours: int = 24) -> dict:
    """Obtém histórico de localizações"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{LOCATION_SERVER}/location/history",
                params={"hours": hours, "limit": 20},
                timeout=10,
            )
            return response.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}


async def get_events(hours: int = 24) -> dict:
    """Obtém eventos de geofencing"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{LOCATION_SERVER}/events", params={"hours": hours}, timeout=10
            )
            return response.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}


async def get_geofences() -> dict:
    """Lista geofences configurados"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{LOCATION_SERVER}/geofences", timeout=10)
            return response.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}


def format_location_message(data: dict) -> str:
    """Formata mensagem de localização para Telegram"""
    if data.get("status") == "error":
        return f"❌ Erro: {data.get('message', 'Desconhecido')}"

    if data.get("status") == "no_data":
        return "📍 Nenhuma localização registrada ainda.\n\nConfigure o OwnTracks no seu celular!"

    loc = data.get("location", {})
    fences = data.get("geofences", [])

    msg = "📍 <b>Localização Atual</b>\n\n"

    # Onde está
    if fences:
        fence_names = [f"{f['icon']} {f['name']}" for f in fences]
        msg += f"📌 Você está em: {', '.join(fence_names)}\n\n"
    else:
        msg += "📌 Você não está em nenhum lugar conhecido\n\n"

    # Coordenadas
    lat = loc.get("latitude")
    lon = loc.get("longitude")
    if lat and lon:
        msg += f"🌐 Coordenadas: {lat:.6f}, {lon:.6f}\n"
        msg += f'🗺️ <a href="https://maps.google.com/?q={lat},{lon}">Ver no Google Maps</a>\n'

    # Precisão
    if loc.get("accuracy"):
        msg += f"🎯 Precisão: ±{loc['accuracy']:.0f}m\n"

    # Bateria
    if loc.get("battery"):
        battery = loc["battery"]
        emoji = "🔋" if battery > 20 else "🪫"
        msg += f"{emoji} Bateria: {battery}%\n"

    # Última atualização
    if loc.get("timestamp"):
        msg += f"\n⏰ Atualizado: {loc['timestamp']}"

    return msg


def format_history_message(data: dict) -> str:
    """Formata histórico para Telegram"""
    if data.get("status") == "error":
        return f"❌ Erro: {data.get('message', 'Desconhecido')}"

    locations = data.get("locations", [])
    if not locations:
        return "📊 Nenhum histórico de localização encontrado."

    msg = "📊 <b>Histórico de Localizações</b>\n"
    msg += f"Últimas {data.get('hours', 24)}h - {len(locations)} registros\n\n"

    for loc in locations[:10]:  # Mostrar últimos 10
        timestamp = loc.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime("%H:%M")
            except:
                time_str = timestamp[:16]
        else:
            time_str = "?"

        lat = loc.get("latitude", 0)
        lon = loc.get("longitude", 0)

        msg += f"• {time_str} - ({lat:.4f}, {lon:.4f})\n"

    if len(locations) > 10:
        msg += f"\n... e mais {len(locations) - 10} registros"

    return msg


def format_events_message(data: dict) -> str:
    """Formata eventos para Telegram"""
    if data.get("status") == "error":
        return f"❌ Erro: {data.get('message', 'Desconhecido')}"

    events = data.get("events", [])
    if not events:
        return "📋 Nenhum evento de entrada/saída registrado nas últimas 24h."

    msg = "📋 <b>Eventos de Localização</b>\n\n"

    for event in events[:15]:
        event_type = event.get("type", "unknown")
        geofence = event.get("geofence", "?")
        timestamp = event.get("timestamp", "")

        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime("%d/%m %H:%M")
            except:
                time_str = timestamp[:16]
        else:
            time_str = "?"

        emoji = "🟢" if event_type == "enter" else "🔴"
        action = "Chegou em" if event_type == "enter" else "Saiu de"

        msg += f"{emoji} {time_str} - {action} {geofence}\n"

    return msg


def format_geofences_message(data: dict) -> str:
    """Formata lista de geofences para Telegram"""
    if data.get("status") == "error":
        return f"❌ Erro: {data.get('message', 'Desconhecido')}"

    fences = data.get("geofences", {})
    if not fences:
        return "📍 Nenhum lugar configurado."

    msg = "📍 <b>Lugares Configurados</b>\n\n"

    for fence_id, fence in fences.items():
        icon = fence.get("icon", "📍")
        name = fence.get("name", fence_id)
        radius = fence.get("radius", 0)
        lat = fence.get("latitude", 0)
        lon = fence.get("longitude", 0)

        msg += f"{icon} <b>{name}</b>\n"
        msg += f"   Raio: {radius}m\n"
        msg += (
            f'   <a href="https://maps.google.com/?q={lat},{lon}">Ver no mapa</a>\n\n'
        )

    return msg


async def handle_location_command(command: str, args: str = "") -> str:
    """Processa comandos de localização"""

    if command in ["/onde", "/location", "/loc", "/where"]:
        data = await get_current_location()
        return format_location_message(data)

    elif command in ["/historico", "/history", "/hist"]:
        hours = 24
        if args:
            try:
                hours = int(args)
            except:
                pass
        data = await get_location_history(hours)
        return format_history_message(data)

    elif command in ["/eventos", "/events"]:
        data = await get_events()
        return format_events_message(data)

    elif command in ["/geofences", "/lugares", "/places"]:
        data = await get_geofences()
        return format_geofences_message(data)

    elif command in ["/bateria", "/battery", "/batt"]:
        data = await get_current_location()
        if data.get("status") == "ok":
            loc = data.get("location", {})
            battery = loc.get("battery")
            if battery is not None:
                emoji = "🔋" if battery > 20 else "🪫"
                return f"{emoji} Bateria: {battery}%"
            return "❓ Informação de bateria não disponível"
        return format_location_message(data)

    return None


# Função para adicionar ao bot principal
def get_location_help() -> str:
    """Retorna ajuda dos comandos de localização"""
    msg = "📍 <b>Comandos de Localização</b>\n\n"
    for cmd, desc in LOCATION_COMMANDS.items():
        msg += f"{cmd} - {desc}\n"
    return msg


if __name__ == "__main__":
    # Teste
    import asyncio

    async def test():
        print("Testando comandos de localização...")

        print("\n/onde:")
        result = await handle_location_command("/onde")
        print(result)

        print("\n/geofences:")
        result = await handle_location_command("/geofences")
        print(result)

    asyncio.run(test())
