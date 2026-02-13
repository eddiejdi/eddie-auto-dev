"""
Executor Tinytuya para controle local de dispositivos.

Suporta:
- Descoberta de dispositivos via broadcast (sem Cloud API)
- Controle local via LAN
- Múltiplos protocolos (v3.1, v3.4, v3.5)

Design:
- Não depende de Cloud API (evita subscription expired)
- Busca local_keys via tinytuya.wizard ou Smart Life export
- Cached por sessão para evitar rescans
"""

import logging
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime, timedelta
import tinytuya

logger = logging.getLogger(__name__)


class TinyTuyaExecutor:
    """Gerenciador de controle local de dispositivos Tuya"""

    def __init__(
        self,
        device_map_file: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ):
        """
        Args:
            device_map_file: Path para arquivo JSON com mapeamento device_id -> {ip, local_key, name}
            cache_dir: Diretório para cachear descoberta
        """
        self.device_map_file = device_map_file or "agent_data/home_automation/device_map.json"
        self.cache_dir = Path(cache_dir or "agent_data/home_automation/.cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache em memória
        self.devices: Dict[str, Dict[str, Any]] = {}
        self.scan_cache: Dict[str, Dict[str, Any]] = {}
        self.last_scan_time: Optional[datetime] = None

        # Carregar mapa de dispositivos
        self._load_device_map()

    def _load_device_map(self):
        """Carrega mapa de dispositivos de arquivo"""
        try:
            with open(self.device_map_file, "r") as f:
                self.devices = json.load(f)
                logger.info(f"Loaded {len(self.devices)} devices from {self.device_map_file}")
        except FileNotFoundError:
            logger.warning(f"Device map file not found: {self.device_map_file}")
            self.devices = {}

    def _save_device_map(self):
        """Salva mapa de dispositivos em arquivo"""
        try:
            Path(self.device_map_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self.device_map_file, "w") as f:
                json.dump(self.devices, f, indent=2)
                logger.info(f"Saved {len(self.devices)} devices to {self.device_map_file}")
        except Exception as e:
            logger.error(f"Failed to save device map: {e}")

    def scan_network(self, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Scanneia rede para descobrir dispositivos Tuya.

        Returns:
            Dict de {device_id: {ip, key, device_name, version, ...}}
        """
        # Check cache (5 min)
        cache_file = self.cache_dir / "scan_cache.json"
        if (
            not force_refresh
            and cache_file.exists()
            and (datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime) < timedelta(minutes=5))
        ):
            with open(cache_file, "r") as f:
                return json.load(f)

        logger.info("[Scan] Iniciando descoberta de dispositivos...")

        try:
            # Usar tinytuya.deviceScan para descobrir devices na rede
            devices = tinytuya.deviceScan()

            if not devices:
                logger.warning("[Scan] Nenhum device descoberto")
                return {}

            logger.info(f"[Scan] Encontrados {len(devices)} devices")

            # Converter para formato interno
            result = {}
            for device_id, device_info in devices.items():
                result[device_id] = {
                    "device_id": device_id,
                    "ip": device_info.get("ip"),
                    "local_key": device_info.get("key", ""),
                    "device_name": device_info.get("name", "Unknown"),
                    "protocol_version": device_info.get("protocol_version", 3.4),
                    "discovered_at": datetime.now().isoformat(),
                }

            # Cachear resultado
            with open(cache_file, "w") as f:
                json.dump(result, f, indent=2)

            return result

        except Exception as e:
            logger.error(f"[Scan] Erro durante descoberta: {e}")
            return {}

    def register_device(
        self,
        device_id: str,
        ip: str,
        local_key: str,
        name: str,
        version: float = 3.4,
    ):
        """Registra device manualmente"""
        self.devices[device_id] = {
            "device_id": device_id,
            "ip": ip,
            "local_key": local_key,
            "name": name,
            "version": version,
            "registered_at": datetime.now().isoformat(),
        }
        self._save_device_map()
        logger.info(f"Registered device: {name} ({device_id}) at {ip}")

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Obtém config de device por ID"""
        return self.devices.get(device_id)

    def list_devices(self) -> List[Dict[str, Any]]:
        """Lista todos os devices registrados"""
        return list(self.devices.values())

    def turn_on(self, device_id: str) -> Dict[str, Any]:
        """Liga dispositivo"""
        return self._execute_command(device_id, "on")

    def turn_off(self, device_id: str) -> Dict[str, Any]:
        """Desliga dispositivo"""
        return self._execute_command(device_id, "off")

    def set_brightness(self, device_id: str, brightness: int) -> Dict[str, Any]:
        """Define brightness (0-100)"""
        brightness = max(0, min(100, brightness))
        return self._execute_command(device_id, "brightness", {"value": brightness})

    def set_temperature(self, device_id: str, temp: float) -> Dict[str, Any]:
        """Define temperatura"""
        return self._execute_command(device_id, "temperature", {"value": round(temp * 10)})

    def get_status(self, device_id: str) -> Dict[str, Any]:
        """Obtém status atual do device"""
        return self._execute_command(device_id, "status")

    def _execute_command(
        self,
        device_id: str,
        command: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executa comando no device via conexão local.

        Args:
            device_id: ID do device
            command: "on", "off", "status", "brightness", "temperature", etc
            params: Parâmetros específicos do comando

        Returns:
            {"success": bool, "result": {...}, "error": str}
        """
        device_config = self.get_device(device_id)
        if not device_config:
            return {
                "success": False,
                "error": f"Device não encontrado: {device_id}",
            }

        try:
            device = tinytuya.OutletDevice(
                dev_id=device_id,
                address=device_config["ip"],
                local_key=device_config.get("local_key", ""),
                version=device_config.get("version", 3.4),
                persist=False,
                port=6668,  # Porta padrão Tuya
            )

            # Executar comando
            if command == "on":
                result = device.turn_on()
            elif command == "off":
                result = device.turn_off()
            elif command == "status":
                result = device.status()
            elif command == "brightness" and params:
                # Usar set_value com DPS específico
                dps = params.get("dps", 2)  # DPS 2 é típico para brightness
                result = device.set_value(dps, params.get("value", 100))
            elif command == "temperature" and params:
                dps = params.get("dps", 4)  # DPS 4 é típico para temperatura
                result = device.set_value(dps, params.get("value", 250))  # Enviar em decisíveis
            else:
                result = device.status()

            # Verificar erro
            if isinstance(result, dict) and "Error" in result:
                return {
                    "success": False,
                    "error": result.get("Error", "Unknown error"),
                    "result": result,
                }

            return {
                "success": True,
                "command": command,
                "device_id": device_id,
                "device_name": device_config["name"],
                "result": result,
            }

        except Exception as e:
            logger.error(f"Error executing {command} on {device_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "device_id": device_id,
            }


# Singleton global
_executor: Optional[TinyTuyaExecutor] = None


def get_executor() -> TinyTuyaExecutor:
    """Obtém executor global"""
    global _executor
    if _executor is None:
        _executor = TinyTuyaExecutor()
    return _executor


def set_executor(executor: TinyTuyaExecutor):
    """Define executor global"""
    global _executor
    _executor = executor
