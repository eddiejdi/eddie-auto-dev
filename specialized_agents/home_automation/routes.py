"""
FastAPI routes para o Google Assistant Home Automation Agent.
Endpoints REST para controle de dispositivos, cenas e rotinas.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Import do novo router Gemini/Google Assistant
from .google_assistant import router as google_assistant_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/home", tags=["Home Automation"])

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class DeviceRegisterRequest(BaseModel):
    id: str
    name: str
    device_type: str = "custom"
    room: str = "default"
    google_device_id: Optional[str] = None
    brightness: Optional[int] = None
    temperature: Optional[float] = None
    volume: Optional[int] = None


class CommandRequest(BaseModel):
    command: str = Field(..., description="Comando em linguagem natural, ex.: 'Apagar luzes da sala'")


class DeviceActionRequest(BaseModel):
    device_id: str
    action: str = Field(..., description="on, off, set_brightness, set_temperature, set_volume, lock, unlock")
    params: Dict[str, Any] = Field(default_factory=dict)


class SceneCreateRequest(BaseModel):
    name: str
    actions: List[Dict[str, Any]] = Field(
        ..., description="Lista de ações: [{'device_id': '...', 'command': 'set_state', 'params': {'state': 'on'}}]"
    )


class RoutineCreateRequest(BaseModel):
    name: str
    trigger: str = Field(..., description="Cron expression ou evento (sunset, motion_detected)")
    actions: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_agent():
    from specialized_agents.home_automation.agent import get_google_assistant_agent
    return get_google_assistant_agent()


def _get_ha():
    """Retorna HomeAssistantAdapter se disponível."""
    agent = _get_agent()
    if agent._ha:
        return agent._ha
    return None


# ---------------------------------------------------------------------------
# Health & Status
# ---------------------------------------------------------------------------

@router.get("/status")
async def home_status():
    """Status geral do sistema de automação residencial."""
    agent = _get_agent()
    return agent.get_status()


@router.get("/health")
async def home_health():
    """Healthcheck do agente."""
    agent = _get_agent()
    stats = agent.device_manager.stats()
    return {
        "status": "ok",
        "agent": agent.name,
        "devices": stats["total_devices"],
        "online": stats["devices_online"],
    }


# ---------------------------------------------------------------------------
# Natural Language Command
# ---------------------------------------------------------------------------

@router.post("/command")
async def execute_command(req: CommandRequest):
    """
    Executa comando por linguagem natural.
    Ex.: 'Ligar luzes da sala', 'Ar condicionado do quarto a 22 graus'
    """
    agent = _get_agent()
    result = await agent.process_command(req.command)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result)
    return result


# ---------------------------------------------------------------------------
# Devices CRUD
# ---------------------------------------------------------------------------

@router.get("/devices")
async def list_devices(room: Optional[str] = None, device_type: Optional[str] = None):
    """Lista dispositivos. Filtros opcionais por room e tipo."""
    from specialized_agents.home_automation.device_manager import DeviceType
    agent = _get_agent()
    dtype = None
    if device_type:
        try:
            dtype = DeviceType(device_type)
        except ValueError:
            raise HTTPException(400, f"Tipo inválido: {device_type}")
    devices = agent.device_manager.list_devices(room=room, device_type=dtype)
    return [d.to_dict() for d in devices]


@router.get("/devices/{device_id}")
async def get_device(device_id: str):
    """Retorna detalhes de um dispositivo."""
    agent = _get_agent()
    status = agent.get_device_status(device_id)
    if not status:
        raise HTTPException(404, f"Dispositivo não encontrado: {device_id}")
    return status


@router.post("/devices")
async def register_device(req: DeviceRegisterRequest):
    """Registra um novo dispositivo manualmente."""
    from specialized_agents.home_automation.device_manager import Device, DeviceType, DeviceState
    agent = _get_agent()
    try:
        dtype = DeviceType(req.device_type)
    except ValueError:
        dtype = DeviceType.CUSTOM

    device = Device(
        id=req.id,
        name=req.name,
        device_type=dtype,
        room=req.room,
        google_device_id=req.google_device_id,
        brightness=req.brightness,
        temperature=req.temperature,
        volume=req.volume,
    )
    agent.device_manager.register_device(device)
    return device.to_dict()


@router.delete("/devices/{device_id}")
async def remove_device(device_id: str):
    """Remove um dispositivo."""
    agent = _get_agent()
    ok = agent.device_manager.remove_device(device_id)
    if not ok:
        raise HTTPException(404, f"Dispositivo não encontrado: {device_id}")
    return {"removed": device_id}


@router.post("/devices/{device_id}/action")
async def device_action(device_id: str, req: DeviceActionRequest):
    """Executa ação direta em um dispositivo."""
    from specialized_agents.home_automation.device_manager import DeviceState
    agent = _get_agent()
    dev = agent.device_manager.get_device(device_id)
    if not dev:
        raise HTTPException(404, f"Dispositivo não encontrado: {device_id}")

    parsed = {"action": req.action, "target": dev.name, "params": req.params}
    result = await agent._execute_action(dev, parsed)
    if not result.get("success"):
        raise HTTPException(400, result)
    return result


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------

@router.get("/rooms")
async def list_rooms():
    """Lista todos os cômodos com dispositivos."""
    agent = _get_agent()
    rooms = agent.device_manager.list_rooms()
    return {"rooms": rooms, "count": len(rooms)}


@router.get("/rooms/{room}")
async def room_status(room: str):
    """Status dos dispositivos em um cômodo."""
    agent = _get_agent()
    devices = agent.get_room_status(room)
    return {"room": room, "devices": devices, "count": len(devices)}


# ---------------------------------------------------------------------------
# Scenes
# ---------------------------------------------------------------------------

@router.get("/scenes")
async def list_scenes():
    """Lista todas as cenas."""
    agent = _get_agent()
    return [{"id": s.id, "name": s.name, "actions_count": len(s.actions)}
            for s in agent.device_manager.scenes.values()]


@router.post("/scenes")
async def create_scene(req: SceneCreateRequest):
    """Cria uma nova cena."""
    agent = _get_agent()
    scene = await agent.create_scene(req.name, req.actions)
    return {"id": scene.id, "name": scene.name, "actions": len(scene.actions)}


@router.post("/scenes/{scene_id}/activate")
async def activate_scene(scene_id: str):
    """Ativa uma cena (executa todas as ações)."""
    agent = _get_agent()
    if scene_id not in agent.device_manager.scenes:
        raise HTTPException(404, f"Cena não encontrada: {scene_id}")
    results = await agent.activate_scene(scene_id)
    return {"scene_id": scene_id, "results": results}


# ---------------------------------------------------------------------------
# Routines
# ---------------------------------------------------------------------------

@router.get("/routines")
async def list_routines():
    """Lista todas as rotinas."""
    agent = _get_agent()
    return [{"id": r.id, "name": r.name, "trigger": r.trigger, "enabled": r.enabled}
            for r in agent.device_manager.routines.values()]


@router.post("/routines")
async def create_routine(req: RoutineCreateRequest):
    """Cria uma nova rotina."""
    agent = _get_agent()
    routine = await agent.create_routine(req.name, req.trigger, req.actions)
    return {"id": routine.id, "name": routine.name, "trigger": routine.trigger}


@router.put("/routines/{routine_id}/toggle")
async def toggle_routine(routine_id: str, enabled: bool = True):
    """Habilita/desabilita uma rotina."""
    agent = _get_agent()
    r = agent.device_manager.toggle_routine(routine_id, enabled)
    if not r:
        raise HTTPException(404, f"Rotina não encontrada: {routine_id}")
    return {"id": r.id, "name": r.name, "enabled": r.enabled}


# ---------------------------------------------------------------------------
# Sync & History
# ---------------------------------------------------------------------------

@router.post("/sync")
async def sync_google():
    """Sincroniza dispositivos do Google Home (requer token configurado)."""
    agent = _get_agent()
    devices = await agent.sync_devices_from_google()
    return {"synced": len(devices), "devices": [d.to_dict() for d in devices]}


@router.get("/history")
async def command_history(limit: int = 50):
    """Histórico de comandos executados."""
    agent = _get_agent()
    history = agent.get_command_history(limit=limit)
    return {"count": len(history), "history": history}

# ---------------------------------------------------------------------------
# Home Assistant direct endpoints
# ---------------------------------------------------------------------------

@router.get("/ha/devices")
async def ha_list_devices(domain: Optional[str] = None):
    """Lista dispositivos diretamente do Home Assistant."""
    ha = _get_ha()
    if not ha:
        raise HTTPException(503, "Home Assistant não configurado (HOME_ASSISTANT_TOKEN)")
    devices = await ha.get_devices(domain_filter=domain)
    return {"count": len(devices), "devices": devices}


@router.get("/ha/health")
async def ha_health():
    """Health check do Home Assistant."""
    ha = _get_ha()
    if not ha:
        return {"healthy": False, "error": "Home Assistant não configurado"}
    return await ha.health_check()


class HAControlRequest(BaseModel):
    entity_id: str = Field(..., description="Entity ID do HA, ex: switch.aquario_socket_1")
    action: str = Field("toggle", description="turn_on, turn_off, toggle")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parâmetros extras (brightness, temperature, etc)")


@router.post("/ha/control")
async def ha_control_device(req: HAControlRequest):
    """Controla dispositivo diretamente via Home Assistant."""
    ha = _get_ha()
    if not ha:
        raise HTTPException(503, "Home Assistant não configurado")
    if req.action == "turn_on":
        return await ha.turn_on(req.entity_id, **req.params)
    elif req.action == "turn_off":
        return await ha.turn_off(req.entity_id)
    elif req.action == "toggle":
        return await ha.toggle(req.entity_id)
    else:
        domain = req.entity_id.split(".")[0]
        return await ha.call_service(domain, req.action, {"entity_id": req.entity_id, **req.params})