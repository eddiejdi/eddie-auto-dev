"""
SmartLife API - Device Routes
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..app import get_service

router = APIRouter()


# ================== Schemas ==================


class DeviceCommand(BaseModel):
    """Schema para comando de dispositivo."""

    command: str = Field(..., description="Comando: on, off, toggle, dim, color, temp")
    value: Optional[Any] = Field(None, description="Valor opcional (ex: brilho 0-100)")


class DeviceResponse(BaseModel):
    """Schema de resposta de dispositivo."""

    id: str
    name: str
    type: str
    room: Optional[str]
    is_online: bool
    state: Dict[str, Any]


class CommandResult(BaseModel):
    """Schema de resultado de comando."""

    success: bool
    device_id: str
    command: str
    message: Optional[str]
    new_state: Optional[Dict[str, Any]]


# ================== Routes ==================


@router.get("/", response_model=List[Dict[str, Any]])
async def list_devices(
    room: Optional[str] = Query(None, description="Filtrar por cômodo"),
    type: Optional[str] = Query(None, description="Filtrar por tipo"),
    online: Optional[bool] = Query(None, description="Filtrar por status online"),
):
    """
    Lista todos os dispositivos.

    Suporta filtros por:
    - room: Nome do cômodo
    - type: Tipo de dispositivo (light, switch, sensor, etc.)
    - online: Status de conexão (true/false)
    """
    service = get_service()
    devices = await service.get_devices()

    # Aplicar filtros
    if room:
        devices = [d for d in devices if d.get("room", "").lower() == room.lower()]
    if type:
        devices = [d for d in devices if d.get("type", "").lower() == type.lower()]
    if online is not None:
        devices = [d for d in devices if d.get("is_online") == online]

    return devices


@router.get("/{device_id}")
async def get_device(device_id: str):
    """
    Obtém detalhes de um dispositivo específico.

    Args:
        device_id: ID único do dispositivo
    """
    service = get_service()
    device = await service.get_device(device_id)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return device


@router.post("/{device_id}/control")
async def control_device(device_id: str, cmd: DeviceCommand):
    """
    Envia comando para um dispositivo.

    Comandos suportados:
    - on: Liga o dispositivo
    - off: Desliga o dispositivo
    - toggle: Alterna o estado
    - dim: Define brilho (value: 0-100)
    - color: Define cor (value: hex ou nome)
    - temp: Define temperatura (value: graus)
    """
    service = get_service()

    # Verificar se dispositivo existe
    device = await service.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Executar comando
    result = await service.control_device(
        device_id=device_id, command=cmd.command, value=cmd.value
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=400, detail=result.get("error", "Command failed")
        )

    return result


@router.post("/{device_id}/on")
async def turn_on(device_id: str):
    """Liga um dispositivo."""
    service = get_service()
    result = await service.turn_on(device_id)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.post("/{device_id}/off")
async def turn_off(device_id: str):
    """Desliga um dispositivo."""
    service = get_service()
    result = await service.turn_off(device_id)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.post("/{device_id}/toggle")
async def toggle_device(device_id: str):
    """Alterna o estado de um dispositivo (on/off)."""
    service = get_service()
    result = await service.toggle(device_id)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.post("/{device_id}/brightness/{level}")
async def set_brightness(device_id: str, level: int):
    """
    Define o brilho de uma lâmpada.

    Args:
        device_id: ID do dispositivo
        level: Nível de brilho (0-100)
    """
    if not 0 <= level <= 100:
        raise HTTPException(status_code=400, detail="Brightness must be 0-100")

    service = get_service()
    result = await service.set_brightness(device_id, level)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.post("/{device_id}/color")
async def set_color(device_id: str, color: str):
    """
    Define a cor de uma lâmpada RGB.

    Args:
        device_id: ID do dispositivo
        color: Cor em hex (#FF0000) ou nome (vermelho, azul, etc.)
    """
    service = get_service()
    result = await service.set_color(device_id, color)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.get("/{device_id}/state")
async def get_state(device_id: str):
    """Obtém o estado atual de um dispositivo."""
    service = get_service()
    device = await service.get_device(device_id)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return {
        "device_id": device_id,
        "is_online": device.get("is_online", False),
        "state": device.get("current_state", {}),
    }


@router.get("/rooms/list")
async def list_rooms():
    """Lista todos os cômodos com dispositivos."""
    service = get_service()
    devices = await service.get_devices()

    rooms = {}
    for device in devices:
        room = device.get("room", "Sem cômodo")
        if room not in rooms:
            rooms[room] = {"count": 0, "devices": []}
        rooms[room]["count"] += 1
        rooms[room]["devices"].append(
            {
                "id": device["id"],
                "name": device["name"],
                "type": device.get("type", "unknown"),
            }
        )

    return rooms


@router.get("/types/list")
async def list_types():
    """Lista tipos de dispositivos disponíveis."""
    service = get_service()
    devices = await service.get_devices()

    types = {}
    for device in devices:
        device_type = device.get("type", "unknown")
        if device_type not in types:
            types[device_type] = 0
        types[device_type] += 1

    return types


@router.post("/room/{room}/on")
async def turn_on_room(room: str):
    """Liga todos os dispositivos de um cômodo."""
    service = get_service()
    devices = await service.get_devices()

    results = []
    for device in devices:
        if device.get("room", "").lower() == room.lower():
            result = await service.turn_on(device["id"])
            results.append(
                {
                    "device_id": device["id"],
                    "device_name": device["name"],
                    "success": result.get("success", False),
                }
            )

    return {"room": room, "total_devices": len(results), "results": results}


@router.post("/room/{room}/off")
async def turn_off_room(room: str):
    """Desliga todos os dispositivos de um cômodo."""
    service = get_service()
    devices = await service.get_devices()

    results = []
    for device in devices:
        if device.get("room", "").lower() == room.lower():
            result = await service.turn_off(device["id"])
            results.append(
                {
                    "device_id": device["id"],
                    "device_name": device["name"],
                    "success": result.get("success", False),
                }
            )

    return {"room": room, "total_devices": len(results), "results": results}
