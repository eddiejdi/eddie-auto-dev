"""
SmartLife Core Service
Serviço principal que coordena todas as integrações
"""

import asyncio
import structlog
from typing import Optional, Dict, Any, List

from .device_manager import DeviceManager
from .automation_engine import AutomationEngine
from .event_handler import EventHandler
from .user_manager import UserManager
from ..integrations.tuya_local import TuyaLocalClient
from ..integrations.tuya_cloud import TuyaCloudClient

logger = structlog.get_logger()


class SmartLifeService:
    """
    Serviço central de integração SmartLife.
    Coordena dispositivos, automações, eventos e usuários.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.running = False

        # Componentes core
        self.device_manager: Optional[DeviceManager] = None
        self.automation_engine: Optional[AutomationEngine] = None
        self.event_handler: Optional[EventHandler] = None
        self.user_manager: Optional[UserManager] = None

        # Clientes Tuya
        self.tuya_local: Optional[TuyaLocalClient] = None
        self.tuya_cloud: Optional[TuyaCloudClient] = None

        # Callbacks para interfaces (Telegram, WhatsApp, etc.)
        self._on_device_state_change: List[callable] = []
        self._on_event: List[callable] = []

    async def start(self) -> None:
        """Inicializa todos os componentes do serviço."""
        logger.info("Iniciando SmartLife Service...")

        try:
            # Inicializar clientes Tuya
            await self._init_tuya_clients()

            # Inicializar componentes core
            self.device_manager = DeviceManager(
                local_client=self.tuya_local,
                cloud_client=self.tuya_cloud,
                config=self.config,
            )
            await self.device_manager.start()

            self.user_manager = UserManager(config=self.config)
            await self.user_manager.start()

            self.event_handler = EventHandler(
                device_manager=self.device_manager, config=self.config
            )
            self.event_handler.on_event(self._handle_event)
            await self.event_handler.start()

            self.automation_engine = AutomationEngine(
                device_manager=self.device_manager,
                event_handler=self.event_handler,
                config=self.config,
            )
            await self.automation_engine.start()

            self.running = True
            logger.info("SmartLife Service iniciado com sucesso!")

        except Exception as e:
            logger.error(f"Erro ao iniciar SmartLife Service: {e}")
            raise

    async def stop(self) -> None:
        """Para todos os componentes do serviço."""
        logger.info("Parando SmartLife Service...")
        self.running = False

        if self.automation_engine:
            await self.automation_engine.stop()
        if self.event_handler:
            await self.event_handler.stop()
        if self.device_manager:
            await self.device_manager.stop()
        if self.tuya_cloud:
            await self.tuya_cloud.disconnect()
        if self.tuya_local:
            await self.tuya_local.stop()

        logger.info("SmartLife Service parado.")

    async def _init_tuya_clients(self) -> None:
        """Inicializa os clientes Tuya (local e cloud)."""
        tuya_config = self.config.get("tuya", {})
        local_config = self.config.get("local", {})

        # Cliente Cloud
        self.tuya_cloud = TuyaCloudClient(
            api_key=tuya_config.get("api_key"),
            api_secret=tuya_config.get("api_secret"),
            region=tuya_config.get("region", "eu"),
            device_id=tuya_config.get("device_id"),
        )
        await self.tuya_cloud.connect()

        # Cliente Local (se habilitado)
        if local_config.get("enabled", True):
            devices_file = local_config.get("devices_file", "config/devices.json")
            self.tuya_local = TuyaLocalClient(
                devices_file=devices_file,
                scan_interval=local_config.get("scan_interval", 60),
            )
            await self.tuya_local.start()

    # ========== Operações de Dispositivo ==========

    async def get_devices(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista todos os dispositivos (filtrado por permissão se user_id fornecido)."""
        devices = await self.device_manager.get_all_devices()

        if user_id and self.user_manager:
            # Filtrar por permissões do usuário
            user = await self.user_manager.get_user(user_id)
            if user and user.role != "admin":
                allowed_ids = await self.user_manager.get_user_device_permissions(
                    user_id
                )
                devices = [d for d in devices if d["id"] in allowed_ids]

        return devices

    async def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Obtém detalhes de um dispositivo."""
        return await self.device_manager.get_device(device_id)

    async def control_device(
        self,
        device_id: str,
        command: str,
        value: Any = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Controla um dispositivo.

        Args:
            device_id: ID do dispositivo
            command: Comando (on, off, toggle, dim, color, temp, etc.)
            value: Valor opcional (ex: brilho 0-100)
            user_id: ID do usuário para verificação de permissão

        Returns:
            Resultado da operação
        """
        # Verificar permissão
        if user_id:
            has_permission = await self.user_manager.check_permission(
                user_id=user_id, device_id=device_id, action="control"
            )
            if not has_permission:
                return {
                    "success": False,
                    "error": "Sem permissão para controlar este dispositivo",
                }

        # Executar comando
        result = await self.device_manager.execute_command(device_id, command, value)

        # Registrar log
        if result.get("success"):
            await self._log_action(device_id, command, value, user_id)

        return result

    async def turn_on(
        self, device_id: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Liga um dispositivo."""
        return await self.control_device(device_id, "on", user_id=user_id)

    async def turn_off(
        self, device_id: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Desliga um dispositivo."""
        return await self.control_device(device_id, "off", user_id=user_id)

    async def toggle(
        self, device_id: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Alterna o estado de um dispositivo."""
        return await self.control_device(device_id, "toggle", user_id=user_id)

    async def set_brightness(
        self, device_id: str, brightness: int, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Define o brilho de uma lâmpada (0-100)."""
        return await self.control_device(device_id, "dim", brightness, user_id=user_id)

    async def set_color(
        self,
        device_id: str,
        color: str,  # hex ou nome
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Define a cor de uma lâmpada RGB."""
        return await self.control_device(device_id, "color", color, user_id=user_id)

    async def set_temperature(
        self, device_id: str, temp: int, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Define temperatura de AC."""
        return await self.control_device(device_id, "temp", temp, user_id=user_id)

    # ========== Cenas ==========

    async def get_scenes(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista todas as cenas disponíveis."""
        return await self.device_manager.get_scenes(user_id=user_id)

    async def execute_scene(
        self, scene_id: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Executa uma cena."""
        return await self.device_manager.execute_scene(scene_id, user_id=user_id)

    async def create_scene(
        self, name: str, actions: List[Dict[str, Any]], user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cria uma nova cena."""
        return await self.device_manager.create_scene(name, actions, user_id=user_id)

    # ========== Automações ==========

    async def get_automations(self) -> List[Dict[str, Any]]:
        """Lista todas as automações."""
        return await self.automation_engine.get_all()

    async def create_automation(
        self,
        name: str,
        trigger: Dict[str, Any],
        actions: List[Dict[str, Any]],
        conditions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Cria uma nova automação."""
        return await self.automation_engine.create(
            name=name, trigger=trigger, actions=actions, conditions=conditions
        )

    async def toggle_automation(
        self, automation_id: str, enabled: bool
    ) -> Dict[str, Any]:
        """Ativa ou desativa uma automação."""
        return await self.automation_engine.toggle(automation_id, enabled)

    # ========== Usuários ==========

    async def get_users(self) -> List[Dict[str, Any]]:
        """Lista todos os usuários."""
        return await self.user_manager.get_all_users()

    async def add_user(
        self,
        telegram_id: Optional[int] = None,
        whatsapp_id: Optional[str] = None,
        name: str = "",
        role: str = "user",
    ) -> Dict[str, Any]:
        """Adiciona um novo usuário."""
        return await self.user_manager.create_user(
            telegram_id=telegram_id, whatsapp_id=whatsapp_id, name=name, role=role
        )

    async def set_user_permission(
        self,
        user_id: str,
        device_id: str,
        can_view: bool = True,
        can_control: bool = False,
        can_configure: bool = False,
    ) -> Dict[str, Any]:
        """Define permissões de um usuário para um dispositivo."""
        return await self.user_manager.set_permission(
            user_id=user_id,
            device_id=device_id,
            can_view=can_view,
            can_control=can_control,
            can_configure=can_configure,
        )

    # ========== Eventos e Callbacks ==========

    def on_device_state_change(self, callback: callable) -> None:
        """Registra callback para mudanças de estado."""
        self._on_device_state_change.append(callback)

    def on_event(self, callback: callable) -> None:
        """Registra callback para eventos."""
        self._on_event.append(callback)

    async def _handle_event(self, event: Dict[str, Any]) -> None:
        """Processa eventos internos."""
        for callback in self._on_event:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Erro em callback de evento: {e}")

    async def _log_action(
        self, device_id: str, action: str, value: Any, user_id: Optional[str]
    ) -> None:
        """Registra ação no log de auditoria."""
        logger.info(
            "Ação executada",
            device_id=device_id,
            action=action,
            value=value,
            user_id=user_id,
        )

    # ========== Status e Health ==========

    async def get_status(self) -> Dict[str, Any]:
        """Retorna status geral do sistema."""
        devices = (
            await self.device_manager.get_all_devices() if self.device_manager else []
        )
        online = sum(1 for d in devices if d.get("is_online", False))

        return {
            "status": "running" if self.running else "stopped",
            "devices": {
                "total": len(devices),
                "online": online,
                "offline": len(devices) - online,
            },
            "automations": {
                "total": (
                    len(await self.automation_engine.get_all())
                    if self.automation_engine
                    else 0
                ),
                "active": (
                    len(
                        [
                            a
                            for a in await self.automation_engine.get_all()
                            if a.get("is_active")
                        ]
                    )
                    if self.automation_engine
                    else 0
                ),
            },
            "connections": {
                "local": self.tuya_local.is_connected if self.tuya_local else False,
                "cloud": self.tuya_cloud.is_connected if self.tuya_cloud else False,
                "mqtt": self.tuya_cloud.mqtt_connected if self.tuya_cloud else False,
            },
        }

    async def health_check(self) -> Dict[str, Any]:
        """Health check para monitoring."""
        return {
            "healthy": self.running,
            "components": {
                "device_manager": self.device_manager is not None,
                "automation_engine": self.automation_engine is not None,
                "event_handler": self.event_handler is not None,
                "user_manager": self.user_manager is not None,
                "tuya_local": (
                    self.tuya_local.is_connected if self.tuya_local else False
                ),
                "tuya_cloud": (
                    self.tuya_cloud.is_connected if self.tuya_cloud else False
                ),
            },
        }
