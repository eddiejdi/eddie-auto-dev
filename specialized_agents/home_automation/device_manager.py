"""
Device Manager — modelos e controle de dispositivos smart home.
Abstrai tipos de dispositivos, estados e grupos (rooms / scenes).
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DeviceType(str, Enum):
    LIGHT = "light"
    SWITCH = "switch"
    THERMOSTAT = "thermostat"
    LOCK = "lock"
    CAMERA = "camera"
    SPEAKER = "speaker"
    TV = "tv"
    FAN = "fan"
    PLUG = "plug"
    SENSOR = "sensor"
    VACUUM = "vacuum"
    CURTAIN = "curtain"
    AC = "air_conditioner"
    GARAGE = "garage_door"
    DOORBELL = "doorbell"
    CUSTOM = "custom"


class DeviceState(str, Enum):
    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"
    OFFLINE = "offline"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Device:
    """Representação de um dispositivo smart home."""
    id: str
    name: str
    device_type: DeviceType
    room: str = "default"
    state: DeviceState = DeviceState.UNKNOWN
    brightness: Optional[int] = None          # 0-100  (luzes)
    color_temp: Optional[int] = None          # kelvin (luzes)
    temperature: Optional[float] = None       # °C     (termostatos / sensores)
    target_temperature: Optional[float] = None
    humidity: Optional[float] = None          # %
    volume: Optional[int] = None              # 0-100  (speakers / TVs)
    attributes: Dict[str, Any] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    google_device_id: Optional[str] = None    # ID no ecossistema Google

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "device_type": self.device_type.value,
            "room": self.room,
            "state": self.state.value,
            "brightness": self.brightness,
            "color_temp": self.color_temp,
            "temperature": self.temperature,
            "target_temperature": self.target_temperature,
            "humidity": self.humidity,
            "volume": self.volume,
            "attributes": self.attributes,
            "last_updated": self.last_updated.isoformat(),
            "google_device_id": self.google_device_id,
        }


@dataclass
class Scene:
    """Cena (ex.: 'Noite', 'Filme', 'Saindo de casa')."""
    id: str
    name: str
    actions: List[Dict[str, Any]] = field(default_factory=list)
    # Cada ação: {"device_id": "...", "command": "...", "params": {...}}


@dataclass
class Routine:
    """Rotina agendada (Cron-like ou por evento)."""
    id: str
    name: str
    trigger: str  # cron expression ou evento ("sunset", "motion_detected")
    actions: List[Dict[str, Any]] = field(default_factory=list)
    enabled: bool = True


# ---------------------------------------------------------------------------
# Device Manager
# ---------------------------------------------------------------------------

class DeviceManager:
    """
    Gerencia o inventário de dispositivos, cenas e rotinas.
    Persiste estado em JSON local e sincroniza via Google Home API.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            try:
                from specialized_agents.config import DATA_DIR
                data_dir = DATA_DIR / "home_automation"
            except ImportError:
                data_dir = Path.home() / ".eddie" / "home_automation"
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._devices_file = self._data_dir / "devices.json"
        self._scenes_file = self._data_dir / "scenes.json"
        self._routines_file = self._data_dir / "routines.json"
        self._history_file = self._data_dir / "command_history.json"

        self.devices: Dict[str, Device] = {}
        self.scenes: Dict[str, Scene] = {}
        self.routines: Dict[str, Routine] = {}
        self.command_history: List[Dict[str, Any]] = []

        self._load_all()

    # ------ Persistence ---------------------------------------------------

    def _load_all(self):
        self.devices = self._load_devices()
        self.scenes = self._load_scenes()
        self.routines = self._load_routines()
        self.command_history = self._load_history()

    def _load_devices(self) -> Dict[str, Device]:
        if not self._devices_file.exists():
            return {}
        try:
            raw = json.loads(self._devices_file.read_text())
            devices: Dict[str, Device] = {}
            for d in raw:
                devices[d["id"]] = Device(
                    id=d["id"],
                    name=d["name"],
                    device_type=DeviceType(d.get("device_type", "custom")),
                    room=d.get("room", "default"),
                    state=DeviceState(d.get("state", "unknown")),
                    brightness=d.get("brightness"),
                    color_temp=d.get("color_temp"),
                    temperature=d.get("temperature"),
                    target_temperature=d.get("target_temperature"),
                    humidity=d.get("humidity"),
                    volume=d.get("volume"),
                    attributes=d.get("attributes", {}),
                    google_device_id=d.get("google_device_id"),
                )
            return devices
        except Exception as exc:
            logger.warning("Falha ao carregar devices.json: %s", exc)
            return {}

    def _load_scenes(self) -> Dict[str, Scene]:
        if not self._scenes_file.exists():
            return {}
        try:
            raw = json.loads(self._scenes_file.read_text())
            return {s["id"]: Scene(**s) for s in raw}
        except Exception as exc:
            logger.warning("Falha ao carregar scenes.json: %s", exc)
            return {}

    def _load_routines(self) -> Dict[str, Routine]:
        if not self._routines_file.exists():
            return {}
        try:
            raw = json.loads(self._routines_file.read_text())
            return {r["id"]: Routine(**r) for r in raw}
        except Exception as exc:
            logger.warning("Falha ao carregar routines.json: %s", exc)
            return {}

    def _load_history(self) -> List[Dict[str, Any]]:
        if not self._history_file.exists():
            return []
        try:
            return json.loads(self._history_file.read_text())[-500:]  # últimas 500
        except Exception:
            return []

    def save(self):
        """Persiste estado atual em disco."""
        self._devices_file.write_text(
            json.dumps([d.to_dict() for d in self.devices.values()], indent=2, default=str)
        )
        self._scenes_file.write_text(
            json.dumps([{"id": s.id, "name": s.name, "actions": s.actions}
                        for s in self.scenes.values()], indent=2)
        )
        self._routines_file.write_text(
            json.dumps([{"id": r.id, "name": r.name, "trigger": r.trigger,
                         "actions": r.actions, "enabled": r.enabled}
                        for r in self.routines.values()], indent=2)
        )
        self._history_file.write_text(
            json.dumps(self.command_history[-500:], indent=2, default=str)
        )

    # ------ CRUD Devices ---------------------------------------------------

    def register_device(self, device: Device) -> Device:
        self.devices[device.id] = device
        self.save()
        logger.info("Device registrado: %s (%s) em %s", device.name, device.device_type.value, device.room)
        return device

    def remove_device(self, device_id: str) -> bool:
        if device_id in self.devices:
            del self.devices[device_id]
            self.save()
            return True
        return False

    def get_device(self, device_id: str) -> Optional[Device]:
        return self.devices.get(device_id)

    def list_devices(self, room: Optional[str] = None,
                     device_type: Optional[DeviceType] = None) -> List[Device]:
        result = list(self.devices.values())
        if room:
            result = [d for d in result if d.room.lower() == room.lower()]
        if device_type:
            result = [d for d in result if d.device_type == device_type]
        return result

    def list_rooms(self) -> List[str]:
        return sorted({d.room for d in self.devices.values()})

    # ------ Command execution ---------------------------------------------

    def set_device_state(self, device_id: str, state: DeviceState, **kwargs) -> Optional[Device]:
        """Atualiza estado de um dispositivo localmente."""
        dev = self.devices.get(device_id)
        if not dev:
            return None
        dev.state = state
        for k, v in kwargs.items():
            if hasattr(dev, k):
                setattr(dev, k, v)
        dev.last_updated = datetime.utcnow()
        self._record_command(device_id, "set_state", {"state": state.value, **kwargs})
        self.save()
        return dev

    def _record_command(self, device_id: str, command: str, params: Dict[str, Any]):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "device_id": device_id,
            "command": command,
            "params": params,
        }
        self.command_history.append(entry)

    # ------ Scenes ---------------------------------------------------------

    def create_scene(self, scene: Scene) -> Scene:
        self.scenes[scene.id] = scene
        self.save()
        return scene

    def activate_scene(self, scene_id: str) -> List[Dict[str, Any]]:
        scene = self.scenes.get(scene_id)
        if not scene:
            return []
        results = []
        for action in scene.actions:
            dev_id = action.get("device_id")
            cmd = action.get("command", "set_state")
            params = action.get("params", {})
            if cmd == "set_state" and "state" in params:
                state = DeviceState(params.pop("state"))
                dev = self.set_device_state(dev_id, state, **params)
                results.append({"device_id": dev_id, "success": dev is not None})
            else:
                results.append({"device_id": dev_id, "success": False, "error": "comando desconhecido"})
        return results

    # ------ Routines -------------------------------------------------------

    def create_routine(self, routine: Routine) -> Routine:
        self.routines[routine.id] = routine
        self.save()
        return routine

    def toggle_routine(self, routine_id: str, enabled: bool) -> Optional[Routine]:
        r = self.routines.get(routine_id)
        if r:
            r.enabled = enabled
            self.save()
        return r

    # ------ Stats ----------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        return {
            "total_devices": len(self.devices),
            "rooms": self.list_rooms(),
            "devices_online": sum(1 for d in self.devices.values() if d.state != DeviceState.OFFLINE),
            "devices_offline": sum(1 for d in self.devices.values() if d.state == DeviceState.OFFLINE),
            "scenes": len(self.scenes),
            "routines": len(self.routines),
            "routines_enabled": sum(1 for r in self.routines.values() if r.enabled),
            "commands_executed": len(self.command_history),
        }
