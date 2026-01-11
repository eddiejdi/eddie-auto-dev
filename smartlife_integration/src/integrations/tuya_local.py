"""
Tuya Local Client - Integração via LAN usando TinyTuya
"""
import asyncio
import json
import structlog
from typing import Optional, Dict, Any, List
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

logger = structlog.get_logger()

# TinyTuya é síncrono, então usamos executor
executor = ThreadPoolExecutor(max_workers=5)


class TuyaLocalClient:
    """
    Cliente para comunicação local (LAN) com dispositivos Tuya.
    Usa TinyTuya para comunicação direta sem cloud.
    """
    
    def __init__(
        self,
        devices_file: str = "config/devices.json",
        scan_interval: int = 60
    ):
        self.devices_file = Path(devices_file)
        self.scan_interval = scan_interval
        
        # Cache de dispositivos locais
        self._devices: Dict[str, Dict[str, Any]] = {}
        
        # Cache de conexões TinyTuya
        self._connections: Dict[str, Any] = {}
        
        self._running = False
        self._is_connected = False
    
    @property
    def is_connected(self) -> bool:
        return self._is_connected
    
    async def start(self) -> None:
        """Inicia o cliente local."""
        logger.info("Iniciando Tuya Local Client...")
        
        # Carregar devices.json
        await self._load_devices_file()
        
        # Scan inicial
        await self.scan_network()
        
        self._running = True
        self._is_connected = True
        
        logger.info(f"Tuya Local Client iniciado com {len(self._devices)} dispositivos")
    
    async def stop(self) -> None:
        """Para o cliente local."""
        self._running = False
        self._is_connected = False
        
        # Fechar conexões
        for device_id in list(self._connections.keys()):
            await self._close_connection(device_id)
        
        logger.info("Tuya Local Client parado")
    
    async def _load_devices_file(self) -> None:
        """Carrega arquivo devices.json gerado pelo TinyTuya wizard."""
        if not self.devices_file.exists():
            logger.warning(f"Arquivo {self.devices_file} não encontrado. Execute: python -m tinytuya wizard")
            return
        
        try:
            with open(self.devices_file) as f:
                devices = json.load(f)
            
            for device in devices:
                device_id = device.get("id")
                if device_id:
                    self._devices[device_id] = {
                        "id": device_id,
                        "name": device.get("name", ""),
                        "ip": device.get("ip", ""),
                        "local_key": device.get("key", ""),
                        "version": device.get("version", "3.3"),
                        "category": device.get("category", ""),
                        "product_name": device.get("product_name", "")
                    }
            
            logger.info(f"Carregados {len(self._devices)} dispositivos de {self.devices_file}")
            
        except Exception as e:
            logger.error(f"Erro ao carregar {self.devices_file}: {e}")
    
    async def scan_network(self) -> List[Dict[str, Any]]:
        """Escaneia a rede local em busca de dispositivos Tuya."""
        try:
            import tinytuya
            
            # Scan é síncrono, rodar em executor
            def _scan():
                devices = tinytuya.deviceScan(verbose=False, maxretry=2, timeout=3)
                return devices
            
            loop = asyncio.get_event_loop()
            found_devices = await loop.run_in_executor(executor, _scan)
            
            # Atualizar cache com IPs encontrados
            for device_id, info in (found_devices or {}).items():
                if device_id in self._devices:
                    self._devices[device_id]["ip"] = info.get("ip", "")
                    self._devices[device_id]["online"] = True
            
            logger.info(f"Scan encontrou {len(found_devices or {})} dispositivos")
            return list(self._devices.values())
            
        except ImportError:
            logger.error("TinyTuya não instalado. Execute: pip install tinytuya")
            return []
        except Exception as e:
            logger.error(f"Erro no scan de rede: {e}")
            return []
    
    async def get_status(
        self,
        device_id: str,
        ip: str,
        local_key: str,
        version: str = "3.3"
    ) -> Optional[Dict[str, Any]]:
        """Obtém status de um dispositivo via LAN."""
        try:
            import tinytuya
            
            def _get_status():
                d = tinytuya.Device(device_id, ip, local_key, version=float(version))
                d.set_socketTimeout(3)
                d.set_socketRetryLimit(2)
                return d.status()
            
            loop = asyncio.get_event_loop()
            status = await loop.run_in_executor(executor, _get_status)
            
            if status and "dps" in status:
                return self._parse_dps(status["dps"])
            
            return status
            
        except Exception as e:
            logger.debug(f"Erro ao obter status de {device_id}: {e}")
            return None
    
    async def send_command(
        self,
        device_id: str,
        ip: str,
        local_key: str,
        version: str,
        command: str,
        value: Any = None
    ) -> Dict[str, Any]:
        """
        Envia comando para dispositivo via LAN.
        
        Args:
            device_id: ID do dispositivo
            ip: Endereço IP
            local_key: Chave local
            version: Versão do protocolo (3.1, 3.3, 3.4, 3.5)
            command: Comando (on, off, toggle, dim, color, etc.)
            value: Valor opcional
        """
        try:
            import tinytuya
            
            def _send_command():
                # Determinar tipo de dispositivo
                if command in ["dim", "color"]:
                    d = tinytuya.BulbDevice(device_id, ip, local_key, version=float(version))
                elif command in ["open", "close", "position"]:
                    d = tinytuya.CoverDevice(device_id, ip, local_key, version=float(version))
                else:
                    d = tinytuya.OutletDevice(device_id, ip, local_key, version=float(version))
                
                d.set_socketTimeout(5)
                d.set_socketRetryLimit(2)
                
                result = None
                
                if command == "on":
                    result = d.turn_on()
                elif command == "off":
                    result = d.turn_off()
                elif command == "toggle":
                    status = d.status()
                    if status and "dps" in status:
                        is_on = status["dps"].get("1", False) or status["dps"].get("20", False)
                        result = d.turn_off() if is_on else d.turn_on()
                    else:
                        result = d.turn_on()
                elif command == "dim":
                    # value: 0-100
                    brightness = int((value or 50) * 10)  # Tuya usa 0-1000
                    d.turn_on()
                    result = d.set_brightness(max(10, min(1000, brightness)))
                elif command == "color":
                    # value: hex color
                    d.turn_on()
                    result = d.set_colour(value or "#FFFFFF")
                elif command == "white":
                    d.turn_on()
                    result = d.set_white()
                elif command == "open":
                    result = d.set_value("1", "open")
                elif command == "close":
                    result = d.set_value("1", "close")
                elif command == "stop":
                    result = d.set_value("1", "stop")
                elif command == "position":
                    result = d.set_value("2", int(value or 50))
                else:
                    # Comando genérico: tentar enviar como DPS
                    result = d.set_status(True if value else False, 1)
                
                return result
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(executor, _send_command)
            
            if result is None or (isinstance(result, dict) and "Error" not in str(result)):
                return {"success": True, "result": result}
            else:
                return {"success": False, "error": str(result)}
            
        except Exception as e:
            logger.error(f"Erro ao enviar comando para {device_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def _parse_dps(self, dps: Dict[str, Any]) -> Dict[str, Any]:
        """Converte DPS Tuya para formato padronizado."""
        parsed = {}
        
        # DPS comuns
        dps_map = {
            "1": "switch_1",      # Switch principal
            "2": "switch_2",
            "3": "switch_3",
            "20": "switch_led",   # Lâmpadas
            "21": "work_mode",
            "22": "brightness",
            "23": "color_temp",
            "24": "colour_data",
            "25": "scene_data",
        }
        
        for dps_id, value in dps.items():
            key = dps_map.get(str(dps_id), f"dps_{dps_id}")
            parsed[key] = value
        
        # Determinar estado geral
        parsed["is_on"] = dps.get("1", False) or dps.get("20", False)
        
        return parsed
    
    async def _close_connection(self, device_id: str) -> None:
        """Fecha conexão com dispositivo."""
        if device_id in self._connections:
            del self._connections[device_id]
    
    def get_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Retorna informações de um dispositivo do cache."""
        return self._devices.get(device_id)
    
    def get_all_devices(self) -> List[Dict[str, Any]]:
        """Retorna todos os dispositivos conhecidos."""
        return list(self._devices.values())
