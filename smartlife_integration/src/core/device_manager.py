"""
Device Manager - Gerenciador de Dispositivos SmartLife
"""

import asyncio
import structlog
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = structlog.get_logger()


# Mapeamento de tipos de dispositivos Tuya
DEVICE_TYPES = {
    "switch": {
        "name": "Tomada/Interruptor",
        "icon": "🔌",
        "commands": ["on", "off", "toggle"],
    },
    "light": {
        "name": "Lâmpada",
        "icon": "💡",
        "commands": ["on", "off", "toggle", "dim", "color"],
    },
    "dimmer": {"name": "Dimmer", "icon": "🔆", "commands": ["on", "off", "dim"]},
    "socket": {"name": "Tomada", "icon": "🔌", "commands": ["on", "off", "toggle"]},
    "power_strip": {"name": "Régua", "icon": "🔌", "commands": ["on", "off", "toggle"]},
    "airconditioner": {
        "name": "Ar Condicionado",
        "icon": "❄️",
        "commands": ["on", "off", "temp", "mode"],
    },
    "heater": {"name": "Aquecedor", "icon": "🔥", "commands": ["on", "off", "temp"]},
    "fan": {"name": "Ventilador", "icon": "🌀", "commands": ["on", "off", "speed"]},
    "humidifier": {
        "name": "Umidificador",
        "icon": "💧",
        "commands": ["on", "off", "level"],
    },
    "cover": {
        "name": "Cortina/Persiana",
        "icon": "🪟",
        "commands": ["open", "close", "stop", "position"],
    },
    "lock": {"name": "Fechadura", "icon": "🔒", "commands": ["lock", "unlock"]},
    "sensor": {"name": "Sensor", "icon": "📡", "commands": []},
    "motion": {"name": "Sensor de Movimento", "icon": "🚶", "commands": []},
    "door": {"name": "Sensor de Porta", "icon": "🚪", "commands": []},
    "temperature": {"name": "Sensor Temperatura", "icon": "🌡️", "commands": []},
    "humidity": {"name": "Sensor Umidade", "icon": "💧", "commands": []},
    "camera": {"name": "Câmera", "icon": "📹", "commands": []},
    "ir_remote": {"name": "Controle IR", "icon": "📱", "commands": ["send_ir"]},
    "thermostat": {"name": "Termostato", "icon": "🌡️", "commands": ["temp", "mode"]},
    "robot_vacuum": {
        "name": "Robô Aspirador",
        "icon": "🤖",
        "commands": ["start", "stop", "dock"],
    },
}

# Mapeamento de cores comuns
COLOR_MAP = {
    "vermelho": "#FF0000",
    "red": "#FF0000",
    "verde": "#00FF00",
    "green": "#00FF00",
    "azul": "#0000FF",
    "blue": "#0000FF",
    "amarelo": "#FFFF00",
    "yellow": "#FFFF00",
    "laranja": "#FFA500",
    "orange": "#FFA500",
    "roxo": "#800080",
    "purple": "#800080",
    "rosa": "#FFC0CB",
    "pink": "#FFC0CB",
    "branco": "#FFFFFF",
    "white": "#FFFFFF",
    "ciano": "#00FFFF",
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
}


