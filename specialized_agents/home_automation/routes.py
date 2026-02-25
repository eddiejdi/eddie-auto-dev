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
    """Executa ação direta em um dispositivo — delega ao Home Assistant."""
    agent = _get_agent()
    dev = agent.device_manager.get_device(device_id)
    if not dev:
        raise HTTPException(404, f"Dispositivo não encontrado: {device_id}")

    if not getattr(agent, '_ha', None):
        raise HTTPException(503, "Home Assistant não configurado")

    # Monta comando natural: "ligar Tomada Sala" / "desligar Ventilador"
    action_map = {"on": "ligar", "off": "desligar", "toggle": "alternar"}
    verb = action_map.get(req.action, req.action)
    command = f"{verb} {dev.name}"
    result = await agent._ha.execute_natural_command(command)
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
    """
    Sincroniza dispositivos dinamicamente:
    - Google SDM API (Nest devices) com token auto-refresh
    - Descoberta local via mDNS/Zeroconf (todos na LAN)
    - Google Cast devices (speakers, displays, Chromecasts)
    """
    agent = _get_agent()
    devices = await agent.sync_devices_from_google()
    return {
        "synced": len(devices),
        "devices": [d.to_dict() for d in devices],
        "sources": {
            "total": len(devices),
        },
    }


@router.post("/discover")
async def discover_devices(force: bool = False):
    """
    Descobre dispositivos na rede local e Google Home.
    Retorna dispositivos encontrados SEM registrá-los automaticamente.
    """
    try:
        from specialized_agents.home_automation.google_home_adapter import get_google_home_adapter
        adapter = get_google_home_adapter()
        raw_devices = await adapter.discover_all_devices(force=force)
        return {
            "discovered": len(raw_devices),
            "devices": raw_devices,
        }
    except ImportError:
        raise HTTPException(503, "Google Home adapter não disponível")


@router.get("/auth/setup-url")
async def get_auth_url():
    """
    Gera URL OAuth para (re)autorização com Google SDM/Home.
    O usuário deve visitar a URL, autorizar, e enviar o código para /home/auth/callback.
    """
    try:
        from specialized_agents.home_automation.google_home_adapter import get_google_home_adapter
        adapter = get_google_home_adapter()
        url = adapter.generate_setup_url()
        if not url:
            raise HTTPException(400, "client_id não configurado em google_home_credentials.json")
        return {"auth_url": url, "instructions": "Visite a URL, autorize, copie o código e envie para POST /home/auth/callback"}
    except ImportError:
        raise HTTPException(503, "Google Home adapter não disponível")


@router.post("/auth/callback")
async def auth_callback(code: str):
    """Troca authorization code por tokens. Salva automaticamente."""
    try:
        from specialized_agents.home_automation.google_home_adapter import get_google_home_adapter
        adapter = get_google_home_adapter()
        tokens = await adapter.exchange_auth_code(code)
        return {"success": True, "token_type": tokens.get("token_type"), "expires_in": tokens.get("expires_in")}
    except ImportError:
        raise HTTPException(503, "Google Home adapter não disponível")
    except Exception as exc:
        raise HTTPException(400, f"Falha ao trocar código: {exc}")


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


# ---------------------------------------------------------------------------
# Tuya / Smart Life endpoints
# ---------------------------------------------------------------------------

def _get_tuya():
    """Obtém Tuya adapter (via Google Home adapter)."""
    try:
        from specialized_agents.home_automation.tuya_adapter import get_tuya_adapter
        return get_tuya_adapter()
    except ImportError:
        return None


@router.get("/tuya/devices")
async def tuya_list_devices():
    """Lista dispositivos Tuya descobertos na LAN."""
    tuya = _get_tuya()
    if not tuya:
        raise HTTPException(503, "Tuya adapter não disponível (tinytuya não instalado?)")
    devices = await tuya.discover()
    return {"devices": devices, "count": len(devices)}


@router.post("/tuya/scan")
async def tuya_scan(force: bool = True):
    """Força re-scan de dispositivos Tuya na rede."""
    tuya = _get_tuya()
    if not tuya:
        raise HTTPException(503, "Tuya adapter não disponível")
    devices = await tuya.discover(force=force)
    return {"devices": devices, "count": len(devices), "forced": force}


class TuyaControlRequest(BaseModel):
    tuya_device_id: str = Field(..., description="ID do dispositivo Tuya")
    ip: str = Field(..., description="IP local do dispositivo")
    local_key: str = Field("", description="Chave local de criptografia")
    command: str = Field("status", description="on, off, toggle, status, brightness")
    version: float = Field(3.4, description="Protocolo Tuya (3.4 ou 3.5)")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parâmetros extras")


@router.post("/tuya/control")
async def tuya_control_device(req: TuyaControlRequest):
    """Controla dispositivo Tuya diretamente via LAN."""
    tuya = _get_tuya()
    if not tuya:
        raise HTTPException(503, "Tuya adapter não disponível")
    result = tuya.control_device(
        tuya_device_id=req.tuya_device_id,
        ip=req.ip,
        local_key=req.local_key,
        command=req.command,
        version=req.version,
        params=req.params,
    )
    return result


class TuyaDeviceMapUpdate(BaseModel):
    tuya_device_id: str = Field(..., description="ID do dispositivo Tuya")
    ip: str = Field(..., description="IP local")
    name: str = Field(..., description="Nome amigável")
    local_key: str = Field("", description="Chave local")
    version: float = Field(3.4)


