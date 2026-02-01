"""
Event Handler - Processador de Eventos SmartLife
"""

import asyncio
import structlog
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime

logger = structlog.get_logger()


class EventType:
    """Tipos de eventos do sistema."""

    DEVICE_STATE_CHANGE = "device_state_change"
    DEVICE_ONLINE = "device_online"
    DEVICE_OFFLINE = "device_offline"
    SENSOR_TRIGGERED = "sensor_triggered"
    AUTOMATION_EXECUTED = "automation_executed"
    USER_COMMAND = "user_command"
    ERROR = "error"
    SYSTEM = "system"


class EventHandler:
    """
    Processa e distribui eventos do sistema SmartLife.
    Conecta-se ao MQTT da Tuya para eventos em tempo real.
    """

    def __init__(self, device_manager, config: Dict[str, Any]):
        self.device_manager = device_manager
        self.config = config

        # Fila de eventos
        self._event_queue: asyncio.Queue = asyncio.Queue()

        # Callbacks registrados
        self._listeners: List[Callable] = []

        # Histórico de eventos (últimos N eventos)
        self._event_history: List[Dict[str, Any]] = []
        self._max_history = 1000

        self._running = False
        self._processor_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Inicia o processador de eventos."""
        logger.info("Iniciando Event Handler...")

        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())

        logger.info("Event Handler iniciado")

    async def stop(self) -> None:
        """Para o processador de eventos."""
        self._running = False

        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        logger.info("Event Handler parado")

    def on_event(self, callback: Callable) -> None:
        """Registra um callback para receber eventos."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable) -> None:
        """Remove um callback registrado."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def emit(self, event: Dict[str, Any]) -> None:
        """Emite um evento para processamento."""
        event["timestamp"] = datetime.now().isoformat()
        event["id"] = self._generate_event_id()

        await self._event_queue.put(event)

    async def emit_device_state_change(
        self, device_id: str, old_state: Dict[str, Any], new_state: Dict[str, Any]
    ) -> None:
        """Emite evento de mudança de estado de dispositivo."""
        await self.emit(
            {
                "type": EventType.DEVICE_STATE_CHANGE,
                "device_id": device_id,
                "old_state": old_state,
                "new_state": new_state,
                "changes": self._diff_states(old_state, new_state),
            }
        )

    async def emit_device_online(self, device_id: str) -> None:
        """Emite evento de dispositivo online."""
        await self.emit({"type": EventType.DEVICE_ONLINE, "device_id": device_id})

    async def emit_device_offline(self, device_id: str) -> None:
        """Emite evento de dispositivo offline."""
        await self.emit({"type": EventType.DEVICE_OFFLINE, "device_id": device_id})

    async def emit_sensor_triggered(
        self, device_id: str, sensor_type: str, value: Any
    ) -> None:
        """Emite evento de sensor acionado."""
        await self.emit(
            {
                "type": EventType.SENSOR_TRIGGERED,
                "device_id": device_id,
                "sensor_type": sensor_type,
                "value": value,
            }
        )

    async def emit_automation_executed(
        self,
        automation_id: str,
        automation_name: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emite evento de automação executada."""
        await self.emit(
            {
                "type": EventType.AUTOMATION_EXECUTED,
                "automation_id": automation_id,
                "automation_name": automation_name,
                "success": success,
                "details": details,
            }
        )

    async def emit_user_command(
        self,
        user_id: str,
        device_id: str,
        command: str,
        value: Any = None,
        source: str = "unknown",
    ) -> None:
        """Emite evento de comando de usuário."""
        await self.emit(
            {
                "type": EventType.USER_COMMAND,
                "user_id": user_id,
                "device_id": device_id,
                "command": command,
                "value": value,
                "source": source,
            }
        )

    async def emit_error(
        self, error_type: str, message: str, details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Emite evento de erro."""
        await self.emit(
            {
                "type": EventType.ERROR,
                "error_type": error_type,
                "message": message,
                "details": details,
            }
        )

    async def _process_events(self) -> None:
        """Loop principal de processamento de eventos."""
        while self._running:
            try:
                # Esperar próximo evento
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)

                # Adicionar ao histórico
                self._event_history.append(event)
                if len(self._event_history) > self._max_history:
                    self._event_history.pop(0)

                # Log do evento
                logger.debug(
                    "Evento processado",
                    event_type=event.get("type"),
                    event_id=event.get("id"),
                )

                # Distribuir para listeners
                await self._distribute_event(event)

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro processando evento: {e}")

    async def _distribute_event(self, event: Dict[str, Any]) -> None:
        """Distribui evento para todos os listeners."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event)
                else:
                    listener(event)
            except Exception as e:
                logger.error(f"Erro em listener de evento: {e}")

    def _diff_states(
        self, old_state: Dict[str, Any], new_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calcula diferenças entre estados."""
        changes = {}

        all_keys = set(old_state.keys()) | set(new_state.keys())
        for key in all_keys:
            old_val = old_state.get(key)
            new_val = new_state.get(key)

            if old_val != new_val:
                changes[key] = {"from": old_val, "to": new_val}

        return changes

    def _generate_event_id(self) -> str:
        """Gera ID único para evento."""
        import uuid

        return str(uuid.uuid4())[:12]

    def get_history(
        self,
        event_type: Optional[str] = None,
        device_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retorna histórico de eventos filtrado."""
        events = self._event_history.copy()

        if event_type:
            events = [e for e in events if e.get("type") == event_type]

        if device_id:
            events = [e for e in events if e.get("device_id") == device_id]

        return events[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de eventos."""
        stats = {
            "total_events": len(self._event_history),
            "queue_size": self._event_queue.qsize(),
            "listeners": len(self._listeners),
            "by_type": {},
        }

        for event in self._event_history:
            event_type = event.get("type", "unknown")
            stats["by_type"][event_type] = stats["by_type"].get(event_type, 0) + 1

        return stats