class DeviceManager:
    """
    Gerencia todos os dispositivos SmartLife.
    Prioriza controle local, com fallback para cloud.
    """

    def __init__(self, local_client, cloud_client, config: Dict[str, Any]):
        self.local = local_client
        self.cloud = cloud_client
        self.config = config

        # Cache de dispositivos
        self._devices: Dict[str, Dict[str, Any]] = {}
        self._scenes: Dict[str, Dict[str, Any]] = {}

        # Estado
        self._running = False
        self._last_refresh = None

    async def start(self) -> None:
        """Inicia o gerenciador de dispositivos."""
        logger.info("Iniciando Device Manager...")

        # Carregar dispositivos
        await self.refresh_devices()

        # Iniciar polling de estados
        self._running = True
        asyncio.create_task(self._state_polling_loop())

        logger.info(f"Device Manager iniciado com {len(self._devices)} dispositivos")

    async def stop(self) -> None:
        """Para o gerenciador de dispositivos."""
        self._running = False
        logger.info("Device Manager parado")

    async def refresh_devices(self) -> List[Dict[str, Any]]:
        """Atualiza a lista de dispositivos do cloud."""
        try:
            # Buscar do cloud
            cloud_devices = await self.cloud.get_devices() if self.cloud else []

            for device in cloud_devices:
                device_id = device.get("id")
                device_type = self._detect_device_type(device)

                self._devices[device_id] = {
                    "id": device_id,
                    "name": device.get("name", "Dispositivo"),
                    "type": device_type,
                    "type_info": DEVICE_TYPES.get(device_type, DEVICE_TYPES["switch"]),
                    "room": device.get("room", ""),
                    "local_key": device.get("local_key", ""),
                    "ip": device.get("ip", ""),
                    "protocol_version": device.get("version", "3.3"),
                    "is_online": device.get("online", False),
                    "state": {},
                    "last_update": datetime.now().isoformat(),
                }

            # Tentar obter IPs locais
            if self.local:
                local_devices = await self.local.scan_network()
                for local_dev in local_devices:
                    dev_id = local_dev.get("id")
                    if dev_id in self._devices:
                        self._devices[dev_id]["ip"] = local_dev.get("ip", "")

            self._last_refresh = datetime.now()
            logger.info(f"Dispositivos atualizados: {len(self._devices)}")

            return list(self._devices.values())

        except Exception as e:
            logger.error(f"Erro ao atualizar dispositivos: {e}")
            return list(self._devices.values())

    def _detect_device_type(self, device: Dict[str, Any]) -> str:
        """Detecta o tipo do dispositivo baseado nos dados."""
        category = device.get("category", "").lower()
        product_name = device.get("product_name", "").lower()

        # Mapeamento de categorias Tuya
        category_map = {
            "dj": "light",  # Lâmpada
            "dd": "dimmer",  # Dimmer
            "kg": "switch",  # Interruptor
            "cz": "socket",  # Tomada
            "pc": "power_strip",  # Régua
            "kt": "airconditioner",
            "fs": "fan",
            "jsq": "humidifier",
            "cl": "cover",  # Cortina
            "ms": "lock",  # Fechadura
            "pir": "motion",  # Sensor movimento
            "mcs": "door",  # Sensor porta
            "wsdcg": "temperature",
            "sp": "camera",
            "wnykq": "ir_remote",
            "wk": "thermostat",
            "sd": "robot_vacuum",
        }

        if category in category_map:
            return category_map[category]

        # Tentar por nome do produto
        if "lamp" in product_name or "bulb" in product_name or "light" in product_name:
            return "light"
        if "switch" in product_name or "plug" in product_name:
            return "switch"
        if "curtain" in product_name or "blind" in product_name:
            return "cover"
        if "sensor" in product_name:
            return "sensor"

        return "switch"  # Default

    async def get_all_devices(self) -> List[Dict[str, Any]]:
        """Retorna todos os dispositivos."""
        return list(self._devices.values())

    async def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Retorna um dispositivo específico."""
        return self._devices.get(device_id)

    async def get_device_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Busca dispositivo por nome (case-insensitive, parcial)."""
        name_lower = name.lower()

        # Busca exata primeiro
        for device in self._devices.values():
            if device["name"].lower() == name_lower:
                return device

        # Busca parcial
        for device in self._devices.values():
            if name_lower in device["name"].lower():
                return device

        # Busca por room
        for device in self._devices.values():
            room = device.get("room", "").lower()
            if room and name_lower == room:
                return device

        return None

    async def get_device_state(self, device_id: str) -> Dict[str, Any]:
        """Obtém o estado atual de um dispositivo."""
        device = self._devices.get(device_id)
        if not device:
            return {"error": "Dispositivo não encontrado"}

        try:
            # Tentar local primeiro
            if self.local and device.get("ip"):
                state = await self.local.get_status(
                    device_id=device_id,
                    ip=device["ip"],
                    local_key=device["local_key"],
                    version=device["protocol_version"],
                )
                if state:
                    device["state"] = state
                    device["last_update"] = datetime.now().isoformat()
                    return state

            # Fallback para cloud
            if self.cloud:
                state = await self.cloud.get_device_status(device_id)
                if state:
                    device["state"] = state
                    device["last_update"] = datetime.now().isoformat()
                    return state

            return device.get("state", {})

        except Exception as e:
            logger.error(f"Erro ao obter estado de {device_id}: {e}")
            return device.get("state", {})

    async def execute_command(
        self, device_id: str, command: str, value: Any = None
    ) -> Dict[str, Any]:
        """
        Executa um comando em um dispositivo.

        Args:
            device_id: ID do dispositivo ou nome
            command: Comando (on, off, toggle, dim, color, temp, etc.)
            value: Valor opcional
        """
        # Se device_id é um nome, buscar o dispositivo
        device = self._devices.get(device_id)
        if not device:
            device = await self.get_device_by_name(device_id)
            if device:
                device_id = device["id"]

        if not device:
            return {
                "success": False,
                "error": f"Dispositivo '{device_id}' não encontrado",
            }

        logger.info(f"Executando {command} em {device['name']}", value=value)

        try:
            result = None
            use_cloud = True

            # Tentar local primeiro se disponível
            if self.local and device.get("ip"):
                try:
                    result = await self._execute_local(device, command, value)
                    use_cloud = False
                except Exception as e:
                    logger.warning(f"Comando local falhou, tentando cloud: {e}")

            # Fallback ou usar cloud
            if use_cloud and self.cloud:
                result = await self._execute_cloud(device, command, value)

            if result and result.get("success"):
                # Atualizar cache de estado
                await self._update_device_state_cache(device_id, command, value)

            return result or {"success": False, "error": "Nenhum cliente disponível"}

        except Exception as e:
            logger.error(f"Erro ao executar comando: {e}")
            return {"success": False, "error": str(e)}

    async def _execute_local(
        self, device: Dict[str, Any], command: str, value: Any
    ) -> Dict[str, Any]:
        """Executa comando via LAN."""
        return await self.local.send_command(
            device_id=device["id"],
            ip=device["ip"],
            local_key=device["local_key"],
            version=device["protocol_version"],
            command=command,
            value=value,
        )

    async def _execute_cloud(
        self, device: Dict[str, Any], command: str, value: Any
    ) -> Dict[str, Any]:
        """Executa comando via cloud API."""
        # Converter comando para formato Tuya
        commands = self._build_tuya_commands(device, command, value)
        return await self.cloud.send_commands(device["id"], commands)

    def _build_tuya_commands(
        self, device: Dict[str, Any], command: str, value: Any
    ) -> List[Dict[str, Any]]:
        """Constrói comandos no formato Tuya."""
        device_type = device.get("type", "switch")

        if command in ["on", "off"]:
            return [
                {
                    "code": "switch_led" if device_type == "light" else "switch_1",
                    "value": command == "on",
                }
            ]

        if command == "toggle":
            current = device.get("state", {}).get("switch_1", False)
            return [{"code": "switch_1", "value": not current}]

        if command == "dim":
            # Tuya usa 10-1000 para brilho
            brightness = int((value / 100) * 1000) if value else 500
            return [
                {"code": "switch_led", "value": True},
                {"code": "bright_value_v2", "value": max(10, min(1000, brightness))},
            ]

        if command == "color":
            hex_color = (
                COLOR_MAP.get(value.lower(), value) if isinstance(value, str) else value
            )
            hsv = self._hex_to_hsv(hex_color)
            return [
                {"code": "switch_led", "value": True},
                {"code": "work_mode", "value": "colour"},
                {"code": "colour_data_v2", "value": hsv},
            ]

        if command == "temp":
            return [
                {"code": "switch", "value": True},
                {"code": "temp_set", "value": int(value)},
            ]

        if command in ["open", "close", "stop"]:
            control_map = {"open": "open", "close": "close", "stop": "stop"}
            return [{"code": "control", "value": control_map[command]}]

        if command == "position":
            return [{"code": "percent_control", "value": int(value)}]

        return []

    def _hex_to_hsv(self, hex_color: str) -> str:
        """Converte cor hex para formato HSV Tuya."""
        import colorsys

        hex_color = hex_color.lstrip("#")
        r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

        # Formato Tuya: {"h":0-360,"s":0-1000,"v":0-1000}
        return f'{{"h":{int(h * 360)},"s":{int(s * 1000)},"v":{int(v * 1000)}}}'

    async def _update_device_state_cache(
        self, device_id: str, command: str, value: Any
    ) -> None:
        """Atualiza o cache de estado após comando."""
        if device_id in self._devices:
            device = self._devices[device_id]

            if command == "on":
                device["state"]["is_on"] = True
            elif command == "off":
                device["state"]["is_on"] = False
            elif command == "toggle":
                device["state"]["is_on"] = not device["state"].get("is_on", False)
            elif command == "dim":
                device["state"]["brightness"] = value
            elif command == "color":
                device["state"]["color"] = value
            elif command == "temp":
                device["state"]["temperature"] = value

            device["last_update"] = datetime.now().isoformat()

    async def _state_polling_loop(self) -> None:
        """Loop para atualizar estados periodicamente."""
        poll_interval = self.config.get("local", {}).get("scan_interval", 60)

        while self._running:
            try:
                for device_id in list(self._devices.keys()):
                    if not self._running:
                        break
                    await self.get_device_state(device_id)
                    await asyncio.sleep(1)  # Evitar sobrecarga

            except Exception as e:
                logger.error(f"Erro no polling de estados: {e}")

            await asyncio.sleep(poll_interval)

    # ========== Cenas ==========

    async def get_scenes(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista todas as cenas."""
        # TODO: Buscar cenas do banco de dados
        return list(self._scenes.values())

    async def execute_scene(
        self, scene_id: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Executa uma cena."""
        scene = self._scenes.get(scene_id)
        if not scene:
            return {"success": False, "error": "Cena não encontrada"}

        results = []
        for action in scene.get("actions", []):
            result = await self.execute_command(
                device_id=action["device_id"],
                command=action["command"],
                value=action.get("value"),
            )
            results.append(result)

        success = all(r.get("success", False) for r in results)
        return {
            "success": success,
            "scene": scene["name"],
            "actions_executed": len(results),
            "results": results,
        }

    async def create_scene(
        self, name: str, actions: List[Dict[str, Any]], user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cria uma nova cena."""
        import uuid

        scene_id = str(uuid.uuid4())[:8]
        scene = {
            "id": scene_id,
            "name": name,
            "actions": actions,
            "created_by": user_id,
            "created_at": datetime.now().isoformat(),
        }

        self._scenes[scene_id] = scene
        # TODO: Persistir no banco de dados

        return {"success": True, "scene_id": scene_id, "scene": scene}