@router.post("/tuya/device-map")
async def tuya_update_device_map(req: TuyaDeviceMapUpdate):
    """Atualiza mapeamento de um dispositivo Tuya (nome, local_key, etc)."""
    tuya = _get_tuya()
    if not tuya:
        raise HTTPException(503, "Tuya adapter não disponível")
    tuya.update_device_map(
        tuya_device_id=req.tuya_device_id,
        ip=req.ip,
        name=req.name,
        local_key=req.local_key,
        version=req.version,
    )
    return {"success": True, "message": f"Device map atualizado: {req.name} ({req.ip})"}


# ---------------------------------------------------------------------------
# Grafana integration — sync para PostgreSQL + controle via URL
# ---------------------------------------------------------------------------

def _get_pg_conn():
    """Obtém conexão PostgreSQL para sync Grafana."""
    import os
    try:
        import psycopg2
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:XWGVuESHh2WG8ASIqzFlNkdnzm3ZPoZt@127.0.0.1:5432/estou_aqui",
        )
        return psycopg2.connect(db_url)
    except Exception:
        return None


@router.post("/grafana/sync")
async def grafana_sync_pg():
    """Sincroniza estado dos devices para PostgreSQL (para Grafana)."""
    import json as _json
    conn = _get_pg_conn()
    if not conn:
        raise HTTPException(503, "PostgreSQL não disponível")

    try:
        agent = _get_agent()
        devices = agent.device_manager.list_devices()
        cur = conn.cursor()

        for dev in devices:
            d = dev.to_dict() if hasattr(dev, "to_dict") else dev
            attrs = d.get("attributes", {})
            cur.execute("""
            INSERT INTO home_devices (id, name, device_type, room, state, category, manufacturer,
                                       ip_address, brightness, temperature, last_updated, attributes,
                                       tuya_device_id, tuya_local_key, tuya_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name, state = EXCLUDED.state, room = EXCLUDED.room,
                brightness = EXCLUDED.brightness, temperature = EXCLUDED.temperature,
                last_updated = NOW(), attributes = EXCLUDED.attributes
            """, (
                d["id"], d["name"], d["device_type"], d["room"], d["state"],
                attrs.get("category", "unknown"), attrs.get("manufacturer", ""),
                attrs.get("host", ""), d.get("brightness"), d.get("temperature"),
                _json.dumps(attrs), attrs.get("tuya_device_id", ""),
                attrs.get("tuya_local_key", ""), attrs.get("tuya_version", 3.4),
            ))

        conn.commit()
        return {"synced": len(devices), "status": "ok"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"Sync falhou: {e}")
    finally:
        conn.close()


@router.get("/grafana/control/{device_id}/{action}")
async def grafana_control_device(device_id: str, action: str):
    """
    Controla dispositivo via URL GET (para Grafana Data Links).
    Ex: GET /home/grafana/control/switch_luz_switch_3/on
    Ações: on, off, toggle, status

    O device_id usa underscores (do PG). Converte para entity_id HA
    buscando na tabela home_devices.
    """
    if action not in ("on", "off", "toggle", "status"):
        raise HTTPException(400, f"Ação inválida: '{action}'. Use on/off/toggle/status")

    # 1. Resolver entity_id a partir do id (underscore) no PG
    conn = _get_pg_conn()
    entity_id = None
    device_name = device_id
    old_state = "unknown"
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT entity_id, name, state FROM home_devices WHERE id = %s",
                (device_id,),
            )
            row = cur.fetchone()
            if row:
                entity_id, device_name, old_state = row
        except Exception:
            pass
        finally:
            conn.close()

    # Fallback: tentar converter underscore → dot (domain_entity → domain.entity)
    if not entity_id:
        parts = device_id.split("_", 1)
        if len(parts) == 2 and parts[0] in ("switch", "light", "fan", "media_player", "sensor", "climate"):
            entity_id = f"{parts[0]}.{parts[1]}"
        else:
            raise HTTPException(404, f"Device '{device_id}' não encontrado no banco")

    # 2. Obter HA adapter
    ha = _get_ha()
    if not ha:
        raise HTTPException(503, "Home Assistant não configurado")

    # 3. Executar ação via HA REST API
    new_state = "unknown"
    success = False
    try:
        if action == "status":
            state_data = await ha.get_entity_state(entity_id)
            new_state = state_data.get("state", "unknown")
            success = True
        elif action == "on":
            await ha.turn_on(entity_id)
            new_state = "on"
            success = True
        elif action == "off":
            await ha.turn_off(entity_id)
            new_state = "off"
            success = True
        elif action == "toggle":
            await ha.toggle(entity_id)
            # Ler estado atualizado
            state_data = await ha.get_entity_state(entity_id)
            new_state = state_data.get("state", "unknown")
            success = True
    except ConnectionError as exc:
        raise HTTPException(503, f"Home Assistant inacessível: {exc}")
    except Exception as exc:
        raise HTTPException(500, f"Erro ao executar '{action}' em {entity_id}: {exc}")

    # 4. Registrar no histórico PG e atualizar estado
    conn = _get_pg_conn()
    if conn and action != "status":
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO home_device_history "
                "(device_id, device_name, action, old_state, new_state, source) "
                "VALUES (%s, %s, %s, %s, %s, 'grafana')",
                (device_id, device_name, action, old_state, new_state),
            )
            cur.execute(
                "UPDATE home_devices SET state=%s, last_updated=NOW() WHERE id=%s",
                (new_state, device_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

    emoji = "✅" if success else "❌"
    return {
        "success": success,
        "device": device_name,
        "entity_id": entity_id,
        "action": action,
        "old_state": old_state,
        "new_state": new_state,
        "message": f"{emoji} {device_name} → {action} ({new_state})",
    }