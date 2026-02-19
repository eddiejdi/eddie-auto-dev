"""
Agent Auto-Scaling Manager
Gerencia escalonamento automático de agents baseado em uso de recursos.
"""
import asyncio
import psutil
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

try:
    from .config import AUTOSCALING_CONFIG, SYNERGY_CONFIG
except ImportError:
    AUTOSCALING_CONFIG = {
        "enabled": True,
        "min_agents": 2,
        "max_agents": 16,
        "cpu_scale_up_threshold": 50,
        "cpu_scale_down_threshold": 85,
        "scale_check_interval_seconds": 60,
        "scale_up_increment": 2,
        "scale_down_increment": 1,
        "cooldown_seconds": 120,
    }
    SYNERGY_CONFIG = {
        "communication_bus_enabled": True,
        "max_parallel_tasks_per_agent": 3,
    }


class ScaleAction(Enum):
    NONE = "none"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"


@dataclass
class ResourceMetrics:
    """Métricas de recursos do sistema."""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    active_agents: int
    pending_tasks: int
    timestamp: datetime


@dataclass
class ScalingDecision:
    """Decisão de escalonamento."""
    action: ScaleAction
    current_agents: int
    target_agents: int
    reason: str
    metrics: ResourceMetrics


class AgentAutoScaler:
    """
    Gerencia auto-scaling de agents baseado em uso de CPU/memória.
    
    Regras:
    - CPU < 50% por 1 min → aumentar agents
    - CPU > 85% → reduzir agents
    - Respeitar min/max agents
    - Cooldown entre ações de scaling
    """
    
    def __init__(self):
        self.config = AUTOSCALING_CONFIG
        self.current_agents = self.config["min_agents"]
        self.last_scale_action = None
        self.last_scale_time = 0
        self.metrics_history: List[ResourceMetrics] = []
        self.running = False
        self._task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Inicia monitoramento de auto-scaling."""
        if not self.config["enabled"]:
            logger.info("Auto-scaling desabilitado")
            return
            
        self.running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("🚀 Auto-scaler iniciado")
        
    async def stop(self):
        """Para monitoramento."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("⏹️ Auto-scaler parado")
        
    async def _monitor_loop(self):
        """Loop principal de monitoramento."""
        while self.running:
            try:
                metrics = self._collect_metrics()
                self.metrics_history.append(metrics)
                
                # Manter apenas últimos 10 minutos de histórico
                cutoff = datetime.now().timestamp() - 600
                self.metrics_history = [
                    m for m in self.metrics_history 
                    if m.timestamp.timestamp() > cutoff
                ]
                
                # Avaliar decisão de scaling
                decision = self._evaluate_scaling(metrics)
                
                if decision.action != ScaleAction.NONE:
                    await self._execute_scaling(decision)
                    
                await asyncio.sleep(self.config["scale_check_interval_seconds"])
                
            except Exception as e:
                logger.error(f"Erro no auto-scaler: {e}")
                await asyncio.sleep(10)
                
    def _collect_metrics(self) -> ResourceMetrics:
        """Coleta métricas atuais do sistema."""
        return ResourceMetrics(
            cpu_percent=psutil.cpu_percent(interval=1),
            memory_percent=psutil.virtual_memory().percent,
            disk_percent=psutil.disk_usage('/').percent,
            active_agents=self.current_agents,
            pending_tasks=self._get_pending_tasks(),
            timestamp=datetime.now()
        )
        
    def _get_pending_tasks(self) -> int:
        """Obtém número de tarefas pendentes."""
        # TODO: Integrar com Communication Bus
        return 0
        
    def _evaluate_scaling(self, metrics: ResourceMetrics) -> ScalingDecision:
        """Avalia se deve escalar agents."""
        
        # Verificar cooldown
        if time.time() - self.last_scale_time < self.config["cooldown_seconds"]:
            return ScalingDecision(
                action=ScaleAction.NONE,
                current_agents=self.current_agents,
                target_agents=self.current_agents,
                reason="Em cooldown",
                metrics=metrics
            )
        
        # Calcular média de CPU dos últimos 60 segundos
        recent_metrics = [
            m for m in self.metrics_history
            if (datetime.now() - m.timestamp).seconds < 60
        ]
        
        if not recent_metrics:
            recent_metrics = [metrics]
            
        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        
        # Decisão de scale UP (CPU subutilizada)
        if avg_cpu < self.config["cpu_scale_up_threshold"]:
            if self.current_agents < self.config["max_agents"]:
                target = min(
                    self.current_agents + self.config["scale_up_increment"],
                    self.config["max_agents"]
                )
                return ScalingDecision(
                    action=ScaleAction.SCALE_UP,
                    current_agents=self.current_agents,
                    target_agents=target,
                    reason=f"CPU subutilizada ({avg_cpu:.1f}% < {self.config['cpu_scale_up_threshold']}%)",
                    metrics=metrics
                )
                
        # Decisão de scale DOWN (CPU sobrecarregada)
        if avg_cpu > self.config["cpu_scale_down_threshold"]:
            if self.current_agents > self.config["min_agents"]:
                target = max(
                    self.current_agents - self.config["scale_down_increment"],
                    self.config["min_agents"]
                )
                return ScalingDecision(
                    action=ScaleAction.SCALE_DOWN,
                    current_agents=self.current_agents,
                    target_agents=target,
                    reason=f"CPU sobrecarregada ({avg_cpu:.1f}% > {self.config['cpu_scale_down_threshold']}%)",
                    metrics=metrics
                )
                
        return ScalingDecision(
            action=ScaleAction.NONE,
            current_agents=self.current_agents,
            target_agents=self.current_agents,
            reason=f"CPU estável ({avg_cpu:.1f}%)",
            metrics=metrics
        )
        
    async def _execute_scaling(self, decision: ScalingDecision):
        """Executa ação de scaling."""
        try:
            old_count = self.current_agents
            self.current_agents = decision.target_agents
            self.last_scale_time = time.time()
            self.last_scale_action = decision.action
            
            # Log da ação
            action_emoji = "⬆️" if decision.action == ScaleAction.SCALE_UP else "⬇️"
            logger.info(
                f"{action_emoji} Auto-scaling: {old_count} → {self.current_agents} agents | "
                f"Razão: {decision.reason}"
            )
            
            # Notificar Communication Bus
            await self._notify_scaling(decision)
            
        except Exception as e:
            logger.error(f"Erro ao executar scaling: {e}")
            
    async def _notify_scaling(self, decision: ScalingDecision):
        """Notifica outros componentes sobre scaling."""
        try:
            from .agent_communication_bus import log_coordinator
            log_coordinator(
                f"Auto-scaling: {decision.current_agents} → {decision.target_agents} agents. "
                f"Razão: {decision.reason}"
            )
        except ImportError:
            pass
            
    def get_status(self) -> Dict:
        """Retorna status atual do auto-scaler."""
        recent_metrics = self.metrics_history[-1] if self.metrics_history else None
        
        return {
            "enabled": self.config["enabled"],
            "running": self.running,
            "current_agents": self.current_agents,
            "min_agents": self.config["min_agents"],
            "max_agents": self.config["max_agents"],
            "last_scale_action": self.last_scale_action.value if self.last_scale_action else None,
            "last_scale_time": datetime.fromtimestamp(self.last_scale_time).isoformat() if self.last_scale_time else None,
            "current_metrics": {
                "cpu_percent": recent_metrics.cpu_percent if recent_metrics else 0,
                "memory_percent": recent_metrics.memory_percent if recent_metrics else 0,
                "disk_percent": recent_metrics.disk_percent if recent_metrics else 0,
            } if recent_metrics else None,
            "thresholds": {
                "scale_up_below_cpu": self.config["cpu_scale_up_threshold"],
                "scale_down_above_cpu": self.config["cpu_scale_down_threshold"],
            }
        }
        
    def get_recommended_parallelism(self) -> int:
        """Retorna número recomendado de tarefas paralelas."""
        max_per_agent = SYNERGY_CONFIG.get("max_parallel_tasks_per_agent", 3)
        return self.current_agents * max_per_agent


# Singleton
_autoscaler_instance: Optional[AgentAutoScaler] = None


def get_autoscaler() -> AgentAutoScaler:
    """Retorna instância singleton do auto-scaler."""
    global _autoscaler_instance
    if _autoscaler_instance is None:
        _autoscaler_instance = AgentAutoScaler()
    return _autoscaler_instance
