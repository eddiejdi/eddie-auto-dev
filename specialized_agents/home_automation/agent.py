"""
Google Assistant Agent — controla automações residenciais via Google Home.

Funcionalidades:
- Integração com Google Home Device Access API (SDM)
- Controle de luzes, tomadas, termostatos, câmeras, fechaduras, etc.
- Cenas e rotinas (schedule / evento)
- Comandos por linguagem natural (via LLM local)
- Publicação de eventos no Communication Bus
- Persistência de estado e histórico
"""
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import httpx  # type: ignore
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore

from .device_manager import (
    Device,
    DeviceManager,
    DeviceState,
    DeviceType,
    Routine,
    Scene,
)

# Communication Bus integration
try:
    from specialized_agents.agent_communication_bus import (
        MessageType,
        get_communication_bus,
        log_error,
        log_request,
        log_response,
        log_task_end,
        log_task_start,
    )
    _BUS_OK = True
except ImportError:
    _BUS_OK = False

# Agent Memory integration
try:
    from specialized_agents.agent_memory import get_agent_memory
    _MEMORY_OK = True
except ImportError:
    _MEMORY_OK = False

# Home Assistant adapter
try:
    from specialized_agents.home_automation.ha_adapter import HomeAssistantAdapter
    _HA_OK = True
except ImportError:
    _HA_OK = False

# LLM config
try:
    from specialized_agents.config import LLM_CONFIG
except ImportError:
    LLM_CONFIG = {"base_url": "http://192.168.15.2:11434", "model": "qwen2.5-coder:1.5b"}

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "google_assistant"

GOOGLE_HOME_API_BASE = "https://homegraph.googleapis.com/v1"
GOOGLE_SDM_API_BASE = "https://smartdevicemanagement.googleapis.com/v1"

# Mapeamento tipo SDM → DeviceType
SDM_TYPE_MAP: Dict[str, DeviceType] = {
    "sdm.devices.types.LIGHT": DeviceType.LIGHT,
    "sdm.devices.types.THERMOSTAT": DeviceType.THERMOSTAT,
    "sdm.devices.types.CAMERA": DeviceType.CAMERA,
    "sdm.devices.types.DOORBELL": DeviceType.DOORBELL,
    "sdm.devices.types.LOCK": DeviceType.LOCK,
    "sdm.devices.types.DISPLAY": DeviceType.TV,
    "sdm.devices.types.SPEAKER": DeviceType.SPEAKER,
}

# Mapeamento de comandos em linguagem natural → ações
COMMAND_MAP: Dict[str, Dict[str, Any]] = {
    "ligar": {"state": "on"},
    "ligue": {"state": "on"},
    "liga": {"state": "on"},
    "ativar": {"state": "on"},
    "ative": {"state": "on"},
    "desligar": {"state": "off"},
    "desligue": {"state": "off"},
    "desliga": {"state": "off"},
    "desativar": {"state": "off"},
    "desative": {"state": "off"},
    "acender": {"state": "on"},
    "acenda": {"state": "on"},
    "apagar": {"state": "off"},
    "apague": {"state": "off"},
    "aumentar": {"action": "increase"},
    "aumente": {"action": "increase"},
    "diminuir": {"action": "decrease"},
    "diminua": {"action": "decrease"},
    "trancar": {"state": "on", "device_type": "lock"},
    "tranque": {"state": "on", "device_type": "lock"},
    "destrancar": {"state": "off", "device_type": "lock"},
    "destranque": {"state": "off", "device_type": "lock"},
    "abrir": {"state": "on", "device_type": "curtain"},
    "abra": {"state": "on", "device_type": "curtain"},
    "fechar": {"state": "off", "device_type": "curtain"},
    "feche": {"state": "off", "device_type": "curtain"},
}

# ---------------------------------------------------------------------------
# Agent rules
# ---------------------------------------------------------------------------

