"""
Automation Engine - Motor de Automações SmartLife
"""
import asyncio
import structlog
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

logger = structlog.get_logger()


class TriggerType:
    """Tipos de trigger para automações."""
    TIME = "time"           # Horário específico
    CRON = "cron"           # Expressão cron
    SUNRISE = "sunrise"     # Nascer do sol
    SUNSET = "sunset"       # Pôr do sol
    DEVICE_STATE = "device_state"  # Mudança de estado de dispositivo
    SENSOR = "sensor"       # Valor de sensor
    EVENT = "event"         # Evento específico


class ConditionType:
    """Tipos de condição para automações."""
    TIME_RANGE = "time_range"     # Entre horários
    DEVICE_STATE = "device_state" # Estado de dispositivo
    WEEKDAY = "weekday"           # Dia da semana
    DATE_RANGE = "date_range"     # Entre datas


class AutomationEngine:
    """
    Motor de automações para SmartLife.
    Suporta triggers por horário, eventos e condições.
    """
    
    def __init__(
        self,
        device_manager,
        event_handler,
        config: Dict[str, Any]
    ):
        self.device_manager = device_manager
        self.event_handler = event_handler
        self.config = config
        
        # Scheduler para automações baseadas em tempo
        self.scheduler = AsyncIOScheduler()
        
        # Automações carregadas
        self._automations: Dict[str, Dict[str, Any]] = {}
        
        # Callbacks para notificação
        self._on_automation_executed: List[Callable] = []
        
        self._running = False
    
    async def start(self) -> None:
        """Inicia o motor de automações."""
        logger.info("Iniciando Automation Engine...")
        
        # Carregar automações do banco
        await self._load_automations()
        
        # Iniciar scheduler
        self.scheduler.start()
        
        # Registrar listener de eventos para automações baseadas em eventos
        if self.event_handler:
            self.event_handler.on_event(self._handle_event_trigger)
        
        self._running = True
        logger.info(f"Automation Engine iniciado com {len(self._automations)} automações")
    
    async def stop(self) -> None:
        """Para o motor de automações."""
        self._running = False
        self.scheduler.shutdown(wait=False)
        logger.info("Automation Engine parado")
    
    async def _load_automations(self) -> None:
        """Carrega automações do banco de dados."""
        # TODO: Implementar carregamento do banco
        # Por enquanto, automações de exemplo
        self._automations = {
            "exemplo_boa_noite": {
                "id": "exemplo_boa_noite",
                "name": "Boa Noite",
                "description": "Desliga todas as luzes às 23h",
                "trigger": {
                    "type": TriggerType.CRON,
                    "cron": "0 23 * * *"
                },
                "conditions": [
                    {"type": ConditionType.WEEKDAY, "days": [0, 1, 2, 3, 4, 5, 6]}
                ],
                "actions": [
                    {"device_id": "all_lights", "command": "off"}
                ],
                "is_active": False,
                "last_run": None,
                "created_at": datetime.now().isoformat()
            }
        }
        
        # Agendar automações ativas
        for automation in self._automations.values():
            if automation.get("is_active"):
                await self._schedule_automation(automation)
    
    async def get_all(self) -> List[Dict[str, Any]]:
        """Retorna todas as automações."""
        return list(self._automations.values())
    
    async def get(self, automation_id: str) -> Optional[Dict[str, Any]]:
        """Retorna uma automação específica."""
        return self._automations.get(automation_id)
    
    async def create(
        self,
        name: str,
        trigger: Dict[str, Any],
        actions: List[Dict[str, Any]],
        conditions: Optional[List[Dict[str, Any]]] = None,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Cria uma nova automação.
        
        Args:
            name: Nome da automação
            trigger: Configuração do trigger
            actions: Lista de ações a executar
            conditions: Condições opcionais
            description: Descrição
        """
        import uuid
        
        automation_id = str(uuid.uuid4())[:8]
        automation = {
            "id": automation_id,
            "name": name,
            "description": description,
            "trigger": trigger,
            "conditions": conditions or [],
            "actions": actions,
            "is_active": True,
            "last_run": None,
            "created_at": datetime.now().isoformat()
        }
        
        self._automations[automation_id] = automation
        
        # Agendar se baseada em tempo
        await self._schedule_automation(automation)
        
        # TODO: Persistir no banco de dados
        
        logger.info(f"Automação criada: {name} (ID: {automation_id})")
        return {"success": True, "automation_id": automation_id, "automation": automation}
    
    async def update(
        self,
        automation_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Atualiza uma automação existente."""
        if automation_id not in self._automations:
            return {"success": False, "error": "Automação não encontrada"}
        
        automation = self._automations[automation_id]
        
        # Remover job antigo se existir
        await self._unschedule_automation(automation_id)
        
        # Aplicar atualizações
        for key, value in updates.items():
            if key in automation:
                automation[key] = value
        
        automation["updated_at"] = datetime.now().isoformat()
        
        # Re-agendar se ativa e baseada em tempo
        if automation.get("is_active"):
            await self._schedule_automation(automation)
        
        return {"success": True, "automation": automation}
    
    async def delete(self, automation_id: str) -> Dict[str, Any]:
        """Remove uma automação."""
        if automation_id not in self._automations:
            return {"success": False, "error": "Automação não encontrada"}
        
        await self._unschedule_automation(automation_id)
        del self._automations[automation_id]
        
        # TODO: Remover do banco de dados
        
        return {"success": True}
    
    async def toggle(self, automation_id: str, enabled: bool) -> Dict[str, Any]:
        """Ativa ou desativa uma automação."""
        if automation_id not in self._automations:
            return {"success": False, "error": "Automação não encontrada"}
        
        automation = self._automations[automation_id]
        automation["is_active"] = enabled
        
        if enabled:
            await self._schedule_automation(automation)
        else:
            await self._unschedule_automation(automation_id)
        
        return {"success": True, "is_active": enabled}
    
    async def execute(self, automation_id: str) -> Dict[str, Any]:
        """Executa uma automação manualmente."""
        automation = self._automations.get(automation_id)
        if not automation:
            return {"success": False, "error": "Automação não encontrada"}
        
        return await self._execute_automation(automation)
    
    async def _schedule_automation(self, automation: Dict[str, Any]) -> None:
        """Agenda uma automação baseada em tempo."""
        trigger = automation.get("trigger", {})
        trigger_type = trigger.get("type")
        automation_id = automation["id"]
        
        if trigger_type == TriggerType.CRON:
            cron_expr = trigger.get("cron", "0 0 * * *")
            parts = cron_expr.split()
            
            self.scheduler.add_job(
                self._execute_automation_job,
                CronTrigger(
                    minute=parts[0] if len(parts) > 0 else "*",
                    hour=parts[1] if len(parts) > 1 else "*",
                    day=parts[2] if len(parts) > 2 else "*",
                    month=parts[3] if len(parts) > 3 else "*",
                    day_of_week=parts[4] if len(parts) > 4 else "*"
                ),
                args=[automation_id],
                id=f"automation_{automation_id}",
                replace_existing=True
            )
            logger.debug(f"Automação {automation['name']} agendada: {cron_expr}")
        
        elif trigger_type == TriggerType.TIME:
            # Horário específico diário
            time_str = trigger.get("time", "00:00")
            hour, minute = map(int, time_str.split(":"))
            
            self.scheduler.add_job(
                self._execute_automation_job,
                CronTrigger(hour=hour, minute=minute),
                args=[automation_id],
                id=f"automation_{automation_id}",
                replace_existing=True
            )
        
        elif trigger_type in [TriggerType.SUNRISE, TriggerType.SUNSET]:
            # TODO: Integrar com API de sunrise/sunset
            pass
    
    async def _unschedule_automation(self, automation_id: str) -> None:
        """Remove agendamento de uma automação."""
        job_id = f"automation_{automation_id}"
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass
    
    async def _execute_automation_job(self, automation_id: str) -> None:
        """Callback do scheduler para executar automação."""
        automation = self._automations.get(automation_id)
        if automation and automation.get("is_active"):
            await self._execute_automation(automation)
    
    async def _execute_automation(self, automation: Dict[str, Any]) -> Dict[str, Any]:
        """Executa uma automação."""
        logger.info(f"Executando automação: {automation['name']}")
        
        # Verificar condições
        if not await self._check_conditions(automation.get("conditions", [])):
            logger.debug(f"Condições não atendidas para {automation['name']}")
            return {"success": False, "reason": "conditions_not_met"}
        
        # Executar ações
        results = []
        for action in automation.get("actions", []):
            try:
                result = await self._execute_action(action)
                results.append(result)
            except Exception as e:
                logger.error(f"Erro na ação: {e}")
                results.append({"success": False, "error": str(e)})
        
        # Atualizar último run
        automation["last_run"] = datetime.now().isoformat()
        
        # Notificar callbacks
        success = all(r.get("success", False) for r in results)
        await self._notify_execution(automation, success, results)
        
        return {
            "success": success,
            "automation": automation["name"],
            "actions_executed": len(results),
            "results": results
        }
    
    async def _check_conditions(self, conditions: List[Dict[str, Any]]) -> bool:
        """Verifica se todas as condições são atendidas."""
        for condition in conditions:
            if not await self._check_condition(condition):
                return False
        return True
    
    async def _check_condition(self, condition: Dict[str, Any]) -> bool:
        """Verifica uma condição individual."""
        cond_type = condition.get("type")
        
        if cond_type == ConditionType.TIME_RANGE:
            start = condition.get("start", "00:00")
            end = condition.get("end", "23:59")
            now = datetime.now().strftime("%H:%M")
            return start <= now <= end
        
        if cond_type == ConditionType.WEEKDAY:
            allowed_days = condition.get("days", [0, 1, 2, 3, 4, 5, 6])
            return datetime.now().weekday() in allowed_days
        
        if cond_type == ConditionType.DEVICE_STATE:
            device_id = condition.get("device_id")
            expected_state = condition.get("state")
            
            device = await self.device_manager.get_device(device_id)
            if device:
                actual_state = device.get("state", {})
                # Verificar se o estado esperado está presente
                for key, value in expected_state.items():
                    if actual_state.get(key) != value:
                        return False
            return True
        
        return True
    
    async def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Executa uma ação."""
        device_id = action.get("device_id")
        command = action.get("command")
        value = action.get("value")
        delay = action.get("delay", 0)
        
        if delay > 0:
            await asyncio.sleep(delay)
        
        # Comando especial para todos os dispositivos de um tipo
        if device_id == "all_lights":
            devices = await self.device_manager.get_all_devices()
            results = []
            for device in devices:
                if device.get("type") == "light":
                    result = await self.device_manager.execute_command(
                        device["id"], command, value
                    )
                    results.append(result)
            return {"success": True, "devices_affected": len(results)}
        
        return await self.device_manager.execute_command(device_id, command, value)
    
    async def _handle_event_trigger(self, event: Dict[str, Any]) -> None:
        """Processa eventos como triggers de automação."""
        event_type = event.get("type")
        device_id = event.get("device_id")
        
        for automation in self._automations.values():
            if not automation.get("is_active"):
                continue
            
            trigger = automation.get("trigger", {})
            
            # Verificar se o evento corresponde ao trigger
            if trigger.get("type") == TriggerType.DEVICE_STATE:
                if trigger.get("device_id") == device_id:
                    expected_state = trigger.get("state")
                    actual_state = event.get("state", {})
                    
                    if self._state_matches(expected_state, actual_state):
                        await self._execute_automation(automation)
            
            elif trigger.get("type") == TriggerType.SENSOR:
                if trigger.get("device_id") == device_id:
                    sensor_value = event.get("value")
                    operator = trigger.get("operator", "==")
                    threshold = trigger.get("threshold")
                    
                    if self._compare_values(sensor_value, operator, threshold):
                        await self._execute_automation(automation)
    
    def _state_matches(
        self,
        expected: Dict[str, Any],
        actual: Dict[str, Any]
    ) -> bool:
        """Verifica se o estado corresponde ao esperado."""
        for key, value in expected.items():
            if actual.get(key) != value:
                return False
        return True
    
    def _compare_values(self, value: Any, operator: str, threshold: Any) -> bool:
        """Compara valores com operador."""
        ops = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
        }
        return ops.get(operator, lambda a, b: False)(value, threshold)
    
    def on_automation_executed(self, callback: Callable) -> None:
        """Registra callback para execução de automações."""
        self._on_automation_executed.append(callback)
    
    async def _notify_execution(
        self,
        automation: Dict[str, Any],
        success: bool,
        results: List[Dict[str, Any]]
    ) -> None:
        """Notifica sobre execução de automação."""
        for callback in self._on_automation_executed:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(automation, success, results)
                else:
                    callback(automation, success, results)
            except Exception as e:
                logger.error(f"Erro em callback de automação: {e}")
