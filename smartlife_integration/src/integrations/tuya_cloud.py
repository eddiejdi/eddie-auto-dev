"""
Tuya Cloud Client - Integração via API Cloud da Tuya
"""
import asyncio
import structlog
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = structlog.get_logger()


class TuyaCloudClient:
    """
    Cliente para API Cloud da Tuya.
    Suporta controle de dispositivos, cenas e eventos MQTT.
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        region: str = "eu",
        device_id: Optional[str] = None
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.region = region
        self.device_id = device_id
        
        # Endpoints por região
        self.endpoints = {
            "cn": "https://openapi.tuyacn.com",
            "us": "https://openapi.tuyaus.com",
            "us-e": "https://openapi-ueaz.tuyaus.com",
            "eu": "https://openapi.tuyaeu.com",
            "eu-w": "https://openapi-weaz.tuyaeu.com",
            "in": "https://openapi.tuyain.com"
        }
        
        self.endpoint = self.endpoints.get(region, self.endpoints["eu"])
        
        # TinyTuya Cloud ou SDK oficial
        self._cloud = None
        self._mqtt = None
        
        self._is_connected = False
        self._mqtt_connected = False
        
        # Cache de dispositivos
        self._devices: Dict[str, Dict[str, Any]] = {}
    
    @property
    def is_connected(self) -> bool:
        return self._is_connected
    
    @property
    def mqtt_connected(self) -> bool:
        return self._mqtt_connected
    
    async def connect(self) -> bool:
        """Conecta à API Cloud da Tuya."""
        logger.info(f"Conectando à Tuya Cloud ({self.region})...")
        
        try:
            import tinytuya
            
            # Usar TinyTuya Cloud
            self._cloud = tinytuya.Cloud(
                apiRegion=self.region,
                apiKey=self.api_key,
                apiSecret=self.api_secret,
                apiDeviceID=self.device_id
            )
            
            # Testar conexão
            result = self._cloud.getdevices()
            
            if isinstance(result, dict) and "Error" in str(result):
                logger.error(f"Erro ao conectar: {result}")
                return False
            
            self._is_connected = True
            logger.info(f"Conectado à Tuya Cloud. {len(result or [])} dispositivos encontrados")
            
            # Cachear dispositivos
            for device in (result or []):
                self._devices[device["id"]] = device
            
            return True
            
        except ImportError:
            logger.error("TinyTuya não instalado. Execute: pip install tinytuya")
            return False
        except Exception as e:
            logger.error(f"Erro ao conectar à Tuya Cloud: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Desconecta da API Cloud."""
        self._is_connected = False
        self._mqtt_connected = False
        self._cloud = None
        logger.info("Desconectado da Tuya Cloud")
    
    async def get_devices(self) -> List[Dict[str, Any]]:
        """Obtém lista de todos os dispositivos."""
        if not self._cloud:
            return list(self._devices.values())
        
        try:
            result = self._cloud.getdevices()
            
            if isinstance(result, list):
                # Atualizar cache
                for device in result:
                    self._devices[device["id"]] = device
                return result
            
            return list(self._devices.values())
            
        except Exception as e:
            logger.error(f"Erro ao obter dispositivos: {e}")
            return list(self._devices.values())
    
    async def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Obtém status de um dispositivo."""
        if not self._cloud:
            return None
        
        try:
            result = self._cloud.getstatus(device_id)
            
            if result and isinstance(result, dict):
                # Converter formato Tuya para padronizado
                return self._parse_status(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao obter status de {device_id}: {e}")
            return None
    
    async def send_commands(
        self,
        device_id: str,
        commands: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Envia comandos para um dispositivo.
        
        Args:
            device_id: ID do dispositivo
            commands: Lista de comandos no formato [{"code": "switch_1", "value": True}]
        """
        if not self._cloud:
            return {"success": False, "error": "Não conectado"}
        
        try:
            result = self._cloud.sendcommand(device_id, {"commands": commands})
            
            if result and isinstance(result, dict) and result.get("success", True):
                return {"success": True, "result": result}
            
            return {"success": False, "error": str(result)}
            
        except Exception as e:
            logger.error(f"Erro ao enviar comando para {device_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_device_functions(self, device_id: str) -> List[Dict[str, Any]]:
        """Obtém funções disponíveis de um dispositivo."""
        if not self._cloud:
            return []
        
        try:
            result = self._cloud.getfunctions(device_id)
            return result.get("functions", []) if isinstance(result, dict) else []
        except Exception as e:
            logger.error(f"Erro ao obter funções de {device_id}: {e}")
            return []
    
    async def get_device_logs(
        self,
        device_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Obtém logs de um dispositivo."""
        # TODO: Implementar usando API de logs
        return []
    
    # ========== Cenas da Tuya ==========
    
    async def get_home_id(self) -> Optional[str]:
        """Obtém o ID da home principal."""
        # Tuya organiza dispositivos por "home"
        # Precisamos do home_id para algumas operações
        try:
            # Tenta obter do primeiro dispositivo
            devices = await self.get_devices()
            if devices:
                return devices[0].get("home_id")
            return None
        except Exception:
            return None
    
    async def get_scenes(self, home_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtém cenas da Tuya Cloud."""
        # TODO: Implementar usando API de cenas
        # POST /v1.0/homes/{home_id}/scenes
        return []
    
    async def trigger_scene(self, scene_id: str) -> Dict[str, Any]:
        """Executa uma cena da Tuya."""
        # TODO: Implementar usando API de cenas
        # POST /v1.0/homes/{home_id}/scenes/{scene_id}/trigger
        return {"success": False, "error": "Não implementado"}
    
    # ========== MQTT para eventos em tempo real ==========
    
    async def start_mqtt(self, on_message: callable) -> bool:
        """Inicia conexão MQTT para eventos em tempo real."""
        try:
            from tuya_iot import TuyaOpenAPI, TuyaOpenMQ
            
            # Usar SDK oficial para MQTT
            openapi = TuyaOpenAPI(self.endpoint, self.api_key, self.api_secret)
            openapi.connect()
            
            self._mqtt = TuyaOpenMQ(openapi)
            self._mqtt.start()
            self._mqtt.add_message_listener(on_message)
            
            self._mqtt_connected = True
            logger.info("MQTT conectado para eventos em tempo real")
            return True
            
        except ImportError:
            logger.warning("tuya-iot-py-sdk não instalado. MQTT não disponível.")
            return False
        except Exception as e:
            logger.error(f"Erro ao iniciar MQTT: {e}")
            return False
    
    async def stop_mqtt(self) -> None:
        """Para conexão MQTT."""
        if self._mqtt:
            try:
                self._mqtt.stop()
            except Exception:
                pass
            self._mqtt = None
        self._mqtt_connected = False
    
    def _parse_status(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Converte status da Tuya para formato padronizado."""
        parsed = {"raw": status}
        
        # Status pode vir em diferentes formatos
        if "result" in status:
            items = status["result"]
            for item in items:
                code = item.get("code", "")
                value = item.get("value")
                parsed[code] = value
        
        # Determinar estado geral
        parsed["is_on"] = (
            parsed.get("switch_led", False) or
            parsed.get("switch_1", False) or
            parsed.get("switch", False)
        )
        
        return parsed
    
    def get_cached_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Retorna dispositivo do cache."""
        return self._devices.get(device_id)