AGENT_RULES = {
    "pipeline": {
        "sequence": ["Receber comando", "Interpretar", "Validar dispositivo", "Executar", "Confirmar"],
        "enforce": True,
        "rollback_on_failure": True,
    },
    "token_economy": {
        "prefer_local_llm": True,
        "ollama_url": LLM_CONFIG.get("base_url", "http://192.168.15.2:11434"),
        "cache_results": True,
    },
    "validation": {
        "required_before_delivery": True,
        "never_assume_success": True,
    },
    "communication": {
        "use_bus": True,
        "log_all_actions": True,
    },
    "home_specific": {
        "confirm_destructive_actions": True,  # ex.: destrancar porta
        "log_security_events": True,          # câmeras, fechaduras
        "max_retry_on_failure": 3,
        "timeout_seconds": 15,
    },
}


# ---------------------------------------------------------------------------
# Google Assistant Agent
# ---------------------------------------------------------------------------

class GoogleAssistantAgent:
    """
    Agente especializado em automação residencial via Google Assistant/Home.

    Características:
    - Controle de dispositivos smart home (Google Home ecossistema)
    - Interpretação de comandos em linguagem natural via LLM
    - Cenas e rotinas (schedule / trigger)
    - Publicação de eventos no Communication Bus
    - Memória de decisões para aprendizado
    """

    def __init__(self):
        self.agent_type = AGENT_NAME
        self.device_manager = DeviceManager()
        self._google_token: Optional[str] = os.getenv("GOOGLE_HOME_TOKEN")
        self._google_project_id: Optional[str] = os.getenv("GOOGLE_SDM_PROJECT_ID")
        self._ollama_url = LLM_CONFIG.get("base_url", "http://192.168.15.2:11434")
        self._ollama_model = LLM_CONFIG.get("model", "qwen2.5-coder:1.5b")
        try:
            self._memory = get_agent_memory(AGENT_NAME) if _MEMORY_OK else None
        except Exception:
            self._memory = None
        self._bus = get_communication_bus() if _BUS_OK else None
        self._initialized = False

        # Home Assistant backend (preferido sobre SDM)
        self._ha: Optional[HomeAssistantAdapter] = None
        if _HA_OK and os.getenv("HOME_ASSISTANT_TOKEN"):
            self._ha = HomeAssistantAdapter()
            logger.info("🏠 Home Assistant adapter configurado")

        logger.info("🏠 GoogleAssistantAgent criado (devices: %d, ha=%s)",
                     len(self.device_manager.devices), self._ha is not None)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Google Assistant Home Agent"

    @property
    def capabilities(self) -> List[str]:
        return [
            "Controle de luzes (ligar/desligar, brilho, temperatura de cor)",
            "Controle de tomadas/plugs inteligentes",
            "Termostatos e ar-condicionado",
            "Fechaduras inteligentes (trancar/destrancar)",
            "Câmeras e doorbells (snapshot, stream)",
            "Speakers e TVs (volume, reproduzir, pausar)",
            "Ventiladores e cortinas",
            "Cenas (ex.: 'Boa noite', 'Filme', 'Saindo de casa')",
            "Rotinas agendadas (cron / trigger por evento)",
            "Comandos por linguagem natural (PT-BR)",
            "Integração Google Home / Smart Device Management API",
            "Histórico de comandos e estados",
        ]

    # ------------------------------------------------------------------
    # Init / Sync
    # ------------------------------------------------------------------

    async def initialize(self):
        """Inicializa o agente e sincroniza dispositivos."""
        if self._initialized:
            return
        if self._google_token and self._google_project_id:
            await self.sync_devices_from_google()
        self._initialized = True
        logger.info("🏠 GoogleAssistantAgent inicializado — %d dispositivos",
                     len(self.device_manager.devices))

    async def sync_devices_from_google(self) -> List[Device]:
        """
        Sincroniza dispositivos do Google Smart Device Management API.
        Requer GOOGLE_HOME_TOKEN e GOOGLE_SDM_PROJECT_ID.
        """
        if not self._google_token or not self._google_project_id:
            logger.warning("Google Home token ou project ID não configurados")
            return []

        url = f"{GOOGLE_SDM_API_BASE}/enterprises/{self._google_project_id}/devices"
        headers = {"Authorization": f"Bearer {self._google_token}"}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            synced: List[Device] = []
            for raw_device in data.get("devices", []):
                dev = self._parse_google_device(raw_device)
                if dev:
                    self.device_manager.register_device(dev)
                    synced.append(dev)

            self._bus_publish("sync_complete", {
                "devices_synced": len(synced),
                "timestamp": datetime.utcnow().isoformat(),
            })
            logger.info("Sincronizados %d dispositivos do Google Home", len(synced))
            return synced

        except Exception as exc:
            logger.error("Erro ao sincronizar Google Home: %s", exc)
            self._bus_publish("sync_error", {"error": str(exc)})
            return []

    def _parse_google_device(self, raw: Dict[str, Any]) -> Optional[Device]:
        """Converte device da API Google SDM para modelo interno."""
        device_name = raw.get("name", "")
        device_type_str = raw.get("type", "")
        traits = raw.get("traits", {})
        parent_relations = raw.get("parentRelations", [])

        room = "default"
        if parent_relations:
            room_name = parent_relations[0].get("displayName", "default")
            room = room_name

        display_name = traits.get("sdm.devices.traits.Info", {}).get("customName", device_name.split("/")[-1])
        device_type = SDM_TYPE_MAP.get(device_type_str, DeviceType.CUSTOM)

        # Extrair estado
        state = DeviceState.UNKNOWN
        brightness = None
        temperature = None

        if "sdm.devices.traits.OnOff" in traits:
            on = traits["sdm.devices.traits.OnOff"].get("on", False)
            state = DeviceState.ON if on else DeviceState.OFF

        if "sdm.devices.traits.Brightness" in traits:
            brightness = int(traits["sdm.devices.traits.Brightness"].get("brightness", 0))

        if "sdm.devices.traits.Temperature" in traits:
            temperature = traits["sdm.devices.traits.Temperature"].get("ambientTemperatureCelsius")

        return Device(
            id=device_name.split("/")[-1],
            name=display_name,
            device_type=device_type,
            room=room,
            state=state,
            brightness=brightness,
            temperature=temperature,
            google_device_id=device_name,
        )

    # ------------------------------------------------------------------
    # Natural Language Command Processing
    # ------------------------------------------------------------------

    async def process_command(self, command: str) -> Dict[str, Any]:
        """
        Processa um comando em linguagem natural.
        Ex.: 'Apagar as luzes da sala', 'Ligar ar-condicionado do quarto a 22 graus'
        """
        task_id = f"home_{uuid.uuid4().hex[:8]}"
        if _BUS_OK:
            log_task_start(AGENT_NAME, task_id, f"home_command: {command[:80]}")

        try:
            # Se Home Assistant disponível, usar como backend principal
            if self._ha:
                try:
                    result = await self._ha.execute_natural_command(command)
                    if _BUS_OK:
                        log_task_end(AGENT_NAME, task_id, result.get("success", False))
                    self._bus_publish("command_executed", result)
                    return result
                except Exception as ha_err:
                    logger.warning("HA falhou (%s), fallback p/ parse local", ha_err)
            # 1. Interpretar comando via LLM
            parsed = await self._interpret_command(command)

            if not parsed or not parsed.get("action"):
                return {"success": False, "error": "Não foi possível interpretar o comando", "raw": command}

            # 2. Identificar dispositivo(s)
            devices = self._resolve_devices(parsed)

            if not devices:
                return {
                    "success": False,
                    "error": f"Dispositivo não encontrado: {parsed.get('target', 'desconhecido')}",
                    "parsed": parsed,
                }

            # 3. Executar ação
            results = []
            for dev in devices:
                result = await self._execute_action(dev, parsed)
                results.append(result)

            # 4. Registrar na memória
            if self._memory:
                try:
                    self._memory.record_decision(
                        agent_name=AGENT_NAME,
                        application="home_automation",
                        component=parsed.get("target", "unknown"),
                        error_type="",
                        error_message="",
                        decision_type="command",
                        decision=command,
                        confidence=parsed.get("confidence", 0.8),
                        context={"parsed": parsed, "results": results},
                    )
                except Exception:
                    pass

            success = all(r.get("success") for r in results)
            response = {
                "success": success,
                "command": command,
                "parsed": parsed,
                "devices_affected": len(results),
                "results": results,
                "timestamp": datetime.utcnow().isoformat(),
            }

            if _BUS_OK:
                log_task_end(AGENT_NAME, task_id, success)

            self._bus_publish("command_executed", response)
            return response

        except Exception as exc:
            logger.error("Erro ao processar comando '%s': %s", command, exc)
            if _BUS_OK:
                log_error(AGENT_NAME, str(exc), {"command": command})
            return {"success": False, "error": str(exc), "command": command}

    async def _interpret_command(self, command: str) -> Dict[str, Any]:
        """
        Usa LLM local para interpretar comando em linguagem natural.
        Retorna JSON com: action, target (dispositivo/room), params.
        """
        # Tentativa rápida com regras locais
        quick = self._quick_parse(command)
        if quick:
            return quick

        # Fallback: LLM
        prompt = f"""Interprete o comando de automação residencial abaixo e retorne APENAS JSON válido.

Comando: "{command}"

Retorne JSON com:
- "action": string (on, off, set_brightness, set_temperature, lock, unlock, open, close, set_volume, activate_scene)
- "target": string (nome do dispositivo ou cômodo)
- "device_type": string (light, switch, thermostat, lock, camera, speaker, tv, fan, plug, curtain, ac, vacuum)
- "params": object (brightness: 0-100, temperature: number, volume: 0-100, color: string, scene: string)
- "confidence": float 0-1

Responda APENAS com JSON, sem explicações."""

        try:
            if httpx is None:
                raise ImportError("httpx not available")
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self._ollama_url}/api/generate",
                    json={
                        "model": self._ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 200},
                    },
                )
                resp.raise_for_status()
                text = resp.json().get("response", "")

            # Extrair JSON do texto
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)

        except Exception as exc:
            logger.warning("LLM interpretation falhou: %s — usando parse simples", exc)
            return self._quick_parse(command) or {}

    def _quick_parse(self, command: str) -> Optional[Dict[str, Any]]:
        """Parse rápido baseado em regras para comandos simples."""
        cmd_lower = command.lower().strip()

        action = None
        for keyword, mapping in COMMAND_MAP.items():
            if keyword in cmd_lower:
                action = mapping.get("state") or mapping.get("action")
                break

        if not action:
            return None

        # Tentar encontrar o dispositivo pela menção
        target = None
        device_type = None
        for dev in self.device_manager.devices.values():
            if dev.name.lower() in cmd_lower or dev.id.lower() in cmd_lower:
                target = dev.name
                device_type = dev.device_type.value
                break

        # Tentar encontrar por room
        if not target:
            for room in self.device_manager.list_rooms():
                if room.lower() in cmd_lower:
                    target = room
                    break

        # Extrair parâmetros numéricos
        params: Dict[str, Any] = {}
        import re
        numbers = re.findall(r"(\d+)", cmd_lower)
        if numbers:
            val = int(numbers[-1])
            if "grau" in cmd_lower or "temperatura" in cmd_lower or "°" in cmd_lower:
                params["temperature"] = val
                action = "set_temperature" if action in ("on", "off") else action
            elif "brilho" in cmd_lower or "%" in cmd_lower:
                params["brightness"] = min(val, 100)
                action = "set_brightness" if action in ("on", "off") else action
            elif "volume" in cmd_lower:
                params["volume"] = min(val, 100)
                action = "set_volume" if action in ("on", "off") else action

        return {
            "action": action,
            "target": target or "desconhecido",
            "device_type": device_type,
            "params": params,
            "confidence": 0.7 if target else 0.4,
        }

    def _resolve_devices(self, parsed: Dict[str, Any]) -> List[Device]:
        """Resolve quais dispositivos afetados pelo comando."""
        target = (parsed.get("target") or "").lower()
        dtype_str = parsed.get("device_type")

        # Match exato por nome
        for dev in self.device_manager.devices.values():
            if dev.name.lower() == target or dev.id.lower() == target:
                return [dev]

        # Match por room (retorna todos do room)
        room_devices = [d for d in self.device_manager.devices.values() if d.room.lower() == target]
        if room_devices:
            if dtype_str:
                try:
                    dtype = DeviceType(dtype_str)
                    filtered = [d for d in room_devices if d.device_type == dtype]
                    if filtered:
                        return filtered
                except ValueError:
                    pass
            return room_devices

        # Match parcial por nome
        for dev in self.device_manager.devices.values():
            if target in dev.name.lower():
                return [dev]

        return []

    async def _execute_action(self, device: Device, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Executa ação em um dispositivo."""
        action = parsed.get("action", "")
        params = parsed.get("params", {})

        try:
            # Ações que alteram estado
            if action in ("on", "off"):
                new_state = DeviceState.ON if action == "on" else DeviceState.OFF
                self.device_manager.set_device_state(device.id, new_state)

                # Enviar para Google Home API se disponível
                if device.google_device_id and self._google_token:
                    await self._send_google_command(device, action, params)

                return {
                    "success": True,
                    "device": device.name,
                    "action": action,
                    "new_state": new_state.value,
                }

            elif action == "set_brightness":
                brightness = params.get("brightness", 50)
                self.device_manager.set_device_state(
                    device.id, DeviceState.ON, brightness=brightness
                )
                if device.google_device_id and self._google_token:
                    await self._send_google_command(device, action, {"brightness": brightness})
                return {"success": True, "device": device.name, "action": action, "brightness": brightness}

            elif action == "set_temperature":
                temp = params.get("temperature", 22)
                self.device_manager.set_device_state(
                    device.id, DeviceState.ON, target_temperature=temp
                )
                if device.google_device_id and self._google_token:
                    await self._send_google_command(device, action, {"temperature": temp})
                return {"success": True, "device": device.name, "action": action, "temperature": temp}

            elif action == "set_volume":
                vol = params.get("volume", 50)
                self.device_manager.set_device_state(
                    device.id, DeviceState.ON, volume=vol
                )
                return {"success": True, "device": device.name, "action": action, "volume": vol}

            elif action in ("lock", "unlock"):
                new_state = DeviceState.ON if action == "lock" else DeviceState.OFF
                self.device_manager.set_device_state(device.id, new_state)
                if device.google_device_id and self._google_token:
                    await self._send_google_command(device, action, {})
                return {"success": True, "device": device.name, "action": action}

            elif action in ("open", "close"):
                new_state = DeviceState.ON if action == "open" else DeviceState.OFF
                self.device_manager.set_device_state(device.id, new_state)
                return {"success": True, "device": device.name, "action": action}

            elif action == "activate_scene":
                scene_name = params.get("scene", "")
                for s in self.device_manager.scenes.values():
                    if s.name.lower() == scene_name.lower():
                        results = self.device_manager.activate_scene(s.id)
                        return {"success": True, "scene": s.name, "results": results}
                return {"success": False, "error": f"Cena '{scene_name}' não encontrada"}

            else:
                return {"success": False, "device": device.name, "error": f"Ação desconhecida: {action}"}

        except Exception as exc:
            logger.error("Erro ao executar %s em %s: %s", action, device.name, exc)
            return {"success": False, "device": device.name, "error": str(exc)}

    async def _send_google_command(self, device: Device, action: str, params: Dict[str, Any]):
        """Envia comando para Google Smart Device Management API."""
        if not self._google_token or not device.google_device_id:
            return

        # Mapeamento de ações para traits SDM
        trait_commands = {
            "on": ("sdm.devices.commands.OnOff.SetOnOff", {"on": True}),
            "off": ("sdm.devices.commands.OnOff.SetOnOff", {"on": False}),
            "set_brightness": ("sdm.devices.commands.Brightness.SetBrightness",
                               {"brightness": params.get("brightness", 50)}),
            "set_temperature": ("sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
                                {"heatCelsius": params.get("temperature", 22)}),
            "lock": ("sdm.devices.commands.LockUnlock.SetLock", {"lock": True}),
            "unlock": ("sdm.devices.commands.LockUnlock.SetLock", {"lock": False}),
        }

        if action not in trait_commands:
            logger.warning("Ação '%s' não mapeada para SDM commands", action)
            return

        command_name, command_params = trait_commands[action]
        url = f"{GOOGLE_SDM_API_BASE}/{device.google_device_id}:executeCommand"
        headers = {"Authorization": f"Bearer {self._google_token}"}
        body = {"command": command_name, "params": command_params}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                logger.info("Google SDM command OK: %s → %s", action, device.name)
        except Exception as exc:
            logger.error("Google SDM command falhou: %s → %s: %s", action, device.name, exc)

    # ------------------------------------------------------------------
    # Scene & Routine helpers
    # ------------------------------------------------------------------

    async def create_scene(self, name: str, actions: List[Dict[str, Any]]) -> Scene:
        scene = Scene(id=f"scene_{uuid.uuid4().hex[:8]}", name=name, actions=actions)
        self.device_manager.create_scene(scene)
        self._bus_publish("scene_created", {"scene": name, "actions_count": len(actions)})
        return scene

    async def activate_scene(self, scene_id: str) -> List[Dict[str, Any]]:
        results = self.device_manager.activate_scene(scene_id)
        self._bus_publish("scene_activated", {"scene_id": scene_id, "results": results})
        return results

    async def create_routine(self, name: str, trigger: str,
                             actions: List[Dict[str, Any]]) -> Routine:
        routine = Routine(
            id=f"routine_{uuid.uuid4().hex[:8]}",
            name=name,
            trigger=trigger,
            actions=actions,
        )
        self.device_manager.create_routine(routine)
        self._bus_publish("routine_created", {"routine": name, "trigger": trigger})
        return routine

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Retorna status geral do sistema de automação."""
        stats = self.device_manager.stats()
        stats["agent"] = self.name
        stats["google_connected"] = bool(self._google_token and self._google_project_id)
        stats["capabilities"] = self.capabilities
        return stats

    def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        dev = self.device_manager.get_device(device_id)
        return dev.to_dict() if dev else None

    def get_room_status(self, room: str) -> List[Dict[str, Any]]:
        devices = self.device_manager.list_devices(room=room)
        return [d.to_dict() for d in devices]

    def get_command_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.device_manager.command_history[-limit:]

    # ------------------------------------------------------------------
    # Bus publish helper
    # ------------------------------------------------------------------

    def _bus_publish(self, event_type: str, data: Dict[str, Any]):
        if self._bus:
            try:
                self._bus.publish(
                    MessageType.REQUEST,
                    AGENT_NAME,
                    "broadcast",
                    {"event": event_type, **data},
                    metadata={"agent": AGENT_NAME},
                )
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_agent_instance: Optional[GoogleAssistantAgent] = None


def get_google_assistant_agent() -> GoogleAssistantAgent:
    """Retorna instância singleton do Google Assistant Agent."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = GoogleAssistantAgent()
    return _agent_instance
